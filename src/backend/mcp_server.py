"""
mcp_server.py — MCP Server for IBM Bob Integration

Exposes the TrialGuard AI clinical trial analysis engine as MCP tools
that IBM Bob can invoke. Bob connects via stdio transport and gains
access to deviation detection, risk scoring, and CAPA report generation.

Data comes from the DataSource adapter — which transparently uses
either MockDataSource (in-memory) or SupabaseDataSource (persistent)
depending on environment configuration.
"""

import sys
import os
import builtins

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(__file__))

# Divert standard print to stderr to keep stdout 100% clean for MCP JSON-RPC protocol
_orig_print = builtins.print
def _mcp_stderr_print(*args, **kwargs):
    if "file" not in kwargs:
        kwargs["file"] = sys.stderr
    _orig_print(*args, **kwargs)
builtins.print = _mcp_stderr_print

from datetime import date

from mcp.server.mcpserver import MCPServer

from core.data_source import get_data_source


# Initialize the MCP server
mcp = MCPServer("TrialGuard AI")

# Initialize the analysis engine via DataSource adapter
_ds = get_data_source()
_protocol = _ds.get_protocol()


# ──────────────────────────────────────────────────────────
#  MCP TOOLS — Model-controlled (Bob decides when to call)
# ──────────────────────────────────────────────────────────

@mcp.tool()
def detect_deviations(site_id: str = "") -> str:
    """Detect protocol deviations for a specific site or all sites.
    
    Compares patient visit records against the PHOENIX-301 protocol 
    specification and returns all detected deviations with classification.
    
    Args:
        site_id: Optional site ID (e.g., 'SITE-042'). If empty, returns summary for all sites.
    """
    if site_id:
        site = _ds.get_site(site_id)
        if site is not None:
            devs = _ds.get_deviations_for_site(site_id)
            
            if not devs:
                return f"No deviations found for {site_id} ({site.site_name})."
            
            lines = [f"## Deviations for {site_id} — {site.site_name}",
                     f"Total: {len(devs)} deviation(s)\n"]
            
            for d in devs:
                sev_str = str(d.severity or "unknown").lower()
                severity_icon = {"major": "🔴", "minor": "🟡", "administrative": "🔵"}.get(sev_str, "⚪")
                lines.append(
                    f"- {severity_icon} **{sev_str.upper()}** | {d.deviation_type.value.replace('_', ' ').title()} | "
                    f"Patient {d.patient_id} | {d.visit_name} | {d.description}"
                )
            
            return "\n".join(lines)
        else:
            return f"Site '{site_id}' not found. Use format SITE-001 through SITE-210."
    
    else:
        # Summary across all sites
        from collections import Counter
        all_devs = _ds.get_all_deviations()
        severity_counts = Counter(d.severity for d in all_devs)
        type_counts = Counter(d.deviation_type.value for d in all_devs)
        
        lines = [
            "## Trial-Wide Deviation Summary",
            f"Total deviations: {len(all_devs)}",
            f"- 🔴 Major: {severity_counts.get('major', 0)}",
            f"- 🟡 Minor: {severity_counts.get('minor', 0)}",
            f"- 🔵 Administrative: {severity_counts.get('administrative', 0)}",
            "",
            "### By Type:",
        ]
        for dtype, count in type_counts.most_common():
            lines.append(f"- {dtype.replace('_', ' ').title()}: {count}")
        
        sites = _ds.get_sites()
        lines.append(f"\nSites with deviations: {len(set(d.site_id for d in all_devs))}/{len(sites)}")
        
        return "\n".join(lines)


