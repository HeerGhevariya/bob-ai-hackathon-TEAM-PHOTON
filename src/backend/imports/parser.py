"""
parser.py — File Parsing for Data Imports

Handles:
  - .csv  (UTF-8 BOM, cp1252 fallback, comma/semicolon/tab sniffing)
  - .xlsx (openpyxl data_only=True — formulas are never evaluated)
  - Flat layout (one row per visit) and multi-sheet layout (Sites/Patients/Visits)
  - Header normalisation: lower, strip, spaces+hyphens → underscores
  - Formula-injection prefix safety: values starting with = + - @ kept as plain text
  - Cell length capping per column_spec

Returns a ParseResult with raw row dicts and metadata.
CPU-bound — callers must run this in a threadpool.
"""

import csv
import hashlib
import io
import re
from dataclasses import dataclass, field
from typing import Optional

from .column_spec import (
    COLUMNS,
    COLUMN_MAP,
    FORMULA_PREFIXES,
    MAX_FILE_BYTES,
    MAX_ROWS_HARD,
    MULTISHEET_NAMES,
    PII_PATTERNS,
    SERVER_COMPUTED_COLUMNS,
)

# Pre-compiled PII regex
_PII_RE = [re.compile(p) for p in PII_PATTERNS]


# ── Data structures ────────────────────────────────────────────────────────────

@dataclass
class ParseResult:
    layout: str                             # 'flat' | 'multi_sheet'
    rows: list[dict]                        # normalised flat rows (visit-level)
    ignored_columns: list[str]             # header names present but unknown
    server_computed_found: list[str]       # server-computed columns present (warning)
    file_sha256: str
    filename: str
    raw_row_count: int                     # rows before any deduplication


class ParseError(Exception):
    """Parse-level hard stop — wrong extension, oversized file, PII column."""
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


# ── Header normalisation ───────────────────────────────────────────────────────

def _normalise_header(h: str) -> str:
    """Lower-case, strip whitespace, replace spaces/hyphens with underscores."""
    return re.sub(r"[\s\-]+", "_", h.strip().lower())


def _check_pii_headers(headers: list[str]) -> Optional[str]:
    """Return the first offending header if PII is detected, else None."""
    for h in headers:
        norm = _normalise_header(h)
        for patt in _PII_RE:
            if patt.match(norm):
                return h
    return None


# ── Cell sanitisation ──────────────────────────────────────────────────────────

def _safe_cell(value, col_name: str) -> str:
    """
    Convert cell to plain text string.
    - Neutralise formula-injection: prefix with a single-quote sentinel ONLY
      in the CSV export path; here we just keep as text.
    - Cap length per column_spec.
    """
    if value is None:
        return ""
    s = str(value).strip()
    # Strip formula-injection prefix — keep content, remove leading operator
    if s and s[0] in FORMULA_PREFIXES:
        s = "'" + s   # prefix with apostrophe so downstream CSV export is safe
    spec = COLUMN_MAP.get(col_name)
    if spec and spec.max_length:
        s = s[:spec.max_length]
    return s


# ── CSV parsing ────────────────────────────────────────────────────────────────

def _parse_csv_bytes(data: bytes) -> list[dict[str, str]]:
    """
    Parse CSV bytes. Handles:
    - UTF-8 BOM
    - cp1252 fallback
    - Comma, semicolon, tab delimiter sniffing
    Returns list of raw dicts (string values).
    """
    # Decode — try UTF-8 (with BOM), then cp1252
    for encoding in ("utf-8-sig", "utf-8", "cp1252"):
        try:
            text = data.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ParseError("encoding_error", "File could not be decoded as UTF-8 or cp1252.")

    # Sniff delimiter
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        delimiter = dialect.delimiter
    except csv.Error:
        delimiter = ","  # fallback

    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    rows = []
    for row in reader:
        rows.append(dict(row))
    return rows


# ── XLSX parsing ───────────────────────────────────────────────────────────────

def _parse_xlsx_bytes(data: bytes) -> tuple[str, list[dict[str, str]]]:
    """
    Parse XLSX bytes. Uses openpyxl with data_only=True so formulas are
    never evaluated — only their cached values (or None) are read.

    Detects multi-sheet layout if the workbook contains sheets named exactly
    'Sites', 'Patients', 'Visits'.

    Returns (layout, flat_rows).
    """
    try:
        import openpyxl
    except ImportError:
        raise ParseError(
            "missing_dependency",
            "openpyxl is required to parse .xlsx files. "
            "Install with: pip install openpyxl"
        )

    wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    sheet_names = wb.sheetnames

    # Detect multi-sheet layout
    if all(name in sheet_names for name in MULTISHEET_NAMES):
        flat_rows = _xlsx_multisheet(wb)
        wb.close()
        return "multi_sheet", flat_rows

    # Flat layout — read first sheet
    ws = wb.active
    flat_rows = _xlsx_sheet_to_dicts(ws)
    wb.close()
    return "flat", flat_rows


def _xlsx_sheet_to_dicts(ws) -> list[dict[str, str]]:
    """Convert an openpyxl worksheet to a list of string dicts."""
    rows_iter = ws.iter_rows(values_only=True)
    try:
        header_row = next(rows_iter)
    except StopIteration:
        return []
    headers = [str(h).strip() if h is not None else "" for h in header_row]

    result = []
    for row in rows_iter:
        d = {}
        for i, h in enumerate(headers):
            val = row[i] if i < len(row) else None
            # openpyxl returns datetime objects for date cells
            if hasattr(val, "strftime"):
                # Return as ISO string — validator will accept this
                d[h] = val.strftime("%Y-%m-%d")
            else:
                d[h] = "" if val is None else str(val)
        result.append(d)
    return result


