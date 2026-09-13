import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from 'recharts'

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

export function SeverityDonut({ data }) {
  const chartData = [
    { name: 'Major', value: data?.major || 0, color: SEVERITY_COLORS.major },
    { name: 'Minor', value: data?.minor || 0, color: SEVERITY_COLORS.minor },
    { name: 'Administrative', value: data?.administrative || 0, color: SEVERITY_COLORS.administrative },
  ].filter(d => d.value > 0)

  if (chartData.length === 0) return <div className="empty-state"><p>No data</p></div>

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
        >
          {chartData.map((entry, i) => (
            <Cell key={i} fill={entry.color} />
          ))}
        </Pie>
        <Tooltip
          contentStyle={{
            background: '#111b2e',
            border: '1px solid rgba(255,255,255,0.08)',
            borderRadius: 8,
            color: '#e8ecf4',
            fontSize: 13,
          }}
        />
        <Legend
          verticalAlign="bottom"
          height={36}
          formatter={(value) => <span style={{ color: '#8b95a8', fontSize: 12 }}>{value}</span>}
        />
      </PieChart>
    </ResponsiveContainer>
  )
}

export function RiskTierDonut({ data }) {
  const chartData = [
    { name: 'Critical', value: data?.critical || 0, color: TIER_COLORS.critical },
    { name: 'High', value: data?.high || 0, color: TIER_COLORS.high },
    { name: 'Medium', value: data?.medium || 0, color: TIER_COLORS.medium },
    { name: 'Low', value: data?.low || 0, color: TIER_COLORS.low },
  ].filter(d => d.value > 0)

  if (chartData.length === 0) return <div className="empty-state"><p>No data</p></div>

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
        >
          {chartData.map((entry, i) => (
            <Cell key={i} fill={entry.color} />
          ))}
        </Pie>
        <Tooltip
          contentStyle={{
            background: '#111b2e',
            border: '1px solid rgba(255,255,255,0.08)',
            borderRadius: 8,
            color: '#e8ecf4',
            fontSize: 13,
          }}
        />
        <Legend
          verticalAlign="bottom"
          height={36}
          formatter={(value) => <span style={{ color: '#8b95a8', fontSize: 12 }}>{value}</span>}
        />
      </PieChart>
    </ResponsiveContainer>
  )
}
