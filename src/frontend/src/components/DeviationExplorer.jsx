import { useState, useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Search, X } from 'lucide-react'
import { fetchDeviations } from '../utils/api'

export default function DeviationExplorer() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const [deviations, setDeviations] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [severity, setSeverity] = useState(searchParams.get('severity') || '')
  const [devType, setDevType] = useState(searchParams.get('deviation_type') || '')
  const [siteFilter, setSiteFilter] = useState(searchParams.get('site_id') || '')
  const [page, setPage] = useState(0)
  const pageSize = 40

  useEffect(() => {
    setLoading(true)
    fetchDeviations({
      siteId: siteFilter || null,
      severity: severity || null,
      deviationType: devType || null,
      limit: pageSize,
      offset: page * pageSize,
    })
      .then((data) => {
        setDeviations(data.deviations)
        setTotal(data.total)
      })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [severity, devType, siteFilter, page])

  return (
    <div>
      <div className="page-header">
        <h2>Deviation Explorer</h2>
        <p>Browse and filter all {total} detected protocol deviations</p>
      </div>

      <div className="filter-bar">
        <select className="filter-select" value={severity} onChange={(e) => { setSeverity(e.target.value); setPage(0) }}>
          <option value="">All Severities</option>
          <option value="major">🔴 Major</option>
          <option value="minor">🟡 Minor</option>
          <option value="administrative">🔵 Administrative</option>
        </select>

        <select className="filter-select" value={devType} onChange={(e) => { setDevType(e.target.value); setPage(0) }}>
          <option value="">All Types</option>
          <option value="missed_visit">Missed Visit</option>
          <option value="late_visit">Late Visit</option>
          <option value="early_visit">Early Visit</option>
          <option value="wrong_dose">Wrong Dose</option>
          <option value="banned_comedication">Banned Co-Medication</option>
          <option value="missing_assessment">Missing Assessment</option>
        </select>

        <input
          className="filter-input"
          type="text"
          placeholder="Filter by Site ID (e.g. SITE-042)"
          value={siteFilter}
          onChange={(e) => { setSiteFilter(e.target.value); setPage(0) }}
        />

        {(severity || devType || siteFilter) && (
          <button className="btn btn-ghost" onClick={() => { setSeverity(''); setDevType(''); setSiteFilter(''); setPage(0) }}>
            <X size={13} /> Clear
          </button>
        )}
      </div>

      {loading ? (
        <div className="skeleton-page">
          <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
            {[0,1,2,3,4,5,6,7,8].map(i => <div key={i} className="skeleton skeleton-row" />)}
          </div>
        </div>
      ) : deviations.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon"><Search size={40} /></div>
          <p>No deviations match the current filters.</p>
        </div>
      ) : (
        <>
          <div className="card" style={{ padding: 0, overflow: 'auto' }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Patient</th>
                  <th>Site</th>
                  <th>Visit</th>
                  <th>Type</th>
                  <th>Severity</th>
                  <th>Date</th>
                  <th>Expected</th>
                  <th>Actual</th>
                </tr>
              </thead>
              <tbody>
                {deviations.map((d) => (
                  <tr key={d.deviation_id} onClick={() => navigate(`/sites/${d.site_id}`)}>
                    <td style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: 'monospace' }}>
                      {d.deviation_id}
                    </td>
                    <td style={{ fontWeight: 500 }}>{d.patient_id}</td>
                    <td>
                      <span style={{ color: 'var(--accent)', cursor: 'pointer', fontWeight: 500 }}
                        onClick={(e) => { e.stopPropagation(); navigate(`/sites/${d.site_id}`) }}>
                        {d.site_id}
                      </span>
                    </td>
                    <td>{d.visit_name}</td>
                    <td style={{ whiteSpace: 'nowrap' }}>
                      {d.deviation_type.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
                    </td>
                    <td>
                      <span className={`badge badge-${d.severity}`}>
                        <span className={`sev-dot ${d.severity === 'administrative' ? 'admin' : d.severity}`} />
                        {d.severity}
                      </span>
                    </td>
                    <td style={{ whiteSpace: 'nowrap' }}>{d.detected_date || '—'}</td>
                    <td style={{ maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontSize: 12 }}>
                      {d.expected_value}
                    </td>
                    <td style={{ maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontSize: 12 }}>
                      {d.actual_value}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="pagination">
            <span className="pagination-info">
              Showing {page * pageSize + 1}–{Math.min((page + 1) * pageSize, total)} of {total} deviations
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
