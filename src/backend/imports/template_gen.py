"""
template_gen.py — Generate Import Template Files

Generates a downloadable CSV or XLSX template from column_spec.py.
The template always stays in sync with the column definitions — no drift possible.

XLSX template has two sheets:
  1. Template  — headers + one example row
  2. Column Guide — name, required, type, description for each column

The template endpoint works even in mock mode (no DB required).
"""

import csv
import io
from typing import Literal

from .column_spec import COLUMNS


def generate_csv_template() -> bytes:
    """Return a UTF-8 CSV template with headers and one example row."""
    output = io.StringIO()
    writer = csv.writer(output)

    # Header row
    writer.writerow([c.name for c in COLUMNS])

    # Example row — one value per column
    writer.writerow([c.example for c in COLUMNS])

    return output.getvalue().encode("utf-8-sig")  # BOM for Excel compatibility


def generate_xlsx_template() -> bytes:
    """
    Return an XLSX template with:
      Sheet 1 "Template"    — headers + example row
      Sheet 2 "Column Guide" — one row per column with all metadata
    """
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment
    except ImportError:
        raise RuntimeError(
            "openpyxl is required for XLSX template generation. "
            "Install with: pip install openpyxl"
        )

    wb = openpyxl.Workbook()

    # ── Sheet 1: Template ──────────────────────────────────────────────────────
    ws1 = wb.active
    ws1.title = "Template"

    header_font  = Font(bold=True, color="FFFFFF")
    header_fill  = PatternFill("solid", fgColor="1F4E79")  # dark blue
    req_fill     = PatternFill("solid", fgColor="2E75B6")  # medium blue
    opt_fill     = PatternFill("solid", fgColor="BDD7EE")  # light blue

    for col_idx, spec in enumerate(COLUMNS, start=1):
        cell = ws1.cell(row=1, column=col_idx, value=spec.name)
        cell.font = header_font
        cell.fill = req_fill if spec.required else opt_fill
        cell.alignment = Alignment(wrap_text=False)
        ws1.column_dimensions[cell.column_letter].width = max(len(spec.name) + 4, 18)

    # Example row
    for col_idx, spec in enumerate(COLUMNS, start=1):
        ws1.cell(row=2, column=col_idx, value=spec.example)

    # ── Sheet 2: Column Guide ──────────────────────────────────────────────────
    ws2 = wb.create_sheet("Column Guide")
    guide_headers = ["Column Name", "Required", "Required for New Sites", "Data Type", "Description", "Example"]
    for col_idx, h in enumerate(guide_headers, start=1):
        cell = ws2.cell(row=1, column=col_idx, value=h)
        cell.font = Font(bold=True)
        cell.fill = PatternFill("solid", fgColor="1F4E79")
        cell.font = Font(bold=True, color="FFFFFF")

    for row_idx, spec in enumerate(COLUMNS, start=2):
        ws2.cell(row=row_idx, column=1, value=spec.name)
        ws2.cell(row=row_idx, column=2, value="Yes" if spec.required else "No")
        ws2.cell(row=row_idx, column=3, value="Yes" if spec.required_for_new_site else "No")
        ws2.cell(row=row_idx, column=4, value=spec.dtype)
        desc_cell = ws2.cell(row=row_idx, column=5, value=spec.description)
        desc_cell.alignment = Alignment(wrap_text=True)
        ws2.cell(row=row_idx, column=6, value=spec.example)

    ws2.column_dimensions["A"].width = 30
    ws2.column_dimensions["B"].width = 12
    ws2.column_dimensions["C"].width = 22
    ws2.column_dimensions["D"].width = 12
    ws2.column_dimensions["E"].width = 60
    ws2.column_dimensions["F"].width = 30

    # ── Notes sheet ───────────────────────────────────────────────────────────
    ws3 = wb.create_sheet("Notes")
    notes = [
        ("Format", "Use YYYY-MM-DD for all dates (e.g. 2024-04-15). Ambiguous formats like 03/04/2026 are rejected."),
        ("Lists", "assessments_completed and active_medications are semicolon-separated: vital_signs;blood_panel"),
        ("Missed visits", "Leave actual_date blank to record a missed visit."),
        ("New sites", "If site_id does not exist in the database, provide site_name, city, country, and principal_investigator."),
        ("Privacy", "Do NOT include patient names, dates of birth, phone numbers, emails, MRN, Aadhaar, or SSN. Use pseudonymous IDs only."),
        ("Protocol fields", "Do NOT include protocol_target_day, protocol_dose_mg, assessments_required, or actual_day. These are computed automatically."),
        ("Re-upload", "Re-uploading the same file is safe. Existing rows are skipped (or updated, depending on your choice)."),
    ]
    ws3.cell(row=1, column=1, value="Topic").font = Font(bold=True)
    ws3.cell(row=1, column=2, value="Notes").font = Font(bold=True)
    for row_idx, (topic, note) in enumerate(notes, start=2):
        ws3.cell(row=row_idx, column=1, value=topic)
        cell = ws3.cell(row=row_idx, column=2, value=note)
        cell.alignment = Alignment(wrap_text=True)
    ws3.column_dimensions["A"].width = 20
    ws3.column_dimensions["B"].width = 80

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
