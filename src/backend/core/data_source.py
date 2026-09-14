"""
data_source.py — Data Source Adapter Layer

Provides a clean interface boundary between data storage and the analysis engine:

    [Data Source] → [Ingestion Adapter] → [Deviation Engine]

Two implementations:
    - MockDataSource: Uses the in-memory synthetic data generator (default)
    - SupabaseDataSource: Reads/writes from Supabase (when configured)

The application checks SUPABASE_URL at startup:
    - If set → SupabaseDataSource (persistent, production-like)
    - If not → MockDataSource (in-memory, zero-config demo)

This design means swapping from mock to a live EDC/EHR feed requires only
adding a new DataSource implementation — the detection, scoring, and reporting
logic never changes.
"""

from abc import ABC, abstractmethod
from collections import Counter
from datetime import date
from typing import Optional

from .protocol import ProtocolSpecification, get_protocol
from .synthetic_data import (
    Patient, PatientVisit, Site,
    generate_trial_data, get_trial_statistics,
)
from .deviation_detector import Deviation, DeviationDetector
from .severity_classifier import SeverityClassifier
from .risk_scorer import RiskScorer, SiteRiskProfile
from .capa_generator import CapaGenerator, CapaReport


class DataSource(ABC):
    """
    Abstract interface for clinical trial data access.

    Any data source — synthetic, Supabase, a real EDC API — implements
    this interface. The analysis engine and API layer only depend on
    this abstraction.
    """

    @abstractmethod
    def get_protocol(self) -> ProtocolSpecification:
        """Return the protocol specification."""
        ...

    @abstractmethod
    def get_sites(self) -> list[Site]:
        """Return all trial sites with patients and visits loaded."""
        ...

    @abstractmethod
    def get_site(self, site_id: str) -> Optional[Site]:
        """Return a single site by ID, or None."""
        ...

    @abstractmethod
    def get_all_deviations(self) -> list[Deviation]:
        """Return all classified deviations across the trial."""
        ...

    @abstractmethod
    def get_deviations_for_site(self, site_id: str) -> list[Deviation]:
        """Return deviations for a specific site."""
        ...

    @abstractmethod
    def get_risk_profiles(self) -> list[SiteRiskProfile]:
        """Return risk profiles for all sites, sorted by score descending."""
        ...

    @abstractmethod
    def get_risk_profile(self, site_id: str) -> Optional[SiteRiskProfile]:
        """Return risk profile for a specific site."""
        ...

    @abstractmethod
    def get_site_info(self) -> dict[str, dict]:
        """Return site_id -> {name, total_patients} mapping."""
        ...

    @abstractmethod
    def get_trial_statistics(self) -> dict:
        """Return trial-wide summary statistics."""
        ...

    @abstractmethod
    def generate_capa_report(
        self, site_id: str, site_name: str,
        deviations: list[Deviation],
        risk_profile: Optional[SiteRiskProfile] = None
    ) -> CapaReport:
        """Generate a CAPA report for a site."""
        ...


# ─── MockDataSource ──────────────────────────────────────────────────────────

class MockDataSource(DataSource):
    """
    In-memory data source using the synthetic data generator.

    This is the default when no external database is configured.
    All data is generated at initialization and held in memory.
    """

    def __init__(self, seed: int = 42, reference_date: Optional[date] = None):
        print("📊 Initializing MockDataSource (in-memory synthetic data)...")
        self._protocol = get_protocol()
        self._sites, _ = generate_trial_data(seed=seed)
        self._site_map = {s.site_id: s for s in self._sites}

        # Run the full analysis pipeline
        detector = DeviationDetector(self._protocol)
        classifier = SeverityClassifier()
        self._all_deviations = classifier.classify_all(detector.detect_all(self._sites))
        self._deviation_map = {d.deviation_id: d for d in self._all_deviations}

        scorer = RiskScorer(reference_date=reference_date or date(2024, 9, 1))
        self._site_info = {
            s.site_id: {"name": s.site_name, "total_patients": len(s.patients)}
            for s in self._sites
        }
        self._risk_profiles = scorer.score_all_sites(self._all_deviations, self._site_info)
        self._risk_profile_map = {rp.site_id: rp for rp in self._risk_profiles}

        self._capa_gen = CapaGenerator()

        stats = get_trial_statistics(self._sites)
        print(
            f"   ✅ Loaded {stats['total_sites']} sites, "
            f"{stats['total_patients']} patients, "
            f"{stats['total_visits']} visits, "
            f"{len(self._all_deviations)} deviations"
        )

    def get_protocol(self) -> ProtocolSpecification:
        return self._protocol

    def get_sites(self) -> list[Site]:
        return self._sites

    def get_site(self, site_id: str) -> Optional[Site]:
        return self._site_map.get(site_id)

    def get_all_deviations(self) -> list[Deviation]:
        return self._all_deviations

    def get_deviations_for_site(self, site_id: str) -> list[Deviation]:
        return [d for d in self._all_deviations if d.site_id == site_id]

    def get_risk_profiles(self) -> list[SiteRiskProfile]:
        return self._risk_profiles

    def get_risk_profile(self, site_id: str) -> Optional[SiteRiskProfile]:
        return self._risk_profile_map.get(site_id)

    def get_site_info(self) -> dict[str, dict]:
        return self._site_info

    def get_trial_statistics(self) -> dict:
        return get_trial_statistics(self._sites)

    def generate_capa_report(
        self, site_id: str, site_name: str,
        deviations: list[Deviation],
        risk_profile: Optional[SiteRiskProfile] = None
    ) -> CapaReport:
        return self._capa_gen.generate_site_report(
            site_id=site_id,
            site_name=site_name,
            deviations=deviations,
            risk_profile=risk_profile,
        )


