"""
router.py — FastAPI Router for Data Import Endpoints

Endpoints:
  POST /api/imports/validate   — dry-run validation (admin only)
  POST /api/imports/commit     — write to DB (admin only)
  GET  /api/imports/template   — download CSV/XLSX template (admin only)
  GET  /api/imports            — import history (admin only)
  GET  /api/imports/{id}       — single import record (admin only)
  GET  /api/imports/columns    — column spec for frontend help text

All endpoints that write or read DB return 503 when MockDataSource is active.
Template download works in all modes.

Import token: a signed JWT (HS256, 30-min expiry) containing file_sha256,
row_count, and layout. Never stored server-side — multi-instance safe.
The commit endpoint re-receives the file as multipart so it can re-validate
independently of any prior validate call.

Serverless data-version check: each instance tracks _last_data_version (the
MAX created_at of committed imports when the cache was last loaded). A
background coroutine (throttled to once per 15s) queries this and triggers
_load_all_data() if a newer commit exists. This ensures all Vercel instances
pick up data written by any other instance.
"""

import asyncio
import hashlib
import io
import os
import time
import uuid
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from .column_spec import COLUMNS, MAX_FILE_BYTES, MAX_ROWS_HARD
from .parser import ParseError, parse_file
from .template_gen import generate_csv_template, generate_xlsx_template
from .validator import validate, ValidationReport
from .commit_service import commit_import, CommitResult

router = APIRouter(prefix="/api/imports", tags=["imports"])

_bearer = HTTPBearer(auto_error=False)

# ── Env config ─────────────────────────────────────────────────────────────────
_MAX_IMPORT_ROWS = int(os.getenv("MAX_IMPORT_ROWS", "5000"))
_JWT_SECRET = os.getenv("JWT_SECRET", "trialgard-hackathon-secret-2026")
_JWT_ALGORITHM = "HS256"
_IMPORT_TOKEN_EXPIRE_SECONDS = 30 * 60  # 30 minutes

# ── Version-check state (module-level, one per serverless instance) ────────────
_last_version_check_ts: float = 0.0   # epoch seconds
_VERSION_CHECK_INTERVAL = 15.0        # seconds


# ── Auth helpers (duplicate the minimal needed, avoiding circular import) ──────