@mcp.tool()
def score_site_risk(site_id: str = "", top_n: int = 10, order: str = "desc") -> str:
    """Get risk scores for clinical trial sites.
    
    Calculates composite risk scores using severity-weighted deviations,
    trend analysis, repetition patterns, and recency bias.
    
    Args:
        site_id: Optional specific site ID. If empty, returns top N sites by risk.
        top_n: Number of sites to show (default 10). Only used when site_id is empty.
        order: Sort order — 'desc' for highest-risk first (default), 'asc' for lowest-risk first.
    """
    if site_id:
        rp = _ds.get_risk_profile(site_id)
        if rp:
            trend_icon = {"rising": "📈", "stable": "➡️", "declining": "📉"}.get(rp.trend_direction.value, "➡️")
            tier_icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(rp.risk_tier.value, "⚪")
            
            lines = [
                f"## Risk Profile: {rp.site_id} — {rp.site_name}",
                f"**Risk Score:** {rp.risk_score}/100 {tier_icon} {rp.risk_tier.value.upper()}",
                f"**Trend:** {trend_icon} {rp.trend_direction.value.title()}",
                f"**Total Deviations:** {rp.total_deviations} (🔴 {rp.major_count} Major, 🟡 {rp.minor_count} Minor, 🔵 {rp.administrative_count} Admin)",
                f"**Patients Affected:** {rp.patients_affected}/{rp.total_patients}",
                f"**Recent (30d):** {rp.recent_deviations_30d} deviations",
            ]
            
            if rp.repeat_deviation_types:
                lines.append(f"**⚠️ Repeat Patterns:** {', '.join(rp.repeat_deviation_types)}")
            
            if rp.top_risk_factors:
                lines.append("\n### Risk Factors:")
                for rf in rp.top_risk_factors:
                    lines.append(f"- **{rf.factor_name}** (+{rf.contribution:.1f} pts): {rf.description}")
            
            return "\n".join(lines)
        else:
            return f"Site '{site_id}' not found."
    
    else:
        profiles = _ds.get_risk_profiles()  # already sorted descending by score
        if order == "asc":
            # Reverse to get lowest-risk sites first
            ordered = list(reversed(profiles))
            label = "Lowest-Risk"
            heading = f"## Top {min(top_n, len(ordered))} Lowest-Risk Sites\n"
        else:
            ordered = profiles
            label = "Highest-Risk"
            heading = f"## Top {min(top_n, len(ordered))} Highest-Risk Sites\n"
        
        selected = ordered[:top_n]
        lines = [heading]
        
        for i, rp in enumerate(selected, 1):
            tier_icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(rp.risk_tier.value, "⚪")
            trend_icon = {"rising": "📈", "stable": "➡️", "declining": "📉"}.get(rp.trend_direction.value, "➡️")
            lines.append(
                f"{i}. {tier_icon} **{rp.site_id}** — {rp.site_name} | "
                f"Score: **{rp.risk_score}**/100 | {rp.total_deviations} deviations | "
                f"{trend_icon} {rp.trend_direction.value.title()}"
            )
        
        return "\n".join(lines)


@mcp.tool()
def generate_capa_report(site_id: str) -> str:
    """Generate a CAPA (Corrective and Preventive Action) report for a site.
    
    Creates a regulatory-standard CAPA report with findings, root cause
    analysis, corrective actions, preventive actions, and timeline.
    
    Args:
        site_id: The site ID to generate the report for (e.g., 'SITE-042').
    """
    site = _ds.get_site(site_id)
    if not site:
        return f"Site '{site_id}' not found. Use format SITE-001 through SITE-210."
    
    site_devs = _ds.get_deviations_for_site(site_id)
    risk_profile = _ds.get_risk_profile(site_id)
    
    report = _ds.generate_capa_report(
        site_id=site_id,
        site_name=site.site_name,
        deviations=site_devs,
        risk_profile=risk_profile,
    )
    
    return report.full_report_markdown


