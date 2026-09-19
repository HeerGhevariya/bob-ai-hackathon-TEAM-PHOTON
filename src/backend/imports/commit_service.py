"""
commit_service.py — Write Validated Import Data to Supabase

Responsibilities:
  1. Write sites → patients → visits in FK-safe order, 500 rows/chunk
  2. Run deviation detection ONLY for imported patients (not detect_for_site)
  3. Upsert new deviations, then delete obsolete ones for those visits
  4. Re-score affected sites using ALL their deviations + ALL their patients
  5. Upsert updated site_risk_profiles
  6. Identify stale CAPA reports (never delete them)
  7. Call _load_all_data() to invalidate the in-memory cache
  8. Write audit record to data_imports

All DB writes use parameterized upserts via the supabase-py client.
Cell values beginning with = + - @ were already prefixed in parser.py.

The RiskScorer is constructed with the same reference_date = date(2024,9,1)
that the existing code uses. See the pre-implementation analysis for the
recency-window anchoring behavior.

Deviation ID format: DEV-{visit_id}-{type_abbrev}-{idx:02d}
  where type_abbrev is a 2-char abbreviation defined in DEVIATION_TYPE_ABBREV.
"""

import uuid
from datetime import date
from typing import Any, Optional

from .validator import ValidationReport

# Deviation type abbreviations for deterministic ID generation.
# Two deviations of the same type on one visit get idx 00, 01, etc.
DEVIATION_TYPE_ABBREV: dict[str, str] = {
    "missed_visit":        "MV",
    "late_visit":          "LV",
    "early_visit":         "EV",
    "wrong_dose":          "WD",
    "banned_comedication": "BC",
    "missing_assessment":  "MA",
}

_CHUNK_SIZE = 500


# ── Import result ──────────────────────────────────────────────────────────────

class CommitResult:
    def __init__(self):
        self.import_id: str = str(uuid.uuid4())
        self.sites_written: int = 0
        self.patients_written: int = 0
        self.visits_written: int = 0
        self.visits_updated: int = 0
        self.visits_skipped: int = 0
        self.deviations_added: int = 0
        self.deviations_removed: int = 0
        self.affected_site_ids: list[str] = []
        self.tier_changes: list[dict] = []   # [{site_id, old_tier, new_tier}]
        self.stale_capa_site_ids: list[str] = []
        self.error: Optional[str] = None
        self.status: str = "committed"


# ── Helpers ────────────────────────────────────────────────────────────────────

def _upsert_chunks(client, table: str, rows: list[dict], on_conflict: str) -> int:
    """Upsert rows in chunks of _CHUNK_SIZE. Returns count written."""
    written = 0
    for i in range(0, len(rows), _CHUNK_SIZE):
        chunk = rows[i:i + _CHUNK_SIZE]
        client.table(table).upsert(chunk, on_conflict=on_conflict).execute()
        written += len(chunk)
    return written


def _deviation_id(visit_id: str, dev_type: str, idx: int) -> str:
    abbrev = DEVIATION_TYPE_ABBREV.get(dev_type, dev_type[:2].upper())
    return f"DEV-{visit_id}-{abbrev}-{idx:02d}"


def _build_deviation_rows(deviations: list, visit_id_set: set[str]) -> list[dict]:
    """
    Convert Deviation objects to DB-ready dicts with deterministic IDs.
    Handles multiple deviations of the same type on one visit (e.g. multiple
    banned medications) by using an incrementing per-visit-per-type index.
    """
    # Counter: (visit_id, deviation_type) → next idx
    type_counters: dict[tuple, int] = {}
    rows = []
    for dev in deviations:
        if dev.visit_id not in visit_id_set:
            continue
        key = (dev.visit_id, dev.deviation_type.value)
        idx = type_counters.get(key, 0)
        type_counters[key] = idx + 1

        dev_id = _deviation_id(dev.visit_id, dev.deviation_type.value, idx)
        rows.append({
            "deviation_id": dev_id,
            "patient_id": dev.patient_id,
            "site_id": dev.site_id,
            "visit_id": dev.visit_id,
            "visit_name": dev.visit_name,
            "deviation_type": dev.deviation_type.value,
            "description": dev.description,
            "expected_value": dev.expected_value,
            "actual_value": dev.actual_value,
            "detected_date": dev.detected_date.isoformat() if dev.detected_date else None,
            "protocol_reference": dev.protocol_reference,
            "severity": dev.severity,
            "raw_data": _safe_json(dev.raw_data),
        })
    return rows


