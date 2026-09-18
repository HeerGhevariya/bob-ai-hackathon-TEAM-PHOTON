/**
 * CapaReportPrint.jsx
 *
 * Formal, inspection-ready CAPA report rendered entirely in the browser.
 * This component is HIDDEN on screen (display:none) and revealed only via
 * @media print CSS when the user triggers Print / Save as PDF.
 *
 * Design rules:
 * - All colours are explicit light-theme hex values; no CSS custom properties
 *   that could resolve to dark-mode tokens.
 * - @page header / footer are injected as a real <style> tag at print time
 *   with the actual CAPA number, site, version and demo text baked in
 *   (no attr() tricks). The tag is removed on afterprint.
 * - page-break-inside: avoid is applied to small tables and individual rows
 *   only; Appendix A paginates freely.
 * - The parent component mounts this, waits two rAFs for DOM paint, then
 *   calls window.print().
 */

import { useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'

// ─── Demo mode ───────────────────────────────────────────────────────────────
// Controlled by VITE_DEMO_MODE env variable (default true for hackathon).
// Create src/frontend/.env with VITE_DEMO_MODE=false to remove banners.
const DEMO_MODE = import.meta.env.VITE_DEMO_MODE !== 'false'

// ─── Helpers ─────────────────────────────────────────────────────────────────

function fmtDate(raw) {
  if (!raw) return 'Not recorded'
  try {
    const d = new Date(raw)
    if (isNaN(d)) return raw
    return d.toLocaleDateString('en-GB', {
      day: '2-digit', month: 'short', year: 'numeric',
    }).replace(/ /g, '-')
  } catch { return raw }
}

function fmtUTC(iso) {
  if (!iso) return 'Not recorded'
  try { return new Date(iso).toUTCString() } catch { return iso }
}

function cap(s) {
  if (!s) return ''
  return s.charAt(0).toUpperCase() + s.slice(1)
}

function fmtType(t) {
  return (t || '').replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

function buildDistribution(corrective, preventive) {
  const roles = new Set()
  ;[...corrective, ...preventive].forEach(a => {
    if (a.responsible_party) roles.add(a.responsible_party)
  })
  roles.add('Principal Investigator')
  roles.add('Quality Assurance')
  return Array.from(roles).sort()
}

function groupByRole(actions) {
  const map = {}
  actions.forEach(a => {
    if (!map[a.responsible_party]) map[a.responsible_party] = []
    map[a.responsible_party].push(a)
  })
  return map
}

function subjectsByType(devList) {
  const map = {}
  devList.forEach(d => {
    if (!map[d.deviation_type]) map[d.deviation_type] = new Set()
    map[d.deviation_type].add(d.patient_id)
  })
  const result = {}
  Object.entries(map).forEach(([t, s]) => { result[t] = s.size })
  return result
}

function missingAssessmentCount(devList) {
  return devList.filter(d => d.deviation_type === 'missing_assessment').length
}

// ─── Root cause templates (mirrors capa_generator.py) ────────────────────────
const RCA_TEMPLATES = {
  missed_visit: {
    root_causes: 'Inadequate patient follow-up scheduling system; insufficient patient engagement and reminder protocols.',
    contributing_factors: 'Scheduling process, patient access barriers, staff coverage gaps.',
  },
  late_visit: {
    root_causes: 'Visit scheduling not aligned with protocol windows; site staff unfamiliar with visit window requirements.',
    contributing_factors: 'Scheduling practices, staff training, clinic overbooking.',
  },
  early_visit: {
    root_causes: 'Visit scheduling not aligned with protocol windows; patient attended before allowed window.',
    contributing_factors: 'Scheduling process, patient adherence, visit window communication.',
  },
  wrong_dose: {
    root_causes: 'Dosing calculation error by site staff; miscommunication between pharmacy and clinical team.',
    contributing_factors: 'Dispensing verification process, pharmacy communication, drug accountability records.',
  },
  banned_comedication: {
    root_causes: 'Site staff not checking concomitant medications against prohibited list; patient started medication with external provider without notifying site.',
    contributing_factors: 'Co-medication screening process, patient education, external provider communication.',
  },
  missing_assessment: {
    root_causes: 'Site staff oversight during busy clinic days; assessment equipment unavailable or unclear source document worksheets.',
    contributing_factors: 'Visit checklist adherence, equipment availability, source document clarity.',
  },
}

// ─── Inline style tokens ──────────────────────────────────────────────────────
// All sizes are in pt (text) or mm (spacing) — never px/rem/em — so they are
// independent of the dashboard's root font size and browser zoom.
//
// OLD → NEW summary:
//   page body:   10pt → 12pt, line-height 1.5 → 1.4
//   h2:          12pt → 16pt
//   h3:          10.5pt → 13.5pt
//   p:           10pt → 12pt (inherits from page)
//   table body:  9pt  → 10.5pt
//   table th/td padding: 4pt 5pt / 3pt 5pt → 5pt 7pt (both)
//   table border: 1pt → 0.75pt
//   appTable:    7.5pt → 10.5pt (landscape page)
//   demo/draft stamps: 8.5pt → 9.5pt bold
//   cover box:   9.5pt → 12pt
//   italic note: 8.5pt → 10pt
//   sigTd:       12pt → 42pt tall (≥14mm physical)
//   checkbox:    10pt → 14pt (≈5mm)
//   blank:       minWidth 120pt → 150pt, 9mm tall
//   @page margins: 18/22/15/15mm → 24/24/22/20mm
const S = {
  // Page root: explicit reset blocks Inter + 1.6 line-height from :root
  page: {
    fontFamily: "'Times New Roman','Times',serif",
    fontSize: '12pt',
    color: '#000',
    background: '#fff',
    lineHeight: '1.4',
  },
  // Section heading (h2): 16pt, space above/below per spec
  h2: {
    fontSize: '16pt',
    fontWeight: 'bold',
    borderBottom: '0.75pt solid #000',
    paddingBottom: '4pt',
    marginTop: '18pt',
    marginBottom: '8pt',
    pageBreakAfter: 'avoid',
    color: '#000',
  },
  // Sub-section heading (h3): 13.5pt
  h3: {
    fontSize: '13.5pt',
    fontWeight: 'bold',
    marginTop: '14pt',
    marginBottom: '6pt',
    pageBreakAfter: 'avoid',
    color: '#000',
  },
  // Body paragraph
  p: { marginBottom: '6pt', fontSize: '12pt' },
  // Standard table: 10.5pt, 0.75pt borders, generous padding
  table: {
    width: '100%',
    borderCollapse: 'collapse',
    marginBottom: '14pt',
    fontSize: '10.5pt',
    tableLayout: 'auto',  // allow text wrapping, no clipping
  },
  th: {
    border: '0.75pt solid #888',
    padding: '5pt 7pt',
    background: '#d8d8d8',   // darker grey so it survives photocopying
    fontWeight: 'bold',
    textAlign: 'left',
    color: '#000',
    lineHeight: '1.3',
  },
  td: {
    border: '0.75pt solid #bbb',
    padding: '5pt 7pt',
    verticalAlign: 'top',
    color: '#000',
    background: '#fff',
    lineHeight: '1.3',
    wordBreak: 'break-word',  // prevent clipping in narrow columns
  },
  rowAvoid: { pageBreakInside: 'avoid' },
  // Stamps: 9.5pt bold as specified
  demoStamp: {
    textAlign: 'center',
    fontWeight: 'bold',
    fontSize: '9.5pt',
    color: '#8b0000',
    border: '2pt solid #8b0000',
    padding: '5pt',
    marginBottom: '10pt',
    letterSpacing: '0.04em',
  },
  draftStamp: {
    textAlign: 'center',
    fontWeight: 'bold',
    fontSize: '9.5pt',
    color: '#5a5a00',
    border: '1pt solid #5a5a00',
    padding: '4pt',
    marginBottom: '8pt',
  },
  // Cover metadata box: 12pt
  coverBox: {
    border: '1pt solid #333',
    padding: '10pt 14pt',
    marginBottom: '10pt',
    fontSize: '12pt',
    background: '#fff',
    lineHeight: '1.6',    // generous row height for cover details
  },
  // Cover field row
  row:   { display: 'flex', gap: '8pt', marginBottom: '4pt' },
  label: { minWidth: '150pt', fontWeight: 'bold', flexShrink: 0 },
  // Blank fill-in lines: ≥9mm tall (≈25.5pt), 150pt wide
  blank: {
    borderBottom: '1pt solid #555',
    display: 'inline-block',
    minWidth: '150pt',
    minHeight: '25pt',    // ≈9mm — ensures physical writing space
    verticalAlign: 'bottom',
  },
  // Checkbox: ≈4-5mm → 14pt square
  checkbox: {
    display: 'inline-block',
    width: '14pt',
    height: '14pt',
    border: '1pt solid #000',
    marginRight: '8pt',
    verticalAlign: 'middle',
  },
  sevMajor: { fontWeight: 'bold', color: '#8b0000' },
  sevMinor: { fontStyle: 'italic', color: '#5a3000' },
  sevAdmin: { color: '#333' },
  pageBreak: { pageBreakBefore: 'always' },
  keepTog:   { pageBreakInside: 'avoid' },
  // Signature row: ≥14mm tall → 42pt; role label in cell, rest blank
  sigTd: {
    border: '0.75pt solid #bbb',
    padding: '5pt 7pt',
    minHeight: '42pt',    // ≥14mm physical writing space
    verticalAlign: 'top',
    color: '#000',
    background: '#fff',
  },
  italic: { fontStyle: 'italic', fontSize: '10pt', marginBottom: '6pt' },
  bold:   { fontWeight: 'bold' },
  // Appendix A: landscape page, 10.5pt (same floor as body tables)
  appTable: {
    width: '100%',
    borderCollapse: 'collapse',
    fontSize: '10.5pt',
    tableLayout: 'fixed',   // fixed layout + explicit col widths for landscape
  },
  appTh: {
    border: '0.75pt solid #888',
    padding: '4pt 6pt',
    background: '#d8d8d8',
    fontWeight: 'bold',
    textAlign: 'left',
    color: '#000',
    lineHeight: '1.2',
    wordBreak: 'break-word',
  },
  appTd: {
    border: '0.75pt solid #bbb',
    padding: '4pt 6pt',
    verticalAlign: 'top',
    color: '#000',
    background: '#fff',
    lineHeight: '1.2',
    wordBreak: 'break-word',
  },
}

function sevStyle(sev) {
  if (sev === 'major') return S.sevMajor
  if (sev === 'minor') return S.sevMinor
  return S.sevAdmin
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function Blank({ width = '120pt' }) {
  return <span style={{ ...S.blank, minWidth: width }}>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</span>
}

function Checkbox() {
  return <span style={S.checkbox} />
}

function H2({ id, children }) {
  return <h2 id={id} style={S.h2}>{children}</h2>
}

function H3({ children }) {
  return <h3 style={S.h3}>{children}</h3>
}

function CoverRow({ label, children }) {
  return (
    <div style={S.row}>
      <span style={S.label}>{label}:</span>
      <span>{children}</span>
    </div>
  )
}

// ─── Main component ───────────────────────────────────────────────────────────

export default function CapaReportPrint({ report, protocolConfig, onReady }) {
  const ref = useRef(null)

  useEffect(() => {
    // Two animation frames to ensure the DOM has been painted before print
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        if (onReady) onReady()
      })
    })
  }, [onReady])

  if (!report) return null

  const {
    report_id, site_id, site_name, site_city, site_country,
    principal_investigator, generated_date, generated_at_utc,
    report_version, overall_risk_level, risk_score, risk_tier,
    total_findings, severity_breakdown, highest_severity_label,
    executive_summary, root_cause_analysis, contributing_factors,
    corrective_actions = [], preventive_actions = [],
    next_review_date, deviation_list = [],
    type_action_map = {}, data_source_type,
    total_patients, patients_affected,
  } = report

  const pc = protocolConfig || {}
  const major = severity_breakdown?.major || 0
  const minor = severity_breakdown?.minor || 0
  const admin = severity_breakdown?.administrative || 0
  const distribution = buildDistribution(corrective_actions, preventive_actions)
  const caByRole = groupByRole(corrective_actions)
  const paByRole = groupByRole(preventive_actions)
  const subjByType = subjectsByType(deviation_list)
  const typeSet = [...new Set(deviation_list.map(d => d.deviation_type))]
  const immediateActions = corrective_actions.filter(a => a.priority === 'immediate')
  const typeCountMap = {}
  deviation_list.forEach(d => {
    typeCountMap[d.deviation_type] = (typeCountMap[d.deviation_type] || 0) + 1
  })

  // Mount directly on document.body (outside #root) so that
  // @media print { #root { display:none } } cannot hide this element.
  return createPortal(
    <div id="capa-print-root" ref={ref} style={{ display: 'none' }} aria-hidden="true">
      <div style={S.page}>

        {/* ══════════════════ COVER PAGE ══════════════════════════════════════ */}
        <div style={S.keepTog}>
          {DEMO_MODE && (
            <div style={S.demoStamp}>
              DEMONSTRATION — SYNTHETIC DATA — NOT FOR REGULATORY SUBMISSION
            </div>
          )}
          <div style={S.draftStamp}>
            DRAFT — Generated by TrialGuard AI; requires review and approval by responsible personnel
          </div>

          <h1 style={{ fontSize: '15pt', fontWeight: 'bold', textAlign: 'center', marginBottom: '6pt', marginTop: '10pt', color: '#000' }}>
            Corrective and Preventive Action (CAPA) Report
          </h1>
          <p style={{ textAlign: 'center', fontSize: '9pt', marginBottom: '14pt', color: '#333' }}>
            Prepared by TrialGuard AI | PHOENIX-301 Clinical Trial
          </p>

          <div style={S.coverBox}>
            <CoverRow label="CAPA Report Number">{report_id}</CoverRow>
            <CoverRow label="Protocol">
              PHOENIX-301 — A Phase III, Randomized, Double-Blind Study of Phoenixin (PNX-301)
              versus Standard of Care in Patients with Advanced NSCLC
            </CoverRow>
            <CoverRow label="Site ID">{site_id}</CoverRow>
            <CoverRow label="Site Name">{site_name}</CoverRow>
            <CoverRow label="City / Country">{site_city || 'Not recorded'}, {site_country || 'Not recorded'}</CoverRow>
            <CoverRow label="Principal Investigator">{principal_investigator || 'Not recorded'}</CoverRow>
            <CoverRow label="Sponsor">{pc.sponsor || 'Phoenix Therapeutics Inc.'}</CoverRow>
            <CoverRow label="IND Number"><Blank width="160pt" /></CoverRow>
            <CoverRow label="Report Date">{fmtDate(generated_date)}</CoverRow>
            <CoverRow label="Report Version">{report_version || '1.0'}</CoverRow>
            <CoverRow label="CAPA Status">Open</CoverRow>
            <CoverRow label="Overall Risk">
              {risk_score != null ? `${risk_score}/100` : 'N/A'} — {cap(risk_tier || overall_risk_level || 'N/A')}
            </CoverRow>
            <CoverRow label="Highest Severity">{highest_severity_label || '—'}</CoverRow>
          </div>

          <p style={{ ...S.italic, textAlign: 'center', marginBottom: '12pt' }}>
            CONFIDENTIAL — This document contains proprietary and confidential information.
            It is intended solely for authorised personnel involved in the PHOENIX-301 trial.
            Unauthorised disclosure, copying, or distribution is strictly prohibited.
          </p>

          <div style={S.coverBox}>
            <p style={{ ...S.bold, marginBottom: '4pt' }}>
              Distribution List (roles with actions in this report)
            </p>
            <ul style={{ paddingLeft: '16pt', margin: 0, fontSize: '9pt' }}>
              {distribution.map(role => <li key={role}>{role}</li>)}
            </ul>
          </div>
        </div>

        {/* ══════════════════ DOCUMENT CONTROL + TOC ══════════════════════════ */}
        <div style={S.pageBreak}>
          <H2 id="doc-control">Document Control</H2>
          <table style={S.table}>
            <thead>
              <tr>
                {['Version', 'Date', 'Author', 'Change Description', 'Approved By'].map(h => (
                  <th key={h} style={S.th}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              <tr style={S.rowAvoid}>
                <td style={S.td}>1.0</td>
                <td style={S.td}>{fmtDate(generated_date)}</td>
                <td style={S.td}>TrialGuard AI (automated draft)</td>
                <td style={S.td}>Initial report generation</td>
                <td style={S.td}><Blank /></td>
              </tr>
            </tbody>
          </table>

          <H2 id="toc">Table of Contents</H2>
          {[
            'Cover Page',
            'Document Control and Table of Contents',
            'Decision Summary',
            '1. Purpose and Scope',
            '2. Summary of Findings',
            '3. Impact Assessment',
            '4. Immediate Corrections (72-Hour Actions)',
            '5. Root Cause Analysis',
            '6. Corrective Action Plan',
            '7. Preventive Action Plan',
            '8. Effectiveness Check',
            '9. Notification and Reporting',
            '10. Site Acknowledgement and Approvals',
            '11. Limitations and Assumptions',
            'Appendix A: Deviation Listing',
            'Appendix B: Methodology',
            'Appendix C: Definitions and Abbreviations',
          ].map(item => (
            <p key={item} style={{ marginBottom: '2pt', fontSize: '9.5pt' }}>{item}</p>
          ))}
        </div>

        {/* ══════════════════ DECISION SUMMARY ════════════════════════════════ */}
        <div id="decision-summary" style={{ ...S.pageBreak, ...S.keepTog }}>
          <H2 id="ds">Decision Summary</H2>
          <p style={S.italic}>Self-contained overview for management decision-making.</p>

          {DEMO_MODE && (
            <div style={{ ...S.demoStamp, fontSize: '8pt', marginBottom: '6pt' }}>
              DEMONSTRATION — SYNTHETIC DATA — NOT FOR REGULATORY SUBMISSION
            </div>
          )}

          <table style={S.table}>
            <tbody>
              {[
                ['Site', `${site_name} (${site_id}) — ${site_city || ''}, ${site_country || ''}`],
                ['Risk Score / Tier', `${risk_score != null ? risk_score : 'N/A'}/100 — ${cap(risk_tier || overall_risk_level || 'N/A')}\n(Scale 0–100: Low <25, Medium 25–49, High 50–74, Critical ≥75)`],
                ['Severity Counts', `Major: ${major}  |  Minor: ${minor}  |  Administrative: ${admin}`],
                ['Deviation Types', Object.entries(typeCountMap).map(([t,n]) => `${fmtType(t)} (${n})`).join('; ') || 'None'],
                ['Subjects Affected', `${patients_affected != null ? patients_affected : 'N/A'} of ${total_patients != null ? total_patients : 'N/A'} enrolled`],
                ['Next Review Date', fmtDate(next_review_date)],
              ].map(([label, val]) => (
                <tr key={label} style={S.rowAvoid}>
                  <td style={{ ...S.td, background: '#f5f5f5', fontWeight: 'bold', width: '35%' }}>{label}</td>
                  <td style={{ ...S.td, whiteSpace: 'pre-line' }}>{val}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <H3>Most Urgent Actions (Immediate Priority)</H3>
          {immediateActions.length === 0
            ? <p style={S.p}>No immediate actions identified.</p>
            : (
              <table style={{ ...S.table, ...S.keepTog }}>
                <thead>
                  <tr>
                    {['ID', 'Action', 'Responsible', 'Due Date'].map(h => (
                      <th key={h} style={S.th}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {immediateActions.map(a => (
                    <tr key={a.action_id} style={S.rowAvoid}>
                      <td style={S.td}>{a.action_id}</td>
                      <td style={S.td}>{a.description}</td>
                      <td style={S.td}>{a.responsible_party}</td>
                      <td style={S.td}>{fmtDate(a.deadline)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )
          }

          <H3>Management Decisions Required</H3>
          <table style={{ ...S.table, ...S.keepTog }}>
            <tbody>
              {[
                'CAPA owner assigned',
                'Sponsor confirmation of proposed important protocol deviations',
                'Additional site resources authorised',
                'Escalation to sponsor Medical Monitor',
              ].map(item => (
                <tr key={item} style={S.rowAvoid}>
                  <td style={{ ...S.td, width: '50%' }}>{item}:</td>
                  <td style={{ ...S.td, width: '25%' }}>Decision: <Blank width="60pt" /></td>
                  <td style={{ ...S.td, width: '25%' }}>By: <Blank width="60pt" /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* ══════════════════ §1 PURPOSE AND SCOPE ════════════════════════════ */}
        <div id="sec1" style={S.pageBreak}>
          <H2 id="s1">1. Purpose and Scope</H2>
          <p style={S.p}>
            This report documents protocol deviations detected at {site_name} ({site_id}) during
            the PHOENIX-301 clinical trial, and specifies the corrective and preventive actions
            required to restore compliance and prevent recurrence.
          </p>
          <p style={S.p}>
            <strong>Regulatory basis.</strong> ICH E6(R2) Section 4.5 requires that the
            investigator comply with the protocol agreed upon with the sponsor. Section 5.20
            requires the sponsor to conduct root cause analysis and implement corrective and
            preventive actions whenever non-compliance significantly affects subject protection
            or the reliability of trial results. 21 CFR 312.56(b) requires the sponsor to secure
            compliance or, if unable to do so, discontinue the investigator&apos;s participation.
            Guidance on classification of deviations as &quot;important protocol deviations&quot; follows
            the FDA Draft Guidance &quot;Protocol Deviations for Clinical Investigations of Drugs,
            Biological Products, and Devices&quot; (December 2024, non-binding).
          </p>
          <p style={S.p}>
            <strong>Scope.</strong> This report covers all {total_findings} protocol deviations
            detected at this site through {fmtDate(generated_date)}.
          </p>
        </div>

        {/* ══════════════════ §2 SUMMARY OF FINDINGS ══════════════════════════ */}
        <div id="sec2">
          <H2 id="s2">2. Summary of Findings</H2>
          <p style={S.p}>{executive_summary}</p>

          <H3>Severity Summary</H3>
          <table style={{ ...S.table, ...S.keepTog }}>
            <thead>
              <tr>
                {['Severity', 'Count', 'Classification Rule', 'Proposed IPD'].map(h => (
                  <th key={h} style={S.th}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {[
                ['Major', major, 'TrialGuard rule (see Appendix B)', 'Yes — requires sponsor confirmation'],
                ['Minor', minor, 'TrialGuard rule (see Appendix B)', 'No'],
                ['Administrative', admin, 'TrialGuard rule (see Appendix B)', 'No'],
              ].map(([sev, cnt, rule, ipd]) => (
                <tr key={sev} style={S.rowAvoid}>
                  <td style={{ ...S.td, ...sevStyle(sev.toLowerCase()) }}>{sev}</td>
                  <td style={S.td}>{cnt}</td>
                  <td style={S.td}>{rule}</td>
                  <td style={S.td}>{ipd}</td>
                </tr>
              ))}
              <tr style={{ ...S.rowAvoid, fontWeight: 'bold' }}>
                <td style={S.td}>Total</td>
                <td style={S.td}>{total_findings}</td>
                <td style={S.td} />
                <td style={S.td} />
              </tr>
            </tbody>
          </table>

          <H3>Findings by Deviation Type</H3>
          <table style={S.table}>
            <thead>
              <tr>
                {['Deviation Type', 'Count', 'Subjects Affected', 'Linked Action IDs'].map(h => (
                  <th key={h} style={S.th}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {Object.entries(typeCountMap).map(([type, cnt]) => (
                <tr key={type} style={S.rowAvoid}>
                  <td style={S.td}>{fmtType(type)}</td>
                  <td style={S.td}>{cnt}</td>
                  <td style={S.td}>{subjByType[type] || 0}</td>
                  <td style={S.td}>{(type_action_map[type] || []).join(', ') || '—'}</td>
                </tr>
              ))}
              {Object.keys(typeCountMap).length === 0 && (
                <tr><td colSpan={4} style={S.td}>No deviations recorded.</td></tr>
              )}
            </tbody>
          </table>
        </div>

        {/* ══════════════════ §3 IMPACT ASSESSMENT ════════════════════════════ */}
        <div id="sec3">
          <H2 id="s3">3. Impact Assessment</H2>
          <p style={S.italic}>Template-based draft — to be confirmed by the Medical Monitor.</p>
          <p style={S.p}>
            <strong>Participant safety.</strong>{' '}
            {major > 0
              ? `${major} Major finding(s) have been identified. These may affect subject safety and/or data reliability. Medical Monitor review is required for affected subjects prior to the next patient visit.`
              : 'No Major findings are present. The Medical Monitor should confirm that Minor and Administrative findings do not cumulatively affect subject safety.'}
          </p>
          <p style={S.p}>
            <strong>Data reliability.</strong>{' '}
            {missingAssessmentCount(deviation_list) > 0
              ? `${missingAssessmentCount(deviation_list)} missing assessment finding(s) may result in data gaps that affect evaluability of the primary endpoint.`
              : 'No missing assessment findings were identified; data reliability impact appears limited pending Medical Monitor review.'}
          </p>
          <p style={S.p}>
            <strong>Regulatory reporting.</strong>{' '}
            All Major findings are proposed as important protocol deviations requiring sponsor
            confirmation per the FDA Draft Guidance (December 2024, non-binding). The sponsor
            is responsible for confirming and reporting to regulatory authorities as required.
          </p>
        </div>

        {/* ══════════════════ §4 IMMEDIATE CORRECTIONS ════════════════════════ */}
        <div id="sec4">
          <H2 id="s4">4. Immediate Corrections (Within 72 Hours)</H2>
          {immediateActions.length === 0
            ? <p style={S.p}>No immediate actions identified for this site.</p>
            : (
              <table style={S.table}>
                <thead>
                  <tr>
                    {['Action ID', 'Description', 'Responsible', 'Due Date', 'Status'].map(h => (
                      <th key={h} style={S.th}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {immediateActions.map(a => (
                    <tr key={a.action_id} style={S.rowAvoid}>
                      <td style={S.td}>{a.action_id}</td>
                      <td style={S.td}>{a.description}</td>
                      <td style={S.td}>{a.responsible_party}</td>
                      <td style={S.td}>{fmtDate(a.deadline)}</td>
                      <td style={S.td}>{a.status}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )
          }
        </div>

        {/* ══════════════════ §5 ROOT CAUSE ANALYSIS ══════════════════════════ */}
        <div id="sec5">
          <H2 id="s5">5. Root Cause Analysis</H2>
          <p style={S.p}>{root_cause_analysis}</p>

          {contributing_factors?.length > 0 && (
            <>
              <H3>Contributing Factors</H3>
              <ul style={{ paddingLeft: '16pt', marginBottom: '8pt' }}>
                {contributing_factors.map((f, i) => (
                  <li key={i} style={{ marginBottom: '3pt', fontSize: '9.5pt' }}>{f}</li>
                ))}
              </ul>
            </>
          )}

          {typeSet.map(type => {
            const tmpl = RCA_TEMPLATES[type] || {}
            return (
              <div key={type} style={{ ...S.keepTog, marginBottom: '12pt' }}>
                <H3>{fmtType(type)} — Root Cause Detail</H3>
                <p style={{ ...S.p, fontSize: '9pt' }}>
                  <strong>Potential root causes:</strong> {tmpl.root_causes || 'To be determined during investigation.'}
                </p>
                <p style={{ ...S.p, fontSize: '9pt' }}>
                  <strong>Contributing system / process factors:</strong> {tmpl.contributing_factors || 'To be confirmed during investigation.'}
                </p>
                <p style={{ fontSize: '9pt', fontWeight: 'bold', marginBottom: '2pt' }}>
                  Investigator&apos;s 5-Whys and investigation notes:
                </p>
                {[1,2,3,4,5].map(n => (
                  <div key={n} style={{ borderBottom: '0.5pt solid #ccc', marginBottom: '8pt', paddingBottom: '2pt', fontSize: '9pt' }}>
                    Why {n}: &nbsp;<Blank width="350pt" />
                  </div>
                ))}
              </div>
            )
          })}
        </div>

        {/* ══════════════════ §6 CORRECTIVE ACTION PLAN ═══════════════════════ */}
        <div id="sec6">
          <H2 id="s6">6. Corrective Action Plan</H2>
          <table style={S.table}>
            <thead>
              <tr>
                {['No.', 'Action', 'Linked Finding Type', 'Responsible', 'Priority', 'Due Date', 'Status'].map(h => (
                  <th key={h} style={S.th}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {corrective_actions.map((a, i) => {
                const linkedTypes = Object.entries(type_action_map)
                  .filter(([, ids]) => ids.includes(a.action_id))
                  .map(([t]) => fmtType(t)).join(', ') || '—'
                return (
                  <tr key={a.action_id} style={S.rowAvoid}>
                    <td style={S.td}>{i + 1}</td>
                    <td style={S.td}>{a.description}</td>
                    <td style={S.td}>{linkedTypes}</td>
                    <td style={S.td}>{a.responsible_party}</td>
                    <td style={S.td}>{cap(a.priority)}</td>
                    <td style={S.td}>{fmtDate(a.deadline)}</td>
                    <td style={S.td}>{a.status}</td>
                  </tr>
                )
              })}
              {corrective_actions.length === 0 && (
                <tr><td colSpan={7} style={S.td}>No corrective actions identified.</td></tr>
              )}
            </tbody>
          </table>

          <H3>Corrective Actions by Responsible Role</H3>
          {Object.entries(caByRole).map(([role, actions]) => (
            <div key={role} style={{ ...S.keepTog, marginBottom: '8pt' }}>
              <p style={{ fontWeight: 'bold', fontSize: '9.5pt', marginBottom: '2pt' }}>{role}</p>
              <ul style={{ paddingLeft: '14pt', margin: 0 }}>
                {actions.map(a => (
                  <li key={a.action_id} style={{ fontSize: '9pt', marginBottom: '2pt' }}>
                    {a.action_id} — {a.description} (due {fmtDate(a.deadline)})
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        {/* ══════════════════ §7 PREVENTIVE ACTION PLAN ═══════════════════════ */}
        <div id="sec7">
          <H2 id="s7">7. Preventive Action Plan</H2>
          <table style={S.table}>
            <thead>
              <tr>
                {['No.', 'Action', 'Linked Finding Type', 'Responsible', 'Priority', 'Due Date', 'Status'].map(h => (
                  <th key={h} style={S.th}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {preventive_actions.map((a, i) => {
                const linkedTypes = Object.entries(type_action_map)
                  .filter(([, ids]) => ids.includes(a.action_id))
                  .map(([t]) => fmtType(t)).join(', ') || '—'
                return (
                  <tr key={a.action_id} style={S.rowAvoid}>
                    <td style={S.td}>{i + 1}</td>
                    <td style={S.td}>{a.description}</td>
                    <td style={S.td}>{linkedTypes}</td>
                    <td style={S.td}>{a.responsible_party}</td>
                    <td style={S.td}>{cap(a.priority)}</td>
                    <td style={S.td}>{fmtDate(a.deadline)}</td>
                    <td style={S.td}>{a.status}</td>
                  </tr>
                )
              })}
              {preventive_actions.length === 0 && (
                <tr><td colSpan={7} style={S.td}>No preventive actions identified.</td></tr>
              )}
            </tbody>
          </table>

          <H3>Preventive Actions by Responsible Role</H3>
          {Object.entries(paByRole).map(([role, actions]) => (
            <div key={role} style={{ ...S.keepTog, marginBottom: '8pt' }}>
              <p style={{ fontWeight: 'bold', fontSize: '9.5pt', marginBottom: '2pt' }}>{role}</p>
              <ul style={{ paddingLeft: '14pt', margin: 0 }}>
                {actions.map(a => (
                  <li key={a.action_id} style={{ fontSize: '9pt', marginBottom: '2pt' }}>
                    {a.action_id} — {a.description} (due {fmtDate(a.deadline)})
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        {/* ══════════════════ §8 EFFECTIVENESS CHECK ══════════════════════════ */}
        <div id="sec8">
          <H2 id="s8">8. Effectiveness Check</H2>
          <p style={S.p}>
            For each affected deviation type, the proposed measure is the rate per patient enrolled
            at this site compared with the site&apos;s own current baseline. Targets, review intervals,
            and verifiers are to be completed by the responsible person.
          </p>
          <table style={S.table}>
            <thead>
              <tr>
                {['Deviation Type', 'Current Rate (per patient enrolled)', 'Target Rate', 'Review Interval', 'Verifier', 'Review Date'].map(h => (
                  <th key={h} style={S.th}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {typeSet.map(type => {
                const cnt = typeCountMap[type] || 0
                const rate = (total_patients && total_patients > 0)
                  ? (cnt / total_patients).toFixed(2)
                  : 'N/A'
                return (
                  <tr key={type} style={S.rowAvoid}>
                    <td style={S.td}>{fmtType(type)}</td>
                    <td style={S.td}>{rate}</td>
                    <td style={S.td}><Blank width="60pt" /></td>
                    <td style={S.td}><Blank width="60pt" /></td>
                    <td style={S.td}><Blank width="80pt" /></td>
                    <td style={S.td}>{fmtDate(next_review_date)}</td>
                  </tr>
                )
              })}
              {typeSet.length === 0 && (
                <tr><td colSpan={6} style={S.td}>No deviation types to measure.</td></tr>
              )}
            </tbody>
          </table>
        </div>

        {/* ══════════════════ §9 NOTIFICATION AND REPORTING ═══════════════════ */}
        <div id="sec9" style={S.keepTog}>
          <H2 id="s9">9. Notification and Reporting</H2>
          <table style={S.table}>
            <thead>
              <tr>
                {['Party', 'Notified', 'Date', 'Reference / Method', 'Responsible'].map(h => (
                  <th key={h} style={S.th}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {['Sponsor', 'IRB / Ethics Committee', 'Regulatory Authority'].map(party => (
                <tr key={party} style={S.rowAvoid}>
                  <td style={S.td}>{party}</td>
                  <td style={{ ...S.td, textAlign: 'center' }}><Checkbox /></td>
                  <td style={S.td}><Blank width="60pt" /></td>
                  <td style={S.td}><Blank width="100pt" /></td>
                  <td style={S.td}><Blank width="80pt" /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* ══════════════════ §10 APPROVALS ═══════════════════════════════════ */}
        <div id="sec10" style={S.keepTog}>
          <H2 id="s10">10. Site Acknowledgement and Approvals</H2>
          <H3>Principal Investigator Acknowledgement</H3>
          <p style={{ ...S.p, fontSize: '9pt' }}>
            The Principal Investigator of {site_name} ({site_id}) acknowledges receipt of this
            CAPA Report, confirms that the findings have been reviewed, and commits to implementing
            the corrective and preventive actions within the specified timelines.
          </p>
          <div style={{ marginBottom: '12pt', fontSize: '9pt' }}>
            {[['PI Name (print)', '160pt'], ['PI Signature', '160pt'], ['Date', '120pt']].map(([label, w]) => (
              <div key={label} style={S.row}>
                <span style={S.label}>{label}:</span> <Blank width={w} />
              </div>
            ))}
          </div>

          <H3>Approval Signatures</H3>
          <p style={S.italic}>
            Signatures are handwritten or applied in the sponsor&apos;s validated electronic
            signature system. Leave name, signature, and date blank until signed.
          </p>
          <table style={{ ...S.table, fontSize: '9pt' }}>
            <thead>
              <tr>
                {['Role', 'Meaning of Signature', 'Printed Name', 'Signature', 'Date / Time'].map(h => (
                  <th key={h} style={S.th}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {[
                ['Author', 'Prepared this report'],
                ['Reviewer', 'Reviewed content for accuracy'],
                ['Principal Investigator', 'Approved and acknowledged CAPA'],
                ['Quality Assurance', 'Verified compliance with QA standards'],
                ['Sponsor / Medical Monitor', 'Confirmed and approved on behalf of sponsor'],
              ].map(([role, meaning]) => (
                <tr key={role} style={S.rowAvoid}>
                  <td style={S.sigTd}>{role}</td>
                  <td style={S.sigTd}>{meaning}</td>
                  <td style={S.sigTd}>&nbsp;</td>
                  <td style={S.sigTd}>&nbsp;</td>
                  <td style={S.sigTd}>&nbsp;</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* ══════════════════ §11 LIMITATIONS ═════════════════════════════════ */}
        <div id="sec11" style={S.keepTog}>
          <H2 id="s11">11. Limitations and Assumptions</H2>
          <ul style={{ paddingLeft: '16pt', fontSize: '9.5pt' }}>
            {[
              'This report is a draft generated automatically by TrialGuard AI and requires review and approval by qualified personnel before regulatory submission.',
              'Deviation detection and severity classification are fully deterministic and rule-based. AI (IBM watsonx.ai) was used only to generate explanatory narrative where indicated; it did not alter findings, severities, actions, or risk scores.',
              'Root cause analysis templates are based on deviation types present. The responsible site team must conduct a formal investigation to confirm the primary root cause for each deviation type.',
              'The date of deviation in Appendix A is the actual visit date for timing and dosing deviations, and the scheduled visit date for missed visits. These dates are obtained from the patient visit record in the trial management system.',
              'IND number, sponsor contact, and site street address were not available in the data source at report generation time; blank fields must be completed by the responsible person.',
            ].map((item, i) => (
              <li key={i} style={{ marginBottom: '4pt' }}>{item}</li>
            ))}
            {DEMO_MODE && (
              <li style={{ marginBottom: '4pt', fontWeight: 'bold', color: '#8b0000' }}>
                DEMONSTRATION MODE: The trial, drug, and patient data are simulated for
                demonstration purposes only. This report must not be used for any regulatory,
                clinical, or operational decision.
              </li>
            )}
          </ul>
        </div>

        {/* ══════════════════ APPENDIX A: DEVIATION LISTING ═══════════════════ */}
        <div id="appendix-a" style={S.pageBreak}>
          <H2 id="app-a">Appendix A: Deviation Listing</H2>
          <p style={S.italic}>
            All {deviation_list.length} deviation(s) detected at this site. Table paginates across pages.
            Blank columns (Verified, Resolution, Reported) are for manual completion post-inspection.
          </p>
          {deviation_list.length === 0 ? (
            <p style={S.p}>No deviations recorded for this site.</p>
          ) : (
            <table style={S.appTable}>
              <thead>
                <tr>
                  {[
                    'Finding ID', 'Subject ID', 'Visit', 'Visit Date', 'Detected Date',
                    'Deviation Type', 'Expected', 'Actual', 'Protocol Ref.',
                    'Severity', 'Proposed IPD',
                    'Verified (initials/date)', 'Resolution', 'Reported to Sponsor/IRB',
                  ].map(h => <th key={h} style={S.appTh}>{h}</th>)}
                </tr>
              </thead>
              <tbody>
                {deviation_list.map(d => (
                  <tr key={d.deviation_id}>
                    <td style={S.appTd}>{d.deviation_id}</td>
                    <td style={S.appTd}>{d.patient_id}</td>
                    <td style={S.appTd}>{d.visit_name}</td>
                    <td style={S.appTd}>{fmtDate(d.visit_date)}</td>
                    <td style={S.appTd}>{fmtDate(d.detected_date)}</td>
                    <td style={S.appTd}>{fmtType(d.deviation_type)}</td>
                    <td style={S.appTd}>{d.expected_value}</td>
                    <td style={S.appTd}>{d.actual_value}</td>
                    <td style={S.appTd}>{d.protocol_reference}</td>
                    <td style={{ ...S.appTd, ...sevStyle(d.severity) }}>{cap(d.severity)}</td>
                    <td style={S.appTd}>{d.proposed_ipd || '—'}</td>
                    <td style={S.appTd}>&nbsp;</td>
                    <td style={S.appTd}>&nbsp;</td>
                    <td style={S.appTd}>&nbsp;</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* ══════════════════ APPENDIX B: METHODOLOGY ════════════════════════ */}
        <div id="appendix-b" style={S.pageBreak}>
          <H2 id="app-b">Appendix B: Methodology</H2>
          <p style={S.italic}>
            All values below are read directly from the backend configuration modules at report
            generation time. No values are retyped in the frontend.
            Protocol config version: {pc.protocol_config_version || '1.0'} | Rules version: {pc.rules_version || '1.0'}.
          </p>
          <p style={S.p}>
            <strong>AI role statement.</strong> TrialGuard AI uses rule-based algorithms exclusively
            for deviation detection, severity classification, and risk scoring. IBM watsonx.ai
            (Granite) is used only to generate explanatory prose in the executive summary and root
            cause analysis where labelled &quot;AI-assisted narrative, requires human review.&quot;
            AI does not alter any finding, severity, action, or score.
          </p>

          <H3>B.1 Deviation Detection — Visit Timing Rules</H3>
          <table style={S.table}>
            <thead>
              <tr>
                {['Visit', 'Target Day', 'Window (days before)', 'Window (days after)', 'Required Assessments'].map(h => (
                  <th key={h} style={S.th}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(pc.visit_schedule || []).map(v => (
                <tr key={v.visit_number} style={S.rowAvoid}>
                  <td style={S.td}>{v.visit_name}</td>
                  <td style={S.td}>{v.target_day}</td>
                  <td style={S.td}>{v.window_before}</td>
                  <td style={S.td}>{v.window_after}</td>
                  <td style={{ ...S.td, fontSize: '8pt' }}>{(v.required_assessments || []).join(', ')}</td>
                </tr>
              ))}
              {!(pc.visit_schedule?.length) && (
                <tr><td colSpan={5} style={S.td}>Configuration not loaded.</td></tr>
              )}
            </tbody>
          </table>

          <H3>B.2 Dose Rules</H3>
          <table style={S.table}>
            <thead>
              <tr>
                {['Drug', 'Protocol Dose (mg)', 'Route', 'Frequency', 'Allowed Deviation'].map(h => (
                  <th key={h} style={S.th}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(pc.dose_rules || []).map((dr, i) => (
                <tr key={i} style={S.rowAvoid}>
                  <td style={S.td}>{dr.drug_name}</td>
                  <td style={S.td}>{dr.dose_mg}</td>
                  <td style={S.td}>{dr.route}</td>
                  <td style={S.td}>{dr.frequency}</td>
                  <td style={S.td}>±{dr.allowed_deviation_pct}%</td>
                </tr>
              ))}
              {!(pc.dose_rules?.length) && (
                <tr><td colSpan={5} style={S.td}>Configuration not loaded.</td></tr>
              )}
            </tbody>
          </table>

          <H3>B.3 Prohibited Concomitant Medications</H3>
          <table style={S.table}>
            <thead>
              <tr>
                {['Drug Name', 'Drug Class', 'Reason', 'Interaction Severity'].map(h => (
                  <th key={h} style={S.th}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(pc.banned_medications || []).map(m => (
                <tr key={m.drug_name} style={S.rowAvoid}>
                  <td style={S.td}>{m.drug_name}</td>
                  <td style={S.td}>{m.drug_class}</td>
                  <td style={S.td}>{m.reason}</td>
                  <td style={S.td}>{cap(m.interaction_severity)}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <H3>B.4 Severity Classification (TrialGuard Rules)</H3>
          <p style={{ ...S.p, fontSize: '9pt' }}>
            Severity levels — Major, Minor, Administrative — are TrialGuard&apos;s own classification
            rules. They are not defined by ICH E6(R2) or FDA. &quot;Major&quot; findings are proposed as
            important protocol deviations per the FDA Draft Guidance (December 2024, non-binding)
            and require sponsor confirmation.
          </p>
          {pc.severity_rules && (
            <table style={S.table}>
              <thead>
                <tr>
                  {['Rule Type', 'Major', 'Minor', 'Administrative'].map(h => (
                    <th key={h} style={S.th}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                <tr style={S.rowAvoid}>
                  <td style={S.td}>Timing (days outside window)</td>
                  <td style={S.td}>{pc.severity_rules.timing_thresholds_days?.major}</td>
                  <td style={S.td}>{pc.severity_rules.timing_thresholds_days?.minor}</td>
                  <td style={S.td}>{pc.severity_rules.timing_thresholds_days?.administrative}</td>
                </tr>
                <tr style={S.rowAvoid}>
                  <td style={S.td}>Dose deviation (%)</td>
                  <td style={S.td}>{pc.severity_rules.dose_thresholds_pct?.major}</td>
                  <td style={S.td}>{pc.severity_rules.dose_thresholds_pct?.minor}</td>
                  <td style={S.td}>{pc.severity_rules.dose_thresholds_pct?.administrative} (doses &lt;2% not flagged)</td>
                </tr>
                <tr style={S.rowAvoid}>
                  <td style={S.td}>Banned co-medication</td>
                  <td style={S.td}>{pc.severity_rules.banned_comedication?.major}</td>
                  <td style={S.td}>{pc.severity_rules.banned_comedication?.minor}</td>
                  <td style={S.td}>N/A</td>
                </tr>
                <tr style={S.rowAvoid}>
                  <td style={S.td}>Missed visit</td>
                  <td colSpan={3} style={S.td}>{pc.severity_rules.missed_visit}</td>
                </tr>
                <tr style={S.rowAvoid}>
                  <td style={S.td}>Missing assessment</td>
                  <td style={S.td}>{pc.severity_rules.missing_assessment?.major}</td>
                  <td style={S.td}>{pc.severity_rules.missing_assessment?.minor}</td>
                  <td style={S.td}>{pc.severity_rules.missing_assessment?.administrative}</td>
                </tr>
              </tbody>
            </table>
          )}

          <H3>B.5 Risk Score and Tier Formula</H3>
          {pc.risk_scoring && (
            <>
              <p style={{ ...S.p, fontFamily: 'monospace', fontSize: '9pt' }}>
                {pc.risk_scoring.formula}
              </p>
              <table style={S.table}>
                <thead>
                  <tr>
                    {['Parameter', 'Value'].map(h => <th key={h} style={S.th}>{h}</th>)}
                  </tr>
                </thead>
                <tbody>
                  {[
                    ['Saturation constant k', pc.risk_scoring.score_k],
                    ['Severity weight — Major', pc.risk_scoring.severity_weights?.major],
                    ['Severity weight — Minor', pc.risk_scoring.severity_weights?.minor],
                    ['Severity weight — Administrative', pc.risk_scoring.severity_weights?.administrative],
                    ['Tier: Critical (score ≥)', pc.risk_scoring.tier_thresholds?.critical],
                    ['Tier: High (score ≥)', pc.risk_scoring.tier_thresholds?.high],
                    ['Tier: Medium (score ≥)', pc.risk_scoring.tier_thresholds?.medium],
                    ['Tier: Low (score ≥)', pc.risk_scoring.tier_thresholds?.low],
                    ['Repetition threshold (occurrences)', pc.risk_scoring.repetition_threshold_count],
                    ['Repetition rate bonus', pc.risk_scoring.repetition_rate_bonus],
                    ['Recency window (days)', pc.risk_scoring.recency_window_days],
                    ['Recency rate factor', pc.risk_scoring.recency_rate_factor],
                    ['Trend window (days)', pc.risk_scoring.trend_window_days],
                    ['Trend rising multiplier', pc.risk_scoring.trend_rising_multiplier],
                  ].map(([param, val]) => (
                    <tr key={param} style={S.rowAvoid}>
                      <td style={S.td}>{param}</td>
                      <td style={S.td}>{val ?? '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}

          <H3>B.6 Report Generation Record</H3>
          <table style={S.table}>
            <tbody>
              {[
                ['Data source', data_source_type === 'MockDataSource' ? 'In-memory synthetic data (MockDataSource)' : data_source_type || 'Not recorded'],
                ['Data snapshot timestamp (UTC)', fmtUTC(generated_at_utc)],
                ['Protocol configuration version', pc.protocol_config_version || '1.0'],
                ['Classification rules version', pc.rules_version || '1.0'],
                ['Risk formula version', '1.0'],
                ['Report version', report_version || '1.0'],
              ].map(([label, val]) => (
                <tr key={label} style={S.rowAvoid}>
                  <td style={{ ...S.td, fontWeight: 'bold', width: '45%' }}>{label}</td>
                  <td style={S.td}>{val}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* ══════════════════ APPENDIX C: ABBREVIATIONS ═══════════════════════ */}
        <div id="appendix-c" style={S.pageBreak}>
          <H2 id="app-c">Appendix C: Definitions and Abbreviations</H2>
          <table style={S.table}>
            <thead>
              <tr>
                <th style={S.th}>Abbreviation / Term</th>
                <th style={S.th}>Definition</th>
              </tr>
            </thead>
            <tbody>
              {[
                ['CAPA', 'Corrective and Preventive Action'],
                ['CRA', 'Clinical Research Associate'],
                ['EDC', 'Electronic Data Capture'],
                ['GCP', 'Good Clinical Practice'],
                ['ICH E6(R2)', 'International Council for Harmonisation guideline on Good Clinical Practice, revision 2'],
                ['IND', 'Investigational New Drug application (21 CFR Part 312)'],
                ['Important Protocol Deviation (IPD)', 'A deviation that may affect subject safety, data integrity, or scientific validity; term per FDA Draft Guidance (December 2024, non-binding). Requires sponsor confirmation.'],
                ['IRB', 'Institutional Review Board'],
                ['Major', 'TrialGuard severity classification: proposed important protocol deviation — may significantly affect safety, data reliability, or scientific value.'],
                ['Minor', 'TrialGuard severity classification: non-compliance unlikely to significantly affect safety or data integrity.'],
                ['Administrative', 'TrialGuard severity classification: documentation or process error with no direct impact on safety or data integrity.'],
                ['NSCLC', 'Non-Small Cell Lung Cancer'],
                ['PI', 'Principal Investigator'],
                ['PNX-301', 'Phoenixin — investigational drug in the PHOENIX-301 trial'],
                ['QA', 'Quality Assurance'],
                ['RCA', 'Root Cause Analysis'],
                ['TKI', 'Tyrosine Kinase Inhibitor'],
                ['21 CFR 312.56(b)', 'US Code of Federal Regulations, Title 21, Part 312, Section 56(b) — sponsor duty to secure investigator compliance'],
              ].map(([term, def]) => (
                <tr key={term} style={S.rowAvoid}>
                  <td style={{ ...S.td, fontWeight: 'bold', width: '28%' }}>{term}</td>
                  <td style={S.td}>{def}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

      </div>
    </div>,
    document.body
  )
}
