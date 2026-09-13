export default function RiskBadge({ tier }) {
  const config = {
    critical: { label: 'Critical', className: 'badge-critical', icon: '🔴' },
    high: { label: 'High', className: 'badge-high', icon: '🟠' },
    medium: { label: 'Medium', className: 'badge-medium', icon: '🟡' },
    low: { label: 'Low', className: 'badge-low', icon: '🟢' },
  }
  const c = config[tier] || config.low
  return <span className={`badge ${c.className}`}>{c.icon} {c.label}</span>
}
