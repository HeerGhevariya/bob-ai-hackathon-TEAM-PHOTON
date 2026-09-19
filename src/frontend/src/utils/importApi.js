/**
 * importApi.js — Frontend API helpers for the Data Import feature
 *
 * All calls include the Bearer token from localStorage.
 * Errors are thrown as plain Error objects with readable messages.
 */

import { getToken } from './auth'

const API_BASE = '/api/imports'

function authHeaders() {
  const token = getToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

async function _handleResponse(res) {
  if (res.status === 401) throw new Error('Session expired. Please log in again.')
  if (res.status === 403) throw new Error('Admin access is required to use the Data Import feature.')
  if (res.status === 503) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail || 'Data import is not available in this deployment mode.')
  }
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    const msg = data?.detail?.message || data?.detail || `Server error (${res.status})`
    const err = new Error(msg)
    err.detail = data?.detail
    err.status = res.status
    // Preserve per-row errors array from commit re-validation failures (422)
    err.errors = data?.detail?.errors ?? null
    throw err
  }
  return res.json()
}

/**
 * Validate a file (dry-run). Returns the validation report + import_token.
 * @param {File} file
 * @param {string} sourceLabel
 */
export async function validateImport(file, sourceLabel = '') {
  const body = new FormData()
  body.append('file', file)
  body.append('source_label', sourceLabel)

  const res = await fetch(`${API_BASE}/validate`, {
    method: 'POST',
    headers: authHeaders(),
    body,
  })
  return _handleResponse(res)
}

/**
 * Commit a validated import.
 * @param {File} file        — same file that was validated
 * @param {string} importToken — token returned by validateImport
 * @param {'skip'|'update'} onConflict
 * @param {string} sourceLabel
 */
export async function commitImport(file, importToken, onConflict = 'skip', sourceLabel = '') {
  const body = new FormData()
  body.append('file', file)
  body.append('import_token', importToken)
  body.append('on_conflict', onConflict)
  body.append('source_label', sourceLabel)

  const res = await fetch(`${API_BASE}/commit`, {
    method: 'POST',
    headers: authHeaders(),
    body,
  })
  return _handleResponse(res)
}

/**
 * Download the import template.
 * @param {'csv'|'xlsx'} format
 */
export async function downloadTemplate(format = 'csv') {
  const res = await fetch(`${API_BASE}/template?format=${format}`, {
    headers: authHeaders(),
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data?.detail || `Failed to download template (${res.status})`)
  }
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `trialguard_import_template.${format}`
  a.click()
  URL.revokeObjectURL(url)
}

/**
 * Download the error report as a CSV string (client-side, no server call).
 * @param {Array} errors — array of {row, column, value, reason}
 * @returns {string} CSV content
 */
export function buildErrorCsv(errors) {
  const header = 'row,column,value,reason\n'
  const lines = errors.map(e => {
    const esc = (s) => `"${String(s ?? '').replace(/"/g, '""')}"`
    return [esc(e.row), esc(e.column), esc(e.value), esc(e.reason)].join(',')
  })
  return header + lines.join('\n')
}

/**
 * Fetch import history.
 */
export async function fetchImportHistory(limit = 20, offset = 0) {
  const res = await fetch(`${API_BASE}?limit=${limit}&offset=${offset}`, {
    headers: authHeaders(),
  })
  return _handleResponse(res)
}

/**
 * Fetch column spec (for help text).
 */
export async function fetchColumnSpec() {
  const res = await fetch(`${API_BASE}/columns`, {
    headers: authHeaders(),
  })
  return _handleResponse(res)
}
