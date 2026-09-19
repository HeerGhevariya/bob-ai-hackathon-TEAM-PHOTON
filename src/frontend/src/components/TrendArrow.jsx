import { TrendingUp, TrendingDown, Minus } from 'lucide-react'

export default function TrendArrow({ direction }) {
  const config = {
    rising:   { icon: <TrendingUp size={13} />,  label: 'Rising',   className: 'rising' },
    stable:   { icon: <Minus size={13} />,        label: 'Stable',   className: 'stable' },
    declining:{ icon: <TrendingDown size={13} />, label: 'Declining', className: 'declining' },
  }
  const c = config[direction] || config.stable
  return (
    <span className={`trend-arrow ${c.className}`}>
      {c.icon} {c.label}
    </span>
  )
}
