import { forwardRef } from 'react'

/**
 * DeviationRow — a single <tr> for any deviation table.
 *
 * Props:
 *  deviation   — deviation object (all fields from API)
 *  isOpen      — boolean, highlights this row when its card is open
 *  onClick     — () => void
 *  showSite    — if true, renders the site_id cell (used in DeviationExplorer)
 *
 * Forwards ref to the <tr> element so the caller can return focus on modal close.
 */
const DeviationRow = forwardRef(function DeviationRow(
  { deviation: d, isOpen, onClick, showSite = false },
  ref
) {
  const handleKey = (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      onClick()
    }
  }

  return (
    <tr
      ref={ref}
      className={`dev-row${isOpen ? ' dev-row-open' : ''}`}
      onClick={onClick}
      onKeyDown={handleKey}
      tabIndex={0}
      role="button"
      aria-label={`View details for deviation ${d.deviation_id}`}
      aria-pressed={isOpen}
    >
      <td style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: 'monospace' }}>
        {d.deviation_id}
      </td>
      <td style={{ fontWeight: 500 }}>{d.patient_id}</td>
      {showSite && (
        <td>
          <span style={{ color: 'var(--accent)', fontWeight: 500 }}>
            {d.site_id}
          </span>
        </td>
      )}
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
      {!showSite && (
        <td
          style={{
            maxWidth: 220, overflow: 'hidden', textOverflow: 'ellipsis',
            whiteSpace: 'nowrap', fontSize: 12,
          }}
          title={d.description || `Expected ${d.expected_value}, got ${d.actual_value}`}
        >
          {d.description || `Expected ${d.expected_value}, got ${d.actual_value}`}
        </td>
      )}
      {showSite && (
        <>
          <td style={{
            maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis',
            whiteSpace: 'nowrap', fontSize: 12,
          }} title={d.expected_value}>
            {d.expected_value}
          </td>
          <td style={{
            maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis',
            whiteSpace: 'nowrap', fontSize: 12,
          }} title={d.actual_value}>
            {d.actual_value}
          </td>
        </>
      )}
    </tr>
  )
})

export default DeviationRow