def _xlsx_multisheet(wb) -> list[dict[str, str]]:
    """
    Merge Sites, Patients, Visits sheets into flat visit-level rows.
    JOIN: Visits → Patients (patient_id) → Sites (site_id).
    """
    sites_rows    = _xlsx_sheet_to_dicts(wb[MULTISHEET_NAMES[0]])
    patients_rows = _xlsx_sheet_to_dicts(wb[MULTISHEET_NAMES[1]])
    visits_rows   = _xlsx_sheet_to_dicts(wb[MULTISHEET_NAMES[2]])

    # Build lookup maps
    site_map    = {r.get("site_id", ""): r for r in sites_rows}
    patient_map = {r.get("patient_id", ""): r for r in patients_rows}

    flat = []
    for visit in visits_rows:
        pid = visit.get("patient_id", "")
        patient = patient_map.get(pid, {})
        sid = patient.get("site_id", visit.get("site_id", ""))
        site = site_map.get(sid, {})
        merged = {}
        merged.update(site)
        merged.update(patient)
        merged.update(visit)
        flat.append(merged)
    return flat


# ── Main entry point ───────────────────────────────────────────────────────────

def parse_file(filename: str, data: bytes) -> ParseResult:
    """
    Parse an uploaded file and return a ParseResult.

    Raises ParseError for hard stops (wrong extension, oversized, PII headers).
    Does NOT validate field values — that is validator.py's job.
    """
    # ── Extension check ────────────────────────────────────────────────
    lower_name = filename.lower()
    if lower_name.endswith(".xls"):
        raise ParseError("wrong_extension",
                         "Legacy .xls files are not accepted. Please export as .xlsx or .csv.")
    if lower_name.endswith(".xlsm"):
        raise ParseError("wrong_extension",
                         ".xlsm (macro-enabled) files are not accepted for security reasons. "
                         "Please export as .xlsx or .csv.")
    if not (lower_name.endswith(".csv") or lower_name.endswith(".xlsx")):
        raise ParseError("wrong_extension",
                         f"Unsupported file type '{filename}'. Only .csv and .xlsx are accepted.")

    # ── Size check ─────────────────────────────────────────────────────
    if len(data) > MAX_FILE_BYTES:
        mb = len(data) / (1024 * 1024)
        raise ParseError("file_too_large",
                         f"File is {mb:.1f} MB. Maximum allowed size is 10 MB.")

    # ── Hash ────────────────────────────────────────────────────────────
    sha256 = hashlib.sha256(data).hexdigest()

    # ── Parse ───────────────────────────────────────────────────────────
    if lower_name.endswith(".csv"):
        layout = "flat"
        raw_rows = _parse_csv_bytes(data)
    else:
        layout, raw_rows = _parse_xlsx_bytes(data)

    # ── Row count hard limit ────────────────────────────────────────────
    if len(raw_rows) > MAX_ROWS_HARD:
        raise ParseError("too_many_rows",
                         f"File contains {len(raw_rows):,} data rows. "
                         f"Maximum is {MAX_ROWS_HARD:,} rows.")

    # ── Normalise headers and check PII ────────────────────────────────
    if not raw_rows:
        # Return empty result — validator will catch this
        return ParseResult(
            layout=layout,
            rows=[],
            ignored_columns=[],
            server_computed_found=[],
            file_sha256=sha256,
            filename=filename,
            raw_row_count=0,
        )

    # Collect original headers from first row
    original_headers = list(raw_rows[0].keys())

    pii_hit = _check_pii_headers(original_headers)
    if pii_hit:
        raise ParseError(
            "pii_column",
            f"Column '{pii_hit}' looks like a direct patient identifier. "
            "This file cannot be accepted. Remove all personal identifiers and re-upload. "
            "Only pseudonymous subject IDs and age are permitted."
        )

    # Build header normalisation map: original → canonical
    norm_map: dict[str, str] = {}
    for h in original_headers:
        norm_map[h] = _normalise_header(h)

    # Classify headers
    known_canonical    = {c.name for c in COLUMNS}
    ignored_columns:   list[str] = []
    server_comp_found: list[str] = []

    for orig, norm in norm_map.items():
        if norm in SERVER_COMPUTED_COLUMNS:
            server_comp_found.append(orig)
        elif norm not in known_canonical:
            ignored_columns.append(orig)

    # ── Normalise rows ─────────────────────────────────────────────────
    normalised_rows: list[dict[str, str]] = []
    for raw in raw_rows:
        norm_row: dict[str, str] = {}
        for orig_key, value in raw.items():
            canon = norm_map.get(orig_key)
            if canon and canon in known_canonical:
                norm_row[canon] = _safe_cell(value, canon)
            # server-computed and unknown columns are silently dropped
        normalised_rows.append(norm_row)

    return ParseResult(
        layout=layout,
        rows=normalised_rows,
        ignored_columns=ignored_columns,
        server_computed_found=server_comp_found,
        file_sha256=sha256,
        filename=filename,
        raw_row_count=len(normalised_rows),
    )
