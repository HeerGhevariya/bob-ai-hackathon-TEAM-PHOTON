import { useState, useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { ClipboardList, X } from 'lucide-react'
import { fetchSites } from '../utils/api'
import RiskBadge from './RiskBadge'
import TrendArrow from './TrendArrow'

export default function SiteLeaderboard() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [allSites, setAllSites] = useState([])
  const [sites, setSites] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(0)
  const pageSize = 30
  const navigate = useNavigate()

  // Tier filter driven by URL
  const tierFilter = searchParams.get('tier') || ''
  // Trend filter — frontend-only, not supported by API
  const trendFilter = searchParams.get('trend') || ''

  const setTierFilter = (value) => {
    setSearchParams(prev => {
      const next = new URLSearchParams(prev)
      if (value) next.set('tier', value)
      else next.delete('tier')
      return next
    }, { replace: false })
    setPage(0)
  }

  const clearAllFilters = () => {
    setSearchParams({}, { replace: false })
    setPage(0)
  }

  // Fetch all sites for the tier filter (API supports tier, not trend)
  useEffect(() => {
    setLoading(true)
    // Fetch enough to cover all sites for trend client-side filtering;
    // use a large limit — the mock dataset is bounded.
    fetchSites({ tier: tierFilter || null, limit: 300, offset: 0 })
      .then((data) => {
        setAllSites(data.sites)
      })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [tierFilter])

  // Apply client-side trend filter + paginate
  useEffect(() => {
    let filtered = allSites
    if (trendFilter) {
      filtered = allSites.filter(s =>
        s.trend_direction?.toLowerCase() === trendFilter.toLowerCase()
      )
    }
    setTotal(filtered.length)
    setSites(filtered.slice(page * pageSize, (page + 1) * pageSize))
  }, [allSites, trendFilter, page])

  // Reset page when trend filter changes
  useEffect(() => {
    setPage(0)
  }, [trendFilter])

  // Human-readable filter chip labels
  const tierLabel = tierFilter ? tierFilter.charAt(0).toUpperCase() + tierFilter.slice(1) : ''
  const trendLabel = trendFilter ? trendFilter.charAt(0).toUpperCase() + trendFilter.slice(1) + ' Trend' : ''
  const hasFilter = !!(tierFilter || trendFilter)

  return (
    <div>
      <div className="page-header">
        <h2>Site Risk Leaderboard</h2>
        <p>All {total} sites ranked by composite risk score — highest risk first</p>
      </div>

      <div className="filter-bar">
        <select
          className="filter-select"
          value={tierFilter}
          onChange={(e) => setTierFilter(e.target.value)}
          aria-label="Filter by risk tier"
        >
          <option value="">All Risk Tiers</option>
          <option value="critical">🔴 Critical</option>
          <option value="high">🟠 High</option>
          <option value="medium">🟡 Medium</option>
          <option value="low">🟢 Low</option>
        </select>

        {/* Trend filter — read-only chip when set from URL; also a select for direct use */}
        <select
          className="filter-select"
          value={trendFilter}
          onChange={(e) => {
            setSearchParams(prev => {
              const next = new URLSearchParams(prev)
              if (e.target.value) next.set('trend', e.target.value)
              else next.delete('trend')
              return next
            }, { replace: false })
            setPage(0)
          }}
          aria-label="Filter by trend direction"
        >
          <option value="">All Trends</option>
          <option value="rising">📈 Rising</option>
          <option value="stable">➡️ Stable</option>
          <option value="declining">📉 Declining</option>
        </select>

        {hasFilter && (
          <>
            {tierLabel && (
              <span className="filter-chip">
                Tier: {tierLabel}
                <button
                  type="button"
                  className="filter-chip-clear"
                  aria-label={`Clear tier filter: ${tierLabel}`}
                  onClick={() => setTierFilter('')}
                >
                  <X size={11} />
                </button>
              </span>
            )}
            {trendLabel && (
              <span className="filter-chip">
                {trendLabel}
                <button
                  type="button"
                  className="filter-chip-clear"
                  aria-label={`Clear trend filter: ${trendLabel}`}
                  onClick={() => {
                    setSearchParams(prev => {
                      const next = new URLSearchParams(prev)
                      next.delete('trend')
                      return next
                    }, { replace: false })
                    setPage(0)
                  }}
                >
                  <X size={11} />
                </button>
              </span>
            )}
            <button className="btn btn-ghost" onClick={clearAllFilters} aria-label="Clear all filters">
              <X size={13} /> Clear all
            </button>
          </>
        )}
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
              Showing {total === 0 ? 0 : page * pageSize + 1}–{Math.min((page + 1) * pageSize, total)} of {total} sites
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
