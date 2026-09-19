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

// Custom tooltip that adds "Click to view" hint
function ChartTooltip({ active, payload, total, hint }) {
  if (!active || !payload?.length) return null
  const { name, value } = payload[0]
  const pct = total > 0 ? ((value / total) * 100).toFixed(1) : '0.0'
  return (
    <div style={{
      background: 'var(--bg-card)',
      border: '1px solid var(--border)',
      borderRadius: 8,
      padding: '8px 12px',
      fontSize: 12.5,
      color: 'var(--text-primary)',
      boxShadow: '0 4px 16px rgba(0,0,0,0.10)',
      pointerEvents: 'none',
    }}>
      <div style={{ fontWeight: 600, marginBottom: 2 }}>{name}</div>
      <div>{value.toLocaleString()} &nbsp;<span style={{ color: 'var(--text-muted)' }}>({pct}%)</span></div>
      <div style={{ marginTop: 4, fontSize: 11, color: 'var(--accent)', fontStyle: 'italic' }}>Click to view →</div>
    </div>
  )
}

// Keyboard-accessible legend with real button behaviour
function AccessibleLegend({ payload, onItemClick, getLabel }) {
  const ct = useChartTheme()
  if (!payload?.length) return null
  return (
    <div
      role="list"
      style={{ display: 'flex', justifyContent: 'center', flexWrap: 'wrap', gap: '6px 14px', paddingTop: 6 }}
    >
      {payload.map((entry) => (
        <button
          key={entry.value}
          role="listitem"
          className="chart-legend-btn"
          aria-label={getLabel(entry)}
          onClick={() => onItemClick(entry.value)}
          style={{ '--legend-dot-color': entry.color }}
        >
          <span className="chart-legend-dot" aria-hidden="true" />
          <span style={{ color: ct.tick, fontSize: 12 }}>{entry.value}</span>
        </button>
      ))}
    </div>
  )
}

export function SeverityDonut({ data, onSegmentClick }) {
  const ct = useChartTheme()
  const [hovered, setHovered] = useState(null)
  const chartData = [
    { name: 'Major', value: data?.major || 0, color: SEVERITY_COLORS.major, key: 'major' },
    { name: 'Minor', value: data?.minor || 0, color: SEVERITY_COLORS.minor, key: 'minor' },
    { name: 'Administrative', value: data?.administrative || 0, color: SEVERITY_COLORS.administrative, key: 'administrative' },
  ].filter(d => d.value > 0)

  const total = chartData.reduce((s, d) => s + d.value, 0)

  if (chartData.length === 0) return <div className="empty-state"><p>No data</p></div>

  const handleClick = (entry) => {
    onSegmentClick?.(entry.key || entry.name?.toLowerCase())
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
          onMouseEnter={(_, index) => setHovered(index)}
          onMouseLeave={() => setHovered(null)}
          style={{ cursor: 'pointer' }}
        >
          {chartData.map((entry, i) => (
            <Cell
              key={i}
              fill={entry.color}
              opacity={hovered === null || hovered === i ? 1 : 0.55}
              style={{ cursor: 'pointer', transition: 'opacity 0.15s' }}
            />
          ))}
        </Pie>
        <Tooltip content={<ChartTooltip total={total} />} />
        <Legend
          verticalAlign="bottom"
          height={36}
          content={(props) => (
            <AccessibleLegend
              {...props}
              onItemClick={(name) => {
                const entry = chartData.find(d => d.name === name)
                if (entry) handleClick(entry)
              }}
              getLabel={(entry) => {
                const d = chartData.find(d => d.name === entry.value)
                return `View ${d?.value?.toLocaleString() ?? ''} ${entry.value} deviations`
              }}
            />
          )}
        />
      </PieChart>
    </ResponsiveContainer>
  )
}

export function RiskTierDonut({ data, onSegmentClick }) {
  const ct = useChartTheme()
  const [hovered, setHovered] = useState(null)
  const chartData = [
    { name: 'Critical', value: data?.critical || 0, color: TIER_COLORS.critical, key: 'critical' },
    { name: 'High', value: data?.high || 0, color: TIER_COLORS.high, key: 'high' },
    { name: 'Medium', value: data?.medium || 0, color: TIER_COLORS.medium, key: 'medium' },
    { name: 'Low', value: data?.low || 0, color: TIER_COLORS.low, key: 'low' },
  ].filter(d => d.value > 0)

  const total = chartData.reduce((s, d) => s + d.value, 0)

  if (chartData.length === 0) return <div className="empty-state"><p>No data</p></div>

  const handleClick = (entry) => {
    onSegmentClick?.(entry.key || entry.name?.toLowerCase())
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
          onMouseEnter={(_, index) => setHovered(index)}
          onMouseLeave={() => setHovered(null)}
          style={{ cursor: 'pointer' }}
        >
          {chartData.map((entry, i) => (
            <Cell
              key={i}
              fill={entry.color}
              opacity={hovered === null || hovered === i ? 1 : 0.55}
              style={{ cursor: 'pointer', transition: 'opacity 0.15s' }}
            />
          ))}
        </Pie>
        <Tooltip content={<ChartTooltip total={total} />} />
        <Legend
          verticalAlign="bottom"
          height={36}
          content={(props) => (
            <AccessibleLegend
              {...props}
              onItemClick={(name) => {
                const entry = chartData.find(d => d.name === name)
                if (entry) handleClick(entry)
              }}
              getLabel={(entry) => {
                const d = chartData.find(d => d.name === entry.value)
                return `View ${d?.value?.toLocaleString() ?? ''} ${entry.value} sites`
              }}
            />
          )}
        />
      </PieChart>
    </ResponsiveContainer>
  )
}