@mcp.tool()
def classify_deviation(deviation_description: str) -> str:
    """Classify a deviation description by ICH E6 GCP severity.
    
    Given a description of a protocol deviation, explains how it would
    be classified under ICH E6(R2) guidelines and what action is required.
    
    Args:
        deviation_description: Description of the deviation to classify.
    """
    desc_lower = deviation_description.lower()
    
    # Determine type and severity from description
    if "missed" in desc_lower or "did not attend" in desc_lower or "no show" in desc_lower:
        classification = (
            "**Classification: 🔴 MAJOR**\n\n"
            "Per ICH E6(R2), a missed visit is classified as Major because it:\n"
            "- May compromise data integrity (missing efficacy/safety data points)\n"
            "- Could affect the scientific validity of the trial\n"
            "- Represents a complete failure to follow the protocol schedule\n\n"
            "**Required Actions:**\n"
            "1. Document in deviation log within 24 hours\n"
            "2. Notify sponsor/CRA\n"
            "3. Attempt to reschedule patient within 7 days\n"
            "4. Include in next monitoring report"
        )
    elif "dose" in desc_lower or "dosing" in desc_lower or "mg" in desc_lower:
        classification = (
            "**Classification: Depends on deviation magnitude**\n\n"
            "Per ICH E6(R2) and protocol PHOENIX-301:\n"
            "- 🔴 **MAJOR** if dose deviation >20% — may affect patient safety\n"
            "- 🟡 **MINOR** if dose deviation 5-20% — non-compliance but limited risk\n"
            "- 🔵 **ADMINISTRATIVE** if dose deviation <5% — within acceptable range\n\n"
            "**Required Actions for Major:**\n"
            "1. Immediate safety assessment by Medical Monitor\n"
            "2. Patient follow-up for adverse events\n"
            "3. Root cause investigation (calculation error? dispensing error?)\n"
            "4. Re-training of dispensing staff"
        )
    elif "medication" in desc_lower or "drug" in desc_lower or "co-med" in desc_lower:
        classification = (
            "**Classification: Depends on interaction severity**\n\n"
            "Per ICH E6(R2) Section 6.5 (Prohibited Medications):\n"
            "- 🔴 **MAJOR** if the medication has high interaction risk with PNX-301 "
            "(e.g., Warfarin, Ketoconazole, Rifampin, Methotrexate)\n"
            "- 🟡 **MINOR** if the interaction is moderate "
            "(e.g., Phenytoin, Itraconazole, Simvastatin)\n\n"
            "**Required Actions:**\n"
            "1. Immediate drug interaction assessment\n"
            "2. Consult Medical Monitor for safety decision\n"
            "3. Discontinue prohibited medication if medically safe\n"
            "4. Monitor patient for adverse events"
        )
    elif "late" in desc_lower or "delayed" in desc_lower or "overdue" in desc_lower:
        classification = (
            "**Classification: Based on days outside visit window**\n\n"
            "Per ICH E6(R2) and protocol visit schedules:\n"
            "- 🔴 **MAJOR** if >30 days beyond visit window\n"
            "- 🟡 **MINOR** if 7-30 days beyond visit window\n"
            "- 🔵 **ADMINISTRATIVE** if 1-7 days beyond window\n\n"
            "**Required Actions for Major:**\n"
            "1. Document in deviation log\n"
            "2. Assess impact on data integrity\n"
            "3. Implement patient reminder system\n"
            "4. Review site scheduling practices"
        )
    else:
        classification = (
            "**Cannot definitively classify without specific details.**\n\n"
            "To classify a deviation under ICH E6(R2), I need:\n"
            "- The type of deviation (visit timing, dosing, co-medication, assessment)\n"
            "- The magnitude (how far from protocol specification)\n"
            "- The specific protocol rule violated\n\n"
            "Please provide more details, or use `detect_deviations` to scan "
            "actual patient records against the protocol."
        )
    
    return classification


