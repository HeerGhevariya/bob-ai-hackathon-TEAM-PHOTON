import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'
import { ArrowLeft, MapPin, User, Users, ClipboardList } from 'lucide-react'
import { useChartTheme } from '../utils/useTheme'
import { fetchSiteDetail } from '../utils/api'
import RiskBadge from './RiskBadge'
import TrendArrow from './TrendArrow'

export default function SiteDetail() {
  const { siteId } = useParams()
  const navigate = useNavigate()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const ct = useChartTheme()

  useEffect(() => {
    setLoading(true)
    fetchSiteDetail(siteId)
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [siteId])

  if (loading) return (
    <div className="skeleton-page">
      <div style={{ marginBottom: 20 }}>
        <div className="skeleton skeleton-text short" style={{ height: 28, marginBottom: 12 }} />
        <div className="skeleton skeleton-text wide" style={{ height: 22 }} />
      </div>
      <div className="skeleton-stats-grid">
        {[0,1,2,3].map(i => <div key={i} className="skeleton skeleton-card" />)}
      </div>
      <div className="skeleton skeleton-chart" style={{ height: 260 }} />
    </div>
  )
  if (!data) return <div className="loading">Site not found.</div>

  const { site, risk_profile: rp, deviations, patients } = data

  // Prepare deviation type chart data
  const typeData = {}
  deviations.forEach(d => {
    const label = d.deviation_type.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
    typeData[label] = (typeData[label] || 0) + 1
  })
  const typeChartData = Object.entries(typeData).map(([name, count]) => ({ name, count }))
    .sort((a, b) => b.count - a.count)

  return (
    <div>
      {/* Header */}
      <div className="detail-header">
        <div className="detail-header-info">
          <button className="btn btn-ghost" style={{ marginBottom: 12, fontSize: 12 }}
            onClick={() => navigate('/sites')}>
            <ArrowLeft size={14} /> Back to Leaderboard
          </button>
          <div className="page-header" style={{ marginBottom: 0 }}>
            <h2>{site.site_id} — {site.site_name}</h2>
            <p style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}><MapPin size={13} />{site.city}, {site.country}</span>
              <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}><User size={13} />{site.principal_investigator}</span>
              <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}><Users size={13} />{site.total_patients} patients</span>
            </p>
          </div>
        </div>
        {rp && (
          <div className="detail-score">
            <div className="score-value" style={{
              color: rp.risk_score >= 80 ? 'var(--tier-critical)' :
                     rp.risk_score >= 60 ? 'var(--tier-high)' :
                     rp.risk_score >= 40 ? 'var(--tier-medium)' :
                     'var(--tier-low)'
            }}>
              {rp.risk_score}
            </div>
            <div className="score-label">Risk Score / 100</div>
            <div style={{ marginTop: 8, display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <RiskBadge tier={rp.risk_tier} />
              <TrendArrow direction={rp.trend_direction} />
            </div>
          </div>
        )}
      </div>

      {/* Stats Row */}
      {rp && (
        <div className="stats-grid">
          <div className="stat-card animate-in">
            <div className="stat-label">Total Deviations</div>
            <div className="stat-value">{rp.total_deviations}</div>
          </div>
          <div className="stat-card danger animate-in">
            <div className="stat-label">Major</div>
            <div className="stat-value">{rp.major_count}</div>
          </div>
          <div className="stat-card warning animate-in">
            <div className="stat-label">Minor</div>
            <div className="stat-value">{rp.minor_count}</div>
          </div>
          <div className="stat-card animate-in">
            <div className="stat-label">Patients Affected</div>
            <div className="stat-value">{rp.patients_affected}/{rp.total_patients}</div>
          </div>
        </div>
      )}

      {/* Risk Factors & Deviation Types */}
      <div className="grid-2" style={{ marginBottom: 28 }}>
        {rp?.top_risk_factors?.length > 0 && (
          <div className="card animate-in">
            <div className="chart-title">Top Risk Factors</div>
            {rp.top_risk_factors.map((rf, i) => (
              <div key={i} style={{
                padding: '10px 0',
                borderBottom: i < rp.top_risk_factors.length - 1 ? '1px solid var(--border)' : 'none'
              }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 4 }}>
                  {rf.factor_name}
                  <span style={{ float: 'right', color: 'var(--accent)', fontSize: 12 }}>
                    +{rf.contribution.toFixed(1)} pts
                  </span>
                </div>
                <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                  {rf.description}
                </div>
              </div>
            ))}
          </div>
        )}

        {typeChartData.length > 0 && (
          <div className="chart-container animate-in">
            <div className="chart-title">Deviation Types</div>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={typeChartData} layout="vertical" margin={{ left: 10, right: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={ct.grid} />
                <XAxis type="number" tick={{ fill: ct.tick, fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis dataKey="name" type="category" tick={{ fill: ct.tick, fontSize: 11 }} axisLine={false} tickLine={false} width={130} />
                <Tooltip contentStyle={ct.tooltip} />
                <Bar dataKey="count" fill={ct.accent} radius={[0, 4, 4, 0]} barSize={14} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {/* CAPA Button */}
      <div style={{ marginBottom: 28 }}>
        <button className="btn btn-primary" onClick={() => navigate(`/capa/${site.site_id}`)}>
          Generate CAPA Report for {site.site_id}
        </button>
      </div>

      {/* Deviations Table */}
      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <div style={{ padding: '16px 24px', borderBottom: '1px solid var(--border)' }}>
          <div className="chart-title" style={{ marginBottom: 0 }}>
            Deviation History ({deviations.length} total)
          </div>
        </div>
        <div className="table-responsive">
          <table className="data-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Patient</th>
                <th>Visit</th>
                <th>Type</th>
                <th>Severity</th>
                <th>Date</th>
                <th>Description</th>
              </tr>
            </thead>
            <tbody>
              {deviations.slice(0, 20).map((d) => (
                <tr key={d.deviation_id}>
                  <td style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: 'monospace' }}>{d.deviation_id}</td>
                  <td style={{ fontWeight: 500 }}>{d.patient_id}</td>
                  <td>{d.visit_name}</td>
                  <td>{d.deviation_type.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}</td>
                  <td>
                    <span className={`badge badge-${d.severity}`}>
                      <span className={`sev-dot ${d.severity === 'administrative' ? 'admin' : d.severity}`} />
                      {d.severity}
                    </span>
                  </td>
                  <td style={{ whiteSpace: 'nowrap' }}>{d.detected_date || '—'}</td>
                  <td style={{ maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontSize: 12 }}>
                    Expected {d.expected_value}, got {d.actual_value}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {deviations.length > 20 && (
          <div style={{ padding: '12px 24px', color: 'var(--text-muted)', fontSize: 12, borderTop: '1px solid var(--border)' }}>
            Showing 20 of {deviations.length} deviations.
            <button className="btn btn-ghost" style={{ marginLeft: 12, padding: '4px 12px', fontSize: 11 }}
              onClick={() => navigate(`/deviations?site_id=${site.site_id}`)}>
              View All →
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
