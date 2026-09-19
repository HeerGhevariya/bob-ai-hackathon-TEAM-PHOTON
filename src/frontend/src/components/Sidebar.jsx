import { useState, useEffect } from 'react'
import { useNavigate, NavLink, useLocation } from 'react-router-dom'
import {
  LayoutDashboard, Hospital, AlertTriangle, ClipboardList,
  MessageSquare, FileText, Shield, LogOut, Menu, X,
  Wifi, WifiOff, Loader2, FlaskConical, Scale, Network, Database,
} from 'lucide-react'
import ThemeToggle from './ThemeToggle'
import { fetchMcpStatus } from '../utils/api'
import { logout } from '../utils/auth'

const navItems = [
  { path: '/', icon: <LayoutDashboard size={16} />, label: 'Trial Overview' },
  { path: '/sites', icon: <Hospital size={16} />, label: 'Site Risk Leaderboard' },
  { path: '/deviations', icon: <AlertTriangle size={16} />, label: 'Deviation Explorer' },
  { path: '/capa', icon: <ClipboardList size={16} />, label: 'CAPA Reports' },
]

export default function Sidebar({ user, onLogout }) {
  const location = useLocation()
  const navigate = useNavigate()
  const [mcpState, setMcpState] = useState({
    status: 'connecting', // 'connected' | 'offline' | 'connecting'
    toolCount: 0,
  })
  const [mobileOpen, setMobileOpen] = useState(false)

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
    const interval = setInterval(checkStatus, 15000)
    return () => {
      isMounted = false
      clearInterval(interval)
    }
  }, [])

  // Close mobile drawer on route change
  useEffect(() => {
    setMobileOpen(false)
  }, [location.pathname])

  const statusColors = {
    connected: { dot: '#22c55e', badge: 'rgba(34,197,94,0.12)', label: '#22c55e', icon: <Wifi size={14} /> },
    connecting: { dot: '#f59e0b', badge: 'rgba(245,158,11,0.12)', label: '#f59e0b', icon: <Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} /> },
    offline:    { dot: '#ef4444', badge: 'rgba(239,68,68,0.12)',  label: '#ef4444', icon: <WifiOff size={14} /> },
  }

  const sc = statusColors[mcpState.status]

  const statusLabel = 'Bob Copilot'

  const statusBadgeText =
    mcpState.status === 'connected'  ? 'LIVE' :
    mcpState.status === 'connecting' ? 'CONNECTING' :
    'OFFLINE'

  return (
    <>
      {/* Mobile toggle button */}
      <button
        className="sidebar-mobile-toggle"
        onClick={() => setMobileOpen(o => !o)}
        aria-label="Toggle navigation menu"
      >
        {mobileOpen ? <X size={20} /> : <Menu size={20} />}
      </button>

      {/* Backdrop */}
      {mobileOpen && (
        <div className="sidebar-backdrop" onClick={() => setMobileOpen(false)} />
      )}

      <aside className={`sidebar${mobileOpen ? ' open' : ''}`}>
        <div className="sidebar-brand">
          <h1>
            <span className="brand-icon"><Shield size={20} /></span>
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
              className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}
              end={item.path === '/'}
            >
              <span className="link-icon">{item.icon}</span>
              {item.label}
            </NavLink>
          ))}

          <div className="sidebar-section-label" style={{ marginTop: 20 }}>AI Chatbot</div>
          <NavLink
            to="/chat"
            className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}
            style={{ justifyContent: 'space-between' }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span className="link-icon" style={{ color: sc.label }}>{sc.icon}</span>
              <span>{statusLabel}</span>
            </div>
            <span
              className="sidebar-badge"
              style={{
                background: sc.badge,
                color: sc.label,
              }}
            >
              {statusBadgeText}
            </span>
          </NavLink>

          <div className="sidebar-section-label" style={{ marginTop: 20 }}>Standards & Protocol</div>

          {[
            {
              icon: <FileText size={14} />,
              label: 'PHOENIX-301',
              tooltip: 'Phase III, Randomized, Double-Blind clinical trial studying Phoenixin (PNX-301) in patients with Advanced Non-Small Cell Lung Cancer (NSCLC). Covers visit schedules, dosing rules, banned co-medications, and required assessments across 200+ sites and 5000+ patient visits.',
            },
            {
              icon: <Scale size={14} />,
              label: 'ICH E6(R2) GCP',
              tooltip: 'International Council for Harmonisation — Good Clinical Practice guideline E6(R2). Defines the three-tier severity scale used to classify every detected deviation: Major (safety/data risk), Minor (non-compliance), or Administrative (documentation error).',
            },
            {
              icon: <Network size={14} />,
              label: 'HL7 FHIR R4',
              tooltip: 'Health Level 7 Fast Healthcare Interoperability Resources R4. The global standard format for exchanging patient data with hospital EHR/EDC systems. Trial data is exported as FHIR resources: Patient, Encounter, MedicationAdministration, DetectedIssue.',
            },
            {
              icon: <Database size={14} />,
              label: 'CDISC SDTM',
              tooltip: 'Clinical Data Interchange Standards Consortium — Study Data Tabulation Model. Regulatory submission standard required by the FDA. SDTM domain annotations (DM, SV, CM, FA) are embedded inside FHIR exports so data is ready for regulatory submission.',
            },
          ].map(({ icon, label, tooltip }) => (
            <div
              key={label}
              className="sidebar-info sidebar-info-tooltip"
              title={tooltip}
            >
              <span className="link-icon">{icon}</span>
              {label}
            </div>
          ))}
        </nav>

        <ThemeToggle />

        {/* User profile + logout */}
        {user && (
          <div className="sidebar-user">
            <div className="sidebar-user-avatar">
              {(user.full_name || user.email || 'U')
                .split(' ')
                .map((n) => n[0])
                .slice(0, 2)
                .join('')
                .toUpperCase()}
            </div>
            <div className="sidebar-user-info">
              <div className="sidebar-user-name">{user.full_name || user.email}</div>
              <div className="sidebar-user-role">{user.role}</div>
            </div>
            <button
              id="btn-logout"
              className="sidebar-logout-btn"
              title="Sign out"
              aria-label="Sign out"
              onClick={() => {
                logout()
                onLogout && onLogout()
              }}
            >
              <LogOut size={14} />
            </button>
          </div>
        )}

        <div style={{ padding: '8px 18px 14px', fontSize: 10.5, color: 'var(--text-muted)' }}>
          <div style={{ fontWeight: 600, marginBottom: 1 }}>TEAM PHOTON</div>
          <div>Bob AI Hackathon 2026</div>
        </div>
      </aside>
    </>
  )
}
