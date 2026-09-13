"""
deviation_detector.py — Stage 1: Protocol Deviation Detection

Compares every patient visit record against the protocol specification
and flags any mismatch as a deviation. This is fully deterministic —
every finding traces back to an exact rule and exact patient record.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from .protocol import (
    DeviationType,
    ProtocolSpecification,
    ProtocolVisit,
    get_protocol,
)
from .synthetic_data import Patient, PatientVisit, Site


@dataclass
class Deviation:
    """A single detected protocol deviation."""
    deviation_id: str
    patient_id: str
    site_id: str
    visit_id: str
    visit_name: str
    deviation_type: DeviationType
    description: str
    expected_value: str
    actual_value: str
    detected_date: date
    protocol_reference: str  # Which protocol rule was violated
    severity: Optional[str] = None  # Filled in by severity_classifier
    raw_data: dict = field(default_factory=dict)  # Extra context for scoring


class DeviationDetector:
    """
    Compares patient visit records against the protocol specification.
    
    Every deviation is deterministic and traceable:
    - The exact protocol rule that was violated
    - The expected value vs actual value
    - The patient and visit that triggered it
    """

    def __init__(self, protocol: ProtocolSpecification):
        self.protocol = protocol
        self._visit_map = {v.visit_number: v for v in protocol.visits}
        self._banned_meds = {m.drug_name.lower(): m for m in protocol.banned_medications}
        self._deviation_counter = 0

    def detect_all(self, sites: list[Site]) -> list[Deviation]:
        """Scan all sites and return every detected deviation."""
        deviations = []
        for site in sites:
            for patient in site.patients:
                deviations.extend(self.detect_for_patient(patient))
        return deviations

    def detect_for_site(self, site: Site) -> list[Deviation]:
        """Detect deviations for a specific site."""
        deviations = []
        for patient in site.patients:
            deviations.extend(self.detect_for_patient(patient))
        return deviations

    def detect_for_patient(self, patient: Patient) -> list[Deviation]:
        """Detect all deviations for a single patient."""
        deviations = []
        for visit in patient.visits:
            deviations.extend(self._check_visit(patient, visit))
        return deviations

    def _check_visit(self, patient: Patient, visit: PatientVisit) -> list[Deviation]:
        """Check a single visit against all protocol rules."""
        deviations = []

        protocol_visit = self._visit_map.get(visit.visit_number)
        if not protocol_visit:
            return deviations

        # Check 1: Visit timing
        timing_deviation = self._check_visit_timing(patient, visit, protocol_visit)
        if timing_deviation:
            deviations.append(timing_deviation)

        # Check 2: Dosing (only if visit occurred)
        if visit.actual_date is not None and visit.dose_administered_mg is not None:
            dose_deviation = self._check_dose(patient, visit)
            if dose_deviation:
                deviations.append(dose_deviation)

        # Check 3: Banned co-medications (only if visit occurred)
        if visit.actual_date is not None:
            med_deviations = self._check_medications(patient, visit)
            deviations.extend(med_deviations)

        # Check 4: Missing assessments (only if visit occurred)
        if visit.actual_date is not None:
            assessment_deviation = self._check_assessments(patient, visit, protocol_visit)
            if assessment_deviation:
                deviations.append(assessment_deviation)

        return deviations

    def _check_visit_timing(
        self, patient: Patient, visit: PatientVisit, protocol_visit: ProtocolVisit
    ) -> Optional[Deviation]:
        """Check if the visit occurred within the protocol-specified window."""

        # Missed visit
        if visit.actual_date is None:
            self._deviation_counter += 1
            return Deviation(
                deviation_id=f"DEV-{self._deviation_counter:05d}",
                patient_id=visit.patient_id,
                site_id=visit.site_id,
                visit_id=visit.visit_id,
                visit_name=visit.visit_name,
                deviation_type=DeviationType.MISSED_VISIT,
                description=(
                    f"Patient {visit.patient_id} missed scheduled visit "
                    f"'{visit.visit_name}' (Visit {visit.visit_number}) "
                    f"on {visit.scheduled_date.isoformat()}"
                ),
                expected_value=f"Visit on {visit.scheduled_date.isoformat()}",
                actual_value="Visit not completed",
                detected_date=visit.scheduled_date,
                protocol_reference=(
                    f"Protocol {self.protocol.protocol_id}, "
                    f"Visit {protocol_visit.visit_number} "
                    f"({protocol_visit.visit_name}), "
                    f"Schedule: Day {protocol_visit.target_day}"
                ),
                raw_data={
                    "days_deviation": None,
                    "visit_type": "missed"
                }
            )

        # Calculate day deviation
        actual_day = (visit.actual_date - patient.enrollment_date).days
        day_deviation = actual_day - protocol_visit.target_day

        # Check if outside window
        if day_deviation < -protocol_visit.window_before:
            self._deviation_counter += 1
            return Deviation(
                deviation_id=f"DEV-{self._deviation_counter:05d}",
                patient_id=visit.patient_id,
                site_id=visit.site_id,
                visit_id=visit.visit_id,
                visit_name=visit.visit_name,
                deviation_type=DeviationType.EARLY_VISIT,
                description=(
                    f"Patient {visit.patient_id} attended '{visit.visit_name}' "
                    f"{abs(day_deviation) - protocol_visit.window_before} day(s) "
                    f"before the allowed window"
                ),
                expected_value=(
                    f"Day {protocol_visit.earliest_day} to "
                    f"Day {protocol_visit.latest_day}"
                ),
                actual_value=f"Day {actual_day} ({day_deviation:+d} from target)",
                detected_date=visit.actual_date,
                protocol_reference=(
                    f"Protocol {self.protocol.protocol_id}, "
                    f"Visit {protocol_visit.visit_number}, "
                    f"Window: Day {protocol_visit.earliest_day}–{protocol_visit.latest_day}"
                ),
                raw_data={
                    "days_deviation": day_deviation,
                    "visit_type": "early"
                }
            )

        if day_deviation > protocol_visit.window_after:
            self._deviation_counter += 1
            days_late = day_deviation - protocol_visit.window_after
            return Deviation(
                deviation_id=f"DEV-{self._deviation_counter:05d}",
                patient_id=visit.patient_id,
                site_id=visit.site_id,
                visit_id=visit.visit_id,
                visit_name=visit.visit_name,
                deviation_type=DeviationType.LATE_VISIT,
                description=(
                    f"Patient {visit.patient_id} attended '{visit.visit_name}' "
                    f"{days_late} day(s) after the allowed window"
                ),
                expected_value=(
                    f"Day {protocol_visit.earliest_day} to "
                    f"Day {protocol_visit.latest_day}"
                ),
                actual_value=f"Day {actual_day} ({day_deviation:+d} from target)",
                detected_date=visit.actual_date,
                protocol_reference=(
                    f"Protocol {self.protocol.protocol_id}, "
                    f"Visit {protocol_visit.visit_number}, "
                    f"Window: Day {protocol_visit.earliest_day}–{protocol_visit.latest_day}"
                ),
                raw_data={
                    "days_deviation": day_deviation,
                    "days_late": days_late,
                    "visit_type": "late"
                }
            )

        return None

    def _check_dose(
        self, patient: Patient, visit: PatientVisit
    ) -> Optional[Deviation]:
        """Check if the administered dose matches the protocol."""
        if visit.dose_administered_mg is None or visit.protocol_dose_mg <= 0:
            return None

        deviation_pct = abs(
            (visit.dose_administered_mg - visit.protocol_dose_mg)
            / visit.protocol_dose_mg * 100
        )

        # Only flag if deviation exceeds the administrative threshold (>2%)
        if deviation_pct <= 2.0:
            return None

        self._deviation_counter += 1
        return Deviation(
            deviation_id=f"DEV-{self._deviation_counter:05d}",
            patient_id=visit.patient_id,
            site_id=visit.site_id,
            visit_id=visit.visit_id,
            visit_name=visit.visit_name,
            deviation_type=DeviationType.WRONG_DOSE,
            description=(
                f"Patient {visit.patient_id} received "
                f"{visit.dose_administered_mg}mg instead of "
                f"{visit.protocol_dose_mg}mg "
                f"({deviation_pct:.1f}% deviation) at '{visit.visit_name}'"
            ),
            expected_value=f"{visit.protocol_dose_mg}mg",
            actual_value=f"{visit.dose_administered_mg}mg ({deviation_pct:.1f}% off)",
            detected_date=visit.actual_date,
            protocol_reference=(
                f"Protocol {self.protocol.protocol_id}, "
                f"Dose: {self.protocol.dose_rules[0].drug_name} "
                f"{visit.protocol_dose_mg}mg {self.protocol.dose_rules[0].route}"
            ),
            raw_data={
                "deviation_pct": deviation_pct,
                "expected_mg": visit.protocol_dose_mg,
                "actual_mg": visit.dose_administered_mg
            }
        )

    def _check_medications(
        self, patient: Patient, visit: PatientVisit
    ) -> list[Deviation]:
        """Check if the patient is taking any banned co-medications."""
        deviations = []

        for med_name in visit.active_medications:
            banned = self._banned_meds.get(med_name.lower())
            if banned:
                self._deviation_counter += 1
                deviations.append(Deviation(
                    deviation_id=f"DEV-{self._deviation_counter:05d}",
                    patient_id=visit.patient_id,
                    site_id=visit.site_id,
                    visit_id=visit.visit_id,
                    visit_name=visit.visit_name,
                    deviation_type=DeviationType.BANNED_COMEDICATION,
                    description=(
                        f"Patient {visit.patient_id} is taking banned medication "
                        f"'{banned.drug_name}' ({banned.drug_class}) at "
                        f"'{visit.visit_name}'. Reason: {banned.reason}"
                    ),
                    expected_value="No banned co-medications",
                    actual_value=f"{banned.drug_name} ({banned.drug_class})",
                    detected_date=visit.actual_date,
                    protocol_reference=(
                        f"Protocol {self.protocol.protocol_id}, "
                        f"Section 6.5: Prohibited Concomitant Medications — "
                        f"{banned.drug_name}"
                    ),
                    raw_data={
                        "drug_name": banned.drug_name,
                        "drug_class": banned.drug_class,
                        "interaction_severity": banned.interaction_severity,
                        "reason": banned.reason
                    }
                ))

        return deviations

    def _check_assessments(
        self, patient: Patient, visit: PatientVisit, protocol_visit: ProtocolVisit
    ) -> Optional[Deviation]:
        """Check if all required assessments were completed."""
        required = set(protocol_visit.required_assessments)
        completed = set(visit.assessments_completed)
        missing = required - completed

        if not missing:
            return None

        self._deviation_counter += 1
        return Deviation(
            deviation_id=f"DEV-{self._deviation_counter:05d}",
            patient_id=visit.patient_id,
            site_id=visit.site_id,
            visit_id=visit.visit_id,
            visit_name=visit.visit_name,
            deviation_type=DeviationType.MISSING_ASSESSMENT,
            description=(
                f"Patient {visit.patient_id} missing {len(missing)} required "
                f"assessment(s) at '{visit.visit_name}': {', '.join(sorted(missing))}"
            ),
            expected_value=f"All {len(required)} assessments completed",
            actual_value=f"{len(completed)}/{len(required)} completed, missing: {', '.join(sorted(missing))}",
            detected_date=visit.actual_date,
            protocol_reference=(
                f"Protocol {self.protocol.protocol_id}, "
                f"Visit {protocol_visit.visit_number} "
                f"({protocol_visit.visit_name}), "
                f"Required assessments: {', '.join(sorted(required))}"
            ),
            raw_data={
                "missing_assessments": sorted(missing),
                "completed_assessments": sorted(completed),
                "total_required": len(required)
            }
        )
