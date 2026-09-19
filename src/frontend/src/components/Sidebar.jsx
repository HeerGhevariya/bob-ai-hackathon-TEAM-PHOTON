import { useState, useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import { useNavigate, NavLink, useLocation } from 'react-router-dom'
import {
  LayoutDashboard, Hospital, AlertTriangle, ClipboardList,
  MessageSquare, FileText, Shield, LogOut, Menu, X,
  Wifi, WifiOff, Loader2, Scale, Network, Database,
} from 'lucide-react'
import ThemeToggle from './ThemeToggle'
import { fetchMcpStatus } from '../utils/api'
import { logout } from '../utils/auth'

const STANDARDS = [
  {
    icon: <FileText size={14} />,
    label: 'PHOENIX-301',
    accent: '#00b894',
    tag: 'Clinical Trial Protocol',
    desc: 'Phase III, Randomized, Double-Blind clinical trial studying Phoenixin (PNX-301) in patients with Advanced Non-Small Cell Lung Cancer (NSCLC).',
    bullets: ['Visit schedules & timing windows', 'Dosing rules & tolerances', 'Banned co-medications', 'Required assessments per visit', '200+ sites · 5000+ patient visits'],
  },
  {
    icon: <Scale size={14} />,
    label: 'ICH E6(R2) GCP',
    accent: '#f59e0b',
    tag: 'Severity Classification',
    desc: 'International Council for Harmonisation — Good Clinical Practice guideline E6(R2). Defines the regulatory grading scale for every detected deviation.',
    bullets: ['🔴 Major — safety or data integrity risk', '🟡 Minor — protocol non-compliance', '🔵 Administrative — documentation error'],
  },
  {
    icon: <Network size={14} />,
    label: 'HL7 FHIR R4',
    accent: '#3b82f6',
    tag: 'Data Export Standard',
    desc: 'Health Level 7 Fast Healthcare Interoperability Resources R4. Global standard for exchanging patient data with hospital EHR/EDC systems.',
    bullets: ['Patient → FHIR Patient resource', 'Visit → FHIR Encounter resource', 'Dose → MedicationAdministration', 'Deviation → DetectedIssue resource'],
  },
  {
    icon: <Database size={14} />,
    label: 'CDISC SDTM',
    accent: '#8b5cf6',
    tag: 'Regulatory Submission',
    desc: 'Clinical Data Interchange Standards Consortium — Study Data Tabulation Model. FDA-required format embedded as domain annotations inside FHIR exports.',
    bullets: ['DM — Demographics', 'SV — Subject Visits', 'CM — Concomitant Medications', 'FA — Findings About'],
  },
]

function StandardItem({ icon, label, accent, tag, desc, bullets }) {
  const itemRef = useRef(null)
  const [tooltip, setTooltip] = useState(null) // { top, left }

  const showTooltip = () => {
    if (!itemRef.current) return
    const rect = itemRef.current.getBoundingClientRect()
    setTooltip({ top: rect.top + rect.height / 2, left: rect.right + 12 })
  }
  const hideTooltip = () => setTooltip(null)

  return (
    <div
      ref={itemRef}
      className="sidebar-info sidebar-std-item"
      onMouseEnter={showTooltip}
      onMouseLeave={hideTooltip}
    >
      <span className="link-icon" style={{ color: accent }}>{icon}</span>
      <span>{label}</span>

      {tooltip && createPortal(
        <div
          className="std-tooltip std-tooltip-visible"
          style={{ top: tooltip.top, left: tooltip.left }}
        >
          <div className="std-tooltip-header" style={{ borderColor: accent }}>
            <span className="std-tooltip-icon" style={{ background: `${accent}22`, color: accent }}>{icon}</span>
            <div>
              <div className="std-tooltip-label">{label}</div>
              <div className="std-tooltip-tag" style={{ color: accent }}>{tag}</div>
            </div>
          </div>
          <p className="std-tooltip-desc">{desc}</p>
          <ul className="std-tooltip-bullets">
            {bullets.map(b => <li key={b}>{b}</li>)}
          </ul>
        </div>,
        document.body
      )}
    </div>
  )
}

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

          {STANDARDS.map(s => <StandardItem key={s.label} {...s} />)}
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