def _require_admin(credentials: HTTPAuthorizationCredentials = Depends(_bearer)) -> dict:
    """Dependency: validates Bearer token and requires role == 'admin'."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Authorization header missing.")
    try:
        import jwt
        from jwt import PyJWTError as JWTError
    except ImportError:
        try:
            from jose import jwt, JWTError
        except ImportError:
            raise HTTPException(status_code=500, detail="JWT library not installed.")
    try:
        payload = jwt.decode(credentials.credentials, _JWT_SECRET, algorithms=[_JWT_ALGORITHM])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")
    if payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required.")
    return payload


# ── Import token (signed JWT, no server-side state) ────────────────────────────

def _make_import_token(file_sha256: str, row_count: int, layout: str) -> str:
    try:
        import jwt
    except ImportError:
        from jose import jwt
    exp = int(datetime.now(timezone.utc).timestamp()) + _IMPORT_TOKEN_EXPIRE_SECONDS
    payload = {
        "type": "import_token",
        "file_sha256": file_sha256,
        "row_count": row_count,
        "layout": layout,
        "exp": exp,
    }
    return jwt.encode(payload, _JWT_SECRET, algorithm=_JWT_ALGORITHM)


def _decode_import_token(token: str) -> dict:
    try:
        import jwt
        from jwt import PyJWTError as JWTError
    except ImportError:
        from jose import jwt, JWTError
    try:
        payload = jwt.decode(token, _JWT_SECRET, algorithms=[_JWT_ALGORITHM])
    except Exception:
        raise HTTPException(status_code=400, detail="Import token is invalid or has expired. "
                                                     "Please re-upload the file to start a new validation.")
    if payload.get("type") != "import_token":
        raise HTTPException(status_code=400, detail="Invalid import token.")
    return payload


# ── Mock-mode guard ────────────────────────────────────────────────────────────

def _require_supabase():
    """Raises 503 if the active data source is MockDataSource."""
    from core.data_source import get_data_source
    from core.data_source import MockDataSource
    ds = get_data_source()
    if isinstance(ds, MockDataSource):
        raise HTTPException(
            status_code=503,
            detail=(
                "Data import requires a Supabase database connection. "
                "This instance is running on in-memory mock data. "
                "Set SUPABASE_URL and SUPABASE_ANON_KEY (or SUPABASE_SERVICE_ROLE_KEY) "
                "in your .env file to enable imports."
            ),
        )
    return ds


# ── Background version check (serverless multi-instance) ──────────────────────

async def _maybe_reload_if_stale() -> None:
    """
    Throttled check: if another Vercel instance committed an import since this
    instance last loaded its cache, reload now.
    Runs at most once per _VERSION_CHECK_INTERVAL seconds per instance.
    Non-fatal — errors are swallowed.
    """
    global _last_version_check_ts

    now = time.monotonic()
    if now - _last_version_check_ts < _VERSION_CHECK_INTERVAL:
        return
    _last_version_check_ts = now

    try:
        from db.supabase_client import get_supabase_client
        from core.data_source import get_data_source
        from core.data_source import MockDataSource

        ds = get_data_source()
        if isinstance(ds, MockDataSource):
            return

        sb = get_supabase_client()
        if not sb:
            return

        # Fetch the newest committed import's created_at
        res = (sb.table("data_imports")
               .select("created_at")
               .eq("status", "committed")
               .order("created_at", desc=True)
               .limit(1)
               .execute())

        if not res.data:
            return

        newest_str = res.data[0]["created_at"]
        # Parse ISO timestamp
        newest_dt = datetime.fromisoformat(newest_str.replace("Z", "+00:00"))

        # Compare with when this instance last loaded data
        loaded_at = getattr(ds, "_loaded_at", None)
        if loaded_at is None:
            return

        if newest_dt > loaded_at:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, ds._load_all_data)

    except Exception:
        pass  # version check is best-effort


# ── DB state helpers ───────────────────────────────────────────────────────────

def _get_existing_state(ds):
    """
    Return (existing_sites, existing_patients, existing_visits,
            existing_visits_by_key) from the data source cache.
    """
    sites_list = ds.get_sites()

    existing_sites: dict[str, dict] = {}
    existing_patients: dict[str, dict] = {}
    existing_visits: dict[str, dict] = {}
    existing_visits_by_key: dict[tuple, dict] = {}

    for site in sites_list:
        existing_sites[site.site_id] = {
            "site_name": site.site_name,
            "city": site.city,
            "country": site.country,
            "principal_investigator": site.principal_investigator,
        }
        for patient in site.patients:
            existing_patients[patient.patient_id] = {
                "site_id": patient.site_id,
                "enrollment_date": patient.enrollment_date.isoformat(),
                "age": patient.age,
                "sex": patient.sex,
            }
            for visit in patient.visits:
                v_dict = {
                    "visit_id": visit.visit_id,
                    "patient_id": visit.patient_id,
                    "site_id": visit.site_id,
                    "visit_number": visit.visit_number,
                    "actual_date": visit.actual_date.isoformat() if visit.actual_date else None,
                    "dose_administered_mg": visit.dose_administered_mg,
                }
                existing_visits[visit.visit_id] = v_dict
                existing_visits_by_key[(visit.patient_id, visit.visit_number)] = v_dict

    return existing_sites, existing_patients, existing_visits, existing_visits_by_key


def _get_protocol_maps():
    """Return (visit_map, protocol_dose_mg) from the protocol config."""
    from core.protocol import get_protocol
    proto = get_protocol()
    visit_map = {v.visit_number: v for v in proto.visits}
    dose_mg = proto.dose_rules[0].dose_mg if proto.dose_rules else 200.0
    return visit_map, dose_mg


def _report_to_dict(r: ValidationReport) -> dict:
    return {
        "layout": r.layout,
        "row_count": r.row_count,
        "filename": r.filename,
        "sites": {
            "new": r.sites_new,
            "existing_same": r.sites_existing_same,
            "existing_changed": r.sites_existing_diff,
        },
        "patients": {
            "new": r.patients_new,
            "existing_same": r.patients_existing_same,
            "existing_changed": r.patients_existing_diff,
        },
        "visits": {
            "new": r.visits_new,
            "existing_same": r.visits_existing_same,
            "existing_changed": r.visits_existing_diff,
        },
        "ignored_columns": r.ignored_columns,
        "server_computed_found": r.server_computed_found,
        "warnings": r.warnings,
        "errors": [
            {
                "row": e.row,
                "column": e.column,
                "value": e.value,
                "reason": e.reason,
                "blocking": e.blocking,
            }
            for e in r.errors
        ],
        "total_error_count": r.total_error_count,
        "rows_skipped_with_errors": r.rows_skipped_with_errors,
        "blocking": r.blocking,
    }


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("/validate")
async def validate_import(
    file: UploadFile = File(...),
    source_label: str = Form(default=""),
    user: dict = Depends(_require_admin),
):
    """
    Dry-run validation. Parses and validates the file, returns a full report.
    Writes NOTHING to the database.
    Returns an import_token (signed JWT) tied to the file hash, valid 30 min.
    """
    ds = _require_supabase()

    # Trigger background version check
    asyncio.ensure_future(_maybe_reload_if_stale())

    # Read file into memory
    data = await file.read()

    # Deployed row-count cap (soft, checked after parse)
    # Hard limit MAX_ROWS_HARD is enforced inside parse_file itself

    # Run parse + validate in threadpool (CPU-bound)
    loop = asyncio.get_running_loop()

    filename = file.filename or "upload"
    try:
        parse_result = await loop.run_in_executor(
            None, parse_file, filename, data
        )
    except ParseError as e:
        raise HTTPException(status_code=422, detail={"code": e.code, "message": e.message})

    # Deployed cap check (after parse so we know actual count)
    if parse_result.raw_row_count > _MAX_IMPORT_ROWS:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "row_cap_exceeded",
                "message": (
                    f"This deployment accepts at most {_MAX_IMPORT_ROWS:,} rows per import "
                    f"(file has {parse_result.raw_row_count:,}). "
                    "Split the file or contact the administrator."
                ),
            },
        )

    existing_sites, existing_patients, existing_visits, existing_visits_by_key = (
        _get_existing_state(ds)
    )
    protocol_visit_map, protocol_dose_mg = _get_protocol_maps()
    today = date.today()

    report = await loop.run_in_executor(
        None,
        validate,
        parse_result,
        existing_sites,
        existing_patients,
        existing_visits,
        existing_visits_by_key,
        protocol_visit_map,
        protocol_dose_mg,
        today,
    )

    import_token = _make_import_token(
        parse_result.file_sha256,
        parse_result.raw_row_count,
        parse_result.layout,
    )

    return {
        **_report_to_dict(report),
        "import_token": import_token,
        "file_sha256": parse_result.file_sha256,
    }


class CommitRequest(BaseModel):
    on_conflict: str = "skip"   # 'skip' | 'update'
    source_label: str = ""


@router.post("/commit")
async def commit_import_endpoint(
    file: UploadFile = File(...),
    import_token: str = Form(...),
    on_conflict: str = Form(default="skip"),
    source_label: str = Form(default=""),
    user: dict = Depends(_require_admin),
):
    """
    Commit a validated import.

    The client re-uploads the file along with the import_token from validate.
    The server re-validates (token expiry + file hash check + full re-validation)
    before writing anything. No server-side state is required.
    """
    ds = _require_supabase()

    if on_conflict not in ("skip", "update"):
        raise HTTPException(status_code=422, detail="on_conflict must be 'skip' or 'update'.")

    token_payload = _decode_import_token(import_token)

    # Read file
    data = await file.read()

    filename = file.filename or "upload"

    loop = asyncio.get_running_loop()

    try:
        parse_result = await loop.run_in_executor(
            None, parse_file, filename, data
        )
    except ParseError as e:
        raise HTTPException(status_code=422, detail={"code": e.code, "message": e.message})

    # Verify file hash matches the token (prevents token reuse with different file)
    if parse_result.file_sha256 != token_payload.get("file_sha256"):
        raise HTTPException(
            status_code=400,
            detail="File does not match the import token. "
                   "Please re-run validation on this file."
        )

    # Row-cap check
    if parse_result.raw_row_count > _MAX_IMPORT_ROWS:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "row_cap_exceeded",
                "message": f"File has {parse_result.raw_row_count:,} rows; max is {_MAX_IMPORT_ROWS:,}.",
            },
        )

    # Full re-validation (never trust the earlier step alone)
    existing_sites, existing_patients, existing_visits, existing_visits_by_key = (
        _get_existing_state(ds)
    )
    protocol_visit_map, protocol_dose_mg = _get_protocol_maps()
    today = date.today()

    report = await loop.run_in_executor(
        None,
        validate,
        parse_result,
        existing_sites,
        existing_patients,
        existing_visits,
        existing_visits_by_key,
        protocol_visit_map,
        protocol_dose_mg,
        today,
    )

    if report.blocking:
        # blocking=True only when validated_rows is empty (nothing importable at all)
        raise HTTPException(
            status_code=422,
            detail={
                "code": "validation_failed",
                "message": f"{report.total_error_count} blocking error(s) found and no valid rows remain — nothing to import.",
                "errors": _report_to_dict(report)["errors"],
            },
        )

    # Run commit in threadpool (DB-bound)
    from db.supabase_client import get_supabase_client
    sb = get_supabase_client()
    if not sb:
        raise HTTPException(status_code=503, detail="Supabase client unavailable.")

    result: CommitResult = await loop.run_in_executor(
        None,
        commit_import,
        sb,
        report,
        on_conflict,
        source_label,
        user.get("email", "unknown"),
        ds,
    )

    if result.status == "failed":
        raise HTTPException(
            status_code=500,
            detail={
                "code": "commit_failed",
                "message": result.error or "Unknown error during commit.",
                "note": (
                    "Some rows may have been written before the error. "
                    "Re-uploading with on_conflict='skip' is safe — "
                    "all writes are upsert-by-primary-key and will not duplicate."
                ),
            },
        )

    return {
        "import_id": result.import_id,
        "status": result.status,
        "sites_written": result.sites_written,
        "patients_written": result.patients_written,
        "visits_written": result.visits_written,
        "visits_updated": result.visits_updated,
        "visits_skipped": result.visits_skipped,
        "deviations_added": result.deviations_added,
        "deviations_removed": result.deviations_removed,
        "affected_site_ids": result.affected_site_ids,
        "tier_changes": result.tier_changes,
        "stale_capa_site_ids": result.stale_capa_site_ids,
        "rows_skipped_with_errors": report.rows_skipped_with_errors,
        "rows_imported": len(report.validated_rows),
        "recency_window_note": (
            "Risk scores use a fixed reference date of 2024-09-01. "
            "Deviations dated >= 2024-08-02 receive the recency bonus. "
            "This is the same anchor used for all existing trial data."
        ),
    }


@router.get("/template")
async def download_template(
    format: str = "csv",
    user: dict = Depends(_require_admin),
):
    """
    Download a CSV or XLSX template.
    Works in both mock and Supabase modes.
    """
    if format not in ("csv", "xlsx"):
        raise HTTPException(status_code=422, detail="format must be 'csv' or 'xlsx'.")

    loop = asyncio.get_event_loop()

    if format == "csv":
        content = await loop.run_in_executor(None, generate_csv_template)
        return Response(
            content=content,
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": "attachment; filename=trialguard_import_template.csv"},
        )
    else:
        try:
            content = await loop.run_in_executor(None, generate_xlsx_template)
        except RuntimeError as e:
            raise HTTPException(status_code=500, detail=str(e))
        return Response(
            content=content,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=trialguard_import_template.xlsx"},
        )


@router.get("")
async def list_imports(
    limit: int = 20,
    offset: int = 0,
    user: dict = Depends(_require_admin),
):
    """Return paginated import history from data_imports table."""
    _require_supabase()

    from db.supabase_client import get_supabase_client
    sb = get_supabase_client()
    if not sb:
        raise HTTPException(status_code=503, detail="Supabase client unavailable.")

    asyncio.ensure_future(_maybe_reload_if_stale())

    res = (sb.table("data_imports")
           .select("*")
           .order("created_at", desc=True)
           .range(offset, offset + limit - 1)
           .execute())

    return {"imports": res.data or [], "limit": limit, "offset": offset}


@router.get("/columns")
async def get_column_spec(
    user: dict = Depends(_require_admin),
):
    """Return the column specification for frontend help text."""
    return {
        "columns": [
            {
                "name": c.name,
                "required": c.required,
                "required_for_new_site": c.required_for_new_site,
                "dtype": c.dtype,
                "description": c.description,
                "example": c.example,
                "max_length": c.max_length,
            }
            for c in COLUMNS
        ]
    }


@router.get("/{import_id}")
async def get_import(
    import_id: str,
    user: dict = Depends(_require_admin),
):
    """Return a single import record."""
    _require_supabase()

    from db.supabase_client import get_supabase_client
    sb = get_supabase_client()
    if not sb:
        raise HTTPException(status_code=503, detail="Supabase client unavailable.")

    res = (sb.table("data_imports")
           .select("*")
           .eq("import_id", import_id)
           .limit(1)
           .execute())

    if not res.data:
        raise HTTPException(status_code=404, detail=f"Import '{import_id}' not found.")

    return res.data[0]
