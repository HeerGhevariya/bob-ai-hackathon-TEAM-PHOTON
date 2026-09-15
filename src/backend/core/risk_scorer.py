"""
risk_scorer.py — Stage 3: Site-Level Risk Scoring

Scores each clinical trial site using composite leading indicators that
predict future non-compliance, not just tally past problems.

Scoring factors:
1. Severity-weighted deviation count (normalised per patient)
2. Trend direction (rising = higher risk)
3. Repetition of same deviation type (systemic issue signal)
4. Recency bias (recent deviations weigh more)

Final score: 100 * (1 - e^(-k * composite_rate)), a saturating function
that avoids the hard-cap clustering problem.  Tuned so that:
  - Low-risk sites (0-1 weighted pts/patient)    →  0-15
  - Medium-risk sites (~3-5 weighted pts/patient) →  25-50
  - High-risk sites  (~8-12 pts/patient)          →  50-70
  - Critical sites   (15+ pts/patient + bonuses)  →  75-95+

Produces a 0-100 risk score per site, bucketed into tiers:
  Critical (75-100), High (50-74), Medium (25-49), Low (0-24)
"""

import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

from .protocol import DeviationType, RiskTier, Severity, TrendDirection
from .deviation_detector import Deviation


# Severity weights — recalibrated so a single major deviation per patient
# contributes ~5 raw pts, keeping scores well below the saturation ceiling
# unless the site is genuinely extreme.
#
# Old weights (10 / 3 / 1) caused even small sites to exceed 100 before
# bonuses, so min(score, 100) flattened everything into Critical.
# New weights (5 / 2 / 0.8) give meaningful spread across the full 0-100 range.
SEVERITY_WEIGHTS = {
    Severity.MAJOR.value: 5.0,
    Severity.MINOR.value: 2.0,
    Severity.ADMINISTRATIVE.value: 0.8,
    "major": 5.0,
    "minor": 2.0,
    "administrative": 0.8,
}

# Risk tier thresholds — recalibrated to match the new saturating score
# distribution (old thresholds were 80/60/40 but the new formula compresses
# extreme values, so the tiers need to shift down accordingly).
TIER_THRESHOLDS = {
    RiskTier.CRITICAL: 75,
    RiskTier.HIGH: 50,
    RiskTier.MEDIUM: 25,
    RiskTier.LOW: 0,
}

# Saturation constant for the exponential scoring function.
# final_score = 100 * (1 - e^(-SCORE_K * composite_rate))
# k=0.08 means:
#   rate=5  → score≈33   (medium risk)
#   rate=10 → score≈55   (high risk)
#   rate=20 → score≈80   (critical risk)
#   rate=30 → score≈91   (very critical)
SCORE_K = 0.08

# Repetition penalty — same deviation type occurring 3+ times signals systemic
# training or process failure.  Added as bonus rate pts (not raw score pts)
# so it feeds the saturating function correctly.
REPETITION_THRESHOLD = 3
REPETITION_RATE_BONUS = 3.0   # extra rate pts per repeated deviation type

# Trend detection window
TREND_WINDOW_DAYS = 60
TREND_RISING_MULTIPLIER = 1.3

