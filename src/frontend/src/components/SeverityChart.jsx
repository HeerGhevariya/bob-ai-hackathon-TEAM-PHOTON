import { useState } from 'react'
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from 'recharts'
import { useChartTheme } from '../utils/useTheme'

const SEVERITY_COLORS = {
  major: '#ef4444',
  minor: '#f59e0b',
  administrative: '#3b82f6',
}

const TIER_COLORS = {
  critical: '#ef4444',
  high: '#f97316',
  medium: '#eab308',
  low: '#22c55e',
}

/* Custom tooltip for interactive donuts */
function DonutTooltip({ active, payload, ct, clickable }) {
  if (!active || !payload?.length) return null
  const { name, value } = payload[0]
  const total = payload[0].payload.total
  const pct = total > 0 ? ((value / total) * 100).toFixed(1) : 0
  return (
    <div style={{ ...ct.tooltip, pointerEvents: 'none' }}>
      <div style={{ fontWeight: 600, marginBottom: 2 }}>{name}</div>
      <div style={{ marginBottom: clickable ? 4 : 0 }}>
        {value.toLocaleString()} <span style={{ opacity: 0.6 }}>({pct}%)</span>
      </div>
      {clickable && (
        <div style={{ fontSize: 11, opacity: 0.65, borderTop: `1px solid ${ct.isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.08)'}`, paddingTop: 4 }}>
          Click to view
        </div>
      )}
    </div>
  )
}

/* Accessible, clickable legend rendered as a list of buttons */
function ClickableLegend({ payload, onItemClick, ct }) {
  return (
    <ul
      role="list"
      style={{
        display: 'flex',
        flexWrap: 'wrap',
        justifyContent: 'center',
        gap: '4px 12px',
        margin: 0,
        padding: 0,
        listStyle: 'none',
      }}
    >
      {payload.map((entry) => (
        <li key={entry.value} style={{ margin: 0 }}>
          <button
            type="button"
            aria-label={`View ${entry.payload.value} ${entry.value} items`}
            onClick={() => onItemClick && onItemClick(entry.payload)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 5,
              background: 'none',
              border: 'none',
              padding: '2px 4px',
              cursor: onItemClick ? 'pointer' : 'default',
              borderRadius: 4,
              fontSize: 12,
              color: ct.tick,
              transition: 'opacity 0.15s',
            }}
            onMouseEnter={e => { if (onItemClick) e.currentTarget.style.opacity = '0.7' }}
            onMouseLeave={e => { e.currentTarget.style.opacity = '1' }}
          >
            <span style={{
              display: 'inline-block',
              width: 10,
              height: 10,
              borderRadius: '50%',
              background: entry.color,
              flexShrink: 0,
            }} />
            {entry.value}
          </button>
        </li>
      ))}
    </ul>
  )
}

export function SeverityDonut({ data, onSegmentClick }) {
  const ct = useChartTheme()
  const [activeIndex, setActiveIndex] = useState(null)

  const total = (data?.major || 0) + (data?.minor || 0) + (data?.administrative || 0)

  const chartData = [
    { name: 'Major',          value: data?.major || 0,          color: SEVERITY_COLORS.major,          key: 'major',          total },
    { name: 'Minor',          value: data?.minor || 0,          color: SEVERITY_COLORS.minor,          key: 'minor',          total },
    { name: 'Administrative', value: data?.administrative || 0, color: SEVERITY_COLORS.administrative, key: 'administrative', total },
  ].filter(d => d.value > 0)

  if (chartData.length === 0) return <div className="empty-state"><p>No data</p></div>

  const clickable = !!onSegmentClick

  const handleClick = (entry) => {
    if (onSegmentClick) onSegmentClick(entry.key || entry.name.toLowerCase())
  }

  return (
    <ResponsiveContainer width="100%" height={220}>
      <PieChart>
        <Pie
          data={chartData}
          cx="50%"
          cy="50%"
          innerRadius={55}
          outerRadius={85}
          paddingAngle={3}
          dataKey="value"
          stroke="none"
          onClick={(entry) => handleClick(entry)}
          style={{ cursor: clickable ? 'pointer' : 'default' }}
          onMouseEnter={(_, index) => setActiveIndex(index)}
          onMouseLeave={() => setActiveIndex(null)}
        >
          {chartData.map((entry, i) => (
            <Cell
              key={i}
              fill={entry.color}
              opacity={activeIndex === null || activeIndex === i ? 1 : 0.55}
              style={{
                cursor: clickable ? 'pointer' : 'default',
                /* transition for non-reduced-motion contexts is handled via CSS */
                outline: 'none',
              }}
            />
          ))}
        </Pie>
        <Tooltip content={<DonutTooltip ct={ct} clickable={clickable} />} />
        <Legend
          verticalAlign="bottom"
          height={36}
          content={({ payload }) => (
            <ClickableLegend
              payload={payload}
              ct={ct}
              onItemClick={clickable ? handleClick : undefined}
            />
          )}
        />
      </PieChart>
    </ResponsiveContainer>
  )
}

export function RiskTierDonut({ data, onSegmentClick }) {
  const ct = useChartTheme()
  const [activeIndex, setActiveIndex] = useState(null)

  const total = (data?.critical || 0) + (data?.high || 0) + (data?.medium || 0) + (data?.low || 0)

  const chartData = [
    { name: 'Critical', value: data?.critical || 0, color: TIER_COLORS.critical, key: 'critical', total },
    { name: 'High',     value: data?.high || 0,     color: TIER_COLORS.high,     key: 'high',     total },
    { name: 'Medium',   value: data?.medium || 0,   color: TIER_COLORS.medium,   key: 'medium',   total },
    { name: 'Low',      value: data?.low || 0,      color: TIER_COLORS.low,      key: 'low',      total },
  ].filter(d => d.value > 0)

  if (chartData.length === 0) return <div className="empty-state"><p>No data</p></div>

  const clickable = !!onSegmentClick

  const handleClick = (entry) => {
    if (onSegmentClick) onSegmentClick(entry.key || entry.name.toLowerCase())
  }

  return (
    <ResponsiveContainer width="100%" height={220}>
      <PieChart>
        <Pie
          data={chartData}
          cx="50%"
          cy="50%"
          innerRadius={55}
          outerRadius={85}
          paddingAngle={3}
          dataKey="value"
          stroke="none"
          onClick={(entry) => handleClick(entry)}
          style={{ cursor: clickable ? 'pointer' : 'default' }}
          onMouseEnter={(_, index) => setActiveIndex(index)}
          onMouseLeave={() => setActiveIndex(null)}
        >
          {chartData.map((entry, i) => (
            <Cell
              key={i}
              fill={entry.color}
              opacity={activeIndex === null || activeIndex === i ? 1 : 0.55}
              style={{
                cursor: clickable ? 'pointer' : 'default',
                outline: 'none',
              }}
            />
          ))}
        </Pie>
        <Tooltip content={<DonutTooltip ct={ct} clickable={clickable} />} />
        <Legend
          verticalAlign="bottom"
          height={36}
          content={({ payload }) => (
            <ClickableLegend
              payload={payload}
              ct={ct}
              onItemClick={clickable ? handleClick : undefined}
            />
          )}
        />
      </PieChart>
    </ResponsiveContainer>
  )
}
