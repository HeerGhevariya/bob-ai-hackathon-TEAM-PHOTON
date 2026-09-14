"""
api.py — FastAPI REST API for the TrialGuard AI Dashboard

Serves the React frontend with clinical trial data endpoints.
Data comes from the DataSource adapter — which transparently uses
either in-memory synthetic data (MockDataSource) or Supabase
(SupabaseDataSource) depending on environment configuration.
"""

import json
from collections import Counter, defaultdict
from datetime import date
from typing import Optional

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse

from core.data_source import get_data_source


# ─── Initialize via DataSource Adapter ────────────────────────────

_ds = get_data_source()
_protocol = _ds.get_protocol()


# ─── FastAPI App ──────────────────────────────────────────────────

app = FastAPI(
    title="TrialGuard AI API",
    description="Clinical Trial Risk Monitor & Protocol Deviation Detector",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Helper: serialize dataclasses to dicts ───────────────────────

def _dev_to_dict(d) -> dict:
    return {
        "deviation_id": d.deviation_id,
        "patient_id": d.patient_id,
        "site_id": d.site_id,
        "visit_id": d.visit_id,
        "visit_name": d.visit_name,
        "deviation_type": d.deviation_type.value,
        "description": d.description,
        "expected_value": d.expected_value,
        "actual_value": d.actual_value,
        "detected_date": d.detected_date.isoformat() if d.detected_date else None,
        "protocol_reference": d.protocol_reference,
        "severity": d.severity,
    }


def _profile_to_dict(rp) -> dict:
    return {
        "site_id": rp.site_id,
        "site_name": rp.site_name,
        "risk_score": rp.risk_score,
        "risk_tier": rp.risk_tier.value,
        "trend_direction": rp.trend_direction.value,
        "total_deviations": rp.total_deviations,
        "major_count": rp.major_count,
        "minor_count": rp.minor_count,
        "administrative_count": rp.administrative_count,
        "deviation_types": rp.deviation_types,
        "patients_affected": rp.patients_affected,
        "total_patients": rp.total_patients,
        "recent_deviations_30d": rp.recent_deviations_30d,
        "repeat_deviation_types": rp.repeat_deviation_types,
        "top_risk_factors": [
            {
                "factor_name": rf.factor_name,
                "description": rf.description,
                "contribution": rf.contribution,
            }
            for rf in rp.top_risk_factors
        ],
    }


# ─── API Endpoints ────────────────────────────────────────────────

@app.get("/api/trial/summary")
def trial_summary():
    """Get trial-wide statistics and overview."""
    all_deviations = _ds.get_all_deviations()
    risk_profiles = _ds.get_risk_profiles()
    stats = _ds.get_trial_statistics()

    severity_counts = Counter(d.severity for d in all_deviations)
    type_counts = Counter(d.deviation_type.value for d in all_deviations)
    tier_counts = Counter(rp.risk_tier.value for rp in risk_profiles)

    return {
        "trial": {
            "protocol_id": _protocol.protocol_id,
            "protocol_title": _protocol.protocol_title,
            "phase": _protocol.phase,
            "indication": _protocol.indication,
        },
        "overview": {
            "total_sites": stats["total_sites"],
            "total_patients": stats["total_patients"],
            "total_visits": stats["total_visits"],
            "countries": stats["countries"],
        },
        "deviations": {
            "total": len(all_deviations),
            "by_severity": dict(severity_counts),
            "by_type": dict(type_counts),
        },
        "risk_distribution": dict(tier_counts),
        "alerts": {
            "critical_sites": [
                {"site_id": rp.site_id, "site_name": rp.site_name, "risk_score": rp.risk_score}
                for rp in risk_profiles if rp.risk_tier.value == "critical"
            ],
            "rising_trends": sum(1 for rp in risk_profiles if rp.trend_direction.value == "rising"),
        },
    }


@app.get("/api/sites")
def list_sites(
    sort_by: str = Query("risk_score", enum=["risk_score", "site_id", "total_deviations"]),
    tier: Optional[str] = Query(None, enum=["critical", "high", "medium", "low"]),
    limit: int = Query(50, ge=1, le=300),
    offset: int = Query(0, ge=0),
):
    """List all sites with risk profiles, sortable and filterable."""
    profiles = list(_ds.get_risk_profiles())

    if tier:
        profiles = [rp for rp in profiles if rp.risk_tier.value == tier]

    if sort_by == "site_id":
        profiles = sorted(profiles, key=lambda rp: rp.site_id)
    elif sort_by == "total_deviations":
        profiles = sorted(profiles, key=lambda rp: rp.total_deviations, reverse=True)
    # Default is already sorted by risk_score desc

    total = len(profiles)
    profiles = profiles[offset:offset + limit]

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "sites": [_profile_to_dict(rp) for rp in profiles],
    }


@app.get("/api/sites/{site_id}")
def get_site(site_id: str):
    """Get detailed profile for a specific site."""
    site = _ds.get_site(site_id)
    if not site:
        raise HTTPException(status_code=404, detail=f"Site '{site_id}' not found")

    rp = _ds.get_risk_profile(site_id)
    devs = _ds.get_deviations_for_site(site_id)

    return {
        "site": {
            "site_id": site.site_id,
            "site_name": site.site_name,
            "city": site.city,
            "country": site.country,
            "principal_investigator": site.principal_investigator,
            "total_patients": len(site.patients),
        },
        "risk_profile": _profile_to_dict(rp) if rp else None,
        "deviations": [_dev_to_dict(d) for d in devs],
        "patients": [
            {
                "patient_id": p.patient_id,
                "age": p.age,
                "sex": p.sex,
                "enrollment_date": p.enrollment_date.isoformat(),
                "total_visits": len(p.visits),
            }
            for p in site.patients
        ],
    }


