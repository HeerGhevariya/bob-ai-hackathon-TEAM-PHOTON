"""
seed.py — Populate Supabase with Synthetic Clinical Trial Data

Generates data using the existing synthetic data engine, runs the full
analysis pipeline (detect → classify → score), and inserts everything
into Supabase tables.

Usage:
    cd src/backend
    python db/seed.py

Requires SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in .env
"""

import os
import sys
import json
from datetime import date

# Add backend to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

from supabase import create_client


def main():
    print("🌱 TrialGuard AI — Supabase Seed Script")
    print("=" * 50)

    # Connect to Supabase
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY")

    if not url or not key:
        print("❌ Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in .env")
        print("   Copy src/.env.example to src/.env and fill in your Supabase credentials.")
        sys.exit(1)

    client = create_client(url, key)
    print(f"✅ Connected to Supabase: {url[:40]}...")

    # Generate synthetic data
    print("\n📊 Generating synthetic trial data...")
    from core.protocol import get_protocol
    from core.synthetic_data import generate_trial_data, get_trial_statistics
    from core.deviation_detector import DeviationDetector
    from core.severity_classifier import SeverityClassifier
    from core.risk_scorer import RiskScorer

    sites, protocol = generate_trial_data(seed=42)
    stats = get_trial_statistics(sites)
    print(f"   Sites: {stats['total_sites']}, Patients: {stats['total_patients']}, Visits: {stats['total_visits']}")

    # Run analysis pipeline
    print("\n🔍 Running deviation detection pipeline...")
    detector = DeviationDetector(protocol)
    classifier = SeverityClassifier()
    all_deviations = classifier.classify_all(detector.detect_all(sites))
    print(f"   Deviations detected: {len(all_deviations)}")

    print("\n📈 Running risk scoring pipeline...")
    scorer = RiskScorer(reference_date=date(2024, 9, 1))
    site_info = {
        s.site_id: {"name": s.site_name, "total_patients": len(s.patients)}
        for s in sites
    }
    risk_profiles = scorer.score_all_sites(all_deviations, site_info)
    print(f"   Risk profiles computed: {len(risk_profiles)}")

    # Clear existing data (order matters due to foreign keys)
    print("\n🗑️  Clearing existing data...")
    for table in ["capa_reports", "site_risk_profiles", "deviations", "patient_visits", "patients", "sites"]:
        try:
            client.table(table).delete().neq("site_id", "__never_match__").execute()
            print(f"   Cleared {table}")
        except Exception as e:
            print(f"   ⚠️  Could not clear {table}: {e}")

    # Insert sites
    print("\n📥 Inserting sites...")
    site_rows = [
        {
            "site_id": s.site_id,
            "site_name": s.site_name,
            "city": s.city,
            "country": s.country,
            "principal_investigator": s.principal_investigator,
            "is_problem_site": s.is_problem_site,
        }
        for s in sites
    ]
    _batch_insert(client, "sites", site_rows)
    print(f"   ✅ {len(site_rows)} sites")

    # Insert patients
    print("📥 Inserting patients...")
    patient_rows = []
    for site in sites:
        for p in site.patients:
            patient_rows.append({
                "patient_id": p.patient_id,
                "site_id": p.site_id,
                "enrollment_date": p.enrollment_date.isoformat(),
                "age": p.age,
                "sex": p.sex,
            })
    _batch_insert(client, "patients", patient_rows)
    print(f"   ✅ {len(patient_rows)} patients")

    # Insert visits
    print("📥 Inserting patient visits...")
    visit_rows = []
    for site in sites:
        for p in site.patients:
            for v in p.visits:
                visit_rows.append({
                    "visit_id": v.visit_id,
                    "patient_id": v.patient_id,
                    "site_id": v.site_id,
                    "visit_number": v.visit_number,
                    "visit_name": v.visit_name,
                    "scheduled_date": v.scheduled_date.isoformat(),
                    "actual_date": v.actual_date.isoformat() if v.actual_date else None,
                    "protocol_target_day": v.protocol_target_day,
                    "actual_day": v.actual_day,
                    "dose_administered_mg": v.dose_administered_mg,
                    "protocol_dose_mg": v.protocol_dose_mg,
                    "assessments_completed": v.assessments_completed,
                    "assessments_required": v.assessments_required,
                    "active_medications": v.active_medications,
                    "notes": v.notes if hasattr(v, "notes") else "",
                })
    _batch_insert(client, "patient_visits", visit_rows)
    print(f"   ✅ {len(visit_rows)} visits")

    # Insert deviations
    print("📥 Inserting deviations...")
    dev_rows = []
    for d in all_deviations:
        dev_rows.append({
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
            "raw_data": _safe_json(d.raw_data),
        })
    _batch_insert(client, "deviations", dev_rows)
    print(f"   ✅ {len(dev_rows)} deviations")

    # Insert risk profiles
    print("📥 Inserting risk profiles...")
    profile_rows = []
    for rp in risk_profiles:
        profile_rows.append({
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
        })
    _batch_insert(client, "site_risk_profiles", profile_rows)
    print(f"   ✅ {len(profile_rows)} risk profiles")

    # ─── Seed Demo Users ────────────────────────────────────────────
    print("\n👤 Seeding demo user accounts...")
    
    def _hash_pw(plain: str) -> str:
        # Force sha256 to guarantee compatibility with Vercel serverless
        # environments where the bcrypt C-extension fails to load.
        import hashlib
        return hashlib.sha256(plain.encode("utf-8")).hexdigest()

    demo_users = [
        {
            "email": "demo@trialgard.ai",
            "full_name": "Demo User",
            "role": "admin",
            "password_hash": _hash_pw("Demo@2026"),
        },
        {
            "email": "judge@trialgard.ai",
            "full_name": "Judge Evaluator",
            "role": "judge",
            "password_hash": _hash_pw("Demo@2026"),
        },
        {
            "email": "reviewer@trialgard.ai",
            "full_name": "Clinical Reviewer",
            "role": "reviewer",
            "password_hash": _hash_pw("Demo@2026"),
        },
        {
            "email": "admin@trialgard.ai",
            "full_name": "Trial Administrator",
            "role": "admin",
            "password_hash": _hash_pw("Demo@2026"),
        },
    ]

    for user in demo_users:
        try:
            # Upsert by email so re-running seed doesn't fail on duplicate
            client.table("users").upsert(user, on_conflict="email").execute()
            print(f"   ✅ {user['role']}: {user['email']}")
        except Exception as e:
            print(f"   ⚠️  Could not seed user {user['email']}: {e}")

    print("\n" + "=" * 50)
    print("🎉 Seed complete! All data loaded into Supabase.")
    print(f"   Total: {len(site_rows)} sites, {len(patient_rows)} patients, "
          f"{len(visit_rows)} visits, {len(dev_rows)} deviations, "
          f"{len(profile_rows)} risk profiles")


def _batch_insert(client, table: str, rows: list[dict], batch_size: int = 500):
    """Insert rows in batches to avoid Supabase payload limits."""
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]
        try:
            client.table(table).insert(batch).execute()
        except Exception as e:
            print(f"   ❌ Error inserting batch {i // batch_size + 1} into {table}: {e}")
            # Try individual inserts for failed batch
            for row in batch:
                try:
                    client.table(table).insert(row).execute()
                except Exception as row_err:
                    print(f"      ⚠️  Failed row: {row.get('site_id') or row.get('patient_id') or row.get('deviation_id', '?')}: {row_err}")


def _safe_json(data: dict) -> dict:
    """Ensure all values in raw_data are JSON-serializable."""
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


if __name__ == "__main__":
    main()
