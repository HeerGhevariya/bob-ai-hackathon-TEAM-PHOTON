export default function TrendArrow({ direction }) {
  const config = {
    rising: { arrow: '↑', label: 'Rising', className: 'rising' },
    stable: { arrow: '→', label: 'Stable', className: 'stable' },
    declining: { arrow: '↓', label: 'Declining', className: 'declining' },
  }
  const c = config[direction] || config.stable
  return (
    <span className={`trend-arrow ${c.className}`}>
      {c.arrow} {c.label}
    </span>
  )
}
