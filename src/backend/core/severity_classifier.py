"""
severity_classifier.py — Stage 2: ICH E6 GCP Severity Classification

Classifies every detected deviation according to ICH E6(R2) Good Clinical
Practice guidelines into Major, Minor, or Administrative severity.

Classification is fully deterministic and rule-based — no AI involved.
Every classification traces back to a specific rule and threshold.
"""

from .protocol import DeviationType, Severity
from .deviation_detector import Deviation


# Classification thresholds based on ICH E6(R2) GCP guidelines
# These are codified from regulatory standards, not arbitrary
TIMING_THRESHOLDS = {
    "major_days": 30,      # >30 days late/missed = Major
    "minor_days": 7,       # 7-30 days late = Minor
    "administrative_days": 7,  # 1-7 days late = Administrative
}

DOSE_THRESHOLDS = {
    "major_pct": 20.0,     # >20% dose deviation = Major
    "minor_pct": 5.0,      # 5-20% = Minor
    "administrative_pct": 5.0,  # <5% = Administrative (but >2% to be flagged)
}


class SeverityClassifier:
    """
    Classifies protocol deviations by ICH E6 GCP severity.
    
    Severity Definitions (per ICH E6(R2)):
    
    Major: Deviations that may significantly affect:
        - Subject safety
        - Data integrity
        - Scientific value of the trial
        Examples: wrong dose >20%, banned co-medication with high interaction,
                  missed critical visits
    
    Minor: Deviations that are unlikely to significantly affect:
        - Subject safety or data integrity
        - But still represent non-compliance
        Examples: moderate dose deviation, moderately late visits,
                  banned co-medication with moderate interaction
    
    Administrative: Deviations that are:
        - Documentation or process errors
        - No impact on safety or data integrity
        Examples: slightly late visit within tolerance, minor dose rounding
    """

    def classify(self, deviation: Deviation) -> Severity:
        """Classify a single deviation by severity."""
        if deviation.deviation_type == DeviationType.MISSED_VISIT:
            return self._classify_missed_visit(deviation)
        elif deviation.deviation_type == DeviationType.LATE_VISIT:
            return self._classify_late_visit(deviation)
        elif deviation.deviation_type == DeviationType.EARLY_VISIT:
            return self._classify_early_visit(deviation)
        elif deviation.deviation_type == DeviationType.WRONG_DOSE:
            return self._classify_wrong_dose(deviation)
        elif deviation.deviation_type == DeviationType.BANNED_COMEDICATION:
            return self._classify_banned_medication(deviation)
        elif deviation.deviation_type == DeviationType.MISSING_ASSESSMENT:
            return self._classify_missing_assessment(deviation)
        else:
            return Severity.MINOR  # Default for unknown types

    def classify_all(self, deviations: list[Deviation]) -> list[Deviation]:
        """Classify all deviations and update their severity field in-place."""
        for dev in deviations:
            dev.severity = self.classify(dev).value
        return deviations

    def _classify_missed_visit(self, deviation: Deviation) -> Severity:
        """Missed visits are always Major — they represent a complete protocol violation."""
        return Severity.MAJOR

    def _classify_late_visit(self, deviation: Deviation) -> Severity:
        """Classify based on how many days outside the allowed window."""
        days_late = deviation.raw_data.get("days_late", 0)

        if days_late > TIMING_THRESHOLDS["major_days"]:
            return Severity.MAJOR
        elif days_late > TIMING_THRESHOLDS["minor_days"]:
            return Severity.MINOR
        else:
            return Severity.ADMINISTRATIVE

    def _classify_early_visit(self, deviation: Deviation) -> Severity:
        """Early visits follow similar thresholds as late visits."""
        days_deviation = abs(deviation.raw_data.get("days_deviation", 0))

        if days_deviation > TIMING_THRESHOLDS["major_days"]:
            return Severity.MAJOR
        elif days_deviation > TIMING_THRESHOLDS["minor_days"]:
            return Severity.MINOR
        else:
            return Severity.ADMINISTRATIVE

    def _classify_wrong_dose(self, deviation: Deviation) -> Severity:
        """Classify based on percentage deviation from protocol dose."""
        deviation_pct = deviation.raw_data.get("deviation_pct", 0)

        if deviation_pct > DOSE_THRESHOLDS["major_pct"]:
            return Severity.MAJOR
        elif deviation_pct > DOSE_THRESHOLDS["minor_pct"]:
            return Severity.MINOR
        else:
            return Severity.ADMINISTRATIVE

    def _classify_banned_medication(self, deviation: Deviation) -> Severity:
        """Classify based on the interaction severity of the banned medication."""
        interaction_severity = deviation.raw_data.get("interaction_severity", "moderate")

        if interaction_severity == "high":
            return Severity.MAJOR
        else:
            return Severity.MINOR

    def _classify_missing_assessment(self, deviation: Deviation) -> Severity:
        """
        Classify based on which assessments are missing.
        Safety-critical assessments = Major, others = Minor/Administrative.
        """
        missing = set(deviation.raw_data.get("missing_assessments", []))
        total_required = deviation.raw_data.get("total_required", 1)

        # Safety-critical assessments
        safety_critical = {
            "vital_signs", "ecg", "blood_panel", "adverse_events",
            "informed_consent", "pregnancy_test"
        }

        missing_critical = missing & safety_critical

        if missing_critical:
            return Severity.MAJOR
        elif len(missing) > total_required * 0.5:
            return Severity.MINOR
        else:
            return Severity.ADMINISTRATIVE


def get_severity_description(severity: Severity) -> dict:
    """Return a human-readable description of a severity level."""
    descriptions = {
        Severity.MAJOR: {
            "level": "Major",
            "color": "#ef4444",
            "icon": "🔴",
            "definition": (
                "May significantly affect subject safety, data integrity, "
                "or the scientific value of the trial. Requires immediate "
                "corrective action and regulatory reporting."
            ),
            "action_required": (
                "Immediate investigation, CAPA report required, "
                "sponsor notification within 24 hours"
            ),
        },
        Severity.MINOR: {
            "level": "Minor",
            "color": "#f59e0b",
            "icon": "🟡",
            "definition": (
                "Unlikely to significantly affect subject safety or data "
                "integrity, but represents protocol non-compliance. "
                "Should be documented and addressed."
            ),
            "action_required": (
                "Document in deviation log, implement corrective action, "
                "review at next monitoring visit"
            ),
        },
        Severity.ADMINISTRATIVE: {
            "level": "Administrative",
            "color": "#3b82f6",
            "icon": "🔵",
            "definition": (
                "Documentation or process error with no impact on subject "
                "safety or data integrity. Represents minor non-compliance."
            ),
            "action_required": (
                "Log in deviation tracker, address at next scheduled review"
            ),
        },
    }
    return descriptions.get(severity, descriptions[Severity.MINOR])
