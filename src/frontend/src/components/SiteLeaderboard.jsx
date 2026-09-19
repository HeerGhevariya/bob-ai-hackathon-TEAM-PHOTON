import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { ClipboardList } from 'lucide-react'
import { fetchSites } from '../utils/api'
import RiskBadge from './RiskBadge'
import TrendArrow from './TrendArrow'

export default function SiteLeaderboard() {
  const [sites, setSites] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [tierFilter, setTierFilter] = useState('')
  const [page, setPage] = useState(0)
  const pageSize = 30
  const navigate = useNavigate()

  useEffect(() => {
    setLoading(true)
    fetchSites({ tier: tierFilter || null, limit: pageSize, offset: page * pageSize })
      .then((data) => {
        setSites(data.sites)
        setTotal(data.total)
      })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [tierFilter, page])

  return (
    <div>
      <div className="page-header">
        <h2>Site Risk Leaderboard</h2>
        <p>All {total} sites ranked by composite risk score — highest risk first</p>
      </div>

      <div className="filter-bar">
        <select className="filter-select" value={tierFilter} onChange={(e) => { setTierFilter(e.target.value); setPage(0) }}>
          <option value="">All Risk Tiers</option>
          <option value="critical">🔴 Critical</option>
          <option value="high">🟠 High</option>
          <option value="medium">🟡 Medium</option>
          <option value="low">🟢 Low</option>
        </select>
      </div>

      {loading ? (
        <div className="skeleton-page">
          <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
            {[0,1,2,3,4,5,6,7].map(i => <div key={i} className="skeleton skeleton-row" />)}
          </div>
        </div>
      ) : (
        <>
          <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          <div className="table-responsive">
            <table className="data-table">
              <thead>
                <tr>
                  <th style={{ width: 50 }}>#</th>
                  <th>Site ID</th>
                  <th>Site Name</th>
                  <th>Risk Score</th>
                  <th>Tier</th>
                  <th>Trend</th>
                  <th>Deviations</th>
                  <th style={{ textAlign: 'center' }}>Major</th>
                  <th style={{ textAlign: 'center' }}>Minor</th>
                  <th style={{ textAlign: 'center' }}>Admin</th>
                  <th>Patients</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {sites.map((site, i) => (
                  <tr key={site.site_id} onClick={() => navigate(`/sites/${site.site_id}`)}>
                    <td style={{ color: 'var(--text-muted)', fontSize: 12 }}>
                      {page * pageSize + i + 1}
                    </td>
                    <td style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                      {site.site_id}
                    </td>
                    <td>{site.site_name}</td>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        <span style={{
                          fontWeight: 700,
                          color: site.risk_score >= 80 ? 'var(--tier-critical)' :
                                 site.risk_score >= 60 ? 'var(--tier-high)' :
                                 site.risk_score >= 40 ? 'var(--tier-medium)' :
                                 'var(--tier-low)',
                          minWidth: 36,
                        }}>
                          {site.risk_score}
                        </span>
                        <div className="risk-bar" style={{ width: 60 }}>
                          <div
                            className={`risk-bar-fill ${site.risk_tier}`}
                            style={{ width: `${site.risk_score}%` }}
                          />
                        </div>
                      </div>
                    </td>
                    <td><RiskBadge tier={site.risk_tier} /></td>
                    <td><TrendArrow direction={site.trend_direction} /></td>
                    <td style={{ fontWeight: 500 }}>{site.total_deviations}</td>
                    <td style={{ textAlign: 'center', color: 'var(--severity-major)' }}>{site.major_count}</td>
                    <td style={{ textAlign: 'center', color: 'var(--severity-minor)' }}>{site.minor_count}</td>
                    <td style={{ textAlign: 'center', color: 'var(--severity-admin)' }}>{site.administrative_count}</td>
                    <td>{site.patients_affected}/{site.total_patients}</td>
                    <td>
                      <button
                        className="btn btn-ghost"
                        style={{ padding: '5px 12px', fontSize: 11 }}
                        onClick={(e) => { e.stopPropagation(); navigate(`/capa/${site.site_id}`) }}
                      >
                        <ClipboardList size={12} /> CAPA
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          </div>

          <div className="pagination">
            <span className="pagination-info">
              Showing {page * pageSize + 1}–{Math.min((page + 1) * pageSize, total)} of {total} sites
            </span>
            <div className="pagination-buttons">
              <button className="btn btn-ghost" disabled={page === 0} onClick={() => setPage(p => p - 1)}>← Prev</button>
              <button className="btn btn-ghost" disabled={(page + 1) * pageSize >= total} onClick={() => setPage(p => p + 1)}>Next →</button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
