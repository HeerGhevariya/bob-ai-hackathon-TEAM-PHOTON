import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { fetchCapaReport, fetchSites } from '../utils/api'

export default function CapaReport() {
  const { siteId: paramSiteId } = useParams()
  const navigate = useNavigate()
  const [siteId, setSiteId] = useState(paramSiteId || '')
  const [report, setReport] = useState(null)
  const [loading, setLoading] = useState(false)
  const [topSites, setTopSites] = useState([])

  // Load top risk sites for the selector
  useEffect(() => {
    fetchSites({ limit: 15 })
      .then((data) => setTopSites(data.sites))
      .catch(console.error)
  }, [])

  // Auto-load if siteId is in URL
  useEffect(() => {
    if (paramSiteId) {
      setSiteId(paramSiteId)
      loadReport(paramSiteId)
    }
  }, [paramSiteId])

  function loadReport(id) {
    if (!id) return
    setLoading(true)
    fetchCapaReport(id)
      .then(setReport)
      .catch(console.error)
      .finally(() => setLoading(false))
  }

  return (
    <div>
      <div className="page-header">
        <h2>CAPA Report Generator</h2>
        <p>Generate Corrective and Preventive Action reports for regulatory compliance</p>
      </div>

      {/* Site Selector */}
      {!paramSiteId && (
        <div className="card" style={{ marginBottom: 28 }}>
          <div className="chart-title">Select a Site</div>
          <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 16 }}>
            <input
              className="filter-input"
              type="text"
              placeholder="Enter Site ID (e.g. SITE-042)"
              value={siteId}
              onChange={(e) => setSiteId(e.target.value.toUpperCase())}
              onKeyDown={(e) => e.key === 'Enter' && loadReport(siteId)}
            />
            <button className="btn btn-primary" onClick={() => loadReport(siteId)} disabled={!siteId || loading}>
              {loading ? '⏳ Generating...' : '📋 Generate CAPA Report'}
            </button>
          </div>

          {topSites.length > 0 && (
            <>
              <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 10 }}>
                Or select from highest-risk sites:
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                {topSites.filter(s => s.total_deviations > 0).slice(0, 10).map((s) => (
                  <button
                    key={s.site_id}
                    className="btn btn-ghost"
                    style={{ padding: '6px 14px', fontSize: 12 }}
                    onClick={() => { setSiteId(s.site_id); loadReport(s.site_id) }}
                  >
                    <span style={{
                      color: s.risk_tier === 'critical' ? 'var(--tier-critical)' :
                             s.risk_tier === 'high' ? 'var(--tier-high)' : 'var(--text-secondary)'
                    }}>
                      {s.risk_tier === 'critical' ? '🔴' : s.risk_tier === 'high' ? '🟠' : '🟡'}
                    </span>
                    {s.site_id} — {s.risk_score}/100
                  </button>
                ))}
              </div>
            </>
          )}
        </div>
      )}

      {loading && (
        <div className="loading"><div className="loading-spinner" />Generating CAPA report...</div>
      )}

      {/* Report Display */}
      {report && !loading && (
        <div className="animate-in">

          {/* ── Finding Summary Hero ── */}
          <div style={{
            background: 'linear-gradient(135deg, var(--bg-card) 0%, rgba(0,212,170,0.04) 100%)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius-lg)',
            padding: '28px 32px',
            marginBottom: 24,
            position: 'relative',
            overflow: 'hidden',
          }}>
            {/* Accent top bar */}
            <div style={{
              position: 'absolute', top: 0, left: 0, right: 0, height: 3,
              background: report.overall_risk_level === 'High'
                ? 'linear-gradient(90deg, #ef4444, #f97316)'
                : report.overall_risk_level === 'Medium'
                ? 'linear-gradient(90deg, #f59e0b, #eab308)'
                : 'linear-gradient(90deg, #22c55e, #00d4aa)',
            }} />

            {/* Row 1: Report header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20, flexWrap: 'wrap', gap: 16 }}>
              <div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 600 }}>
                  CAPA Report
                </div>
                <div style={{ fontSize: 22, fontWeight: 800, color: 'var(--accent)', marginTop: 4, letterSpacing: '-0.02em' }}>
                  {report.report_id}
                </div>
                <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 4 }}>
                  {report.site_name} ({report.site_id}) • Generated {report.generated_date}
                </div>
              </div>
              <div style={{ textAlign: 'right' }}>
                <div style={{
                  display: 'inline-flex', alignItems: 'center', gap: 8,
                  padding: '8px 18px', borderRadius: 99,
                  fontSize: 13, fontWeight: 700,
                  background: report.overall_risk_level === 'High' ? 'rgba(239,68,68,0.12)'
                    : report.overall_risk_level === 'Medium' ? 'rgba(245,158,11,0.12)'
                    : 'rgba(34,197,94,0.12)',
                  color: report.overall_risk_level === 'High' ? '#ef4444'
                    : report.overall_risk_level === 'Medium' ? '#f59e0b'
                    : '#22c55e',
                }}>
                  {report.overall_risk_level === 'High' ? '🔴' : report.overall_risk_level === 'Medium' ? '🟡' : '🟢'}
                  {report.overall_risk_level} Risk
                </div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 6 }}>
                  {report.ich_classification}
                </div>
              </div>
            </div>

            {/* Row 2: Key metrics */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 12, marginBottom: 24 }}>
              {[
                { label: 'Total Findings', value: report.total_findings, color: 'var(--text-primary)' },
                { label: 'Major', value: report.severity_breakdown?.major || 0, color: '#ef4444', icon: '🔴' },
                { label: 'Minor', value: report.severity_breakdown?.minor || 0, color: '#f59e0b', icon: '🟡' },
                { label: 'Administrative', value: report.severity_breakdown?.administrative || 0, color: '#3b82f6', icon: '🔵' },
                { label: 'Corrective Actions', value: report.corrective_actions.length, color: 'var(--accent)' },
                { label: 'Preventive Actions', value: report.preventive_actions.length, color: 'var(--accent)' },
              ].map((m, i) => (
                <div key={i} style={{
                  background: 'rgba(255,255,255,0.02)',
                  borderRadius: 'var(--radius-sm)',
                  padding: '14px 16px',
                  border: '1px solid rgba(255,255,255,0.04)',
                }}>
                  <div style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 600, marginBottom: 6 }}>
                    {m.icon || ''} {m.label}
                  </div>
                  <div style={{ fontSize: 26, fontWeight: 800, color: m.color, letterSpacing: '-0.03em', lineHeight: 1 }}>
                    {m.value}
                  </div>
                </div>
              ))}
            </div>

            {/* Row 3: Severity distribution bar */}
            {report.total_findings > 0 && (() => {
              const major = report.severity_breakdown?.major || 0;
              const minor = report.severity_breakdown?.minor || 0;
              const admin = report.severity_breakdown?.administrative || 0;
              const total = major + minor + admin || 1;
              return (
                <div style={{ marginBottom: 20 }}>
                  <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 8 }}>
                    Severity Distribution
                  </div>
                  <div style={{ display: 'flex', height: 28, borderRadius: 8, overflow: 'hidden', gap: 2 }}>
                    {major > 0 && (
                      <div style={{
                        width: `${(major / total) * 100}%`,
                        background: 'linear-gradient(135deg, #ef4444, #dc2626)',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        fontSize: 11, fontWeight: 700, color: '#fff',
                        minWidth: major > 0 ? 40 : 0,
                        transition: 'width 0.6s cubic-bezier(0.4,0,0.2,1)',
                      }}>
                        {major} Major
                      </div>
                    )}
                    {minor > 0 && (
                      <div style={{
                        width: `${(minor / total) * 100}%`,
                        background: 'linear-gradient(135deg, #f59e0b, #d97706)',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        fontSize: 11, fontWeight: 700, color: '#fff',
                        minWidth: minor > 0 ? 40 : 0,
                        transition: 'width 0.6s cubic-bezier(0.4,0,0.2,1)',
                      }}>
                        {minor} Minor
                      </div>
                    )}
                    {admin > 0 && (
                      <div style={{
                        width: `${(admin / total) * 100}%`,
                        background: 'linear-gradient(135deg, #3b82f6, #2563eb)',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        fontSize: 11, fontWeight: 700, color: '#fff',
                        minWidth: admin > 0 ? 40 : 0,
                        transition: 'width 0.6s cubic-bezier(0.4,0,0.2,1)',
                      }}>
                        {admin} Admin
                      </div>
                    )}
                  </div>
                </div>
              );
            })()}

            {/* Row 4: Contributing factors */}
            {report.contributing_factors?.length > 0 && (
              <div style={{ marginBottom: 16 }}>
                <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 8 }}>
                  Contributing Factors
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                  {report.contributing_factors.map((f, i) => (
                    <span key={i} style={{
                      padding: '5px 14px',
                      borderRadius: 99,
                      fontSize: 12,
                      fontWeight: 500,
                      background: 'rgba(255,255,255,0.04)',
                      border: '1px solid rgba(255,255,255,0.08)',
                      color: 'var(--text-secondary)',
                    }}>
                      {f}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* ── Executive Summary Panel ── */}
          <div style={{
            background: 'var(--bg-card)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius)',
            padding: '20px 24px',
            marginBottom: 24,
          }}>
            <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--accent)', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
              Executive Summary
            </div>
            <p style={{ fontSize: 14, lineHeight: 1.7, color: 'var(--text-secondary)', margin: 0 }}>
              {report.executive_summary}
            </p>
          </div>

          {/* ── Action Tracking — THE MAIN SECTION ── */}
          {/* Corrective Actions */}
          <div style={{
            background: 'var(--bg-card)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius-lg)',
            padding: '28px 32px',
            marginBottom: 20,
            borderLeft: '4px solid #ef4444',
          }}>
            <div style={{ fontSize: 18, fontWeight: 800, color: 'var(--text-primary)', marginBottom: 6, display: 'flex', alignItems: 'center', gap: 10 }}>
              🔧 Corrective Actions
              <span style={{
                fontSize: 13, padding: '3px 14px', borderRadius: 99,
                background: 'rgba(239,68,68,0.12)', color: '#ef4444', fontWeight: 700,
              }}>
                {report.corrective_actions.length}
              </span>
            </div>
            <p style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 20, marginTop: 0 }}>
              Immediate response actions to address findings and prevent recurrence
            </p>
            {report.corrective_actions.map((a, i) => (
              <div key={i} style={{
                padding: '18px 20px',
                marginBottom: 10,
                background: 'rgba(255,255,255,0.02)',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid rgba(255,255,255,0.04)',
                transition: 'all 0.2s ease',
              }}>
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: 14 }}>
                  <div style={{
                    minWidth: 32, height: 32, borderRadius: 99,
                    background: a.priority === 'immediate' ? 'rgba(239,68,68,0.15)' : a.priority === 'short-term' ? 'rgba(245,158,11,0.15)' : 'rgba(59,130,246,0.15)',
                    color: a.priority === 'immediate' ? '#ef4444' : a.priority === 'short-term' ? '#f59e0b' : '#3b82f6',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 14, fontWeight: 800, flexShrink: 0,
                  }}>
                    {i + 1}
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 15, color: 'var(--text-primary)', fontWeight: 600, lineHeight: 1.5, marginBottom: 10 }}>
                      {a.description}
                    </div>
                    <div style={{ display: 'flex', gap: 16, fontSize: 13, color: 'var(--text-secondary)', flexWrap: 'wrap', alignItems: 'center' }}>
                      <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                        👤 <strong style={{ color: 'var(--text-primary)', fontWeight: 600 }}>{a.responsible_party}</strong>
                      </span>
                      <span style={{
                        padding: '3px 12px', borderRadius: 99, fontWeight: 700, fontSize: 11,
                        background: a.priority === 'immediate' ? 'rgba(239,68,68,0.15)' : a.priority === 'short-term' ? 'rgba(245,158,11,0.15)' : 'rgba(59,130,246,0.15)',
                        color: a.priority === 'immediate' ? '#ef4444' : a.priority === 'short-term' ? '#f59e0b' : '#3b82f6',
                        textTransform: 'uppercase', letterSpacing: '0.04em',
                      }}>
                        {a.priority}
                      </span>
                      <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}>📅 Due: {a.deadline}</span>
                      <span style={{
                        padding: '3px 12px', borderRadius: 99, fontWeight: 600, fontSize: 11,
                        background: 'rgba(255,255,255,0.04)', color: 'var(--text-muted)',
                      }}>
                        {a.status}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Preventive Actions */}
          <div style={{
            background: 'var(--bg-card)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius-lg)',
            padding: '28px 32px',
            marginBottom: 24,
            borderLeft: '4px solid #00d4aa',
          }}>
            <div style={{ fontSize: 18, fontWeight: 800, color: 'var(--text-primary)', marginBottom: 6, display: 'flex', alignItems: 'center', gap: 10 }}>
              🛡️ Preventive Actions
              <span style={{
                fontSize: 13, padding: '3px 14px', borderRadius: 99,
                background: 'rgba(0,212,170,0.12)', color: '#00d4aa', fontWeight: 700,
              }}>
                {report.preventive_actions.length}
              </span>
            </div>
            <p style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 20, marginTop: 0 }}>
              Long-term improvements to prevent similar deviations from recurring
            </p>
            {report.preventive_actions.map((a, i) => (
              <div key={i} style={{
                padding: '18px 20px',
                marginBottom: 10,
                background: 'rgba(255,255,255,0.02)',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid rgba(255,255,255,0.04)',
                transition: 'all 0.2s ease',
              }}>
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: 14 }}>
                  <div style={{
                    minWidth: 32, height: 32, borderRadius: 99,
                    background: 'rgba(0,212,170,0.12)',
                    color: '#00d4aa',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 14, fontWeight: 800, flexShrink: 0,
                  }}>
                    {i + 1}
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 15, color: 'var(--text-primary)', fontWeight: 600, lineHeight: 1.5, marginBottom: 10 }}>
                      {a.description}
                    </div>
                    <div style={{ display: 'flex', gap: 16, fontSize: 13, color: 'var(--text-secondary)', flexWrap: 'wrap', alignItems: 'center' }}>
                      <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                        👤 <strong style={{ color: 'var(--text-primary)', fontWeight: 600 }}>{a.responsible_party}</strong>
                      </span>
                      <span style={{
                        padding: '3px 12px', borderRadius: 99, fontWeight: 700, fontSize: 11,
                        background: a.priority === 'immediate' ? 'rgba(239,68,68,0.15)' : a.priority === 'short-term' ? 'rgba(245,158,11,0.15)' : 'rgba(59,130,246,0.15)',
                        color: a.priority === 'immediate' ? '#ef4444' : a.priority === 'short-term' ? '#f59e0b' : '#3b82f6',
                        textTransform: 'uppercase', letterSpacing: '0.04em',
                      }}>
                        {a.priority}
                      </span>
                      <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}>📅 Due: {a.deadline}</span>
                      <span style={{
                        padding: '3px 12px', borderRadius: 99, fontWeight: 600, fontSize: 11,
                        background: 'rgba(255,255,255,0.04)', color: 'var(--text-muted)',
                      }}>
                        {a.status}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* ── Timeline & Next Steps ── */}
          <div style={{
            background: 'var(--bg-card)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius)',
            padding: '16px 24px',
            marginBottom: 24,
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: 12,
          }}>
            <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
              ⏱️ {report.timeline_summary}
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <span style={{
                fontSize: 11, fontWeight: 600, padding: '4px 12px', borderRadius: 99,
                background: 'rgba(0,212,170,0.1)', color: 'var(--accent)',
              }}>
                📅 Next Review: {report.next_review_date}
              </span>
            </div>
          </div>

          {/* Print / Navigation Buttons */}
          <div style={{ display: 'flex', gap: 12, marginBottom: 20 }}>
            <button className="btn btn-primary" onClick={() => window.print()}>
              🖨️ Print / Export Report
            </button>
            <button className="btn btn-ghost" onClick={() => navigate(`/sites/${report.site_id}`)}>
              🏥 View Site Detail
            </button>
            <button className="btn btn-ghost" onClick={() => { setReport(null); setSiteId(''); navigate('/capa') }}>
              📋 Generate Another
            </button>
          </div>

          {/* Full Markdown Report (collapsible) */}
          <details style={{ marginTop: 8 }}>
            <summary style={{
              cursor: 'pointer',
              fontSize: 14,
              fontWeight: 600,
              color: 'var(--text-secondary)',
              padding: '12px 0',
              userSelect: 'none',
            }}>
              📄 View Full Regulatory Report (Markdown)
            </summary>
            <div className="capa-report" style={{ marginTop: 12 }}>
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{report.full_report_markdown}</ReactMarkdown>
            </div>
          </details>
        </div>
      )}

      {!report && !loading && !paramSiteId && (
        <div className="empty-state">
          <div className="empty-icon">📋</div>
          <p>Select a site above to generate a CAPA report.</p>
          <p style={{ fontSize: 12, marginTop: 8 }}>
            Reports follow ICH E6(R2) GCP guidelines and include findings, root cause analysis,
            corrective actions, and preventive actions.
          </p>
        </div>
      )}
    </div>
  )
}
