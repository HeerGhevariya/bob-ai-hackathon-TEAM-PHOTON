import { useState } from 'react'
import { BarChart2, AlertTriangle, ClipboardList, Bot, Trophy, Scale, Shield } from 'lucide-react'
import { login, register } from '../utils/auth'

const DEMO_CREDENTIAL = {
  email: 'demo@trialgard.ai',
  password: 'Demo@2026',
  role: 'Demo',
  label: 'Demo Access',
  description: 'Full access to all trial data, risk reports & AI assistant',
}

export default function LoginPage({ onAuthenticated }) {
  const [tab, setTab] = useState('login') // 'login' | 'register'
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [fullName, setFullName] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [fieldErrors, setFieldErrors] = useState({})

  const applyDemo = () => {
    setTab('login')
    setEmail(DEMO_CREDENTIAL.email)
    setPassword(DEMO_CREDENTIAL.password)
    setError('')
    setFieldErrors({})
  }

  const validate = () => {
    const errs = {}
    if (!email.trim()) errs.email = 'Email is required'
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) errs.email = 'Enter a valid email'
    if (!password) errs.password = 'Password is required'
    else if (tab === 'register' && password.length < 6) errs.password = 'Minimum 6 characters'
    if (tab === 'register' && !fullName.trim()) errs.fullName = 'Full name is required'
    return errs
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    const errs = validate()
    setFieldErrors(errs)
    if (Object.keys(errs).length > 0) return

    setLoading(true)
    try {
      let user
      if (tab === 'login') {
        user = await login(email.trim(), password)
      } else {
        user = await register(email.trim(), password, fullName.trim())
      }
      onAuthenticated(user)
    } catch (err) {
      setError(err.message || 'Something went wrong. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="login-root">
      {/* Animated background */}
      <div className="login-bg">
        <div className="login-bg-grid" />
        <div className="login-bg-glow login-bg-glow-1" />
        <div className="login-bg-glow login-bg-glow-2" />
        <div className="login-bg-glow login-bg-glow-3" />
      </div>

      <div className="login-layout">
        {/* Left — Branding panel */}
        <div className="login-brand-panel">
          <div className="login-brand-content">
            <div className="login-logo">
              <span className="login-logo-icon"><Shield size={48} /></span>
              <span className="login-logo-text">
                Trial<span className="login-logo-accent">Guard</span> AI
              </span>
            </div>
            <p className="login-tagline">Clinical Trial Risk Monitor &amp; Protocol Deviation Detector</p>

            <div className="login-features">
              {[
                { icon: <BarChart2 size={18} />, label: 'Real-time Risk Scoring', desc: 'Composite risk scores across all trial sites' },
                { icon: <AlertTriangle size={18} />, label: 'Protocol Deviation Detection', desc: 'AI-powered deviation classification & severity' },
                { icon: <ClipboardList size={18} />, label: 'CAPA Report Generation', desc: 'Automated corrective action reports via watsonx.ai' },
                { icon: <Bot size={18} />, label: 'MCP-Powered AI Assistant', desc: 'IBM Bob-integrated conversational data analysis' },
              ].map((f) => (
                <div key={f.label} className="login-feature">
                  <span className="login-feature-icon">{f.icon}</span>
                  <div>
                    <div className="login-feature-label">{f.label}</div>
                    <div className="login-feature-desc">{f.desc}</div>
                  </div>
                </div>
              ))}
            </div>

            <div className="login-hackathon-badge">
              <Trophy size={13} />
              <span>Bob AI Hackathon 2026 — Team Photon</span>
            </div>
          </div>
        </div>

        {/* Right — Auth card */}
        <div className="login-card-panel">
          <div className="login-card">
            {/* Tab switcher */}
            <div className="login-tabs">
              <button
                id="tab-login"
                className={`login-tab ${tab === 'login' ? 'active' : ''}`}
                onClick={() => { setTab('login'); setError(''); setFieldErrors({}) }}
              >
                Sign In
              </button>
              <button
                id="tab-register"
                className={`login-tab ${tab === 'register' ? 'active' : ''}`}
                onClick={() => { setTab('register'); setError(''); setFieldErrors({}) }}
              >
                Register
              </button>
            </div>

            <h2 className="login-card-title">
              {tab === 'login' ? 'Welcome back' : 'Create account'}
            </h2>
            <p className="login-card-subtitle">
              {tab === 'login'
                ? 'Sign in to access the TrialGuard AI dashboard'
                : 'Register to start monitoring clinical trial risks'}
            </p>

            {/* Demo credential card — login tab only */}
            {tab === 'login' && (
              <div className="login-demo-card" onClick={applyDemo} id="demo-credential-card" role="button" tabIndex={0} onKeyDown={e => e.key === 'Enter' && applyDemo()}>
                <div className="login-demo-badge">DEMO ACCESS</div>
                <div className="login-demo-header">
                  <span className="login-demo-role-icon"><Scale size={20} /></span>
                  <div>
                    <div className="login-demo-role">{DEMO_CREDENTIAL.label}</div>
                    <div className="login-demo-desc">{DEMO_CREDENTIAL.description}</div>
                  </div>
                </div>
                <div className="login-demo-creds">
                  <div className="login-demo-cred-row">
                    <span className="login-demo-cred-label">Email</span>
                    <span className="login-demo-cred-value">{DEMO_CREDENTIAL.email}</span>
                  </div>
                  <div className="login-demo-cred-row">
                    <span className="login-demo-cred-label">Password</span>
                    <span className="login-demo-cred-value">{DEMO_CREDENTIAL.password}</span>
                  </div>
                </div>
                <div className="login-demo-hint">Click to auto-fill credentials</div>
              </div>
            )}

            {/* Form */}
            <form className="login-form" onSubmit={handleSubmit} noValidate>
              {tab === 'register' && (
                <div className="login-field">
                  <label htmlFor="field-fullname" className="login-label">Full Name</label>
                  <input
                    id="field-fullname"
                    type="text"
                    className={`login-input ${fieldErrors.fullName ? 'error' : ''}`}
                    placeholder="Dr. Jane Smith"
                    value={fullName}
                    onChange={e => setFullName(e.target.value)}
                    autoComplete="name"
                  />
                  {fieldErrors.fullName && <span className="login-field-error">{fieldErrors.fullName}</span>}
                </div>
              )}

              <div className="login-field">
                <label htmlFor="field-email" className="login-label">Email Address</label>
                <input
                  id="field-email"
                  type="email"
                  className={`login-input ${fieldErrors.email ? 'error' : ''}`}
                  placeholder="you@example.com"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  autoComplete="email"
                />
                {fieldErrors.email && <span className="login-field-error">{fieldErrors.email}</span>}
              </div>

              <div className="login-field">
                <label htmlFor="field-password" className="login-label">Password</label>
                <input
                  id="field-password"
                  type="password"
                  className={`login-input ${fieldErrors.password ? 'error' : ''}`}
                  placeholder={tab === 'register' ? 'Minimum 6 characters' : '••••••••'}
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  autoComplete={tab === 'login' ? 'current-password' : 'new-password'}
                />
                {fieldErrors.password && <span className="login-field-error">{fieldErrors.password}</span>}
              </div>

              {error && (
                <div className="login-error-banner" role="alert">
                  <AlertTriangle size={15} />
                  <span>{error}</span>
                </div>
              )}

              <button
                id="btn-submit-auth"
                type="submit"
                className="login-submit-btn"
                disabled={loading}
              >
                {loading
                  ? <span className="login-spinner" />
                  : tab === 'login' ? 'Sign In to Dashboard →' : 'Create Account →'}
              </button>
            </form>

            <p className="login-switch-text">
              {tab === 'login' ? "Don't have an account? " : 'Already have an account? '}
              <button
                className="login-switch-link"
                onClick={() => { setTab(tab === 'login' ? 'register' : 'login'); setError(''); setFieldErrors({}) }}
              >
                {tab === 'login' ? 'Register' : 'Sign in'}
              </button>
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
