"""
protocol.py — Clinical Trial Protocol Specification Model

Defines the master protocol that governs the clinical trial. Every deviation
is detected by comparing patient records against this specification.

Modeled after a realistic Phase III oncology trial (PHOENIX-301).
"""

from dataclasses import dataclass, field
from datetime import timedelta
from enum import Enum
from typing import Optional


class VisitType(str, Enum):
    SCREENING = "screening"
    BASELINE = "baseline"
    TREATMENT = "treatment"
    FOLLOW_UP = "follow_up"
    END_OF_STUDY = "end_of_study"


class DeviationType(str, Enum):
    MISSED_VISIT = "missed_visit"
    LATE_VISIT = "late_visit"
    EARLY_VISIT = "early_visit"
    WRONG_DOSE = "wrong_dose"
    BANNED_COMEDICATION = "banned_comedication"
    MISSING_ASSESSMENT = "missing_assessment"


class Severity(str, Enum):
    MAJOR = "major"
    MINOR = "minor"
    ADMINISTRATIVE = "administrative"


class RiskTier(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TrendDirection(str, Enum):
    RISING = "rising"
    STABLE = "stable"
    DECLINING = "declining"


@dataclass
class ProtocolVisit:
    """A single visit in the protocol schedule."""
    visit_number: int
    visit_name: str
    visit_type: VisitType
    target_day: int  # Day relative to enrollment (Day 0 = baseline)
    window_before: int  # Allowed days before target
    window_after: int  # Allowed days after target
    required_assessments: list[str] = field(default_factory=list)

    @property
    def earliest_day(self) -> int:
        return self.target_day - self.window_before

    @property
    def latest_day(self) -> int:
        return self.target_day + self.window_after


@dataclass
class DoseRule:
    """Dosing specification for the trial drug."""
    drug_name: str
    dose_mg: float
    route: str  # e.g., "oral", "IV"
    frequency: str  # e.g., "once daily", "every 3 weeks"
    allowed_deviation_pct: float = 5.0  # ±5% is administrative, 5-20% minor, >20% major


@dataclass
class BannedMedication:
    """A medication prohibited during the trial."""
    drug_name: str
    drug_class: str
    reason: str
    interaction_severity: str  # "high" = major deviation, "moderate" = minor


@dataclass
class ProtocolSpecification:
    """The master protocol specification for the entire trial."""
    protocol_id: str
    protocol_title: str
    phase: str
    indication: str
    sponsor: str
    visits: list[ProtocolVisit]
    dose_rules: list[DoseRule]
    banned_medications: list[BannedMedication]
    max_enrollment_per_site: int = 30
    total_target_enrollment: int = 600


def get_protocol() -> ProtocolSpecification:
    """
    Returns the PHOENIX-301 protocol specification.
    
    Modeled after a realistic Phase III oncology trial for a novel
    oral tyrosine kinase inhibitor (TKI) in advanced non-small cell
    lung cancer (NSCLC).
    """
    visits = [
        ProtocolVisit(
            visit_number=1,
            visit_name="Screening",
            visit_type=VisitType.SCREENING,
            target_day=-14,
            window_before=7,
            window_after=7,
            required_assessments=["informed_consent", "medical_history", "vital_signs",
                                  "ecg", "ct_scan", "blood_panel", "pregnancy_test"]
        ),
        ProtocolVisit(
            visit_number=2,
            visit_name="Baseline / Randomization",
            visit_type=VisitType.BASELINE,
            target_day=0,
            window_before=0,
            window_after=3,
            required_assessments=["randomization", "vital_signs", "ecg", "blood_panel",
                                  "quality_of_life", "first_dose"]
        ),
        ProtocolVisit(
            visit_number=3,
            visit_name="Week 2",
            visit_type=VisitType.TREATMENT,
            target_day=14,
            window_before=3,
            window_after=3,
            required_assessments=["vital_signs", "blood_panel", "adverse_events",
                                  "dose_compliance"]
        ),
        ProtocolVisit(
            visit_number=4,
            visit_name="Week 4",
            visit_type=VisitType.TREATMENT,
            target_day=28,
            window_before=3,
            window_after=3,
            required_assessments=["vital_signs", "blood_panel", "adverse_events",
                                  "dose_compliance", "ecg"]
        ),
        ProtocolVisit(
            visit_number=5,
            visit_name="Week 8",
            visit_type=VisitType.TREATMENT,
            target_day=56,
            window_before=5,
            window_after=5,
            required_assessments=["vital_signs", "blood_panel", "adverse_events",
                                  "dose_compliance", "ct_scan", "quality_of_life"]
        ),
        ProtocolVisit(
            visit_number=6,
            visit_name="Week 12",
            visit_type=VisitType.TREATMENT,
            target_day=84,
            window_before=5,
            window_after=5,
            required_assessments=["vital_signs", "blood_panel", "adverse_events",
                                  "dose_compliance"]
        ),
        ProtocolVisit(
            visit_number=7,
            visit_name="Week 16",
            visit_type=VisitType.TREATMENT,
            target_day=112,
            window_before=5,
            window_after=5,
            required_assessments=["vital_signs", "blood_panel", "adverse_events",
                                  "dose_compliance", "ct_scan"]
        ),
        ProtocolVisit(
            visit_number=8,
            visit_name="Week 24",
            visit_type=VisitType.TREATMENT,
            target_day=168,
            window_before=7,
            window_after=7,
            required_assessments=["vital_signs", "blood_panel", "adverse_events",
                                  "dose_compliance", "ct_scan", "quality_of_life", "ecg"]
        ),
        ProtocolVisit(
            visit_number=9,
            visit_name="Week 36",
            visit_type=VisitType.TREATMENT,
            target_day=252,
            window_before=7,
            window_after=7,
            required_assessments=["vital_signs", "blood_panel", "adverse_events",
                                  "dose_compliance", "ct_scan"]
        ),
        ProtocolVisit(
            visit_number=10,
            visit_name="Week 48 / End of Treatment",
            visit_type=VisitType.END_OF_STUDY,
            target_day=336,
            window_before=7,
            window_after=14,
            required_assessments=["vital_signs", "blood_panel", "adverse_events",
                                  "ct_scan", "quality_of_life", "ecg", "end_of_study_form"]
        ),
        ProtocolVisit(
            visit_number=11,
            visit_name="Follow-Up (30 days post-treatment)",
            visit_type=VisitType.FOLLOW_UP,
            target_day=366,
            window_before=7,
            window_after=14,
            required_assessments=["vital_signs", "adverse_events", "survival_status"]
        ),
    ]

    dose_rules = [
        DoseRule(
            drug_name="Phoenixin (PNX-301)",
            dose_mg=200.0,
            route="oral",
            frequency="once daily",
            allowed_deviation_pct=5.0
        ),
        DoseRule(
            drug_name="Phoenixin (PNX-301) — reduced dose",
            dose_mg=150.0,
            route="oral",
            frequency="once daily (dose reduction level 1)",
            allowed_deviation_pct=5.0
        ),
    ]

    banned_medications = [
        BannedMedication("Warfarin", "Anticoagulant",
                         "Risk of severe bleeding with TKI", "high"),
        BannedMedication("Ketoconazole", "Antifungal (CYP3A4 inhibitor)",
                         "Increases PNX-301 plasma levels 3x — toxicity risk", "high"),
        BannedMedication("Rifampin", "Antibiotic (CYP3A4 inducer)",
                         "Reduces PNX-301 efficacy by 80%", "high"),
        BannedMedication("St. John's Wort", "Herbal (CYP3A4 inducer)",
                         "Reduces PNX-301 efficacy significantly", "high"),
        BannedMedication("Phenytoin", "Anticonvulsant (CYP3A4 inducer)",
                         "Reduces PNX-301 plasma levels", "moderate"),
        BannedMedication("Carbamazepine", "Anticonvulsant (CYP3A4 inducer)",
                         "Reduces PNX-301 plasma levels", "moderate"),
        BannedMedication("Itraconazole", "Antifungal (CYP3A4 inhibitor)",
                         "Moderately increases PNX-301 levels", "moderate"),
        BannedMedication("Grapefruit juice", "CYP3A4 inhibitor (dietary)",
                         "Mild increase in PNX-301 levels", "moderate"),
        BannedMedication("Simvastatin", "Statin (CYP3A4 substrate)",
                         "Increased statin toxicity risk with PNX-301", "moderate"),
        BannedMedication("Methotrexate", "Antimetabolite",
                         "Overlapping hepatotoxicity risk", "high"),
    ]

    return ProtocolSpecification(
        protocol_id="PHOENIX-301",
        protocol_title="A Phase III, Randomized, Double-Blind Study of Phoenixin (PNX-301) "
                       "versus Standard of Care in Patients with Advanced NSCLC",
        phase="Phase III",
        indication="Advanced Non-Small Cell Lung Cancer (NSCLC)",
        sponsor="Phoenix Therapeutics Inc.",
        visits=visits,
        dose_rules=dose_rules,
        banned_medications=banned_medications,
        max_enrollment_per_site=30,
        total_target_enrollment=600
    )
