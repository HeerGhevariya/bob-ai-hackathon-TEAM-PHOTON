"""
test_imports.py — Comprehensive tests for the Data Import feature

Covers all cases from the spec (section 8) plus the recency-window pin test.

Test groups:
  A. column_spec drift detection
  B. Parser — CSV and XLSX
  C. Validator — valid files
  D. Validator — failure cases
  E. Validator — protocol field enforcement
  F. Recency window pinning (date behavior)
  G. Deviation ID format and collision resistance
  H. visit_id format
  I. Demo sample files (skipped gracefully if files not present)

Run from src/backend/:
    pip install pytest openpyxl
    pytest test_imports.py -v

Note: Commit-path tests (H, I partial) require a live Supabase connection.
      The pure-logic tests (A–G) run entirely in memory.
"""

import io
import os
import csv
import sys
import pytest
from datetime import date, timedelta
from pathlib import Path

# Add backend to path
sys.path.insert(0, os.path.dirname(__file__))

from imports.column_spec import (
    COLUMNS, COLUMN_MAP, PII_PATTERNS,
    SERVER_COMPUTED_COLUMNS, MULTISHEET_NAMES,
)
from imports.parser import parse_file, ParseError, _normalise_header
from imports.validator import validate, ValidationReport
from core.protocol import get_protocol


# ── Helpers ────────────────────────────────────────────────────────────────────

def _protocol_maps():
    proto = get_protocol()
    visit_map = {v.visit_number: v for v in proto.visits}
    dose_mg = proto.dose_rules[0].dose_mg
    return visit_map, dose_mg


def _make_csv(rows: list[dict], extra_headers: list[str] = None) -> bytes:
    """Build a CSV bytes object from a list of dicts."""
    if not rows:
        return b""
    headers = list(rows[0].keys())
    if extra_headers:
        headers = extra_headers + headers
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=headers, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return buf.getvalue().encode("utf-8")


def _make_xlsx(rows: list[dict], sheet_name: str = "Sheet1") -> bytes:
    """Build an XLSX bytes object."""
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet_name
    if not rows:
        buf = io.BytesIO(); wb.save(buf); return buf.getvalue()
    headers = list(rows[0].keys())
    ws.append(headers)
    for row in rows:
        ws.append([row.get(h, "") for h in headers])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _make_multisheet_xlsx(sites: list[dict], patients: list[dict], visits: list[dict]) -> bytes:
    """Build an XLSX with Sites, Patients, Visits sheets."""
    import openpyxl
    wb = openpyxl.Workbook()
    ws_sites = wb.active
    ws_sites.title = "Sites"
    if sites:
        ws_sites.append(list(sites[0].keys()))
        for r in sites: ws_sites.append(list(r.values()))

    ws_patients = wb.create_sheet("Patients")
    if patients:
        ws_patients.append(list(patients[0].keys()))
        for r in patients: ws_patients.append(list(r.values()))

    ws_visits = wb.create_sheet("Visits")
    if visits:
        ws_visits.append(list(visits[0].keys()))
        for r in visits: ws_visits.append(list(r.values()))

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# Baseline valid row for a real protocol visit
VALID_VISIT_ROW = {
    "site_id": "SITE-999",
    "site_name": "Test Hospital",
    "city": "Mumbai",
    "country": "India",
    "principal_investigator": "Dr. Test",
    "patient_id": "PAT-9001",
    "enrollment_date": "2024-04-01",
    "age": "45",
    "sex": "F",
    "visit_number": "3",        # Week 2 — visit 3 in protocol
    "visit_name": "Week 2",
    "scheduled_date": "2024-04-15",
    "actual_date": "2024-04-16",
    "dose_administered_mg": "200",
    "assessments_completed": "vital_signs;blood_panel;adverse_events;dose_compliance",
    "active_medications": "Metformin",
    "notes": "All good",
}


