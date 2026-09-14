import { useState, useEffect } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import ThemeToggle from './ThemeToggle'
import { fetchMcpStatus } from '../utils/api'

const navItems = [
  { path: '/', icon: '📊', label: 'Trial Overview' },
  { path: '/sites', icon: '🏥', label: 'Site Risk Leaderboard' },
  { path: '/deviations', icon: '⚠️', label: 'Deviation Explorer' },
  { path: '/capa', icon: '📋', label: 'CAPA Reports' },
]

export default function Sidebar() {
  const location = useLocation()
  const [mcpState, setMcpState] = useState({
    status: 'connecting', // 'connected' | 'offline' | 'connecting'
    toolCount: 0,
  })

  useEffect(() => {
    let isMounted = true

    const checkStatus = () => {
      fetchMcpStatus()
        .then((res) => {
          if (isMounted) {
            if (res && res.connected) {
              setMcpState({
                status: 'connected',
                toolCount: res.tools ? res.tools.length : 5,
              })
            } else {
              setMcpState({ status: 'offline', toolCount: 0 })
            }
          }
        })
        .catch(() => {
          if (isMounted) {
            setMcpState({ status: 'offline', toolCount: 0 })
          }
        })
    }

    checkStatus()
    const interval = setInterval(checkStatus, 15000) // Poll every 15s
    return () => {
      isMounted = false
      clearInterval(interval)
    }
  }, [])

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <h1>
          <span className="brand-icon">🛡️</span>
          Trial<span className="brand-accent">Guard</span> AI
        </h1>
        <p>Clinical Trial Risk Monitor</p>
      </div>

      <nav className="sidebar-nav">
        <div className="sidebar-section-label">Dashboard</div>
        {navItems.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            className={({ isActive }) =>
              `sidebar-link ${isActive ? 'active' : ''}`
            }
            end={item.path === '/'}
          >
            <span className="link-icon">{item.icon}</span>
            {item.label}
          </NavLink>
        ))}

        <div className="sidebar-section-label" style={{ marginTop: 24 }}>IBM Bob Integration</div>
        <div className="sidebar-info" style={{ justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span className="link-icon">
              {mcpState.status === 'connected' ? '🟢' : mcpState.status === 'connecting' ? '🟡' : '🔴'}
            </span>
            <span style={{ fontSize: 12, fontWeight: 500 }}>
              {mcpState.status === 'connected'
                ? 'MCP Server Connected'
                : mcpState.status === 'connecting'
                ? 'MCP Server Connecting'
                : 'MCP Server Offline'}
            </span>
          </div>
          <span
            className="sidebar-badge"
            style={{
              background:
                mcpState.status === 'connected'
                  ? 'rgba(34,197,94,0.12)'
                  : mcpState.status === 'connecting'
                  ? 'rgba(245,158,11,0.12)'
                  : 'rgba(239,68,68,0.12)',
              color:
                mcpState.status === 'connected'
                  ? '#22c55e'
                  : mcpState.status === 'connecting'
                  ? '#f59e0b'
                  : '#ef4444',
            }}
          >
            {mcpState.status === 'connected'
              ? 'LIVE'
              : mcpState.status === 'connecting'
              ? 'CONNECTING'
              : 'OFFLINE'}
          </span>
        </div>

        <div className="sidebar-section-label" style={{ marginTop: 24 }}>Protocol</div>
        <div className="sidebar-info">
          <span className="link-icon">📄</span>
          PHOENIX-301
        </div>
        <div className="sidebar-info">
          <span className="link-icon">💊</span>
          Phoenixin (PNX-301)
        </div>
      </nav>

      <ThemeToggle />

      <div style={{
        padding: '16px 20px',
        borderTop: '1px solid var(--border)',
        fontSize: 11,
        color: 'var(--text-muted)'
      }}>
        <div style={{ fontWeight: 600, marginBottom: 2 }}>TEAM PHOTON</div>
        <div>Bob AI Hackathon 2026</div>
      </div>
    </aside>
  )
}