@mcp.tool()
def get_trial_summary() -> str:
    """Get a comprehensive summary of the PHOENIX-301 clinical trial status.
    
    Returns trial-wide statistics including site counts, patient counts,
    deviation summary, and risk tier distribution.
    """
    stats = _ds.get_trial_statistics()
    all_devs = _ds.get_all_deviations()
    risk_profiles = _ds.get_risk_profiles()
    
    from collections import Counter
    severity_counts = Counter(d.severity for d in all_devs)
    tier_counts = Counter(rp.risk_tier.value for rp in risk_profiles)
    
    lines = [
        "## PHOENIX-301 Clinical Trial — Status Dashboard",
        "",
        "### Trial Overview",
        f"- **Sites:** {stats['total_sites']} across {stats['countries']} countries",
        f"- **Patients Enrolled:** {stats['total_patients']}",
        f"- **Total Visits Recorded:** {stats['total_visits']}",
        f"- **Protocol:** Phase III, Advanced NSCLC, Phoenixin (PNX-301)",
        "",
        "### Deviation Summary",
        f"- **Total Deviations Detected:** {len(all_devs)}",
        f"  - 🔴 Major: {severity_counts.get('major', 0)}",
        f"  - 🟡 Minor: {severity_counts.get('minor', 0)}",
        f"  - 🔵 Administrative: {severity_counts.get('administrative', 0)}",
        "",
        "### Site Risk Distribution",
        f"  - 🔴 Critical: {tier_counts.get('critical', 0)} sites",
        f"  - 🟠 High: {tier_counts.get('high', 0)} sites",
        f"  - 🟡 Medium: {tier_counts.get('medium', 0)} sites",
        f"  - 🟢 Low: {tier_counts.get('low', 0)} sites",
        "",
        "### Key Alerts",
    ]
    
    # Top 3 critical sites
    critical_sites = [rp for rp in risk_profiles if rp.risk_tier.value == "critical"]
    if critical_sites:
        lines.append(f"⚠️ **{len(critical_sites)} site(s) at CRITICAL risk level:**")
        for rp in critical_sites[:3]:
            lines.append(f"  - {rp.site_id} ({rp.site_name}): Score {rp.risk_score}/100")
    else:
        lines.append("✅ No sites at Critical risk level.")
    
    # Rising trends
    rising = [rp for rp in risk_profiles if rp.trend_direction.value == "rising"]
    if rising:
        lines.append(f"\n📈 **{len(rising)} site(s) with RISING deviation trends** — requires attention")
    
    # Data source info
    ds_type = type(_ds).__name__
    lines.append(f"\n*Data source: {ds_type}*")
    
    return "\n".join(lines)



@mcp.tool()
def filter_sites_by_score_range(min_score: float = 0, max_score: float = 100) -> str:
    """Get all clinical trial sites whose risk score falls within a specified range.

    Useful for questions like 'show sites with score between 10 and 40',
    'which sites score around 20-50?', or 'sites in the medium range'.

    Args:
        min_score: Minimum risk score (inclusive), 0-100.
        max_score: Maximum risk score (inclusive), 0-100.
    """
    if min_score > max_score:
        min_score, max_score = max_score, min_score

    min_score = max(0.0, min_score)
    max_score = min(100.0, max_score)

    profiles = _ds.get_risk_profiles()  # already sorted descending by score
    matched = [rp for rp in profiles if min_score <= rp.risk_score <= max_score]

    if not matched:
        return (
            f"## No Sites Found in Score Range {min_score:.0f}–{max_score:.0f}\n\n"
            f"No sites currently have a risk score between **{min_score:.0f}** and **{max_score:.0f}**.\n\n"
            f"Try widening the range, or use `score_site_risk` to see the full ranking."
        )

    lines = [
        f"## Sites with Risk Score {min_score:.0f}–{max_score:.0f} ({len(matched)} found)\n"
    ]

    for i, rp in enumerate(matched, 1):
        tier_icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(
            rp.risk_tier.value, "⚪"
        )
        trend_icon = {"rising": "📈", "stable": "➡️", "declining": "📉"}.get(
            rp.trend_direction.value, "➡️"
        )
        lines.append(
            f"{i}. {tier_icon} **{rp.site_id}** — {rp.site_name} | "
            f"Score: **{rp.risk_score}**/100 ({rp.risk_tier.value.upper()}) | "
            f"{rp.total_deviations} deviations | {trend_icon} {rp.trend_direction.value.title()}"
        )

    return "\n".join(lines)