# Recency bias — deviations in the last 30 days signal active, ongoing problems.
RECENCY_WINDOW_DAYS = 30
RECENCY_RATE_FACTOR = 2.5     # multiplier applied to recent deviation rate


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

        # --- Factor 1: Severity-weighted deviation rate (per patient) ---
        #
        # We compute a *rate* (weighted_sum / total_patients) rather than a raw
        # count.  This normalises for site size and feeds the saturating function
        # below instead of a hard min(score, 100) cap.
        severity_counts = Counter(d.severity for d in deviations)
        major_count = severity_counts.get("major", 0)
        minor_count = severity_counts.get("minor", 0)
        admin_count = severity_counts.get("administrative", 0)

        weighted_sum = sum(
            SEVERITY_WEIGHTS.get(d.severity, 1.0) for d in deviations
        )

        # Normalize by patient count to avoid penalising large sites
        total_patients = max(site_info.get("total_patients", 1), 1)
        base_rate = weighted_sum / total_patients  # pts-per-patient (unbounded)

        risk_factors = [
            RiskFactor(
                factor_name="Severity-Weighted Deviation Rate",
                description=(
                    f"{len(deviations)} deviations across {total_patients} patients "
                    f"(weighted sum: {weighted_sum:.1f}, rate: {base_rate:.2f} pts/patient)"
                ),
                contribution=base_rate,
            )
        ]

        # --- Factor 2: Repetition penalty ---
        #
        # Same deviation type recurring 3+ times signals a systemic process or
        # training failure.  Expressed as additional *rate* points so it feeds
        # the saturating function alongside the base rate.
        type_counts = Counter(d.deviation_type.value for d in deviations)
        repeat_types = [
            dtype for dtype, count in type_counts.items()
            if count >= REPETITION_THRESHOLD
        ]

        repetition_rate_bonus = 0.0
        if repeat_types:
            repetition_rate_bonus = len(repeat_types) * REPETITION_RATE_BONUS
            risk_factors.append(RiskFactor(
                factor_name="Repeat Deviation Pattern",
                description=(
                    f"{len(repeat_types)} deviation type(s) occurring "
                    f"{REPETITION_THRESHOLD}+ times: {', '.join(repeat_types)}. "
                    f"This suggests systemic training or process issues."
                ),
                contribution=repetition_rate_bonus,
                severity="warning"
            ))

        # --- Factor 3: Recency bias ---
        #
        # Recent deviations are weighted by RECENCY_RATE_FACTOR relative to the
        # overall rate.  We add only the *incremental* boost above the baseline
        # already captured in base_rate.
        recent_cutoff = self.reference_date - timedelta(days=RECENCY_WINDOW_DAYS)
        recent_devs = [
            d for d in deviations
            if d.detected_date and d.detected_date >= recent_cutoff
        ]
        recency_rate_bonus = 0.0
        if recent_devs:
            recent_weighted = sum(
                SEVERITY_WEIGHTS.get(d.severity, 1.0) for d in recent_devs
            )
            # Extra rate contribution from recency amplification (factor - 1 to
            # avoid double-counting the base rate for recent deviations).
            recency_rate_bonus = (
                (recent_weighted / total_patients) * (RECENCY_RATE_FACTOR - 1.0)
            )
            risk_factors.append(RiskFactor(
                factor_name="Recent Activity (Last 30 Days)",
                description=(
                    f"{len(recent_devs)} deviations in the last 30 days "
                    f"(weighted: {recent_weighted:.1f})"
                ),
                contribution=recency_rate_bonus,
            ))

        # --- Factor 4: Trend direction ---
        #
        # Rising trend adds a flat rate boost rather than a flat score boost,
        # so it integrates cleanly with the saturating function.
        trend = self._detect_trend(deviations)
        trend_rate_bonus = 0.0
        if trend == TrendDirection.RISING:
            trend_rate_bonus = 8.0
            risk_factors.append(RiskFactor(
                factor_name="Rising Trend",
                description=(
                    "Deviation rate is increasing over the last "
                    f"{TREND_WINDOW_DAYS} days — this site is getting worse."
                ),
                contribution=trend_rate_bonus,
                severity="critical"
            ))

        # --- Composite saturating score ---
        #
        # FIX: Instead of a hard min(raw_sum, 100) cap (which caused every site
        # with >10 weighted pts/patient to score exactly 100), we pass the
        # composite *rate* through a saturating exponential:
        #
        #   score = 100 * (1 - e^(-k * composite_rate))
        #
        # This maps [0, ∞) → [0, 100) smoothly, so genuinely extreme sites
        # approach 100 asymptotically while low/medium sites get proportionally
        # lower scores, giving meaningful spread across all tiers.
        composite_rate = base_rate + repetition_rate_bonus + recency_rate_bonus + trend_rate_bonus
        risk_score = 100.0 * (1.0 - math.exp(-SCORE_K * composite_rate))

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
