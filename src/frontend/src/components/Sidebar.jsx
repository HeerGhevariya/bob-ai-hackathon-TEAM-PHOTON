import { NavLink, useLocation } from 'react-router-dom'
import ThemeToggle from './ThemeToggle'

const navItems = [
  { path: '/', icon: '📊', label: 'Trial Overview' },
  { path: '/sites', icon: '🏥', label: 'Site Risk Leaderboard' },
  { path: '/deviations', icon: '⚠️', label: 'Deviation Explorer' },
  { path: '/capa', icon: '📋', label: 'CAPA Reports' },
]

export default function Sidebar() {
  const location = useLocation()

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
        <div className="sidebar-info">
          <span className="link-icon">🤖</span>
          MCP Server Active
          <span className="sidebar-badge" style={{
            background: 'rgba(34,197,94,0.12)',
            color: '#22c55e'
          }}>Live</span>
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
