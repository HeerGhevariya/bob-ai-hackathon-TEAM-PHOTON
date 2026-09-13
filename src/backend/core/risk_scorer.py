"""
risk_scorer.py — Stage 3: Site-Level Risk Scoring

Scores each clinical trial site using composite leading indicators that
predict future non-compliance, not just tally past problems.

Scoring factors:
1. Severity-weighted deviation count
2. Trend direction (rising = higher risk)
3. Repetition of same deviation type (systemic issue signal)
4. Recency bias (recent deviations weigh more)

Produces a 0-100 risk score per site, bucketed into tiers:
  Critical (80-100), High (60-79), Medium (40-59), Low (0-39)
"""

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

from .protocol import DeviationType, RiskTier, Severity, TrendDirection
from .deviation_detector import Deviation


# Severity weights — a major counts 10x an administrative
SEVERITY_WEIGHTS = {
    Severity.MAJOR.value: 10.0,
    Severity.MINOR.value: 3.0,
    Severity.ADMINISTRATIVE.value: 1.0,
    "major": 10.0,
    "minor": 3.0,
    "administrative": 1.0,
}

# Risk tier thresholds
TIER_THRESHOLDS = {
    RiskTier.CRITICAL: 80,
    RiskTier.HIGH: 60,
    RiskTier.MEDIUM: 40,
    RiskTier.LOW: 0,
}

# Repetition penalty — same deviation type occurring 3+ times
REPETITION_THRESHOLD = 3
REPETITION_MULTIPLIER = 1.5

# Trend detection window
TREND_WINDOW_DAYS = 60
TREND_RISING_MULTIPLIER = 1.3

# Recency decay — deviations in last 30 days get 2x weight
RECENCY_WINDOW_DAYS = 30
RECENCY_MULTIPLIER = 2.0


@dataclass
class RiskFactor:
    """A single contributing factor to a site's risk score."""
    factor_name: str
    description: str
    contribution: float  # Points contributed to total score
    severity: str = ""


@dataclass
class SiteRiskProfile:
    """Complete risk profile for a single site."""
    site_id: str
    site_name: str
    risk_score: float  # 0-100
    risk_tier: RiskTier
    trend_direction: TrendDirection
    total_deviations: int
    major_count: int
    minor_count: int
    administrative_count: int
    top_risk_factors: list[RiskFactor] = field(default_factory=list)
    deviation_types: dict[str, int] = field(default_factory=dict)
    patients_affected: int = 0
    total_patients: int = 0
    recent_deviations_30d: int = 0
    repeat_deviation_types: list[str] = field(default_factory=list)


