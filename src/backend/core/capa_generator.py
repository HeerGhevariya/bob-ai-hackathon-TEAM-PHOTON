"""
capa_generator.py — Stage 4: CAPA-Ready Report Generation

Generates Corrective and Preventive Action (CAPA) reports in the format
regulators expect. Each report contains:
- Finding summary
- ICH E6 classification
- Root cause analysis
- Corrective actions (immediate)
- Preventive actions (long-term)
- Timeline and responsible parties

Uses deterministic template-based generation (no AI dependency).
"""

from collections import Counter
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

from .protocol import DeviationType, Severity
from .deviation_detector import Deviation
from .risk_scorer import SiteRiskProfile


@dataclass
class CapaAction:
    """A single corrective or preventive action."""
    action_id: str
    action_type: str  # "corrective" or "preventive"
    description: str
    responsible_party: str
    deadline: str
    priority: str  # "immediate", "short-term", "long-term"
    status: str = "Open"


@dataclass
class CapaReport:
    """A complete CAPA report for a site or set of deviations."""
    report_id: str
    site_id: str
    site_name: str
    generated_date: date
    report_type: str  # "site_level" or "deviation_specific"
    
    # Summary
    executive_summary: str
    total_findings: int
    severity_breakdown: dict[str, int]
    
    # Classification
    ich_classification: str
    overall_risk_level: str
    
    # Root cause analysis
    root_cause_analysis: str
    contributing_factors: list[str]
    
    # Actions
    corrective_actions: list[CapaAction] = field(default_factory=list)
    preventive_actions: list[CapaAction] = field(default_factory=list)
    
    # Timeline
    timeline_summary: str = ""
    next_review_date: str = ""
    
    # Full markdown report
    full_report_markdown: str = ""


# Root cause templates by deviation type
ROOT_CAUSE_TEMPLATES = {
    DeviationType.MISSED_VISIT: {
        "root_causes": [
            "Inadequate patient follow-up scheduling system",
            "Insufficient patient engagement and reminder protocols",
            "Transportation or accessibility barriers for patients",
            "Staff turnover leading to gaps in patient management"
        ],
        "corrective": [
            ("Implement automated patient reminder system (SMS/phone 72h, 24h, 2h before visit)", 
             "Site Coordinator", "immediate"),
            ("Contact all patients with missed visits to reschedule within 7 days", 
             "Clinical Research Associate", "immediate"),
            ("Review and update patient contact information", 
             "Site Coordinator", "short-term"),
        ],
        "preventive": [
            ("Implement transportation assistance program for patients with access barriers",
             "Site Manager", "short-term"),
            ("Establish backup scheduling protocol for staff absences",
             "Principal Investigator", "short-term"),
            ("Add missed visit rate to monthly site performance dashboard",
             "Clinical Operations", "long-term"),
        ]
    },
    DeviationType.LATE_VISIT: {
        "root_causes": [
            "Visit scheduling not aligned with protocol windows",
            "Site staff unfamiliar with visit window requirements",
            "Overbooking of clinic schedules",
            "Patient non-compliance with scheduled dates"
        ],
        "corrective": [
            ("Re-train site staff on protocol visit windows and acceptable deviation ranges",
             "Clinical Research Associate", "immediate"),
            ("Implement visit window tracking alerts in site management system",
             "Site Coordinator", "immediate"),
            ("Audit all upcoming scheduled visits against protocol windows",
             "Site Coordinator", "short-term"),
        ],
        "preventive": [
            ("Configure automated window alerts in electronic data capture (EDC) system",
             "Data Management", "short-term"),
            ("Include visit window compliance in monthly monitoring reports",
             "Clinical Operations", "long-term"),
            ("Implement proactive scheduling — book next visit before patient leaves site",
             "Site Coordinator", "short-term"),
        ]
    },
    DeviationType.WRONG_DOSE: {
        "root_causes": [
            "Dosing calculation error by site staff",
            "Miscommunication between pharmacy and clinical team",
            "Drug supply issue leading to improvised dosing",
            "Incorrect drug accountability records"
        ],
        "corrective": [
            ("Conduct immediate dose reconciliation for all affected patients",
             "Principal Investigator", "immediate"),
            ("Assess patient safety impact and report to safety monitor if dose deviation >20%",
             "Medical Monitor", "immediate"),
            ("Re-train dispensing staff on protocol dose requirements and verification steps",
             "Site Manager", "immediate"),
        ],
        "preventive": [
            ("Implement double-verification protocol for all drug dispensing",
             "Site Manager", "short-term"),
            ("Add automated dose calculation tool to EDC system",
             "Data Management", "long-term"),
            ("Conduct quarterly dosing accuracy audits",
             "Quality Assurance", "long-term"),
        ]
    },
    DeviationType.BANNED_COMEDICATION: {
        "root_causes": [
            "Site staff not checking concomitant medications against prohibited list",
            "Patient started medication with external provider without notifying trial site",
            "Protocol prohibited medications list not readily accessible to site staff",
            "Insufficient patient education on medication restrictions"
        ],
        "corrective": [
            ("Immediately assess drug interaction risk and consult medical monitor",
             "Principal Investigator", "immediate"),
            ("Contact patient to discontinue prohibited medication if medically safe",
             "Principal Investigator", "immediate"),
            ("Document interaction assessment and any adverse events",
             "Clinical Research Associate", "immediate"),
        ],
        "preventive": [
            ("Provide laminated prohibited medications reference card to all site staff",
             "Clinical Operations", "short-term"),
            ("Implement automated co-medication screening in EDC system",
             "Data Management", "long-term"),
            ("Enhance patient education materials about medication restrictions",
             "Clinical Operations", "short-term"),
            ("Establish communication protocol with patients' external healthcare providers",
             "Site Coordinator", "long-term"),
        ]
    },
    DeviationType.MISSING_ASSESSMENT: {
        "root_causes": [
            "Site staff oversight during busy clinic days",
            "Assessment equipment unavailable or under maintenance",
            "Insufficient training on required assessment procedures",
            "Unclear source document worksheets"
        ],
        "corrective": [
            ("Complete missing assessments at next patient contact if clinically valid",
             "Site Coordinator", "immediate"),
            ("Review assessment completion rates for all active patients",
             "Clinical Research Associate", "short-term"),
        ],
        "preventive": [
            ("Implement visit-specific checklists that must be completed before patient departure",
             "Site Coordinator", "short-term"),
            ("Add mandatory assessment fields in EDC that block visit completion without entry",
             "Data Management", "long-term"),
            ("Conduct targeted training on frequently missed assessments",
             "Clinical Research Associate", "short-term"),
        ]
    },
}