@mcp.tool()
def get_site_details(site_id: str) -> str:
    """Get full details for a specific clinical trial site.

    Returns location, principal investigator, patient count, enrollment info,
    risk profile, and a breakdown of all deviation types for that site.

    Args:
        site_id: The site ID to look up (e.g., 'SITE-042').
    """
    site = _ds.get_site(site_id)
    if not site:
        return f"Site '{site_id}' not found. Use format SITE-001 through SITE-210."

    rp = _ds.get_risk_profile(site_id)
    devs = _ds.get_deviations_for_site(site_id)

    from collections import Counter
    type_counts = Counter(d.deviation_type.value for d in devs)
    sev_counts = Counter(d.severity for d in devs)

    tier_icon = {
        "critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"
    }.get(rp.risk_tier.value if rp else "low", "⚪")

    lines = [
        f"## Site: {site.site_id} — {site.site_name}",
        f"**Location:** {site.city}, {site.country}",
        f"**Principal Investigator:** {site.principal_investigator}",
        f"**Patients Enrolled:** {len(site.patients)}",
    ]

    if rp:
        trend_icon = {"rising": "📈", "stable": "➡️", "declining": "📉"}.get(
            rp.trend_direction.value, "➡️"
        )
        lines += [
            "",
            f"### Risk Profile",
            f"- **Score:** {rp.risk_score}/100 {tier_icon} ({rp.risk_tier.value.upper()})",
            f"- **Trend:** {trend_icon} {rp.trend_direction.value.title()}",
            f"- **Total Deviations:** {rp.total_deviations}",
            f"- **Patients Affected:** {rp.patients_affected}/{rp.total_patients}",
            f"- **Recent (30d):** {rp.recent_deviations_30d} deviations",
            f"- 🔴 Major: {rp.major_count}  🟡 Minor: {rp.minor_count}  🔵 Admin: {rp.administrative_count}",
        ]

        if rp.repeat_deviation_types:
            lines.append(f"- **⚠️ Repeat Patterns:** {', '.join(rp.repeat_deviation_types)}")

    if type_counts:
        lines.append("\n### Deviation Type Breakdown")
        for dtype, count in type_counts.most_common():
            lines.append(f"- {dtype.replace('_', ' ').title()}: {count}")

    return "\n".join(lines)


@mcp.tool()
def get_sites_by_country(country: str = "") -> str:
    """Get a summary of all clinical trial sites grouped by country.

    Returns site counts, patient counts, average risk scores per country.
    If country is specified, lists all sites in that country with their risk tier.

    Args:
        country: Optional country name (e.g., 'USA', 'Germany'). If empty, returns all countries.
    """
    from collections import defaultdict

    sites = _ds.get_sites()
    profiles = {rp.site_id: rp for rp in _ds.get_risk_profiles()}

    if country:
        # Filter by country (case-insensitive)
        matched = [s for s in sites if country.lower() in s.country.lower()]
        if not matched:
            # List available countries
            available = sorted(set(s.country for s in sites))
            return (
                f"No sites found for country: '{country}'.\n\n"
                f"**Available countries ({len(available)}):**\n" +
                ", ".join(available)
            )

        lines = [
            f"## Sites in {matched[0].country} ({len(matched)} sites)\n"
        ]
        for s in sorted(matched, key=lambda x: x.site_id):
            rp = profiles.get(s.site_id)
            tier_icon = {
                "critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"
            }.get(rp.risk_tier.value if rp else "low", "⚪")
            score_str = f"{rp.risk_score}/100" if rp else "N/A"
            lines.append(
                f"- {tier_icon} **{s.site_id}** — {s.site_name} | "
                f"Score: {score_str} | PI: {s.principal_investigator} | "
                f"Patients: {len(s.patients)}"
            )
        return "\n".join(lines)

    else:
        # Aggregate by country
        country_data = defaultdict(lambda: {"sites": [], "patients": 0, "scores": []})
        for s in sites:
            rp = profiles.get(s.site_id)
            country_data[s.country]["sites"].append(s.site_id)
            country_data[s.country]["patients"] += len(s.patients)
            if rp:
                country_data[s.country]["scores"].append(rp.risk_score)

        lines = [f"## Trial Country Distribution ({len(country_data)} countries)\n"]
        sorted_countries = sorted(
            country_data.items(),
            key=lambda x: len(x[1]["sites"]),
            reverse=True
        )
        for ctry, data in sorted_countries:
            avg_score = (
                round(sum(data["scores"]) / len(data["scores"]), 1)
                if data["scores"] else 0
            )
            lines.append(
                f"- **{ctry}** — {len(data['sites'])} sites | "
                f"{data['patients']} patients | Avg risk: {avg_score}/100"
            )

        return "\n".join(lines)


