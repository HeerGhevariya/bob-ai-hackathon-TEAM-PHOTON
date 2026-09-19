"""
validator.py — Row-Level Validation for Data Imports

All validation rules from the spec:
  - Privacy guard (no PII columns — already checked in parser, re-checked here)
  - Type checks: age, sex, visit_number, dose
  - Date checks: ISO only, no ambiguous formats, not in future, ordering
  - Consistency: patient attributes stable across rows, same site details
  - Duplicate (patient_id, visit_number) within file
  - Foreign key checks against existing DB data
  - Protocol lookup: visit_number/visit_name must exist in protocol config
  - Protocol-computed fields: protocol_target_day, protocol_dose_mg,
    assessments_required filled from protocol; actual_day computed from dates

Returns a ValidationReport — does NOT write anything.
CPU-bound — callers run this in a threadpool.
"""

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Optional

from .column_spec import COLUMNS, COLUMN_MAP, MULTISHEET_NAMES
from .parser import ParseResult


# ── Data structures ────────────────────────────────────────────────────────────

@dataclass
class RowError:
    row: int        # 1-based (1 = first data row, not header)
    column: str
    value: str
    reason: str
    blocking: bool = True


@dataclass
class ValidationReport:
    layout: str
    row_count: int
    file_sha256: str
    filename: str

    # Counts of what would happen
    sites_new: int = 0
    sites_existing_same: int = 0
    sites_existing_diff: int = 0

    patients_new: int = 0
    patients_existing_same: int = 0
    patients_existing_diff: int = 0

    visits_new: int = 0
    visits_existing_same: int = 0
    visits_existing_diff: int = 0

    ignored_columns: list[str] = field(default_factory=list)
    server_computed_found: list[str] = field(default_factory=list)  # warned, not blocked
    warnings: list[str] = field(default_factory=list)
    errors: list[RowError] = field(default_factory=list)
    total_error_count: int = 0
    blocking: bool = False          # True only when validated_rows is empty (nothing to import)
    rows_skipped_with_errors: int = 0  # rows excluded due to blocking errors (partial import)

    # Validated + enriched rows ready for commit (always set; partial import skips errored rows)
    validated_rows: list[dict] = field(default_factory=list)


# ── Helpers ────────────────────────────────────────────────────────────────────

_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# Ambiguous patterns like 03/04/2026 or 04-03-2026
_AMBIGUOUS_DATE_RE = re.compile(r"^\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{4}$")
_MAX_ERRORS_RETURNED = 200


def _parse_iso_date(s: str) -> Optional[date]:
    """Parse YYYY-MM-DD string. Returns None on failure."""
    if not s:
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def _is_ambiguous_date(s: str) -> bool:
    return bool(_AMBIGUOUS_DATE_RE.match(s.strip()))


def _coerce_int(s: str) -> Optional[int]:
    try:
        return int(str(s).strip())
    except (ValueError, TypeError):
        return None


def _coerce_float(s: str) -> Optional[float]:
    s2 = str(s).strip()
    if not s2:
        return None
    try:
        return float(s2)
    except (ValueError, TypeError):
        return None


def _split_list(s: str) -> list[str]:
    """Split a semicolon-separated list cell into items."""
    if not s or not s.strip():
        return []
    return [item.strip() for item in s.split(";") if item.strip()]


# ── Main validation function ───────────────────────────────────────────────────

