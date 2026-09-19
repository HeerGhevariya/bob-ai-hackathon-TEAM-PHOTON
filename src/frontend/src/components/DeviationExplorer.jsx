import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Search, X } from 'lucide-react'
import { fetchDeviations } from '../utils/api'
import DeviationRow from './DeviationRow'
import DeviationDetailModal from './DeviationDetailModal'

// Human-readable labels for deviation type keys
const DEVIATION_TYPE_LABELS = {
  missed_visit: 'Missed Visit',
  late_visit: 'Late Visit',
  early_visit: 'Early Visit',
  wrong_dose: 'Wrong Dose',
  banned_comedication: 'Banned Co-Medication',
  missing_assessment: 'Missing Assessment',
}

const SEVERITY_LABELS = {
  major: 'Major',
  minor: 'Minor',
  administrative: 'Administrative',
}

export default function DeviationExplorer() {
  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()
  const [deviations, setDeviations] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(0)
  const pageSize = 40

  // Filter state driven entirely by URL
  const severity = searchParams.get('severity') || ''
  const devType = searchParams.get('deviation_type') || ''
  const siteFilter = searchParams.get('site_id') || ''

  // The deviation ID from the URL (for shareable links / back-button close)
  const devIdFromUrl = searchParams.get('dev')

  // Map from deviation_id → row DOM node (for focus return on modal close)
  const rowRefs = useRef({})

  // Helper: update a single filter param in the URL
  const setFilter = useCallback((key, value) => {
    setSearchParams(prev => {
      const next = new URLSearchParams(prev)
      if (value) next.set(key, value)
      else next.delete(key)
      // Reset page when filter changes
      next.delete('page')
      return next
    }, { replace: false })
    setPage(0)
  }, [setSearchParams])

  const clearAllFilters = useCallback(() => {
    setSearchParams(prev => {
      const next = new URLSearchParams(prev)
      next.delete('severity')
      next.delete('deviation_type')
      next.delete('site_id')
      return next
    }, { replace: false })
    setPage(0)
  }, [setSearchParams])

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

  const selectedDeviation = devIdFromUrl
    ? deviations.find(d => d.deviation_id === devIdFromUrl) || null
    : null
  const selectedIndex = selectedDeviation
    ? deviations.findIndex(d => d.deviation_id === selectedDeviation.deviation_id)
    : -1

  const openDeviation = useCallback((deviation) => {
    setSearchParams(prev => {
      const next = new URLSearchParams(prev)
      next.set('dev', deviation.deviation_id)
      return next
    }, { replace: false })
  }, [setSearchParams])

  const closeDeviation = useCallback(() => {
    const returnId = searchParams.get('dev')
    setSearchParams(prev => {
      const next = new URLSearchParams(prev)
      next.delete('dev')
      return next
    }, { replace: false })
    if (returnId) {
      setTimeout(() => {
        rowRefs.current[returnId]?.focus()
      }, 50)
    }
  }, [searchParams, setSearchParams])

  const navigateDeviation = useCallback((index) => {
    const dev = deviations[index]
    if (!dev) return
    setSearchParams(prev => {
      const next = new URLSearchParams(prev)
      next.set('dev', dev.deviation_id)
      return next
    }, { replace: true })
  }, [deviations, setSearchParams])

  const hasFilter = !!(severity || devType || siteFilter)

  return (
    <div>
      <div className="page-header">
        <h2>Deviation Explorer</h2>
        <p>Browse and filter all {total} detected protocol deviations</p>
      </div>

      <div className="filter-bar">
        <select
          className="filter-select"
          value={severity}
          onChange={(e) => setFilter('severity', e.target.value)}
          aria-label="Filter by severity"
        >
          <option value="">All Severities</option>
          <option value="major">🔴 Major</option>
          <option value="minor">🟡 Minor</option>
          <option value="administrative">🔵 Administrative</option>
        </select>

        <select
          className="filter-select"
          value={devType}
          onChange={(e) => setFilter('deviation_type', e.target.value)}
          aria-label="Filter by deviation type"
        >
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
          onChange={(e) => setFilter('site_id', e.target.value)}
          aria-label="Filter by site ID"
        />

        {/* Filter chips */}
        {hasFilter && (
          <>
            {severity && (
              <span className="filter-chip">
                Severity: {SEVERITY_LABELS[severity] || severity}
                <button
                  type="button"
                  className="filter-chip-clear"
                  aria-label={`Clear severity filter: ${SEVERITY_LABELS[severity] || severity}`}
                  onClick={() => setFilter('severity', '')}
                >
                  <X size={11} />
                </button>
              </span>
            )}
            {devType && (
              <span className="filter-chip">
                Type: {DEVIATION_TYPE_LABELS[devType] || devType}
                <button
                  type="button"
                  className="filter-chip-clear"
                  aria-label={`Clear type filter: ${DEVIATION_TYPE_LABELS[devType] || devType}`}
                  onClick={() => setFilter('deviation_type', '')}
                >
                  <X size={11} />
                </button>
              </span>
            )}
            {siteFilter && (
              <span className="filter-chip">
                Site: {siteFilter}
                <button
                  type="button"
                  className="filter-chip-clear"
                  aria-label={`Clear site filter: ${siteFilter}`}
                  onClick={() => setFilter('site_id', '')}
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
                  <DeviationRow
                    key={d.deviation_id}
                    deviation={d}
                    isOpen={selectedDeviation?.deviation_id === d.deviation_id}
                    onClick={() => openDeviation(d)}
                    showSite={true}
                    ref={el => { rowRefs.current[d.deviation_id] = el }}
                  />
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

      {/* Deviation Detail Modal */}
      {selectedDeviation && (
        <DeviationDetailModal
          deviation={selectedDeviation}
          deviations={deviations}
          currentIndex={selectedIndex}
          onClose={closeDeviation}
          onNavigate={navigateDeviation}
        />
      )}
    </div>
  )
}