@mcp.tool()
def get_sites_by_tier(tier: str = "critical", top_n: int = 10) -> str:
    """Get all sites at a specific risk tier level.

    Args:
        tier: Risk tier to filter by — 'critical', 'high', 'medium', or 'low'.
        top_n: Maximum number of sites to return (default 10).
    """
    tier_lower = tier.lower().strip()
    valid_tiers = {"critical", "high", "medium", "low"}
    if tier_lower not in valid_tiers:
        return (
            f"Invalid tier '{tier}'. Valid tiers: critical, high, medium, low.\n\n"
            f"**Examples:**\n"
            f"- 'Show me critical sites'\n"
            f"- 'Which sites are at high risk?'\n"
            f"- 'List low-risk sites'"
        )

    profiles = _ds.get_risk_profiles()
    matched = [rp for rp in profiles if rp.risk_tier.value == tier_lower]

    tier_icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(tier_lower, "⚪")

    if not matched:
        return f"No sites currently at **{tier_lower.upper()}** risk tier."

    lines = [
        f"## {tier_icon} {tier_lower.upper()} Risk Sites ({len(matched)} total)\n"
    ]

    for i, rp in enumerate(matched[:top_n], 1):
        trend_icon = {"rising": "📈", "stable": "➡️", "declining": "📉"}.get(
            rp.trend_direction.value, "➡️"
        )
        lines.append(
            f"{i}. **{rp.site_id}** — {rp.site_name} | "
            f"Score: {rp.risk_score}/100 | {rp.total_deviations} deviations | "
            f"{trend_icon} {rp.trend_direction.value.title()}"
        )

    if len(matched) > top_n:
        lines.append(f"\n*... and {len(matched) - top_n} more {tier_lower} sites.*")

    return "\n".join(lines)


@mcp.tool()
def get_trending_sites(direction: str = "rising", top_n: int = 10) -> str:
    """Get sites by their deviation trend direction.

    Args:
        direction: Trend to filter by — 'rising', 'stable', or 'declining'.
        top_n: Maximum number of sites to return (default 10).
    """
    direction_lower = direction.lower().strip()
    valid_dirs = {"rising", "stable", "declining"}
    if direction_lower not in valid_dirs:
        return f"Invalid direction '{direction}'. Valid values: rising, stable, declining."

    profiles = _ds.get_risk_profiles()
    matched = [rp for rp in profiles if rp.trend_direction.value == direction_lower]

    icon_map = {"rising": "📈", "stable": "➡️", "declining": "📉"}
    trend_icon = icon_map.get(direction_lower, "➡️")

    if not matched:
        return f"No sites currently showing a **{direction_lower}** deviation trend."

    lines = [
        f"## {trend_icon} Sites with {direction_lower.title()} Deviation Trends ({len(matched)} total)\n"
    ]

    if direction_lower == "rising":
        lines.append(
            "⚠️ *These sites are getting worse over time — they require proactive attention.*\n"
        )
    elif direction_lower == "declining":
        lines.append(
            "✅ *These sites are improving — recent interventions appear to be working.*\n"
        )

    for i, rp in enumerate(matched[:top_n], 1):
        tier_icon = {
            "critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"
        }.get(rp.risk_tier.value, "⚪")
        lines.append(
            f"{i}. {tier_icon} **{rp.site_id}** — {rp.site_name} | "
            f"Score: {rp.risk_score}/100 ({rp.risk_tier.value.upper()}) | "
            f"{rp.total_deviations} deviations"
        )

    if len(matched) > top_n:
        lines.append(f"\n*... and {len(matched) - top_n} more {direction_lower} sites.*")

    return "\n".join(lines)