# ─── SupabaseDataSource ─────────────────────────────────────────────────────

class SupabaseDataSource(DataSource):
    """
    Persistent data source backed by Supabase (PostgreSQL).

    Reads pre-seeded clinical trial data from Supabase tables.
    The seed script (db/seed.py) must be run once to populate the database.

    This demonstrates the production-ready architecture: swap from
    MockDataSource to SupabaseDataSource with zero changes to the
    detection, scoring, or reporting logic.
    """

    def __init__(self):
        from db.supabase_client import get_supabase_client
        print("🗄️  Initializing SupabaseDataSource (Supabase PostgreSQL)...")
        self._client = get_supabase_client()
        if not self._client:
            raise RuntimeError(
                "Supabase client could not be initialized. "
                "Check SUPABASE_URL and SUPABASE_ANON_KEY in .env"
            )
        self._protocol = get_protocol()
        self._capa_gen = CapaGenerator()

        # Cache for performance (loaded once, like the mock)
        self._sites_cache = None
        self._deviations_cache = None
        self._profiles_cache = None
        self._load_all_data()

    def _load_all_data(self):
        """Load all data from Supabase into memory cache."""
        # Load sites
        sites_data = self._client.table("sites").select("*").execute().data
        patients_data = self._client.table("patients").select("*").execute().data
        visits_data = self._client.table("patient_visits").select("*").execute().data

        # Build patient map
        patient_map: dict[str, list] = {}
        for p in patients_data:
            patient_map.setdefault(p["site_id"], []).append(p)

        # Build visit map
        visit_map: dict[str, list] = {}
        for v in visits_data:
            visit_map.setdefault(v["patient_id"], []).append(v)

        # Assemble Site objects
        self._sites_cache = []
        for s in sites_data:
            patients = []
            for p_data in patient_map.get(s["site_id"], []):
                visits = []
                for v_data in visit_map.get(p_data["patient_id"], []):
                    visit = PatientVisit(
                        visit_id=v_data["visit_id"],
                        patient_id=v_data["patient_id"],
                        site_id=v_data["site_id"],
                        visit_number=v_data["visit_number"],
                        visit_name=v_data["visit_name"],
                        scheduled_date=date.fromisoformat(v_data["scheduled_date"]),
                        actual_date=date.fromisoformat(v_data["actual_date"]) if v_data["actual_date"] else None,
                        protocol_target_day=v_data["protocol_target_day"],
                        actual_day=v_data["actual_day"],
                        dose_administered_mg=v_data["dose_administered_mg"],
                        protocol_dose_mg=v_data["protocol_dose_mg"],
                        assessments_completed=v_data.get("assessments_completed", []) or [],
                        assessments_required=v_data.get("assessments_required", []) or [],
                        active_medications=v_data.get("active_medications", []) or [],
                        notes=v_data.get("notes", ""),
                    )
                    visits.append(visit)

                patient = Patient(
                    patient_id=p_data["patient_id"],
                    site_id=p_data["site_id"],
                    enrollment_date=date.fromisoformat(p_data["enrollment_date"]),
                    age=p_data["age"],
                    sex=p_data["sex"],
                    visits=visits,
                )
                patients.append(patient)

            site = Site(
                site_id=s["site_id"],
                site_name=s["site_name"],
                city=s["city"],
                country=s["country"],
                principal_investigator=s["principal_investigator"],
                patients=patients,
                is_problem_site=s.get("is_problem_site", False),
            )
            self._sites_cache.append(site)

        self._site_map = {s.site_id: s for s in self._sites_cache}

        # Load deviations
        devs_data = self._client.table("deviations").select("*").execute().data
        self._deviations_cache = []
        for d in devs_data:
            from .protocol import DeviationType
            dev = Deviation(
                deviation_id=d["deviation_id"],
                patient_id=d["patient_id"],
                site_id=d["site_id"],
                visit_id=d["visit_id"],
                visit_name=d["visit_name"],
                deviation_type=DeviationType(d["deviation_type"]),
                description=d["description"],
                expected_value=d["expected_value"],
                actual_value=d["actual_value"],
                detected_date=date.fromisoformat(d["detected_date"]) if d["detected_date"] else None,
                protocol_reference=d["protocol_reference"],
                severity=d["severity"],
                raw_data=d.get("raw_data", {}),
            )
            self._deviations_cache.append(dev)

        # Load risk profiles
        profiles_data = self._client.table("site_risk_profiles").select("*").order("risk_score", desc=True).execute().data
        from .protocol import RiskTier, TrendDirection
        from .risk_scorer import RiskFactor
        self._profiles_cache = []
        for rp in profiles_data:
            factors = []
            for rf_data in (rp.get("top_risk_factors") or []):
                factors.append(RiskFactor(
                    factor_name=rf_data.get("factor_name", ""),
                    description=rf_data.get("description", ""),
                    contribution=rf_data.get("contribution", 0),
                ))
            profile = SiteRiskProfile(
                site_id=rp["site_id"],
                site_name=rp["site_name"],
                risk_score=rp["risk_score"],
                risk_tier=RiskTier(rp["risk_tier"]),
                trend_direction=TrendDirection(rp["trend_direction"]),
                total_deviations=rp["total_deviations"],
                major_count=rp["major_count"],
                minor_count=rp["minor_count"],
                administrative_count=rp["administrative_count"],
                top_risk_factors=factors,
                deviation_types=rp.get("deviation_types", {}),
                patients_affected=rp.get("patients_affected", 0),
                total_patients=rp.get("total_patients", 0),
                recent_deviations_30d=rp.get("recent_deviations_30d", 0),
                repeat_deviation_types=rp.get("repeat_deviation_types", []) or [],
            )
            self._profiles_cache.append(profile)

        self._profile_map = {rp.site_id: rp for rp in self._profiles_cache}

        print(
            f"   ✅ Loaded {len(self._sites_cache)} sites, "
            f"{sum(len(s.patients) for s in self._sites_cache)} patients, "
            f"{len(self._deviations_cache)} deviations from Supabase"
        )

    def get_protocol(self) -> ProtocolSpecification:
        return self._protocol

    def get_sites(self) -> list[Site]:
        return self._sites_cache

    def get_site(self, site_id: str) -> Optional[Site]:
        return self._site_map.get(site_id)

    def get_all_deviations(self) -> list[Deviation]:
        return self._deviations_cache

    def get_deviations_for_site(self, site_id: str) -> list[Deviation]:
        return [d for d in self._deviations_cache if d.site_id == site_id]

    def get_risk_profiles(self) -> list[SiteRiskProfile]:
        return self._profiles_cache

    def get_risk_profile(self, site_id: str) -> Optional[SiteRiskProfile]:
        return self._profile_map.get(site_id)

    def get_site_info(self) -> dict[str, dict]:
        return {
            s.site_id: {"name": s.site_name, "total_patients": len(s.patients)}
            for s in self._sites_cache
        }

    def get_trial_statistics(self) -> dict:
        return get_trial_statistics(self._sites_cache)

    def generate_capa_report(
        self, site_id: str, site_name: str,
        deviations: list[Deviation],
        risk_profile: Optional[SiteRiskProfile] = None
    ) -> CapaReport:
        return self._capa_gen.generate_site_report(
            site_id=site_id,
            site_name=site_name,
            deviations=deviations,
            risk_profile=risk_profile,
        )


# ─── Factory Function ────────────────────────────────────────────────────────

_data_source: Optional[DataSource] = None


def get_data_source() -> DataSource:
    """
    Get the configured data source (singleton).

    - If SUPABASE_URL is set → SupabaseDataSource (reads from database)
    - Otherwise → MockDataSource (in-memory synthetic data)

    This is the ONE swap point: changing data source never requires
    changes to the detection, scoring, or reporting logic.
    """
    global _data_source

    if _data_source is not None:
        return _data_source

    from db.supabase_client import is_supabase_configured

    if is_supabase_configured():
        try:
            _data_source = SupabaseDataSource()
        except Exception as e:
            print(f"⚠️  Supabase initialization failed: {e}")
            print("   Falling back to MockDataSource...")
            _data_source = MockDataSource()
    else:
        _data_source = MockDataSource()

    return _data_source