def _safe_json(data: dict) -> dict:
    clean = {}
    for k, v in data.items():
        if v is None:
            clean[k] = None
        elif isinstance(v, (int, float, str, bool)):
            clean[k] = v
        elif isinstance(v, (list, tuple)):
            clean[k] = [str(x) if not isinstance(x, (int, float, str, bool, type(None))) else x for x in v]
        else:
            clean[k] = str(v)
    return clean


# ── Main commit function ───────────────────────────────────────────────────────

def commit_import(
    client,              # supabase client
    report: ValidationReport,
    on_conflict: str,    # 'skip' | 'update'
    source_label: str,
    uploaded_by: str,
    data_source_instance,  # SupabaseDataSource singleton for cache reload
) -> CommitResult:
    """
    Write validated import data to Supabase.

    Strategy:
    - Sites upserted first (FK dependency)
    - Patients second
    - Visits third
    - on_conflict='skip'   → upsert ignores rows that already exist with same PK
    - on_conflict='update' → upsert overwrites changed rows
    - Deviation upsert-then-delete for affected visit_ids
    - Re-score affected sites using ALL deviations
    - Cache reload via data_source_instance._load_all_data()

    Writes are NOT transactional (Supabase REST has no BEGIN/COMMIT).
    Order is FK-safe. On failure, the import is marked 'failed' and the
    error summary is stored. Re-uploading with on_conflict='skip' is safe.
    """
    result = CommitResult()
    rows = report.validated_rows

    if not rows:
        result.error = "No validated rows to commit."
        result.status = "failed"
        _write_audit(client, result, report, source_label, uploaded_by, on_conflict)
        return result

    try:
        # ── 1. Deduplicate sites ───────────────────────────────────────────────
        seen_sites: dict[str, dict] = {}
        for r in rows:
            sid = r["site_id"]
            if sid not in seen_sites and r.get("site_name"):
                seen_sites[sid] = {
                    "site_id": sid,
                    "site_name": r["site_name"],
                    "city": r["city"],
                    "country": r["country"],
                    "principal_investigator": r["principal_investigator"],
                    "is_problem_site": False,  # never set from file
                }

        if seen_sites:
            site_rows = list(seen_sites.values())
            if on_conflict == "update":
                result.sites_written += _upsert_chunks(
                    client, "sites", site_rows, "site_id"
                )
            else:
                # skip: only insert new ones
                existing_ids = {
                    row["site_id"]
                    for row in (client.table("sites")
                                .select("site_id")
                                .in_("site_id", list(seen_sites.keys()))
                                .execute().data or [])
                }
                new_site_rows = [r for r in site_rows if r["site_id"] not in existing_ids]
                if new_site_rows:
                    result.sites_written += _upsert_chunks(
                        client, "sites", new_site_rows, "site_id"
                    )

        # ── 2. Deduplicate patients ────────────────────────────────────────────
        seen_patients: dict[str, dict] = {}
        for r in rows:
            pid = r["patient_id"]
            if pid not in seen_patients:
                seen_patients[pid] = {
                    "patient_id": pid,
                    "site_id": r["site_id"],
                    "enrollment_date": r["enrollment_date"],
                    "age": r["age"],
                    "sex": r["sex"],
                }

        if seen_patients:
            patient_rows = list(seen_patients.values())
            if on_conflict == "update":
                result.patients_written += _upsert_chunks(
                    client, "patients", patient_rows, "patient_id"
                )
            else:
                existing_ids = {
                    row["patient_id"]
                    for row in (client.table("patients")
                                .select("patient_id")
                                .in_("patient_id", list(seen_patients.keys()))
                                .execute().data or [])
                }
                new_patient_rows = [r for r in patient_rows if r["patient_id"] not in existing_ids]
                if new_patient_rows:
                    result.patients_written += _upsert_chunks(
                        client, "patients", new_patient_rows, "patient_id"
                    )

        # ── 3. Visits ──────────────────────────────────────────────────────────
        # Check which visits already exist to track skip/update/new counts
        all_visit_ids = [r["visit_id"] for r in rows]
        existing_visit_id_set: set[str] = set()
        for chunk_start in range(0, len(all_visit_ids), 200):
            chunk_ids = all_visit_ids[chunk_start:chunk_start + 200]
            existing_data = (client.table("patient_visits")
                             .select("visit_id")
                             .in_("visit_id", chunk_ids)
                             .execute().data or [])
            existing_visit_id_set.update(r["visit_id"] for r in existing_data)

        visit_rows_to_write = []
        for r in rows:
            vid = r["visit_id"]
            visit_row = {
                "visit_id": vid,
                "patient_id": r["patient_id"],
                "site_id": r["site_id"],
                "visit_number": r["visit_number"],
                "visit_name": r["visit_name"],
                "scheduled_date": r["scheduled_date"],
                "actual_date": r["actual_date"],
                "protocol_target_day": r["protocol_target_day"],
                "actual_day": r["actual_day"],
                "dose_administered_mg": r["dose_administered_mg"],
                "protocol_dose_mg": r["protocol_dose_mg"],
                "assessments_completed": r["assessments_completed"],
                "assessments_required": r["assessments_required"],
                "active_medications": r["active_medications"],
                "notes": r["notes"],
            }

            if vid in existing_visit_id_set:
                if on_conflict == "update":
                    visit_rows_to_write.append(visit_row)
                    result.visits_updated += 1
                else:
                    result.visits_skipped += 1
            else:
                visit_rows_to_write.append(visit_row)
                result.visits_written += 1

        if visit_rows_to_write:
            _upsert_chunks(client, "patient_visits", visit_rows_to_write, "visit_id")

        # ── 4. Deviation detection for imported patients only ──────────────────
        affected_site_ids   = list({r["site_id"] for r in rows})
        affected_patient_ids = list({r["patient_id"] for r in rows})
        imported_visit_ids   = set(r["visit_id"] for r in rows)
        result.affected_site_ids = affected_site_ids

        # Reload cache so we can run detection on the freshly written data
        data_source_instance._load_all_data()

        # Import detection uses the existing pipeline classes
        from core.deviation_detector import DeviationDetector
        from core.severity_classifier import SeverityClassifier
        from core.risk_scorer import RiskScorer
        from core.protocol import get_protocol

        protocol = get_protocol()
        detector = DeviationDetector(protocol)
        classifier = SeverityClassifier()

        # Detect ONLY for imported patients
        new_deviations = []
        for site in data_source_instance.get_sites():
            if site.site_id not in affected_site_ids:
                continue
            for patient in site.patients:
                if patient.patient_id not in set(affected_patient_ids):
                    continue
                new_deviations.extend(detector.detect_for_patient(patient))

        new_deviations = classifier.classify_all(new_deviations)

        # Build new deviation rows (only for imported visit_ids)
        new_dev_rows = _build_deviation_rows(new_deviations, imported_visit_ids)
        new_dev_id_set = {r["deviation_id"] for r in new_dev_rows}

        # Fetch existing deviation IDs for imported visit_ids
        old_dev_ids: set[str] = set()
        for chunk_start in range(0, len(imported_visit_ids), 200):
            chunk_vids = list(imported_visit_ids)[chunk_start:chunk_start + 200]
            old_data = (client.table("deviations")
                        .select("deviation_id")
                        .in_("visit_id", chunk_vids)
                        .execute().data or [])
            old_dev_ids.update(r["deviation_id"] for r in old_data)

        # Upsert new deviations
        if new_dev_rows:
            _upsert_chunks(client, "deviations", new_dev_rows, "deviation_id")
            result.deviations_added = len(new_dev_rows)

        # Delete obsolete deviations (old IDs no longer produced)
        ids_to_delete = list(old_dev_ids - new_dev_id_set)
        if ids_to_delete:
            for chunk_start in range(0, len(ids_to_delete), 200):
                chunk = ids_to_delete[chunk_start:chunk_start + 200]
                client.table("deviations").delete().in_("deviation_id", chunk).execute()
            result.deviations_removed = len(ids_to_delete)

        # ── 5. Re-score affected sites using ALL their data ────────────────────
        # Reload again so deviations are fresh
        data_source_instance._load_all_data()

        scorer = RiskScorer(reference_date=date(2024, 9, 1))
        all_devs = data_source_instance.get_all_deviations()
        all_sites = data_source_instance.get_sites()

        site_map = {s.site_id: s for s in all_sites}
        old_profile_map = {rp.site_id: rp for rp in data_source_instance.get_risk_profiles()}

        profile_rows = []
        for site_id in affected_site_ids:
            site = site_map.get(site_id)
            if not site:
                continue
            site_devs = [d for d in all_devs if d.site_id == site_id]
            site_info = {site_id: {"name": site.site_name, "total_patients": len(site.patients)}}
            new_profiles = scorer.score_all_sites(site_devs, site_info)
            if not new_profiles:
                continue
            new_rp = new_profiles[0]

            # Track tier changes
            old_rp = old_profile_map.get(site_id)
            if old_rp and old_rp.risk_tier != new_rp.risk_tier:
                result.tier_changes.append({
                    "site_id": site_id,
                    "old_tier": old_rp.risk_tier.value if hasattr(old_rp.risk_tier, "value") else str(old_rp.risk_tier),
                    "new_tier": new_rp.risk_tier.value if hasattr(new_rp.risk_tier, "value") else str(new_rp.risk_tier),
                })

            profile_rows.append({
                "site_id": new_rp.site_id,
                "site_name": new_rp.site_name,
                "risk_score": new_rp.risk_score,
                "risk_tier": new_rp.risk_tier.value if hasattr(new_rp.risk_tier, "value") else str(new_rp.risk_tier),
                "trend_direction": new_rp.trend_direction.value if hasattr(new_rp.trend_direction, "value") else str(new_rp.trend_direction),
                "total_deviations": new_rp.total_deviations,
                "major_count": new_rp.major_count,
                "minor_count": new_rp.minor_count,
                "administrative_count": new_rp.administrative_count,
                "deviation_types": new_rp.deviation_types,
                "patients_affected": new_rp.patients_affected,
                "total_patients": new_rp.total_patients,
                "recent_deviations_30d": new_rp.recent_deviations_30d,
                "repeat_deviation_types": new_rp.repeat_deviation_types,
                "top_risk_factors": [
                    {
                        "factor_name": rf.factor_name,
                        "description": rf.description,
                        "contribution": rf.contribution,
                    }
                    for rf in new_rp.top_risk_factors
                ],
            })

        if profile_rows:
            _upsert_chunks(client, "site_risk_profiles", profile_rows, "site_id")

        # ── 6. Stale CAPA reports (identify only, do NOT delete) ──────────────
        stale_data = (client.table("capa_reports")
                      .select("site_id")
                      .in_("site_id", affected_site_ids)
                      .execute().data or [])
        result.stale_capa_site_ids = [r["site_id"] for r in stale_data]

        # ── 7. Final cache reload ──────────────────────────────────────────────
        data_source_instance._load_all_data()

    except Exception as exc:
        result.error = str(exc)
        result.status = "failed"
        import traceback
        print(f"[import] commit failed: {exc}")
        traceback.print_exc()

    # ── 8. Write audit record ──────────────────────────────────────────────────
    _write_audit(client, result, report, source_label, uploaded_by, on_conflict)

    return result


def _write_audit(
    client,
    result: CommitResult,
    report: ValidationReport,
    source_label: str,
    uploaded_by: str,
    on_conflict: str,
) -> None:
    """Write (or update) the data_imports audit row. Never raises."""
    try:
        error_summary: dict = {}
        if result.error:
            error_summary["error"] = result.error
        if report.total_error_count:
            error_summary["blocking_errors"] = report.total_error_count
        if report.warnings:
            error_summary["warnings"] = report.warnings[:20]

        client.table("data_imports").upsert({
            "import_id": result.import_id,
            "uploaded_by": uploaded_by,
            "source_label": source_label,
            "filename": report.filename,
            "file_sha256": report.file_sha256,
            "layout": report.layout,
            "rows_total": report.row_count,
            "sites_new": report.sites_new,
            "patients_new": report.patients_new,
            "visits_new": result.visits_written,
            "visits_updated": result.visits_updated,
            "visits_skipped": result.visits_skipped,
            "status": result.status,
            "error_summary": error_summary,
        }, on_conflict="import_id").execute()
    except Exception as e:
        # Audit failure is non-fatal
        print(f"[import] audit write failed: {e}")