class CapaGenerator:
    """
    Generates CAPA (Corrective and Preventive Action) reports.
    
    Reports are generated using deterministic templates that follow
    regulatory standards. Each report is immediately usable for
    regulatory submissions.
    """

    def __init__(self):
        self._report_counter = 0

    def generate_site_report(
        self,
        site_id: str,
        site_name: str,
        deviations: list[Deviation],
        risk_profile: Optional[SiteRiskProfile] = None,
    ) -> CapaReport:
        """Generate a comprehensive CAPA report for a site."""
        self._report_counter += 1
        report_id = f"CAPA-{self._report_counter:04d}"

        if not deviations:
            return CapaReport(
                report_id=report_id,
                site_id=site_id,
                site_name=site_name,
                generated_date=date.today(),
                report_type="site_level",
                executive_summary=f"No protocol deviations detected at {site_name} ({site_id}).",
                total_findings=0,
                severity_breakdown={},
                ich_classification="N/A — No findings",
                overall_risk_level="Low",
                root_cause_analysis="N/A",
                contributing_factors=[],
                full_report_markdown=f"# CAPA Report: {site_name}\n\nNo findings to report.",
            )

        # Analyze deviations
        severity_counts = Counter(d.severity for d in deviations)
        type_counts = Counter(d.deviation_type for d in deviations)
        most_common_type = type_counts.most_common(1)[0][0]
        patients_affected = len(set(d.patient_id for d in deviations))

        # Determine overall risk
        if severity_counts.get("major", 0) > 0:
            overall_risk = "High"
            ich_class = "Major — ICH E6(R2) Section 4.5"
        elif severity_counts.get("minor", 0) > 2:
            overall_risk = "Medium"
            ich_class = "Minor (recurring) — ICH E6(R2) Section 4.5"
        else:
            overall_risk = "Low"
            ich_class = "Administrative — ICH E6(R2) Section 4.5"

        # Executive summary
        exec_summary = self._build_executive_summary(
            site_id, site_name, deviations, severity_counts,
            type_counts, patients_affected, risk_profile
        )

        # Root cause analysis
        root_cause, contributing_factors = self._build_root_cause(
            deviations, type_counts
        )

        # Actions
        corrective_actions = self._build_corrective_actions(
            report_id, deviations, type_counts
        )
        preventive_actions = self._build_preventive_actions(
            report_id, deviations, type_counts
        )

        # Timeline
        timeline = self._build_timeline(corrective_actions, preventive_actions)

        # Full markdown report
        full_report = self._build_markdown_report(
            report_id=report_id,
            site_id=site_id,
            site_name=site_name,
            exec_summary=exec_summary,
            severity_counts=severity_counts,
            type_counts=type_counts,
            patients_affected=patients_affected,
            ich_class=ich_class,
            overall_risk=overall_risk,
            root_cause=root_cause,
            contributing_factors=contributing_factors,
            corrective_actions=corrective_actions,
            preventive_actions=preventive_actions,
            timeline=timeline,
            deviations=deviations,
            risk_profile=risk_profile,
        )

        return CapaReport(
            report_id=report_id,
            site_id=site_id,
            site_name=site_name,
            generated_date=date.today(),
            report_type="site_level",
            executive_summary=exec_summary,
            total_findings=len(deviations),
            severity_breakdown=dict(severity_counts),
            ich_classification=ich_class,
            overall_risk_level=overall_risk,
            root_cause_analysis=root_cause,
            contributing_factors=contributing_factors,
            corrective_actions=corrective_actions,
            preventive_actions=preventive_actions,
            timeline_summary=timeline,
            next_review_date=(date.today() + timedelta(days=14)).isoformat(),
            full_report_markdown=full_report,
        )

    def _build_executive_summary(
        self, site_id, site_name, deviations, severity_counts,
        type_counts, patients_affected, risk_profile
    ) -> str:
        major = severity_counts.get("major", 0)
        minor = severity_counts.get("minor", 0)
        admin = severity_counts.get("administrative", 0)

        risk_text = ""
        if risk_profile:
            risk_text = (
                f" The site's current risk score is {risk_profile.risk_score}/100 "
                f"({risk_profile.risk_tier.value.upper()}), with a "
                f"{risk_profile.trend_direction.value} trend."
            )

        summary = (
            f"This CAPA report documents {len(deviations)} protocol deviation(s) "
            f"identified at {site_name} ({site_id}) during the PHOENIX-301 clinical trial. "
            f"Severity breakdown: {major} Major, {minor} Minor, {admin} Administrative. "
            f"A total of {patients_affected} patient(s) are affected across "
            f"{len(type_counts)} deviation category/categories.{risk_text} "
            f"Immediate corrective actions are required for all Major findings."
        )
        return summary

    def _build_root_cause(
        self, deviations, type_counts
    ) -> tuple[str, list[str]]:
        # Gather root causes from most common deviation types
        all_causes = []
        contributing_factors = []

        for dev_type, count in type_counts.most_common(3):
            template = ROOT_CAUSE_TEMPLATES.get(dev_type)
            if template:
                all_causes.extend(template["root_causes"][:2])
                contributing_factors.append(
                    f"{dev_type.value.replace('_', ' ').title()} "
                    f"({count} occurrence{'s' if count > 1 else ''})"
                )

        root_cause = (
            "Root cause analysis indicates the following potential factors: "
            + "; ".join(all_causes[:4]) + ". "
            "A systematic investigation is recommended to confirm the primary "
            "root cause and ensure corrective actions address the underlying issue."
        )

        return root_cause, contributing_factors

    def _build_corrective_actions(
        self, report_id, deviations, type_counts
    ) -> list[CapaAction]:
        actions = []
        action_counter = 0
        seen_actions = set()

        for dev_type, _count in type_counts.most_common():
            template = ROOT_CAUSE_TEMPLATES.get(dev_type)
            if template:
                for desc, responsible, priority in template["corrective"]:
                    if desc not in seen_actions:
                        action_counter += 1
                        seen_actions.add(desc)
                        days = {"immediate": 3, "short-term": 14, "long-term": 30}
                        deadline = (date.today() + timedelta(days=days.get(priority, 14))).isoformat()
                        actions.append(CapaAction(
                            action_id=f"{report_id}-CA-{action_counter:02d}",
                            action_type="corrective",
                            description=desc,
                            responsible_party=responsible,
                            deadline=deadline,
                            priority=priority,
                        ))

        return actions

    def _build_preventive_actions(
        self, report_id, deviations, type_counts
    ) -> list[CapaAction]:
        actions = []
        action_counter = 0
        seen_actions = set()

        for dev_type, _count in type_counts.most_common():
            template = ROOT_CAUSE_TEMPLATES.get(dev_type)
            if template:
                for desc, responsible, priority in template["preventive"]:
                    if desc not in seen_actions:
                        action_counter += 1
                        seen_actions.add(desc)
                        days = {"immediate": 7, "short-term": 30, "long-term": 90}
                        deadline = (date.today() + timedelta(days=days.get(priority, 30))).isoformat()
                        actions.append(CapaAction(
                            action_id=f"{report_id}-PA-{action_counter:02d}",
                            action_type="preventive",
                            description=desc,
                            responsible_party=responsible,
                            deadline=deadline,
                            priority=priority,
                        ))

        return actions

    def _build_timeline(self, corrective, preventive) -> str:
        immediate = [a for a in corrective + preventive if a.priority == "immediate"]
        short_term = [a for a in corrective + preventive if a.priority == "short-term"]
        long_term = [a for a in corrective + preventive if a.priority == "long-term"]

        return (
            f"Immediate (within 72 hours): {len(immediate)} action(s). "
            f"Short-term (within 14-30 days): {len(short_term)} action(s). "
            f"Long-term (within 90 days): {len(long_term)} action(s). "
            f"Next review date: {(date.today() + timedelta(days=14)).isoformat()}"
        )

    def _build_markdown_report(
        self, report_id, site_id, site_name, exec_summary,
        severity_counts, type_counts, patients_affected,
        ich_class, overall_risk, root_cause, contributing_factors,
        corrective_actions, preventive_actions, timeline,
        deviations, risk_profile
    ) -> str:
        major = severity_counts.get("major", 0)
        minor = severity_counts.get("minor", 0)
        admin = severity_counts.get("administrative", 0)

        md = f"""# CAPA Report — {report_id}

**Site:** {site_name} ({site_id})
**Generated:** {date.today().isoformat()}
**Protocol:** PHOENIX-301
**Classification:** {ich_class}
**Overall Risk Level:** {overall_risk}

---

## 1. Executive Summary

{exec_summary}

---

## 2. Finding Summary

| Metric | Value |
|---|---|
| Total Deviations | {len(deviations)} |
| Major | {major} |
| Minor | {minor} |
| Administrative | {admin} |
| Patients Affected | {patients_affected} |
"""

        if risk_profile:
            md += f"""| Risk Score | {risk_profile.risk_score}/100 ({risk_profile.risk_tier.value.upper()}) |
| Trend | {risk_profile.trend_direction.value.title()} |
"""

        md += f"""
### Deviation Breakdown by Type

| Deviation Type | Count |
|---|---|
"""
        for dev_type, count in type_counts.most_common():
            md += f"| {dev_type.value.replace('_', ' ').title()} | {count} |\n"

        md += f"""
---

## 3. ICH E6 GCP Classification

**Classification:** {ich_class}

Deviations have been classified per ICH E6(R2) Good Clinical Practice guidelines:
- **Major**: May significantly affect subject safety, data integrity, or scientific value
- **Minor**: Unlikely to significantly affect safety/integrity but represents non-compliance
- **Administrative**: Documentation/process errors with no safety or integrity impact

---

## 4. Root Cause Analysis

{root_cause}

### Contributing Factors
"""
        for factor in contributing_factors:
            md += f"- {factor}\n"

        md += """
---

## 5. Corrective Actions (Immediate Response)

| ID | Action | Responsible | Priority | Deadline | Status |
|---|---|---|---|---|---|
"""
        for action in corrective_actions:
            md += (
                f"| {action.action_id} | {action.description} | "
                f"{action.responsible_party} | {action.priority.upper()} | "
                f"{action.deadline} | {action.status} |\n"
            )

        md += """
---

## 6. Preventive Actions (Long-Term Improvements)

| ID | Action | Responsible | Priority | Deadline | Status |
|---|---|---|---|---|---|
"""
        for action in preventive_actions:
            md += (
                f"| {action.action_id} | {action.description} | "
                f"{action.responsible_party} | {action.priority.upper()} | "
                f"{action.deadline} | {action.status} |\n"
            )

        md += f"""
---

## 7. Timeline & Next Steps

{timeline}

**Next Scheduled Review:** {(date.today() + timedelta(days=14)).isoformat()}
**Report prepared by:** TrialGuard AI — Clinical Trial Risk Monitor
**Approval required from:** Principal Investigator, Sponsor Medical Monitor

---

## 8. Detailed Findings

"""
        # List top 10 deviations by severity
        sorted_devs = sorted(
            deviations,
            key=lambda d: {"major": 0, "minor": 1, "administrative": 2}.get(d.severity, 3)
        )

        for i, dev in enumerate(sorted_devs[:10], 1):
            severity_icon = {"major": "🔴", "minor": "🟡", "administrative": "🔵"}.get(
                dev.severity, "⚪"
            )
            md += f"""### Finding {i}: {severity_icon} {dev.deviation_type.value.replace('_', ' ').title()} [{dev.severity.upper() if dev.severity else 'UNCLASSIFIED'}]

- **Deviation ID:** {dev.deviation_id}
- **Patient:** {dev.patient_id}
- **Visit:** {dev.visit_name}
- **Date:** {dev.detected_date.isoformat() if dev.detected_date else 'N/A'}
- **Description:** {dev.description}
- **Expected:** {dev.expected_value}
- **Actual:** {dev.actual_value}
- **Protocol Reference:** {dev.protocol_reference}

"""

        if len(deviations) > 10:
            md += f"\n*... and {len(deviations) - 10} additional finding(s) not shown in this summary.*\n"

        md += """
---

*This report was generated by TrialGuard AI and should be reviewed by the Principal
Investigator and Sponsor Medical Monitor before submission to regulatory authorities.
All classifications follow ICH E6(R2) Good Clinical Practice guidelines.*
"""
        return md
