import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'
import { fetchTrialSummary, fetchTrends } from '../utils/api'
import { SeverityDonut, RiskTierDonut } from './SeverityChart'
import { useChartTheme } from '../utils/useTheme'

export default function TrialOverview() {
  const [summary, setSummary] = useState(null)
  const [trends, setTrends] = useState(null)
  const [loading, setLoading] = useState(true)
  const [currentPage, setCurrentPage] = useState(1)
  const navigate = useNavigate()
  const ct = useChartTheme()
  const ITEMS_PER_PAGE = 5

  useEffect(() => {
    Promise.all([fetchTrialSummary(), fetchTrends()])
      .then(([s, t]) => { setSummary(s); setTrends(t) })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="loading"><div className="loading-spinner" />Loading trial data...</div>
  if (!summary) return <div className="loading">Failed to load data.</div>

  const { overview, deviations, risk_distribution, alerts, trial } = summary

  const totalPages = Math.ceil((alerts?.critical_sites?.length || 0) / ITEMS_PER_PAGE)
  const paginatedSites = alerts?.critical_sites?.slice(
    (currentPage - 1) * ITEMS_PER_PAGE,
    currentPage * ITEMS_PER_PAGE
  ) || []

  return (
    <div>
      <div className="page-header">
        <h2>Trial Overview</h2>
        <p>{trial.protocol_id} — {trial.phase}, {trial.indication}</p>
      </div>

      {/* Stat Cards */}
      <div className="stats-grid">
        <div className="stat-card animate-in">
          <div className="stat-label">Total Sites</div>
          <div className="stat-value">{overview.total_sites}</div>
          <div className="stat-subtitle">{overview.countries} countries</div>
        </div>
        <div className="stat-card animate-in">
          <div className="stat-label">Patients Enrolled</div>
          <div className="stat-value">{overview.total_patients.toLocaleString()}</div>
          <div className="stat-subtitle">{overview.total_visits.toLocaleString()} total visits</div>
        </div>
        <div className="stat-card danger animate-in">
          <div className="stat-label">Total Deviations</div>
          <div className="stat-value">{deviations.total}</div>
          <div className="stat-subtitle">
            🔴 {deviations.by_severity.major || 0} Major • 🟡 {deviations.by_severity.minor || 0} Minor • 🔵 {deviations.by_severity.administrative || 0} Admin
          </div>
        </div>
        <div className="stat-card animate-in" style={alerts.critical_sites.length > 0 ? {borderColor: 'rgba(239,68,68,0.3)'} : {}}>
          <div className="stat-label">Critical Sites</div>
          <div className="stat-value" style={{color: alerts.critical_sites.length > 0 ? 'var(--severity-major)' : 'var(--tier-low)'}}>
            {alerts.critical_sites.length}
          </div>
          <div className="stat-subtitle">
            {alerts.rising_trends} sites with rising trends
          </div>
        </div>
      </div>

      {/* Charts Row */}
      <div className="grid-3" style={{ marginBottom: 28 }}>
        <div className="chart-container animate-in">
          <div className="chart-title">Deviations by Severity</div>
          <SeverityDonut data={deviations.by_severity} />
        </div>
        <div className="chart-container animate-in">
          <div className="chart-title">Site Risk Distribution</div>
          <RiskTierDonut data={risk_distribution} />
        </div>
        <div className="chart-container animate-in">
          <div className="chart-title">Deviations by Type</div>
          {trends?.deviation_type_distribution && (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={trends.deviation_type_distribution} layout="vertical" margin={{ left: 10, right: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={ct.grid} />
                <XAxis type="number" tick={{ fill: ct.tick, fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis dataKey="type" type="category" tick={{ fill: ct.tick, fontSize: 11 }} axisLine={false} tickLine={false} width={110} />
                <Tooltip contentStyle={ct.tooltip} />
                <Bar dataKey="count" fill={ct.accent} radius={[0, 4, 4, 0]} barSize={16} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* Monthly Trend Chart */}
      {trends?.monthly_deviations?.length > 0 && (
        <div className="chart-container animate-in" style={{ marginBottom: 28 }}>
          <div className="chart-title">Monthly Deviation Trend</div>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={trends.monthly_deviations} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={ct.grid} />
              <XAxis dataKey="month" tick={{ fill: ct.tick, fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: ct.tick, fontSize: 11 }} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={ct.tooltip} />
              <Bar dataKey="major" stackId="a" fill="#ef4444" radius={[0, 0, 0, 0]} name="Major" />
              <Bar dataKey="minor" stackId="a" fill="#f59e0b" radius={[0, 0, 0, 0]} name="Minor" />
              <Bar dataKey="administrative" stackId="a" fill="#3b82f6" radius={[4, 4, 0, 0]} name="Administrative" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Alerts Panel */}
      {alerts.critical_sites.length > 0 && (
        <div className="card animate-in" style={{ borderColor: 'rgba(239,68,68,0.2)', background: 'rgba(239,68,68,0.04)' }}>
          <div className="chart-title" style={{ color: 'var(--severity-major)' }}>
            ⚠️ Critical Site Alerts
          </div>
          <table className="data-table">
            <thead>
              <tr>
                <th>Site ID</th>
                <th>Site Name</th>
                <th>Risk Score</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {paginatedSites.map((site) => (
                <tr key={site.site_id} onClick={() => navigate(`/sites/${site.site_id}`)}>
                  <td style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{site.site_id}</td>
                  <td>{site.site_name}</td>
                  <td>
                    <span style={{ color: 'var(--severity-major)', fontWeight: 700 }}>
                      {site.risk_score}/100
                    </span>
                  </td>
                  <td>
                    <button className="btn btn-ghost" style={{ padding: '6px 14px', fontSize: 12 }}
                      onClick={(e) => { e.stopPropagation(); navigate(`/capa/${site.site_id}`) }}>
                      📋 Generate CAPA
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {totalPages > 1 && (
            <div className="pagination">
              <div className="pagination-info">
                Showing {(currentPage - 1) * ITEMS_PER_PAGE + 1} - {Math.min(currentPage * ITEMS_PER_PAGE, alerts.critical_sites.length)} of {alerts.critical_sites.length} sites
              </div>
              <div className="pagination-buttons">
                <button
                  className="btn btn-ghost"
                  disabled={currentPage === 1}
                  onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
                >
                  Previous
                </button>
                <button
                  className="btn btn-ghost"
                  disabled={currentPage === totalPages}
                  onClick={() => setCurrentPage(prev => Math.min(totalPages, prev + 1))}
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