@mcp.tool()
def get_deviation_type_breakdown(site_id: str = "", deviation_type: str = "") -> str:
    """Analyze deviations by type across the trial or for a specific site.

    Deviation types: missed_visit, late_visit, early_visit, wrong_dose,
    banned_comedication, missing_assessment.

    Args:
        site_id: Optional site ID to scope to a single site.
        deviation_type: Optional type filter (e.g., 'missed_visit', 'wrong_dose').
                        If empty, returns a breakdown of all types.
    """
    from collections import Counter, defaultdict

    if site_id:
        site = _ds.get_site(site_id)
        if not site:
            return f"Site '{site_id}' not found."
        devs = _ds.get_deviations_for_site(site_id)
        scope_label = f"{site_id} ({site.site_name})"
    else:
        devs = _ds.get_all_deviations()
        scope_label = "All Sites (Trial-Wide)"

    if not devs:
        return f"No deviations found for {scope_label}."

    # Filter by deviation type if specified
    VALID_TYPES = {
        "missed_visit", "late_visit", "early_visit",
        "wrong_dose", "banned_comedication", "missing_assessment"
    }

    if deviation_type:
        dtype_lower = deviation_type.lower().replace(" ", "_")
        if dtype_lower not in VALID_TYPES:
            return (
                f"Unknown deviation type '{deviation_type}'.\n\n"
                f"**Valid types:** {', '.join(sorted(VALID_TYPES))}"
            )

        filtered = [d for d in devs if d.deviation_type.value == dtype_lower]
        if not filtered:
            return f"No '{dtype_lower}' deviations found for {scope_label}."

        sev_counts = Counter(d.severity for d in filtered)
        site_counts = Counter(d.site_id for d in filtered)
        lines = [
            f"## {dtype_lower.replace('_', ' ').title()} Deviations — {scope_label}",
            f"**Total:** {len(filtered)}",
            f"- 🔴 Major: {sev_counts.get('major', 0)}",
            f"- 🟡 Minor: {sev_counts.get('minor', 0)}",
            f"- 🔵 Administrative: {sev_counts.get('administrative', 0)}",
        ]

        if not site_id:
            lines.append(f"\n**Top Sites with this deviation type:**")
            profiles = {rp.site_id: rp for rp in _ds.get_risk_profiles()}
            for sid, count in site_counts.most_common(10):
                rp = profiles.get(sid)
                site = _ds.get_site(sid)
                name = site.site_name if site else sid
                lines.append(f"- **{sid}** ({name}): {count} deviations")

        return "\n".join(lines)

    else:
        # Full breakdown by type
        type_counts = Counter(d.deviation_type.value for d in devs)
        sev_counts = Counter(d.severity for d in devs)

        TYPE_ICONS = {
            "missed_visit": "🚫",
            "late_visit": "⏰",
            "early_visit": "⏩",
            "wrong_dose": "💊",
            "banned_comedication": "⚠️",
            "missing_assessment": "📋",
        }

        lines = [
            f"## Deviation Type Breakdown — {scope_label}",
            f"**Total Deviations:** {len(devs)}",
            f"- 🔴 Major: {sev_counts.get('major', 0)}",
            f"- 🟡 Minor: {sev_counts.get('minor', 0)}",
            f"- 🔵 Administrative: {sev_counts.get('administrative', 0)}",
            "",
            "### By Type:",
        ]

        for dtype, count in type_counts.most_common():
            icon = TYPE_ICONS.get(dtype, "•")
            pct = round(count / len(devs) * 100, 1)
            lines.append(
                f"- {icon} **{dtype.replace('_', ' ').title()}**: {count} ({pct}%)"
            )

        return "\n".join(lines)


# ──────────────────────────────────────────────────────────
#  MCP RESOURCES — Application-controlled (data Bob can read)
# ──────────────────────────────────────────────────────────

