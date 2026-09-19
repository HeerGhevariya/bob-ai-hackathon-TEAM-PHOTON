export default function RiskBadge({ tier }) {
  const config = {
    critical: { label: 'Critical', className: 'badge-critical' },
    high:     { label: 'High',     className: 'badge-high' },
    medium:   { label: 'Medium',   className: 'badge-medium' },
    low:      { label: 'Low',      className: 'badge-low' },
  }
  const c = config[tier] || config.low
  return (
    <span className={`badge ${c.className}`}>
      <span className="sev-dot" style={{
        background:
          tier === 'critical' ? 'var(--tier-critical)' :
          tier === 'high'     ? 'var(--tier-high)' :
          tier === 'medium'   ? 'var(--tier-medium)' :
          'var(--tier-low)'
      }} />
      {c.label}
    </span>
  )
}
