"""
column_spec.py — Single Source of Truth for Import Column Definitions

Used by:
  - validator.py     (required/optional check, type rules)
  - parser.py        (header normalisation)
  - template_gen.py  (template column order + descriptions)
  - test_imports.py  (golden list for drift detection)
  - DataImport.jsx   (help text — fetched via /api/imports/columns)

Changing a column name here propagates everywhere automatically.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class ColumnSpec:
    name: str                       # canonical snake_case name stored in DB
    required: bool                  # True = blocking error if absent
    required_for_new_site: bool     # True = required only when site not in DB
    dtype: str                      # 'str' | 'int' | 'float' | 'date' | 'sex' | 'list'
    description: str
    example: str
    max_length: Optional[int] = None  # for str columns, cap at this


# ── Ordered list of all accepted columns ──────────────────────────────────────
# This is the authoritative definition. Do not add columns in any other file.

COLUMNS: list[ColumnSpec] = [
    # ── Site identity ─────────────────────────────────────────────────
    ColumnSpec(
        name="site_id",
        required=True,
        required_for_new_site=False,
        dtype="str",
        description="Unique site identifier (e.g. SITE-042). Must match an existing "
                    "site in the database OR be accompanied by site_name, city, country, "
                    "and principal_investigator columns.",
        example="SITE-042",
        max_length=64,
    ),
    ColumnSpec(
        name="site_name",
        required=False,
        required_for_new_site=True,
        dtype="str",
        description="Full name of the clinical site. Required only when the site_id is "
                    "not yet in the database.",
        example="Mumbai Oncology Center",
        max_length=256,
    ),
    ColumnSpec(
        name="city",
        required=False,
        required_for_new_site=True,
        dtype="str",
        description="City where the site is located. Required for new sites.",
        example="Mumbai",
        max_length=128,
    ),
    ColumnSpec(
        name="country",
        required=False,
        required_for_new_site=True,
        dtype="str",
        description="Country where the site is located. Required for new sites.",
        example="India",
        max_length=128,
    ),
    ColumnSpec(
        name="principal_investigator",
        required=False,
        required_for_new_site=True,
        dtype="str",
        description="Full name of the Principal Investigator. Required for new sites.",
        example="Dr. Priya Sharma",
        max_length=256,
    ),

    # ── Patient identity ──────────────────────────────────────────────
    ColumnSpec(
        name="patient_id",
        required=True,
        required_for_new_site=False,
        dtype="str",
        description="Pseudonymous subject identifier (e.g. PAT-0501). "
                    "Must NOT be a real patient name, date of birth, or MRN.",
        example="PAT-0501",
        max_length=64,
    ),
    ColumnSpec(
        name="enrollment_date",
        required=True,
        required_for_new_site=False,
        dtype="date",
        description="Date the patient was enrolled in the trial. "
                    "Format: YYYY-MM-DD. Must not be in the future.",
        example="2024-04-15",
    ),
    ColumnSpec(
        name="age",
        required=True,
        required_for_new_site=False,
        dtype="int",
        description="Patient age in years at enrollment (0–120).",
        example="54",
    ),
    ColumnSpec(
        name="sex",
        required=True,
        required_for_new_site=False,
        dtype="sex",
        description="Biological sex: M or F (case-insensitive).",
        example="F",
    ),

    # ── Visit identity ────────────────────────────────────────────────
    ColumnSpec(
        name="visit_id",
        required=False,
        required_for_new_site=False,
        dtype="str",
        description="Optional visit identifier. If omitted, a deterministic ID is "
                    "generated as VIS-{patient_id}-{visit_number:02d}.",
        example="VIS-PAT-0501-03",
        max_length=128,
    ),
    ColumnSpec(
        name="visit_number",
        required=True,
        required_for_new_site=False,
        dtype="int",
        description="Protocol visit number (positive integer, 1–11 for PHOENIX-301). "
                    "Must match a visit defined in the protocol configuration.",
        example="3",
    ),
    ColumnSpec(
        name="visit_name",
        required=True,
        required_for_new_site=False,
        dtype="str",
        description="Protocol visit name (e.g. 'Week 2'). "
                    "Must match the protocol configuration for the given visit_number.",
        example="Week 2",
        max_length=128,
    ),
    ColumnSpec(
        name="scheduled_date",
        required=True,
        required_for_new_site=False,
        dtype="date",
        description="Date the visit was scheduled. Format: YYYY-MM-DD. "
                    "Must be on or after enrollment_date.",
        example="2024-04-29",
    ),
    ColumnSpec(
        name="actual_date",
        required=False,
        required_for_new_site=False,
        dtype="date",
        description="Date the visit actually occurred. Format: YYYY-MM-DD. "
                    "Leave blank for a missed visit (stored as NULL).",
        example="2024-04-30",
    ),
    ColumnSpec(
        name="dose_administered_mg",
        required=False,
        required_for_new_site=False,
        dtype="float",
        description="Dose actually administered in milligrams. "
                    "Leave blank if unknown or if visit was missed.",
        example="200",
    ),
    ColumnSpec(
        name="assessments_completed",
        required=False,
        required_for_new_site=False,
        dtype="list",
        description="Semicolon-separated list of completed assessments. "
                    "Example: vital_signs;blood_panel;adverse_events",
        example="vital_signs;blood_panel;adverse_events;dose_compliance",
        max_length=2000,
    ),
    ColumnSpec(
        name="active_medications",
        required=False,
        required_for_new_site=False,
        dtype="list",
        description="Semicolon-separated list of medications the patient is currently "
                    "taking. Use drug names as listed in the protocol.",
        example="Metformin;Lisinopril",
        max_length=2000,
    ),
    ColumnSpec(
        name="notes",
        required=False,
        required_for_new_site=False,
        dtype="str",
        description="Free-text notes for this visit. Maximum 2000 characters.",
        example="Patient reported mild nausea.",
        max_length=2000,
    ),
]

# Fast lookup by canonical name
COLUMN_MAP: dict[str, ColumnSpec] = {c.name: c for c in COLUMNS}

# Columns the upload must NEVER accept (computed server-side)
SERVER_COMPUTED_COLUMNS: frozenset[str] = frozenset({
    "is_problem_site",
    "protocol_target_day",
    "protocol_dose_mg",
    "assessments_required",
    "actual_day",
    "severity",
    "deviation_id",
    "deviation_type",
    "risk_score",
    "risk_tier",
})

# Direct-identifier patterns — reject the whole file if any header matches.
# The regex is applied after header normalisation (lower, strip, spaces→_).
PII_PATTERNS: list[str] = [
    r"^name$",
    r"^patient_name$",
    r"^subject_name$",
    r"^full_name$",
    r"^first_name$",
    r"^last_name$",
    r"^surname$",
    r"^dob$",
    r"^date_of_birth$",
    r"^birth_date$",
    r"^birthdate$",
    r"^phone$",
    r"^telephone$",
    r"^mobile$",
    r"^email$",
    r"^address$",
    r"^street$",
    r"^zip$",
    r"^postal_code$",
    r"^postcode$",
    r"^mrn$",
    r"^medical_record_number$",
    r"^aadhaar$",
    r"^ssn$",
    r"^social_security$",
    r"^national_id$",
    r"^passport$",
    r"^nhs_number$",
    r"^insurance_id$",
    r"^health_card$",
]

# Multi-sheet layout sheet names (exact, case-sensitive after strip)
MULTISHEET_NAMES: tuple[str, str, str] = ("Sites", "Patients", "Visits")

# Columns expected in each sheet of the multi-sheet layout
MULTISHEET_SITES_COLS:    list[str] = ["site_id", "site_name", "city", "country", "principal_investigator"]
MULTISHEET_PATIENTS_COLS: list[str] = ["patient_id", "site_id", "enrollment_date", "age", "sex"]
MULTISHEET_VISITS_COLS:   list[str] = [c.name for c in COLUMNS if c.name not in ("site_name", "city", "country", "principal_investigator")]

# Maximum file size and row count (hard limits; env overrides IMPORT_MAX_ROWS for deployed cap)
MAX_FILE_BYTES: int = 10 * 1024 * 1024  # 10 MB
MAX_ROWS_HARD:  int = 20_000            # parse-time absolute ceiling
# Deployed cap is read from env MAX_IMPORT_ROWS (default 5000) in router.py

# Formula-injection prefixes — keep as plain text, never evaluate
FORMULA_PREFIXES: tuple[str, ...] = ("=", "+", "-", "@")
