/**
 * auth.js — TrialGuard AI Authentication Utilities
 *
 * Manages JWT tokens in localStorage and provides
 * login / register / logout / session helpers.
 */

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8080'
const TOKEN_KEY = 'trialgard_token'
const USER_KEY = 'trialgard_user'

// ─── Storage helpers ───────────────────────────────────────────────

export function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}

export function getUser() {
  try {
    const raw = localStorage.getItem(USER_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

export function isAuthenticated() {
  const token = getToken()
  if (!token) return false
  try {
    // Decode JWT payload (no signature verification — server validates)
    const payload = JSON.parse(atob(token.split('.')[1]))
    // Check expiry
    if (payload.exp && payload.exp < Math.floor(Date.now() / 1000)) {
      clearSession()
      return false
    }
    return true
  } catch {
    return false
  }
}

function saveSession(token, user) {
  localStorage.setItem(TOKEN_KEY, token)
  localStorage.setItem(USER_KEY, JSON.stringify(user))
}

export function clearSession() {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
}

// ─── API calls ─────────────────────────────────────────────────────

export async function login(email, password) {
  const res = await fetch(`${API_BASE}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })
  const data = await res.json()
  if (!res.ok) {
    throw new Error(data.detail || 'Login failed')
  }
  saveSession(data.access_token, data.user)
  return data.user
}

export async function register(email, password, full_name) {
  const res = await fetch(`${API_BASE}/api/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password, full_name }),
  })
  const data = await res.json()
  if (!res.ok) {
    throw new Error(data.detail || 'Registration failed')
  }
  saveSession(data.access_token, data.user)
  return data.user
}

export function logout() {
  clearSession()
}