@mcp.resource("trial://protocol")
def get_protocol_resource() -> str:
    """The PHOENIX-301 protocol specification.
    
    Contains visit schedule, dosing rules, and prohibited medications.
    """
    p = _protocol
    lines = [
        f"# Protocol: {p.protocol_id}",
        f"**Title:** {p.protocol_title}",
        f"**Phase:** {p.phase}",
        f"**Indication:** {p.indication}",
        f"**Sponsor:** {p.sponsor}",
        "",
        "## Visit Schedule",
    ]
    
    for v in p.visits:
        lines.append(
            f"- Visit {v.visit_number}: {v.visit_name} (Day {v.target_day}, "
            f"Window: -{v.window_before}/+{v.window_after} days)"
        )
    
    lines.append("\n## Dosing Rules")
    for d in p.dose_rules:
        lines.append(f"- {d.drug_name}: {d.dose_mg}mg {d.route} ({d.frequency})")
    
    lines.append("\n## Prohibited Medications")
    for m in p.banned_medications:
        lines.append(f"- **{m.drug_name}** ({m.drug_class}): {m.reason} [Severity: {m.interaction_severity}]")
    
    return "\n".join(lines)


@mcp.resource("trial://sites/{site_id}")
def get_site_resource(site_id: str) -> str:
    """Detailed data for a specific clinical trial site."""
    site = _ds.get_site(site_id)
    if not site:
        return f"Site '{site_id}' not found."
    
    rp = _ds.get_risk_profile(site_id)
    devs = _ds.get_deviations_for_site(site_id)
    
    lines = [
        f"# Site: {site.site_id} — {site.site_name}",
        f"**Location:** {site.city}, {site.country}",
        f"**Principal Investigator:** {site.principal_investigator}",
        f"**Patients Enrolled:** {len(site.patients)}",
    ]
    
    if rp:
        lines.extend([
            f"**Risk Score:** {rp.risk_score}/100 ({rp.risk_tier.value.upper()})",
            f"**Trend:** {rp.trend_direction.value.title()}",
            f"**Total Deviations:** {rp.total_deviations}",
        ])
    
    if devs:
        lines.append("\n## Recent Deviations:")
        for d in devs[:10]:
            sev_label = str(d.severity or "UNKNOWN").upper()
            lines.append(f"- [{sev_label}] {d.description}")
    
    return "\n".join(lines)


# ──────────────────────────────────────────────────────────
#  MCP PROMPTS — User-controlled (templates for common queries)
# ──────────────────────────────────────────────────────────

@mcp.prompt()
def risk_briefing() -> str:
    """Generate a daily risk briefing for the clinical trial risk manager.
    
    Summarizes the current state of the trial, highlights critical sites,
    and recommends priority actions for today.
    """
    return (
        "You are a clinical trial risk manager reviewing the PHOENIX-301 trial. "
        "Please provide a daily risk briefing that covers:\n"
        "1. Use get_trial_summary to get the current trial status\n"
        "2. Use score_site_risk to identify the top 5 highest-risk sites\n"
        "3. For each critical or high-risk site, use detect_deviations to see specific issues\n"
        "4. Recommend which site should be prioritized for investigation today\n"
        "5. Note any rising trends that need proactive attention\n\n"
        "Format your response as a concise briefing suitable for a morning standup meeting."
    )


@mcp.prompt()
def site_investigation(site_id: str) -> str:
    """Generate a structured investigation prompt for a flagged site.
    
    Creates a step-by-step investigation plan for a specific site
    that has been identified as high-risk.
    
    Args:
        site_id: The site to investigate (e.g., 'SITE-042').
    """
    return (
        f"You are investigating site {site_id} in the PHOENIX-301 clinical trial "
        f"because it has been flagged as high-risk. Please conduct a thorough investigation:\n\n"
        f"1. Use score_site_risk with site_id='{site_id}' to understand the risk profile\n"
        f"2. Use detect_deviations with site_id='{site_id}' to see all deviations\n"
        f"3. Identify patterns: Are deviations clustered around specific patients, "
        f"visit types, or time periods?\n"
        f"4. Use generate_capa_report with site_id='{site_id}' to create the formal report\n"
        f"5. Summarize your findings with:\n"
        f"   - The primary root cause(s)\n"
        f"   - Whether this is a training issue, process issue, or individual error\n"
        f"   - Your recommended immediate corrective actions\n"
        f"   - Whether escalation to the sponsor is warranted"
    )


# Entry point for running the MCP server
if __name__ == "__main__":
    import sys
    mcp.run(transport="stdio")