@app.get("/api/deviations")
def list_deviations(
    site_id: Optional[str] = None,
    severity: Optional[str] = Query(None, enum=["major", "minor", "administrative"]),
    deviation_type: Optional[str] = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """List deviations with optional filtering."""
    if site_id:
        devs = _ds.get_deviations_for_site(site_id)
    else:
        devs = _ds.get_all_deviations()

    if severity:
        devs = [d for d in devs if d.severity == severity]
    if deviation_type:
        devs = [d for d in devs if d.deviation_type.value == deviation_type]

    total = len(devs)
    devs = devs[offset:offset + limit]

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "deviations": [_dev_to_dict(d) for d in devs],
    }


@app.get("/api/deviations/{deviation_id}")
def get_deviation(deviation_id: str):
    """Get details for a specific deviation."""
    all_devs = _ds.get_all_deviations()
    dev = next((d for d in all_devs if d.deviation_id == deviation_id), None)
    if not dev:
        raise HTTPException(status_code=404, detail=f"Deviation '{deviation_id}' not found")

    return _dev_to_dict(dev)


@app.get("/api/capa/{site_id}")
def generate_capa(site_id: str):
    """Generate a CAPA report for a specific site."""
    site = _ds.get_site(site_id)
    if not site:
        raise HTTPException(status_code=404, detail=f"Site '{site_id}' not found")

    devs = _ds.get_deviations_for_site(site_id)
    rp = _ds.get_risk_profile(site_id)

    report = _ds.generate_capa_report(
        site_id=site_id,
        site_name=site.site_name,
        deviations=devs,
        risk_profile=rp,
    )

    return {
        "report_id": report.report_id,
        "site_id": report.site_id,
        "site_name": report.site_name,
        "generated_date": report.generated_date.isoformat(),
        "executive_summary": report.executive_summary,
        "total_findings": report.total_findings,
        "severity_breakdown": report.severity_breakdown,
        "ich_classification": report.ich_classification,
        "overall_risk_level": report.overall_risk_level,
        "root_cause_analysis": report.root_cause_analysis,
        "contributing_factors": report.contributing_factors,
        "corrective_actions": [
            {
                "action_id": a.action_id,
                "action_type": a.action_type,
                "description": a.description,
                "responsible_party": a.responsible_party,
                "deadline": a.deadline,
                "priority": a.priority,
                "status": a.status,
            }
            for a in report.corrective_actions
        ],
        "preventive_actions": [
            {
                "action_id": a.action_id,
                "action_type": a.action_type,
                "description": a.description,
                "responsible_party": a.responsible_party,
                "deadline": a.deadline,
                "priority": a.priority,
                "status": a.status,
            }
            for a in report.preventive_actions
        ],
        "timeline_summary": report.timeline_summary,
        "next_review_date": report.next_review_date,
        "full_report_markdown": report.full_report_markdown,
    }


@app.get("/api/trends")
def get_trends():
    """Get time-series trend data for charts."""
    all_deviations = _ds.get_all_deviations()
    risk_profiles = _ds.get_risk_profiles()

    # Group deviations by month
    monthly = defaultdict(lambda: {"major": 0, "minor": 0, "administrative": 0, "total": 0})

    for d in all_deviations:
        if d.detected_date:
            month_key = d.detected_date.strftime("%Y-%m")
            monthly[month_key][d.severity] += 1
            monthly[month_key]["total"] += 1

    # Sort by month
    sorted_months = sorted(monthly.items())

    # Risk tier distribution
    tier_data = Counter(rp.risk_tier.value for rp in risk_profiles)

    # Deviation type distribution
    type_data = Counter(d.deviation_type.value for d in all_deviations)

    return {
        "monthly_deviations": [
            {"month": month, **counts}
            for month, counts in sorted_months
        ],
        "risk_tier_distribution": [
            {"tier": tier, "count": count}
            for tier, count in [
                ("critical", tier_data.get("critical", 0)),
                ("high", tier_data.get("high", 0)),
                ("medium", tier_data.get("medium", 0)),
                ("low", tier_data.get("low", 0)),
            ]
        ],
        "deviation_type_distribution": [
            {"type": dtype.replace("_", " ").title(), "count": count}
            for dtype, count in type_data.most_common()
        ],
        "severity_distribution": [
            {"severity": sev, "count": count}
            for sev, count in [
                ("major", sum(1 for d in all_deviations if d.severity == "major")),
                ("minor", sum(1 for d in all_deviations if d.severity == "minor")),
                ("administrative", sum(1 for d in all_deviations if d.severity == "administrative")),
            ]
        ],
    }


@app.get("/api/data-source")
def get_data_source_info():
    """Get information about the current data source (mock vs Supabase)."""
    return {
        "type": type(_ds).__name__,
        "description": (
            "Supabase (PostgreSQL)" if type(_ds).__name__ == "SupabaseDataSource"
            else "In-memory synthetic data (MockDataSource)"
        ),
    }


@app.get("/api/export/fhir/{site_id}")
def export_fhir_bundle(site_id: str):
    """
    Export a site's data as a FHIR R4 Bundle.

    Returns all patients, encounters, medication records, and detected
    deviations in HL7 FHIR R4 format — the industry standard for
    clinical data exchange.

    This demonstrates that TrialGuard AI data is interoperable with
    real EHR/EDC systems (e.g., Epic, Cerner, Medidata Rave).
    """
    site = _ds.get_site(site_id)
    if not site:
        raise HTTPException(status_code=404, detail=f"Site '{site_id}' not found")

    devs = _ds.get_deviations_for_site(site_id)

    from core.fhir_adapter import site_to_fhir_bundle
    bundle = site_to_fhir_bundle(site, deviations=devs)

    return bundle