def validate(
    parse_result: ParseResult,
    existing_sites: dict[str, dict],     # site_id → {site_name, city, country, principal_investigator}
    existing_patients: dict[str, dict],  # patient_id → {site_id, enrollment_date(str), age, sex}
    existing_visits: dict[str, dict],    # visit_id → full visit dict
    # Also pass keyed by (patient_id, visit_number) for duplicate detection
    existing_visits_by_key: dict[tuple, dict],  # (patient_id, visit_number) → visit dict
    protocol_visit_map: dict[int, Any],          # visit_number → ProtocolVisit
    protocol_dose_mg: float,
    today: date,
) -> ValidationReport:
    """
    Validate a ParseResult against existing DB state and protocol config.

    Parameters:
        existing_sites:           All sites currently in DB (from SupabaseDataSource cache)
        existing_patients:        All patients currently in DB
        existing_visits:          All visits by visit_id
        existing_visits_by_key:   All visits keyed by (patient_id, visit_number)
        protocol_visit_map:       visit_number → ProtocolVisit (from get_protocol())
        protocol_dose_mg:         The single protocol dose in mg (from dose_rules[0])
        today:                    Passed in, never use date.today() inside
    """
    report = ValidationReport(
        layout=parse_result.layout,
        row_count=parse_result.raw_row_count,
        file_sha256=parse_result.file_sha256,
        filename=parse_result.filename,
        ignored_columns=parse_result.ignored_columns,
        server_computed_found=parse_result.server_computed_found,
    )

    if parse_result.server_computed_found:
        report.warnings.append(
            f"The following server-computed columns were found and ignored: "
            f"{', '.join(parse_result.server_computed_found)}. "
            "Values for these columns are always computed by TrialGuard's pipeline."
        )

    rows = parse_result.rows
    errors: list[RowError] = []

    def add_error(row_num: int, column: str, value: str, reason: str, blocking: bool = True):
        errors.append(RowError(row=row_num, column=column, value=value,
                               reason=reason, blocking=blocking))

    if not rows:
        add_error(0, "(file)", "", "The file contains no data rows.")
        report.errors = errors
        report.total_error_count = len(errors)
        report.blocking = True
        return report

    # ── Pass 1: Required column presence check ─────────────────────────────────
    present_cols = set(rows[0].keys())
    for spec in COLUMNS:
        if spec.required and spec.name not in present_cols:
            add_error(0, spec.name, "",
                      f"Required column '{spec.name}' is missing from the file.")

    if any(e.blocking for e in errors):
        report.errors = errors[:_MAX_ERRORS_RETURNED]
        report.total_error_count = len(errors)
        report.blocking = True
        return report

    # ── Per-row state for cross-row consistency ────────────────────────────────
    # patient_id → {enrollment_date, age, sex, site_id} accumulated from this file
    file_patient_attrs: dict[str, dict] = {}
    # site_id → {site_name, city, country, principal_investigator} from this file
    file_site_attrs: dict[str, dict] = {}
    # (patient_id, visit_number) → row_num to catch in-file duplicates
    seen_visit_keys: dict[tuple, int] = {}

    validated_rows: list[dict] = []

    # ── Pass 2: Row-level validation ───────────────────────────────────────────
    for i, row in enumerate(rows):
        row_num = i + 1  # 1-based
        ok = True  # track per-row fatal issues

        def err(col, val, reason, blocking=True):
            nonlocal ok
            add_error(row_num, col, str(val), reason, blocking)
            if blocking:
                ok = False

        # ── site_id ────────────────────────────────────────────────────────────
        site_id = row.get("site_id", "").strip()
        if not site_id:
            err("site_id", "", "site_id is required and cannot be blank.")

        # ── patient_id ─────────────────────────────────────────────────────────
        patient_id = row.get("patient_id", "").strip()
        if not patient_id:
            err("patient_id", "", "patient_id is required and cannot be blank.")

        # ── age ────────────────────────────────────────────────────────────────
        age_raw = row.get("age", "")
        age = _coerce_int(age_raw)
        if age is None:
            err("age", age_raw, "age must be an integer.")
        elif not (0 <= age <= 120):
            err("age", age_raw, f"age {age} is outside the valid range 0–120.")

        # ── sex ────────────────────────────────────────────────────────────────
        sex_raw = row.get("sex", "").strip()
        sex = sex_raw.upper() if sex_raw else ""
        if sex not in ("M", "F"):
            err("sex", sex_raw, "sex must be M or F (case-insensitive).")

        # ── enrollment_date ────────────────────────────────────────────────────
        enr_raw = row.get("enrollment_date", "").strip()
        if _is_ambiguous_date(enr_raw):
            err("enrollment_date", enr_raw,
                "Ambiguous date format. Use YYYY-MM-DD to avoid day/month confusion.")
        enr_date = _parse_iso_date(enr_raw) if not _is_ambiguous_date(enr_raw) else None
        if enr_date is None and not _is_ambiguous_date(enr_raw):
            err("enrollment_date", enr_raw,
                "enrollment_date must be a valid date in YYYY-MM-DD format.")
        if enr_date and enr_date > today:
            err("enrollment_date", enr_raw,
                f"enrollment_date {enr_raw} is in the future.")

        # ── visit_number ───────────────────────────────────────────────────────
        vnum_raw = row.get("visit_number", "")
        visit_number = _coerce_int(vnum_raw)
        if visit_number is None or visit_number < 1:
            err("visit_number", vnum_raw,
                "visit_number must be a positive integer.")

        # ── visit_name ─────────────────────────────────────────────────────────
        visit_name = row.get("visit_name", "").strip()
        if not visit_name:
            err("visit_name", "", "visit_name is required and cannot be blank.")

        # ── scheduled_date ─────────────────────────────────────────────────────
        sched_raw = row.get("scheduled_date", "").strip()
        if _is_ambiguous_date(sched_raw):
            err("scheduled_date", sched_raw,
                "Ambiguous date format. Use YYYY-MM-DD to avoid day/month confusion.")
        sched_date = _parse_iso_date(sched_raw) if not _is_ambiguous_date(sched_raw) else None
        if sched_date is None and not _is_ambiguous_date(sched_raw):
            err("scheduled_date", sched_raw,
                "scheduled_date must be a valid date in YYYY-MM-DD format.")

        # ── actual_date ────────────────────────────────────────────────────────
        actual_raw = row.get("actual_date", "").strip()
        actual_date: Optional[date] = None
        is_missed = not actual_raw
        if actual_raw:
            if _is_ambiguous_date(actual_raw):
                err("actual_date", actual_raw,
                    "Ambiguous date format. Use YYYY-MM-DD to avoid day/month confusion.")
            else:
                actual_date = _parse_iso_date(actual_raw)
                if actual_date is None:
                    err("actual_date", actual_raw,
                        "actual_date must be a valid date in YYYY-MM-DD format.")

        # ── dose_administered_mg ───────────────────────────────────────────────
        dose_raw = row.get("dose_administered_mg", "").strip()
        dose: Optional[float] = None
        if dose_raw:
            dose = _coerce_float(dose_raw)
            if dose is None:
                err("dose_administered_mg", dose_raw,
                    "dose_administered_mg must be a non-negative number.")
            elif dose < 0:
                err("dose_administered_mg", dose_raw,
                    "dose_administered_mg cannot be negative.")
        elif not is_missed:
            # Completed visit with no dose — warn
            report.warnings.append(
                f"Row {row_num}: dose_administered_mg is blank for a completed visit "
                "(actual_date is set). It will be stored as NULL."
            )

        # ── Date ordering ──────────────────────────────────────────────────────
        if enr_date and sched_date and sched_date < enr_date:
            err("scheduled_date", sched_raw,
                f"scheduled_date ({sched_raw}) is before enrollment_date ({enr_raw}).")

        # ── Protocol lookup ────────────────────────────────────────────────────
        protocol_visit = None
        if visit_number is not None and visit_number >= 1:
            protocol_visit = protocol_visit_map.get(visit_number)
            if protocol_visit is None:
                err("visit_number", str(visit_number),
                    f"visit_number {visit_number} is not defined in the protocol configuration. "
                    "Only protocol-defined visits can be imported.")
            elif visit_name and protocol_visit.visit_name.strip().lower() != visit_name.lower():
                err("visit_name", visit_name,
                    f"visit_name '{visit_name}' does not match the protocol name "
                    f"'{protocol_visit.visit_name}' for visit_number {visit_number}.")

        # ── visit_id (deterministic if absent) ────────────────────────────────
        visit_id_from_file = row.get("visit_id", "").strip()
        if visit_id_from_file:
            visit_id = visit_id_from_file
        elif patient_id and visit_number is not None:
            visit_id = f"VIS-{patient_id}-{visit_number:02d}"
        else:
            visit_id = ""

        # ── In-file duplicate (patient_id, visit_number) ───────────────────────
        if patient_id and visit_number is not None:
            vkey = (patient_id, visit_number)
            if vkey in seen_visit_keys:
                err("visit_number", str(visit_number),
                    f"Duplicate row: patient_id '{patient_id}' already has "
                    f"visit_number {visit_number} at row {seen_visit_keys[vkey]}.")
            else:
                seen_visit_keys[vkey] = row_num

        # ── Cross-row patient consistency ──────────────────────────────────────
        if patient_id and enr_date and age is not None and sex in ("M", "F") and site_id:
            attrs = {
                "enrollment_date": enr_date,
                "age": age,
                "sex": sex,
                "site_id": site_id,
            }
            if patient_id in file_patient_attrs:
                prev = file_patient_attrs[patient_id]
                if prev != attrs:
                    err("patient_id", patient_id,
                        f"Patient '{patient_id}' appears with different attributes in "
                        f"this file (first seen at row {prev.get('_row', '?')}). "
                        "enrollment_date, age, sex and site_id must be identical on every row "
                        "for the same patient.")
            else:
                attrs["_row"] = row_num
                file_patient_attrs[patient_id] = attrs

        # ── Cross-row site consistency ─────────────────────────────────────────
        site_detail_cols = ("site_name", "city", "country", "principal_investigator")
        site_details = {c: row.get(c, "").strip() for c in site_detail_cols}
        any_site_detail = any(site_details.values())
        if site_id and any_site_detail:
            if site_id in file_site_attrs:
                prev_details = file_site_attrs[site_id]
                if prev_details != site_details:
                    err("site_id", site_id,
                        f"site_id '{site_id}' appears with different site details "
                        "in this file. All rows for the same site must have identical "
                        "site_name, city, country, and principal_investigator.")
            else:
                file_site_attrs[site_id] = site_details

        # ── Skip further enrichment if this row already has blocking errors ────
        if not ok:
            continue

        # ── Compute server-side fields ─────────────────────────────────────────
        # actual_day: (actual_date - enrollment_date).days, same rule as seed
        actual_day: Optional[int] = None
        if actual_date and enr_date:
            actual_day = (actual_date - enr_date).days

        # detected_date: same rule as seed/detector
        # missed → scheduled_date; otherwise → actual_date
        detected_date: Optional[date] = None
        if actual_date:
            detected_date = actual_date
        elif sched_date:
            detected_date = sched_date

        # protocol fields — from protocol config, never from file
        protocol_target_day = protocol_visit.target_day if protocol_visit else None
        protocol_dose = protocol_dose_mg
        assessments_required = list(protocol_visit.required_assessments) if protocol_visit else []

        # lists from file
        assessments_completed = _split_list(row.get("assessments_completed", ""))
        active_medications = _split_list(row.get("active_medications", ""))
        notes = row.get("notes", "").strip()[:2000]

        validated_rows.append({
            "site_id": site_id,
            "site_name": site_details.get("site_name") or file_site_attrs.get(site_id, {}).get("site_name", ""),
            "city": site_details.get("city") or file_site_attrs.get(site_id, {}).get("city", ""),
            "country": site_details.get("country") or file_site_attrs.get(site_id, {}).get("country", ""),
            "principal_investigator": site_details.get("principal_investigator") or file_site_attrs.get(site_id, {}).get("principal_investigator", ""),
            "patient_id": patient_id,
            "enrollment_date": enr_date.isoformat() if enr_date else None,
            "age": age,
            "sex": sex,
            "visit_id": visit_id,
            "visit_number": visit_number,
            "visit_name": protocol_visit.visit_name if protocol_visit else visit_name,
            "scheduled_date": sched_date.isoformat() if sched_date else None,
            "actual_date": actual_date.isoformat() if actual_date else None,
            "is_missed": is_missed,
            "protocol_target_day": protocol_target_day,
            "actual_day": actual_day,
            "dose_administered_mg": dose,
            "protocol_dose_mg": protocol_dose,
            "assessments_completed": assessments_completed,
            "assessments_required": assessments_required,
            "active_medications": active_medications,
            "notes": notes,
            "detected_date": detected_date.isoformat() if detected_date else None,
        })

    # ── Pass 3: FK checks against existing DB data ─────────────────────────────
    # Build a set of validated patient_ids for FK checks
    vrow_by_patient: dict[str, list] = {}
    for vr in validated_rows:
        vrow_by_patient.setdefault(vr["patient_id"], []).append(vr)

    for patient_id, vrows in vrow_by_patient.items():
        site_id = vrows[0]["site_id"]
        if patient_id in existing_patients:
            db_site = existing_patients[patient_id].get("site_id", "")
            if db_site and db_site != site_id:
                # Patient already exists under a different site — blocking
                r_num = next(
                    (i + 1 for i, r in enumerate(rows)
                     if r.get("patient_id", "").strip() == patient_id),
                    0
                )
                add_error(r_num, "patient_id", patient_id,
                          f"Patient '{patient_id}' already exists in the database under "
                          f"site '{db_site}', but this file assigns them to site '{site_id}'. "
                          "Patients cannot be moved between sites.")

    # site_id not in DB and not in file → blocking
    for i, row in enumerate(rows):
        row_num = i + 1
        sid = row.get("site_id", "").strip()
        if not sid:
            continue
        if sid not in existing_sites and sid not in file_site_attrs:
            add_error(row_num, "site_id", sid,
                      f"site_id '{sid}' is not in the database and no site details "
                      "(site_name, city, country, principal_investigator) were provided "
                      "for it in this file.")

    # ── Pass 4: Counts for preview ─────────────────────────────────────────────
    # Count unique sites, patients, visits from validated_rows
    seen_sites     = set()
    seen_patients  = set()
    seen_visits    = set()

    for vr in validated_rows:
        sid = vr["site_id"]
        pid = vr["patient_id"]
        vid = vr["visit_id"]
        vkey = (pid, vr["visit_number"])

        # Site counts
        if sid not in seen_sites:
            seen_sites.add(sid)
            if sid not in existing_sites:
                report.sites_new += 1
            else:
                db_s = existing_sites[sid]
                file_s = {
                    "site_name": vr["site_name"],
                    "city": vr["city"],
                    "country": vr["country"],
                    "principal_investigator": vr["principal_investigator"],
                }
                if any(file_s.get(k) and db_s.get(k) != file_s[k] for k in file_s if file_s[k]):
                    report.sites_existing_diff += 1
                else:
                    report.sites_existing_same += 1

        # Patient counts
        if pid not in seen_patients:
            seen_patients.add(pid)
            if pid not in existing_patients:
                report.patients_new += 1
            else:
                db_p = existing_patients[pid]
                if (db_p.get("enrollment_date") == vr["enrollment_date"]
                        and db_p.get("age") == vr["age"]
                        and db_p.get("sex") == vr["sex"]):
                    report.patients_existing_same += 1
                else:
                    report.patients_existing_diff += 1

        # Visit counts
        if vkey not in seen_visits:
            seen_visits.add(vkey)
            if vkey not in existing_visits_by_key:
                report.visits_new += 1
            else:
                db_v = existing_visits_by_key[vkey]
                if (db_v.get("actual_date") == vr["actual_date"]
                        and db_v.get("dose_administered_mg") == vr["dose_administered_mg"]):
                    report.visits_existing_same += 1
                else:
                    report.visits_existing_diff += 1

    # ── Finalise ───────────────────────────────────────────────────────────────
    all_blocking = [e for e in errors if e.blocking]
    report.total_error_count = len(all_blocking)
    report.errors = errors[:_MAX_ERRORS_RETURNED]

    # rows_skipped_with_errors = total input rows minus the rows that passed all checks
    report.rows_skipped_with_errors = len(rows) - len(validated_rows)

    # blocking = True ONLY when there is nothing to import at all
    # (partial imports are allowed — errored rows are simply skipped)
    report.blocking = len(validated_rows) == 0

    if report.rows_skipped_with_errors > 0:
        report.warnings.append(
            f"{report.rows_skipped_with_errors} row(s) contained blocking errors and will be "
            "skipped. Only the valid rows will be imported."
        )

    # Always set validated_rows — commit uses only these (the clean subset)
    report.validated_rows = validated_rows

    return report