class RiskScorer:
    """
    Scores sites using composite leading indicators.
    
    The score is NOT just a count of deviations. It weighs:
    - Severity (major deviations dominate)
    - Trends (a site getting worse is higher risk than one holding steady)
    - Repetition (same error type recurring = systemic problem)
    - Recency (recent problems are more actionable)
    """

    def __init__(self, reference_date: Optional[date] = None):
        self.reference_date = reference_date or date.today()

    def score_all_sites(
        self,
        deviations: list[Deviation],
        site_info: dict[str, dict]
    ) -> list[SiteRiskProfile]:
        """
        Score all sites and return ranked profiles.
        
        Args:
            deviations: All detected deviations across the trial
            site_info: Dict mapping site_id -> {"name": str, "total_patients": int}
        
        Returns:
            List of SiteRiskProfile sorted by risk_score descending
        """
        # Group deviations by site
        site_deviations: dict[str, list[Deviation]] = defaultdict(list)
        for dev in deviations:
            site_deviations[dev.site_id].append(dev)

        profiles = []
        for site_id, info in site_info.items():
            site_devs = site_deviations.get(site_id, [])
            profile = self._score_site(site_id, info, site_devs)
            profiles.append(profile)

        # Sort by risk score descending
        profiles.sort(key=lambda p: p.risk_score, reverse=True)
        return profiles

    def _score_site(
        self,
        site_id: str,
        site_info: dict,
        deviations: list[Deviation]
    ) -> SiteRiskProfile:
        """Calculate the composite risk score for a single site."""

        if not deviations:
            return SiteRiskProfile(
                site_id=site_id,
                site_name=site_info.get("name", site_id),
                risk_score=0.0,
                risk_tier=RiskTier.LOW,
                trend_direction=TrendDirection.STABLE,
                total_deviations=0,
                major_count=0,
                minor_count=0,
                administrative_count=0,
                total_patients=site_info.get("total_patients", 0),
            )

        # --- Factor 1: Severity-weighted deviation count ---
        severity_counts = Counter(d.severity for d in deviations)
        major_count = severity_counts.get("major", 0)
        minor_count = severity_counts.get("minor", 0)
        admin_count = severity_counts.get("administrative", 0)

        weighted_sum = sum(
            SEVERITY_WEIGHTS.get(d.severity, 1.0) for d in deviations
        )

        # Normalize by patient count to avoid penalizing large sites
        total_patients = max(site_info.get("total_patients", 1), 1)
        base_score = (weighted_sum / total_patients) * 10

        risk_factors = [
            RiskFactor(
                factor_name="Severity-Weighted Deviation Rate",
                description=(
                    f"{len(deviations)} deviations across {total_patients} patients "
                    f"(weighted sum: {weighted_sum:.1f})"
                ),
                contribution=base_score,
            )
        ]

        # --- Factor 2: Repetition penalty ---
        type_counts = Counter(d.deviation_type.value for d in deviations)
        repeat_types = [
            dtype for dtype, count in type_counts.items()
            if count >= REPETITION_THRESHOLD
        ]

        repetition_bonus = 0.0
        if repeat_types:
            repetition_bonus = len(repeat_types) * 8.0
            risk_factors.append(RiskFactor(
                factor_name="Repeat Deviation Pattern",
                description=(
                    f"{len(repeat_types)} deviation type(s) occurring "
                    f"{REPETITION_THRESHOLD}+ times: {', '.join(repeat_types)}. "
                    f"This suggests systemic training or process issues."
                ),
                contribution=repetition_bonus,
                severity="warning"
            ))

        # --- Factor 3: Recency bias ---
        recent_cutoff = self.reference_date - timedelta(days=RECENCY_WINDOW_DAYS)
        recent_devs = [
            d for d in deviations
            if d.detected_date and d.detected_date >= recent_cutoff
        ]
        recency_bonus = 0.0
        if recent_devs:
            recent_weighted = sum(
                SEVERITY_WEIGHTS.get(d.severity, 1.0) for d in recent_devs
            )
            recency_bonus = (recent_weighted / total_patients) * 5
            risk_factors.append(RiskFactor(
                factor_name="Recent Activity (Last 30 Days)",
                description=(
                    f"{len(recent_devs)} deviations in the last 30 days "
                    f"(weighted: {recent_weighted:.1f})"
                ),
                contribution=recency_bonus,
            ))

        # --- Factor 4: Trend direction ---
        trend = self._detect_trend(deviations)
        trend_bonus = 0.0
        if trend == TrendDirection.RISING:
            trend_bonus = 12.0
            risk_factors.append(RiskFactor(
                factor_name="Rising Trend",
                description=(
                    "Deviation rate is increasing over the last "
                    f"{TREND_WINDOW_DAYS} days — this site is getting worse."
                ),
                contribution=trend_bonus,
                severity="critical"
            ))

        # --- Composite score ---
        raw_score = base_score + repetition_bonus + recency_bonus + trend_bonus

        # Clamp to 0-100
        risk_score = min(100.0, max(0.0, raw_score))

        # Determine tier
        risk_tier = self._get_tier(risk_score)

        # Patients affected
        patients_affected = len(set(d.patient_id for d in deviations))

        return SiteRiskProfile(
            site_id=site_id,
            site_name=site_info.get("name", site_id),
            risk_score=round(risk_score, 1),
            risk_tier=risk_tier,
            trend_direction=trend,
            total_deviations=len(deviations),
            major_count=major_count,
            minor_count=minor_count,
            administrative_count=admin_count,
            top_risk_factors=sorted(risk_factors, key=lambda f: f.contribution, reverse=True)[:5],
            deviation_types=dict(type_counts),
            patients_affected=patients_affected,
            total_patients=total_patients,
            recent_deviations_30d=len(recent_devs),
            repeat_deviation_types=repeat_types,
        )

    def _detect_trend(self, deviations: list[Deviation]) -> TrendDirection:
        """
        Detect whether deviation rate is rising, stable, or declining.
        
        Compares the first half vs second half of the trend window.
        """
        if len(deviations) < 4:
            return TrendDirection.STABLE

        dated_devs = [d for d in deviations if d.detected_date]
        if len(dated_devs) < 4:
            return TrendDirection.STABLE

        dated_devs.sort(key=lambda d: d.detected_date)

        # Split into two halves by time
        mid_idx = len(dated_devs) // 2
        first_half = dated_devs[:mid_idx]
        second_half = dated_devs[mid_idx:]

        # Calculate weighted rate for each half
        first_weighted = sum(
            SEVERITY_WEIGHTS.get(d.severity, 1.0) for d in first_half
        )
        second_weighted = sum(
            SEVERITY_WEIGHTS.get(d.severity, 1.0) for d in second_half
        )

        # Calculate time spans
        first_span = max(
            (first_half[-1].detected_date - first_half[0].detected_date).days, 1
        )
        second_span = max(
            (second_half[-1].detected_date - second_half[0].detected_date).days, 1
        )

        first_rate = first_weighted / first_span
        second_rate = second_weighted / second_span

        if second_rate > first_rate * 1.3:
            return TrendDirection.RISING
        elif second_rate < first_rate * 0.7:
            return TrendDirection.DECLINING
        else:
            return TrendDirection.STABLE

    def _get_tier(self, score: float) -> RiskTier:
        """Map a numeric score to a risk tier."""
        if score >= TIER_THRESHOLDS[RiskTier.CRITICAL]:
            return RiskTier.CRITICAL
        elif score >= TIER_THRESHOLDS[RiskTier.HIGH]:
            return RiskTier.HIGH
        elif score >= TIER_THRESHOLDS[RiskTier.MEDIUM]:
            return RiskTier.MEDIUM
        else:
            return RiskTier.LOW