def _run_validate(rows, today=date(2024, 6, 1), extra_sites=None, extra_patients=None):
    """Helper: parse CSV from rows + run validate with empty DB state."""
    data = _make_csv(rows)
    pr = parse_file("test.csv", data)
    visit_map, dose_mg = _protocol_maps()
    return validate(
        pr,
        existing_sites=extra_sites or {},
        existing_patients=extra_patients or {},
        existing_visits={},
        existing_visits_by_key={},
        protocol_visit_map=visit_map,
        protocol_dose_mg=dose_mg,
        today=today,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# A. column_spec drift detection
# ═══════════════════════════════════════════════════════════════════════════════

class TestColumnSpec:
    def test_all_columns_have_unique_names(self):
        names = [c.name for c in COLUMNS]
        assert len(names) == len(set(names)), "Duplicate column names in COLUMNS"

    def test_column_map_matches_columns(self):
        for c in COLUMNS:
            assert c.name in COLUMN_MAP
            assert COLUMN_MAP[c.name] is c

    def test_required_columns_present(self):
        required = {c.name for c in COLUMNS if c.required}
        expected_required = {
            "site_id", "patient_id", "enrollment_date", "age", "sex",
            "visit_number", "visit_name", "scheduled_date",
        }
        assert expected_required <= required

    def test_server_computed_not_in_columns(self):
        col_names = {c.name for c in COLUMNS}
        assert not SERVER_COMPUTED_COLUMNS & col_names, (
            "A server-computed column name appears in COLUMNS — it should not be importable."
        )

    def test_pii_patterns_compile(self):
        import re
        for p in PII_PATTERNS:
            re.compile(p)  # must not raise

    def test_multisheet_names_tuple(self):
        assert MULTISHEET_NAMES == ("Sites", "Patients", "Visits")


# ═══════════════════════════════════════════════════════════════════════════════
# B. Parser
# ═══════════════════════════════════════════════════════════════════════════════

class TestParser:
    def test_valid_csv_flat(self):
        data = _make_csv([VALID_VISIT_ROW])
        pr = parse_file("test.csv", data)
        assert pr.layout == "flat"
        assert pr.raw_row_count == 1
        assert pr.rows[0]["site_id"] == "SITE-999"
        assert pr.rows[0]["sex"] == "F"

    def test_utf8_bom(self):
        """CSV with UTF-8 BOM must be parsed correctly."""
        data = b"\xef\xbb\xbf" + _make_csv([VALID_VISIT_ROW])
        pr = parse_file("bom.csv", data)
        assert pr.raw_row_count == 1

    def test_semicolon_delimiter(self):
        """Semicolon-delimited CSV must be sniffed and parsed."""
        row = VALID_VISIT_ROW.copy()
        # Build a semicolon CSV manually
        headers = list(row.keys())
        lines = [";".join(headers),
                 ";".join(str(row[h]) for h in headers)]
        data = "\n".join(lines).encode("utf-8")
        pr = parse_file("semi.csv", data)
        assert pr.raw_row_count == 1
        assert pr.rows[0]["site_id"] == "SITE-999"

    def test_header_normalisation(self):
        """Headers with spaces and hyphens must be normalised."""
        assert _normalise_header("Site ID") == "site_id"
        assert _normalise_header("Visit-Number") == "visit_number"
        assert _normalise_header("  Dose Administered MG  ") == "dose_administered_mg"

    def test_wrong_extension_xls(self):
        with pytest.raises(ParseError) as exc:
            parse_file("data.xls", b"fake")
        assert exc.value.code == "wrong_extension"

    def test_wrong_extension_xlsm(self):
        with pytest.raises(ParseError) as exc:
            parse_file("data.xlsm", b"fake")
        assert exc.value.code == "wrong_extension"

    def test_wrong_extension_txt(self):
        with pytest.raises(ParseError) as exc:
            parse_file("data.txt", b"hello")
        assert exc.value.code == "wrong_extension"

    def test_oversized_file(self):
        big = b"x" * (10 * 1024 * 1024 + 1)
        with pytest.raises(ParseError) as exc:
            parse_file("big.csv", big)
        assert exc.value.code == "file_too_large"

    def test_pii_column_name_rejected(self):
        row = VALID_VISIT_ROW.copy()
        row["patient_name"] = "John Smith"
        data = _make_csv([row])
        with pytest.raises(ParseError) as exc:
            parse_file("pii.csv", data)
        assert exc.value.code == "pii_column"
        assert "patient_name" in exc.value.message

    def test_pii_dob_rejected(self):
        row = VALID_VISIT_ROW.copy()
        row["date_of_birth"] = "1980-01-01"
        data = _make_csv([row])
        with pytest.raises(ParseError) as exc:
            parse_file("pii.csv", data)
        assert exc.value.code == "pii_column"

    def test_formula_cell_prefixed(self):
        """Cells starting with = must be kept as text (prefixed with apostrophe)."""
        row = VALID_VISIT_ROW.copy()
        row["notes"] = "=1+1"
        data = _make_csv([row])
        pr = parse_file("formula.csv", data)
        # The cell must be kept as text, starting with apostrophe
        notes_val = pr.rows[0].get("notes", "")
        assert notes_val.startswith("'"), f"Formula cell not neutralised: {notes_val!r}"

    def test_valid_xlsx_flat(self):
        data = _make_xlsx([VALID_VISIT_ROW])
        pr = parse_file("test.xlsx", data)
        assert pr.layout == "flat"
        assert pr.raw_row_count == 1

    def test_valid_xlsx_multisheet(self):
        sites = [{"site_id": "SITE-999", "site_name": "Test Hospital",
                  "city": "Mumbai", "country": "India",
                  "principal_investigator": "Dr. Test"}]
        patients = [{"patient_id": "PAT-9001", "site_id": "SITE-999",
                     "enrollment_date": "2024-04-01", "age": "45", "sex": "F"}]
        visits = [{"patient_id": "PAT-9001", "visit_number": "3",
                   "visit_name": "Week 2", "scheduled_date": "2024-04-15",
                   "actual_date": "2024-04-16", "dose_administered_mg": "200",
                   "assessments_completed": "vital_signs;blood_panel;adverse_events;dose_compliance",
                   "active_medications": "Metformin", "notes": ""}]
        data = _make_multisheet_xlsx(sites, patients, visits)
        pr = parse_file("multi.xlsx", data)
        assert pr.layout == "multi_sheet"
        assert pr.raw_row_count == 1
        assert pr.rows[0]["site_id"] == "SITE-999"
        assert pr.rows[0]["patient_id"] == "PAT-9001"
        assert pr.rows[0]["visit_number"] == "3"

    def test_server_computed_columns_noted(self):
        """Server-computed columns in the file are captured in server_computed_found."""
        row = VALID_VISIT_ROW.copy()
        row["protocol_target_day"] = "14"
        row["protocol_dose_mg"] = "200"
        data = _make_csv([row])
        pr = parse_file("sc.csv", data)
        assert "protocol_target_day" in pr.server_computed_found
        assert "protocol_dose_mg" in pr.server_computed_found
        # Must NOT appear in normalised rows
        assert "protocol_target_day" not in pr.rows[0]

    def test_unknown_columns_ignored_and_listed(self):
        row = VALID_VISIT_ROW.copy()
        row["extra_column_xyz"] = "foo"
        data = _make_csv([row])
        pr = parse_file("extra.csv", data)
        assert "extra_column_xyz" in pr.ignored_columns
        assert "extra_column_xyz" not in pr.rows[0]


# ═══════════════════════════════════════════════════════════════════════════════
# C. Validator — valid files
# ═══════════════════════════════════════════════════════════════════════════════

class TestValidatorValid:
    def test_valid_single_row(self):
        report = _run_validate([VALID_VISIT_ROW])
        assert not report.blocking, f"Unexpected errors: {[e.reason for e in report.errors]}"
        assert report.visits_new == 1
        assert report.patients_new == 1
        assert report.sites_new == 1

    def test_missed_visit_blank_actual_date(self):
        """Blank actual_date is a valid missed visit."""
        row = VALID_VISIT_ROW.copy()
        row["actual_date"] = ""
        report = _run_validate([row])
        assert not report.blocking
        assert report.validated_rows[0]["is_missed"] is True
        assert report.validated_rows[0]["actual_date"] is None
        assert report.validated_rows[0]["actual_day"] is None

    def test_actual_day_computed_correctly(self):
        """actual_day = (actual_date - enrollment_date).days"""
        row = VALID_VISIT_ROW.copy()
        row["enrollment_date"] = "2024-04-01"
        row["actual_date"] = "2024-04-15"  # 14 days after enrollment
        report = _run_validate([row])
        assert not report.blocking
        assert report.validated_rows[0]["actual_day"] == 14

    def test_protocol_fields_from_config_not_file(self):
        """protocol_target_day, protocol_dose_mg, assessments_required come from protocol."""
        row = VALID_VISIT_ROW.copy()
        # Add server-computed cols to the file — parser will strip them
        # but let's confirm the validated row has protocol values
        report = _run_validate([row])
        assert not report.blocking
        vrow = report.validated_rows[0]
        proto_map, proto_dose = _protocol_maps()
        pv = proto_map[3]  # visit_number=3 = Week 2
        assert vrow["protocol_target_day"] == pv.target_day, (
            f"expected target_day={pv.target_day}, got {vrow['protocol_target_day']}"
        )
        assert vrow["protocol_dose_mg"] == proto_dose
        assert set(vrow["assessments_required"]) == set(pv.required_assessments)

    def test_sex_lowercase_normalised(self):
        row = VALID_VISIT_ROW.copy()
        row["sex"] = "f"
        report = _run_validate([row])
        assert not report.blocking
        assert report.validated_rows[0]["sex"] == "F"

    def test_visit_id_generated_deterministically(self):
        """Without visit_id in the file, VIS-{patient_id}-{visit_number:02d} is used."""
        row = VALID_VISIT_ROW.copy()
        # Ensure no visit_id col
        row.pop("visit_id", None)
        report = _run_validate([row])
        assert not report.blocking
        assert report.validated_rows[0]["visit_id"] == "VIS-PAT-9001-03"

    def test_visit_id_from_file_used_as_given(self):
        row = VALID_VISIT_ROW.copy()
        row["visit_id"] = "CUSTOM-VIS-001"
        report = _run_validate([row])
        assert not report.blocking
        assert report.validated_rows[0]["visit_id"] == "CUSTOM-VIS-001"

    def test_reupload_same_file_zero_new(self):
        """Re-uploading the same file with existing data produces zero new counts."""
        row = VALID_VISIT_ROW.copy()
        existing_sites = {"SITE-999": {
            "site_name": "Test Hospital", "city": "Mumbai",
            "country": "India", "principal_investigator": "Dr. Test",
        }}
        existing_patients = {"PAT-9001": {
            "site_id": "SITE-999",
            "enrollment_date": "2024-04-01",
            "age": 45, "sex": "F",
        }}
        existing_visits_by_key = {("PAT-9001", 3): {
            "actual_date": "2024-04-16",
            "dose_administered_mg": 200.0,
        }}
        data = _make_csv([row])
        pr = parse_file("test.csv", data)
        visit_map, dose_mg = _protocol_maps()
        report = validate(
            pr,
            existing_sites=existing_sites,
            existing_patients=existing_patients,
            existing_visits={},
            existing_visits_by_key=existing_visits_by_key,
            protocol_visit_map=visit_map,
            protocol_dose_mg=dose_mg,
            today=date(2024, 6, 1),
        )
        assert not report.blocking
        assert report.visits_new == 0
        assert report.visits_existing_same == 1
        assert report.patients_new == 0
        assert report.sites_new == 0

    def test_detected_date_is_actual_date_for_completed_visit(self):
        row = VALID_VISIT_ROW.copy()
        row["actual_date"] = "2024-04-16"
        report = _run_validate([row])
        assert not report.blocking
        assert report.validated_rows[0]["detected_date"] == "2024-04-16"

    def test_detected_date_is_scheduled_date_for_missed_visit(self):
        row = VALID_VISIT_ROW.copy()
        row["actual_date"] = ""
        row["scheduled_date"] = "2024-04-15"
        report = _run_validate([row])
        assert not report.blocking
        assert report.validated_rows[0]["detected_date"] == "2024-04-15"


# ═══════════════════════════════════════════════════════════════════════════════
# D. Validator — failure cases
# ═══════════════════════════════════════════════════════════════════════════════

class TestValidatorFailures:
    def _assert_blocking_error(self, rows, col=None):
        report = _run_validate(rows)
        assert report.blocking, "Expected blocking errors but got none"
        if col:
            assert any(e.column == col for e in report.errors), (
                f"Expected error on column '{col}', got: {[e.column for e in report.errors]}"
            )
        return report

    def test_missing_required_column(self):
        row = VALID_VISIT_ROW.copy()
        del row["patient_id"]
        data = _make_csv([row])
        pr = parse_file("test.csv", data)
        visit_map, dose_mg = _protocol_maps()
        report = validate(pr, {}, {}, {}, {}, visit_map, dose_mg, date(2024, 6, 1))
        assert report.blocking
        # Error should reference patient_id as missing column
        assert any("patient_id" in e.column or "patient_id" in e.reason for e in report.errors)

    def test_ambiguous_date_rejected(self):
        row = VALID_VISIT_ROW.copy()
        row["enrollment_date"] = "03/04/2024"  # ambiguous DD/MM or MM/DD
        report = self._assert_blocking_error([row])
        assert any("YYYY-MM-DD" in e.reason for e in report.errors)

    def test_invalid_sex(self):
        row = VALID_VISIT_ROW.copy()
        row["sex"] = "X"
        self._assert_blocking_error([row], col="sex")

    def test_age_out_of_range(self):
        row = VALID_VISIT_ROW.copy()
        row["age"] = "150"
        self._assert_blocking_error([row], col="age")

    def test_age_negative(self):
        row = VALID_VISIT_ROW.copy()
        row["age"] = "-5"
        self._assert_blocking_error([row], col="age")

    def test_age_non_integer(self):
        row = VALID_VISIT_ROW.copy()
        row["age"] = "forty"
        self._assert_blocking_error([row], col="age")

    def test_unknown_site_without_details(self):
        """site_id not in DB and no site details in file → blocking error."""
        row = VALID_VISIT_ROW.copy()
        # Remove site detail columns
        for col in ("site_name", "city", "country", "principal_investigator"):
            row.pop(col, None)
        # site_id not in existing_sites
        report = _run_validate([row], extra_sites={})
        assert report.blocking
        assert any("site_id" in e.column or "SITE-999" in e.value for e in report.errors)

    def test_patient_under_different_site(self):
        """Patient already in DB under a different site → blocking error."""
        row = VALID_VISIT_ROW.copy()
        existing_patients = {
            "PAT-9001": {"site_id": "SITE-001", "enrollment_date": "2024-04-01",
                         "age": 45, "sex": "F"}
        }
        report = _run_validate([row], extra_patients=existing_patients)
        assert report.blocking
        assert any("different" in e.reason.lower() or "site" in e.reason.lower()
                   for e in report.errors)

    def test_duplicate_patient_visit_in_file(self):
        """(patient_id, visit_number) duplicated within one file → blocking error."""
        row2 = VALID_VISIT_ROW.copy()
        rows = [VALID_VISIT_ROW.copy(), row2]
        report = _run_validate(rows)
        assert report.blocking
        assert any("duplicate" in e.reason.lower() for e in report.errors)

    def test_visit_not_in_protocol(self):
        """visit_number not in protocol config → blocking error."""
        row = VALID_VISIT_ROW.copy()
        row["visit_number"] = "99"
        row["visit_name"] = "Mystery Visit"
        self._assert_blocking_error([row], col="visit_number")

    def test_enrollment_date_in_future(self):
        row = VALID_VISIT_ROW.copy()
        row["enrollment_date"] = "2030-01-01"
        report = _run_validate([row], today=date(2024, 6, 1))
        assert report.blocking

    def test_scheduled_before_enrollment(self):
        row = VALID_VISIT_ROW.copy()
        row["enrollment_date"] = "2024-05-01"
        row["scheduled_date"] = "2024-04-15"  # before enrollment
        self._assert_blocking_error([row], col="scheduled_date")

    def test_negative_dose(self):
        row = VALID_VISIT_ROW.copy()
        row["dose_administered_mg"] = "-50"
        self._assert_blocking_error([row], col="dose_administered_mg")

    def test_patient_attributes_inconsistent_across_rows(self):
        """Same patient_id with different age on two rows → blocking error."""
        row1 = VALID_VISIT_ROW.copy()
        row2 = VALID_VISIT_ROW.copy()
        row2["visit_number"] = "4"
        row2["visit_name"] = "Week 4"
        row2["age"] = "99"  # different age
        report = _run_validate([row1, row2])
        assert report.blocking
        assert any("patient" in e.reason.lower() for e in report.errors)

    def test_site_details_inconsistent_across_rows(self):
        row1 = VALID_VISIT_ROW.copy()
        row2 = VALID_VISIT_ROW.copy()
        row2["visit_number"] = "4"
        row2["visit_name"] = "Week 4"
        row2["city"] = "Delhi"  # different city for same site
        report = _run_validate([row1, row2])
        assert report.blocking
        assert any("site" in e.reason.lower() for e in report.errors)

    def test_formula_cell_in_notes_stored_as_text(self):
        """A notes cell starting with = is kept as text (not evaluated)."""
        row = VALID_VISIT_ROW.copy()
        row["notes"] = "=SUM(1,2)"
        data = _make_csv([row])
        pr = parse_file("formula_notes.csv", data)
        notes_val = pr.rows[0].get("notes", "")
        assert not notes_val.startswith("="), (
            f"Formula cell was not neutralised in parser: {notes_val!r}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# E. Protocol field enforcement
# ═══════════════════════════════════════════════════════════════════════════════

class TestProtocolFieldEnforcement:
    def test_protocol_target_day_comes_from_config(self):
        """Even if file has protocol_target_day, the validated row uses protocol config."""
        # The parser strips server-computed columns before validate sees them.
        # Verify by confirming the validated row's value matches the real protocol.
        row = VALID_VISIT_ROW.copy()
        # Add a "wrong" protocol_target_day — parser will drop it
        # We build CSV with an extra column that looks server-computed
        row_with_sc = dict(row)
        row_with_sc["protocol_target_day"] = "999"
        data = _make_csv([row_with_sc])
        pr = parse_file("sc.csv", data)
        # Confirm parser stripped it
        assert "protocol_target_day" not in pr.rows[0]

        visit_map, dose_mg = _protocol_maps()
        report = validate(pr, {}, {}, {}, {}, visit_map, dose_mg, date(2024, 6, 1))
        assert not report.blocking
        pv = visit_map[3]  # visit_number=3
        assert report.validated_rows[0]["protocol_target_day"] == pv.target_day
        assert report.validated_rows[0]["protocol_target_day"] != 999

    def test_protocol_dose_mg_comes_from_config(self):
        row = VALID_VISIT_ROW.copy()
        row_with_sc = dict(row)
        row_with_sc["protocol_dose_mg"] = "999"
        data = _make_csv([row_with_sc])
        pr = parse_file("sc.csv", data)
        assert "protocol_dose_mg" not in pr.rows[0]
        visit_map, dose_mg = _protocol_maps()
        report = validate(pr, {}, {}, {}, {}, visit_map, dose_mg, date(2024, 6, 1))
        assert not report.blocking
        assert report.validated_rows[0]["protocol_dose_mg"] == dose_mg
        assert report.validated_rows[0]["protocol_dose_mg"] != 999

    def test_assessments_required_comes_from_config(self):
        row = VALID_VISIT_ROW.copy()
        row_with_sc = dict(row)
        row_with_sc["assessments_required"] = "fake_assessment"
        data = _make_csv([row_with_sc])
        pr = parse_file("sc.csv", data)
        visit_map, dose_mg = _protocol_maps()
        report = validate(pr, {}, {}, {}, {}, visit_map, dose_mg, date(2024, 6, 1))
        assert not report.blocking
        pv = visit_map[3]
        assert set(report.validated_rows[0]["assessments_required"]) == set(pv.required_assessments)


# ═══════════════════════════════════════════════════════════════════════════════
# F. Recency window pinning
# ═══════════════════════════════════════════════════════════════════════════════

class TestRecencyWindowPinning:
    """
    Pins the RiskScorer recency-window behavior for three date categories:
      - BEFORE window:  detected_date < reference_date - 30d  → no recency bonus
      - INSIDE window:  reference_date - 30d <= detected_date  → recency bonus
      - AFTER ref date: detected_date > reference_date          → still counted as recent
                        (open-ended upper bound — confirmed from source)

    Reference date: 2024-09-01  (hardcoded in both MockDataSource and SupabaseDataSource)
    Window start:   2024-08-02
    """

    REF_DATE = date(2024, 9, 1)
    WINDOW_START = REF_DATE - timedelta(days=30)  # 2024-08-02

    def _make_deviation(self, detected_date, severity="major"):
        from core.deviation_detector import Deviation
        from core.protocol import DeviationType
        return Deviation(
            deviation_id="DEV-TEST-001",
            patient_id="PAT-0001",
            site_id="SITE-001",
            visit_id="VIS-PAT-0001-01",
            visit_name="Screening",
            deviation_type=DeviationType.MISSED_VISIT,
            description="test",
            expected_value="x",
            actual_value="y",
            detected_date=detected_date,
            protocol_reference="PHOENIX-301",
            severity=severity,
        )

    def _score(self, deviations, n_patients=1):
        from core.risk_scorer import RiskScorer
        scorer = RiskScorer(reference_date=self.REF_DATE)
        site_info = {"SITE-001": {"name": "Test", "total_patients": n_patients}}
        profiles = scorer.score_all_sites(deviations, site_info)
        return profiles[0]

    def test_before_window_no_recency(self):
        """Deviation 31 days before ref_date → recent_deviations_30d == 0."""
        d = self._make_deviation(self.REF_DATE - timedelta(days=31))
        profile = self._score([d])
        assert profile.recent_deviations_30d == 0, (
            f"Expected 0 recent deviations for date before window, got {profile.recent_deviations_30d}"
        )

    def test_inside_window_counted(self):
        """Deviation 15 days before ref_date (inside window) → recent_deviations_30d == 1."""
        d = self._make_deviation(self.REF_DATE - timedelta(days=15))
        profile = self._score([d])
        assert profile.recent_deviations_30d == 1, (
            f"Expected 1 recent deviation inside window, got {profile.recent_deviations_30d}"
        )

    def test_on_window_boundary_counted(self):
        """Deviation exactly on window_start (2024-08-02) → counted as recent."""
        d = self._make_deviation(self.WINDOW_START)
        profile = self._score([d])
        assert profile.recent_deviations_30d == 1

    def test_after_ref_date_counted_as_recent(self):
        """
        Deviation AFTER reference_date → still counted as recent.
        The upper bound is open (no cutoff above reference_date).
        This is the existing behavior — test pins it so it cannot silently change.
        """
        d = self._make_deviation(self.REF_DATE + timedelta(days=30))  # 2024-10-01
        profile = self._score([d])
        assert profile.recent_deviations_30d == 1, (
            f"Expected 1 recent deviation for post-ref-date deviation (open upper bound), "
            f"got {profile.recent_deviations_30d}. "
            "This behavior is intentional — see implementation analysis in plan."
        )

    def test_recency_score_higher_than_pre_window(self):
        """A recent deviation must produce a higher risk score than an equally-weighted old one."""
        recent_dev = self._make_deviation(self.REF_DATE - timedelta(days=10))
        old_dev    = self._make_deviation(self.REF_DATE - timedelta(days=60))

        recent_profile = self._score([recent_dev])
        old_profile    = self._score([old_dev])

        assert recent_profile.risk_score > old_profile.risk_score, (
            "Recent deviation should produce higher risk score than old deviation of same severity."
        )


# ═══════════════════════════════════════════════════════════════════════════════
# G. Deviation ID format and collision resistance
# ═══════════════════════════════════════════════════════════════════════════════

class TestDeviationIds:
    def test_id_format(self):
        from imports.commit_service import _deviation_id
        assert _deviation_id("VIS-PAT-0001-03", "missed_visit", 0) == "DEV-VIS-PAT-0001-03-MV-00"
        assert _deviation_id("VIS-PAT-0001-03", "banned_comedication", 0) == "DEV-VIS-PAT-0001-03-BC-00"
        assert _deviation_id("VIS-PAT-0001-03", "banned_comedication", 1) == "DEV-VIS-PAT-0001-03-BC-01"

    def test_two_banned_meds_no_collision(self):
        """Two banned_comedication deviations on the same visit must get unique IDs."""
        from imports.commit_service import _build_deviation_rows, _deviation_id
        from core.deviation_detector import Deviation
        from core.protocol import DeviationType

        def make_bc(idx):
            return Deviation(
                deviation_id=f"SEED-{idx}",  # seed ID; will be replaced
                patient_id="PAT-0001",
                site_id="SITE-001",
                visit_id="VIS-PAT-0001-03",
                visit_name="Week 2",
                deviation_type=DeviationType.BANNED_COMEDICATION,
                description=f"Banned med {idx}",
                expected_value="none",
                actual_value=f"drug{idx}",
                detected_date=date(2024, 4, 16),
                protocol_reference="PHOENIX-301",
                severity="major",
            )

        devs = [make_bc(0), make_bc(1)]
        rows = _build_deviation_rows(devs, {"VIS-PAT-0001-03"})
        ids = [r["deviation_id"] for r in rows]
        assert len(ids) == len(set(ids)), f"Collision in deviation IDs: {ids}"
        assert ids[0] == "DEV-VIS-PAT-0001-03-BC-00"
        assert ids[1] == "DEV-VIS-PAT-0001-03-BC-01"

    def test_different_types_on_same_visit_no_collision(self):
        from imports.commit_service import _build_deviation_rows
        from core.deviation_detector import Deviation
        from core.protocol import DeviationType

        devs = [
            Deviation("X", "PAT-0001", "SITE-001", "VIS-PAT-0001-03", "Week 2",
                      DeviationType.MISSED_VISIT, "d", "e", "a",
                      date(2024, 4, 16), "ref", "major"),
            Deviation("Y", "PAT-0001", "SITE-001", "VIS-PAT-0001-03", "Week 2",
                      DeviationType.MISSING_ASSESSMENT, "d", "e", "a",
                      date(2024, 4, 16), "ref", "minor"),
        ]
        rows = _build_deviation_rows(devs, {"VIS-PAT-0001-03"})
        ids = [r["deviation_id"] for r in rows]
        assert len(ids) == len(set(ids)), f"Collision: {ids}"


# ═══════════════════════════════════════════════════════════════════════════════
# H. visit_id format
# ═══════════════════════════════════════════════════════════════════════════════

class TestVisitId:
    def test_deterministic_id_matches_seed_format(self):
        """VIS-{patient_id}-{visit_number:02d} — same pattern as seed."""
        row = VALID_VISIT_ROW.copy()
        row.pop("visit_id", None)
        report = _run_validate([row])
        assert not report.blocking
        vid = report.validated_rows[0]["visit_id"]
        # Pattern: VIS-PAT-9001-03 (visit_number=3 → :02d = "03")
        assert vid == "VIS-PAT-9001-03", f"visit_id was {vid!r}"

    def test_double_digit_visit_number(self):
        row = VALID_VISIT_ROW.copy()
        row["visit_number"] = "10"
        row["visit_name"] = "Week 48 / End of Treatment"
        row.pop("visit_id", None)
        report = _run_validate([row])
        assert not report.blocking
        assert report.validated_rows[0]["visit_id"] == "VIS-PAT-9001-10"

    def test_file_supplied_visit_id_wins(self):
        row = VALID_VISIT_ROW.copy()
        row["visit_id"] = "MY-CUSTOM-ID-42"
        report = _run_validate([row])
        assert not report.blocking
        assert report.validated_rows[0]["visit_id"] == "MY-CUSTOM-ID-42"


# ═══════════════════════════════════════════════════════════════════════════════
# I. Demo sample files (skipped if not present)
# ═══════════════════════════════════════════════════════════════════════════════

DEMO_DIR = Path(__file__).parent.parent.parent / "demo"
CLEAN_CSV = DEMO_DIR / "sample_import_clean.csv"
ERRORS_CSV = DEMO_DIR / "sample_import_errors.csv"


@pytest.mark.skipif(not CLEAN_CSV.exists(), reason="demo/sample_import_clean.csv not present")
class TestDemoCleanFile:
    def test_clean_file_parses(self):
        data = CLEAN_CSV.read_bytes()
        pr = parse_file(CLEAN_CSV.name, data)
        assert pr.raw_row_count > 0

    def test_clean_file_validates(self):
        data = CLEAN_CSV.read_bytes()
        pr = parse_file(CLEAN_CSV.name, data)
        visit_map, dose_mg = _protocol_maps()
        report = validate(pr, {}, {}, {}, {}, visit_map, dose_mg, date(2024, 6, 1))
        assert not report.blocking, (
            f"Clean demo file has unexpected blocking errors: "
            f"{[e.reason for e in report.errors]}"
        )

    def test_clean_file_reupload_zero_new(self):
        """Re-uploading the clean file should report identical counts."""
        data = CLEAN_CSV.read_bytes()
        pr = parse_file(CLEAN_CSV.name, data)
        visit_map, dose_mg = _protocol_maps()
        report1 = validate(pr, {}, {}, {}, {}, visit_map, dose_mg, date(2024, 6, 1))
        assert not report1.blocking

        # Simulate "existing" state from first upload
        existing_sites = {r["site_id"]: {k: r[k] for k in ("site_name", "city", "country", "principal_investigator")}
                          for r in report1.validated_rows}
        existing_patients = {r["patient_id"]: {k: r[k] for k in ("site_id", "enrollment_date", "age", "sex")}
                             for r in report1.validated_rows}
        existing_visits_by_key = {(r["patient_id"], r["visit_number"]): r
                                  for r in report1.validated_rows}

        report2 = validate(pr, existing_sites, existing_patients, {}, existing_visits_by_key,
                           visit_map, dose_mg, date(2024, 6, 1))
        assert not report2.blocking
        assert report2.visits_new == 0
        assert report2.patients_new == 0
        assert report2.sites_new == 0


@pytest.mark.skipif(not ERRORS_CSV.exists(), reason="demo/sample_import_errors.csv not present")
class TestDemoErrorsFile:
    def test_errors_file_has_blocking_errors(self):
        """The deliberate-errors demo file must produce at least one blocking error."""
        data = ERRORS_CSV.read_bytes()
        try:
            pr = parse_file(ERRORS_CSV.name, data)
        except ParseError:
            return  # acceptable — parse-level error also counts
        visit_map, dose_mg = _protocol_maps()
        report = validate(pr, {}, {}, {}, {}, visit_map, dose_mg, date(2024, 6, 1))
        assert report.blocking, "Expected blocking errors in the deliberate-errors demo file"
