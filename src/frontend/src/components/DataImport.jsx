/**
 * DataImport.jsx — Admin-only Data Import page
 *
 * Six-step flow:
 *   1. Source label + template download
 *   2. File pick / drag-drop (client validates extension + size)
 *   3. Validate — loading → report (counts, ignored cols, warnings, errors)
 *   4. Conflict option (skip / update)
 *   5. Confirm dialog
 *   6. Result screen (counts, tier changes, stale CAPA notice)
 *
 * Import history table at the bottom.
 * All API errors are caught and shown with readable messages.
 */

import { useState, useCallback, useRef, useEffect } from 'react'
import { Link } from 'react-router-dom'
import {
  Upload, FileText, AlertTriangle, CheckCircle2, XCircle,
  ChevronRight, Download, Loader2, RefreshCw, Clock,
  Info, Database, ArrowRight, TriangleAlert,
} from 'lucide-react'
import {
  validateImport,
  commitImport,
  downloadTemplate,
  buildErrorCsv,
  fetchImportHistory,
} from '../utils/importApi'

// ── Constants ──────────────────────────────────────────────────────────────────
const MAX_FILE_BYTES = 10 * 1024 * 1024  // 10 MB (client-side pre-check)
const ACCEPTED_EXTENSIONS = ['.csv', '.xlsx']

const STEPS = ['Source', 'File', 'Validate', 'Options', 'Confirm', 'Result']

// ── Small helpers ──────────────────────────────────────────────────────────────
function fmt(n) { return (n ?? 0).toLocaleString() }

function StepIndicator({ current }) {
  return (
    <div style={{ display: 'flex', gap: 0, marginBottom: 28, alignItems: 'center' }}>
      {STEPS.map((label, i) => {
        const done    = i < current
        const active  = i === current
        return (
          <div key={label} style={{ display: 'flex', alignItems: 'center' }}>
            <div style={{
              display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4,
            }}>
              <div style={{
                width: 28, height: 28, borderRadius: '50%', display: 'flex',
                alignItems: 'center', justifyContent: 'center', fontSize: 12,
                fontWeight: 600,
                background: done ? 'var(--accent)' : active ? 'var(--accent)' : 'var(--surface)',
                color: (done || active) ? '#fff' : 'var(--text-muted)',
                border: `2px solid ${(done || active) ? 'var(--accent)' : 'var(--border)'}`,
              }}>
                {done ? <CheckCircle2 size={14} /> : i + 1}
              </div>
              <span style={{ fontSize: 10, color: active ? 'var(--accent)' : 'var(--text-muted)', whiteSpace: 'nowrap' }}>
                {label}
              </span>
            </div>
            {i < STEPS.length - 1 && (
              <div style={{
                width: 32, height: 2, background: done ? 'var(--accent)' : 'var(--border)',
                margin: '0 4px', marginBottom: 18,
              }} />
            )}
          </div>
        )
      })}
    </div>
  )
}

function Card({ children, style }) {
  return (
    <div style={{
      background: 'var(--surface)', border: '1px solid var(--border)',
      borderRadius: 10, padding: 24, marginBottom: 16, ...style,
    }}>
      {children}
    </div>
  )
}

function Alert({ type = 'info', children }) {
  const colors = {
    info:    { bg: 'rgba(59,130,212,0.08)', border: '#3b82d4', icon: <Info size={14} /> },
    warn:    { bg: 'rgba(245,158,11,0.08)', border: '#f59e0b', icon: <TriangleAlert size={14} /> },
    error:   { bg: 'rgba(239,68,68,0.08)',  border: '#ef4444', icon: <XCircle size={14} /> },
    success: { bg: 'rgba(34,197,94,0.08)',  border: '#22c55e', icon: <CheckCircle2 size={14} /> },
  }
  const c = colors[type]
  return (
    <div style={{
      background: c.bg, border: `1px solid ${c.border}`, borderRadius: 8,
      padding: '10px 14px', display: 'flex', gap: 10, alignItems: 'flex-start',
      color: c.border, fontSize: 13, marginBottom: 12,
    }}>
      <span style={{ marginTop: 1 }}>{c.icon}</span>
      <span style={{ color: 'var(--text)' }}>{children}</span>
    </div>
  )
}

function ErrorTable({ errors }) {
  if (!errors?.length) return null
  return (
    <div style={{ overflowX: 'auto', marginTop: 8 }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
        <thead>
          <tr style={{ background: 'var(--surface)', borderBottom: '1px solid var(--border)' }}>
            {['Row', 'Column', 'Value', 'Reason'].map(h => (
              <th key={h} style={{ padding: '6px 10px', textAlign: 'left', color: 'var(--text-muted)', fontWeight: 600 }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {errors.map((e, i) => (
            <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
              <td style={{ padding: '5px 10px', color: '#ef4444' }}>{e.row}</td>
              <td style={{ padding: '5px 10px', fontFamily: 'monospace' }}>{e.column}</td>
              <td style={{ padding: '5px 10px', fontFamily: 'monospace', maxWidth: 120, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={e.value}>{e.value || '(blank)'}</td>
              <td style={{ padding: '5px 10px', color: 'var(--text)' }}>{e.reason}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function CountRow({ label, value, accent }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid var(--border)', fontSize: 13 }}>
      <span style={{ color: 'var(--text-muted)' }}>{label}</span>
      <span style={{ fontWeight: 600, color: accent || 'var(--text)' }}>{fmt(value)}</span>
    </div>
  )
}

function TierBadge({ tier }) {
  const colors = { critical: '#ef4444', high: '#f97316', medium: '#f59e0b', low: '#22c55e' }
  return (
    <span style={{
      background: `${colors[tier] || '#999'}22`, color: colors[tier] || '#999',
      borderRadius: 4, padding: '2px 8px', fontSize: 11, fontWeight: 700, textTransform: 'uppercase',
    }}>
      {tier}
    </span>
  )
}

// ── Import History ─────────────────────────────────────────────────────────────
function ImportHistory({ refresh }) {
  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await fetchImportHistory(20, 0)
      setHistory(data.imports || [])
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load, refresh])

  const statusColor = { committed: '#22c55e', failed: '#ef4444', pending: '#f59e0b' }

  return (
    <Card>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <h3 style={{ margin: 0, fontSize: 15, display: 'flex', alignItems: 'center', gap: 8 }}>
          <Clock size={15} /> Import History
        </h3>
        <button
          onClick={load}
          style={{ background: 'none', border: '1px solid var(--border)', borderRadius: 6, padding: '4px 10px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--text-muted)' }}
        >
          <RefreshCw size={12} /> Refresh
        </button>
      </div>

      {error && <Alert type="error">{error}</Alert>}
      {loading && <div style={{ color: 'var(--text-muted)', fontSize: 13, padding: 8 }}>Loading…</div>}

      {!loading && !error && history.length === 0 && (
        <div style={{ color: 'var(--text-muted)', fontSize: 13, padding: 8 }}>No imports yet.</div>
      )}

      {history.length > 0 && (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)' }}>
                {['Date', 'Source', 'File', 'Layout', 'Rows', 'New Visits', 'Status'].map(h => (
                  <th key={h} style={{ padding: '6px 10px', textAlign: 'left', color: 'var(--text-muted)', fontWeight: 600 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {history.map(imp => (
                <tr key={imp.import_id} style={{ borderBottom: '1px solid var(--border)' }}>
                  <td style={{ padding: '5px 10px', whiteSpace: 'nowrap' }}>
                    {new Date(imp.created_at).toLocaleString()}
                  </td>
                  <td style={{ padding: '5px 10px' }}>{imp.source_label || '—'}</td>
                  <td style={{ padding: '5px 10px', fontFamily: 'monospace', fontSize: 11 }}>{imp.filename}</td>
                  <td style={{ padding: '5px 10px' }}>{imp.layout}</td>
                  <td style={{ padding: '5px 10px' }}>{fmt(imp.rows_total)}</td>
                  <td style={{ padding: '5px 10px' }}>{fmt(imp.visits_new)}</td>
                  <td style={{ padding: '5px 10px' }}>
                    <span style={{ color: statusColor[imp.status] || 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase', fontSize: 11 }}>
                      {imp.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  )
}


// ── Main Component ─────────────────────────────────────────────────────────────
export default function DataImport() {
  const [step, setStep] = useState(0)      // 0–5
  const [sourceLabel, setSourceLabel] = useState('')
  const [file, setFile] = useState(null)
  const [fileError, setFileError] = useState(null)
  const [dragOver, setDragOver] = useState(false)

  const [validating, setValidating] = useState(false)
  const [validationResult, setValidationResult] = useState(null)
  const [importToken, setImportToken] = useState(null)
  const [validateError, setValidateError] = useState(null)

  const [onConflict, setOnConflict] = useState('skip')

  const [committing, setCommitting] = useState(false)
  const [commitResult, setCommitResult] = useState(null)
  const [commitError, setCommitError] = useState(null)
  const [commitErrors, setCommitErrors] = useState(null)  // per-row error list from re-validation 422

  const [historyRefresh, setHistoryRefresh] = useState(0)

  const dropRef = useRef(null)

  // ── File validation ──────────────────────────────────────────────────────────
  function checkFile(f) {
    setFileError(null)
    if (!f) return false
    const lower = f.name.toLowerCase()
    if (!ACCEPTED_EXTENSIONS.some(ext => lower.endsWith(ext))) {
      setFileError(`Unsupported file type "${f.name}". Only .csv and .xlsx are accepted.`)
      return false
    }
    if (f.name.toLowerCase().endsWith('.xls')) {
      setFileError('Legacy .xls files are not accepted. Please export as .xlsx or .csv.')
      return false
    }
    if (f.size > MAX_FILE_BYTES) {
      setFileError(`File is ${(f.size / 1024 / 1024).toFixed(1)} MB. Maximum is 10 MB.`)
      return false
    }
    return true
  }

  function handleFileChange(e) {
    const f = e.target.files?.[0]
    if (f && checkFile(f)) {
      setFile(f)
    }
  }

  function handleDrop(e) {
    e.preventDefault()
    setDragOver(false)
    const f = e.dataTransfer.files?.[0]
    if (f && checkFile(f)) {
      setFile(f)
    }
  }

  // ── Validate step ────────────────────────────────────────────────────────────
  async function runValidate() {
    if (!file) return
    setValidating(true)
    setValidateError(null)
    try {
      const result = await validateImport(file, sourceLabel)
      setValidationResult(result)
      setImportToken(result.import_token)
      setStep(3)  // go to Options step
    } catch (e) {
      setValidateError(e.message)
    } finally {
      setValidating(false)
    }
  }

  // ── Commit step ──────────────────────────────────────────────────────────────
  async function runCommit() {
    if (!file || !importToken) return
    setCommitting(true)
    setCommitError(null)
    setCommitErrors(null)
    try {
      const result = await commitImport(file, importToken, onConflict, sourceLabel)
      setCommitResult(result)
      setStep(5)  // Result
      setHistoryRefresh(r => r + 1)
    } catch (e) {
      setCommitError(e.message)
      // Attach per-row errors from re-validation failures so user sees what went wrong
      if (e.errors?.length) setCommitErrors(e.errors)
    } finally {
      setCommitting(false)
    }
  }

  // ── Error CSV download ───────────────────────────────────────────────────────
  function downloadErrors() {
    if (!validationResult?.errors?.length) return
    const csv = buildErrorCsv(validationResult.errors)
    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'trialguard_import_errors.csv'
    a.click()
    URL.revokeObjectURL(url)
  }

  // ── Reset ────────────────────────────────────────────────────────────────────
  function reset() {
    setStep(0)
    setFile(null)
    setFileError(null)
    setValidationResult(null)
    setImportToken(null)
    setValidateError(null)
    setCommitResult(null)
    setCommitError(null)
    setCommitErrors(null)
    setOnConflict('skip')
  }

  // ── Render ────────────────────────────────────────────────────────────────────
  const vr = validationResult
  const hasErrors = vr?.blocking
  const totalNew = (vr?.visits?.new ?? 0)
  const totalSitesNew = (vr?.sites?.new ?? 0)
  const totalPatientsNew = (vr?.patients?.new ?? 0)

  return (
    <div style={{ maxWidth: 860, margin: '0 auto', padding: '24px 20px' }}>
      <div style={{ marginBottom: 24 }}>
        <h2 style={{ margin: 0, fontSize: 22, display: 'flex', alignItems: 'center', gap: 10 }}>
          <Database size={20} /> Data Import
        </h2>
        <p style={{ margin: '6px 0 0', color: 'var(--text-muted)', fontSize: 13 }}>
          Upload hospital visit data as CSV or XLSX. Data is appended to the existing
          PHOENIX-301 demo dataset — existing deviation detection and risk scoring run
          automatically on the new data.
        </p>
        <Alert type="info">
          <strong>Data provenance:</strong> imported data is added to the same demo dataset used
          by all other views. Deviations and risk scores for affected sites are recomputed
          immediately after a successful import.
        </Alert>
      </div>

      <StepIndicator current={step} />

      {/* ── Step 0: Source ──────────────────────────────────────────────────── */}
      {step === 0 && (
        <Card>
          <h3 style={{ marginTop: 0, fontSize: 15 }}>Step 1 — Identify the data source</h3>
          <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>
            Give this import a label (e.g. the hospital name) so you can identify it in the
            import history.
          </p>
          <div style={{ marginBottom: 20 }}>
            <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 6 }}>
              Source Label
            </label>
            <input
              type="text"
              value={sourceLabel}
              onChange={e => setSourceLabel(e.target.value)}
              placeholder="e.g. Mumbai Oncology Center"
              style={{
                width: '100%', padding: '8px 12px', borderRadius: 6,
                border: '1px solid var(--border)', background: 'var(--bg)',
                color: 'var(--text)', fontSize: 14, boxSizing: 'border-box',
              }}
            />
          </div>

          <div style={{ marginBottom: 20 }}>
            <p style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>Download a template to get started:</p>
            <div style={{ display: 'flex', gap: 10 }}>
              <button
                onClick={() => downloadTemplate('csv').catch(e => alert(e.message))}
                style={{
                  display: 'flex', alignItems: 'center', gap: 7, padding: '8px 16px',
                  background: 'var(--surface)', border: '1px solid var(--border)',
                  borderRadius: 6, cursor: 'pointer', fontSize: 13, color: 'var(--text)',
                }}
              >
                <Download size={14} /> Download CSV template
              </button>
              <button
                onClick={() => downloadTemplate('xlsx').catch(e => alert(e.message))}
                style={{
                  display: 'flex', alignItems: 'center', gap: 7, padding: '8px 16px',
                  background: 'var(--surface)', border: '1px solid var(--border)',
                  borderRadius: 6, cursor: 'pointer', fontSize: 13, color: 'var(--text)',
                }}
              >
                <Download size={14} /> Download XLSX template
              </button>
            </div>
          </div>

          <button
            onClick={() => setStep(1)}
            style={{
              display: 'flex', alignItems: 'center', gap: 8, padding: '9px 20px',
              background: 'var(--accent)', color: '#fff', border: 'none',
              borderRadius: 6, cursor: 'pointer', fontWeight: 600, fontSize: 13,
            }}
          >
            Continue <ChevronRight size={14} />
          </button>
        </Card>
      )}

      {/* ── Step 1: File ────────────────────────────────────────────────────── */}
      {step === 1 && (
        <Card>
          <h3 style={{ marginTop: 0, fontSize: 15 }}>Step 2 — Upload a file</h3>
          <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>
            Accepted: .csv and .xlsx only. Maximum 10 MB.
          </p>

          {/* Drop zone */}
          <div
            ref={dropRef}
            onDragOver={e => { e.preventDefault(); setDragOver(true) }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
            onClick={() => document.getElementById('file-input').click()}
            style={{
              border: `2px dashed ${dragOver ? 'var(--accent)' : 'var(--border)'}`,
              borderRadius: 10, padding: '40px 24px', textAlign: 'center',
              cursor: 'pointer', background: dragOver ? 'rgba(59,130,212,0.04)' : 'var(--bg)',
              transition: 'all 0.15s', marginBottom: 16,
            }}
          >
            <Upload size={28} style={{ color: 'var(--text-muted)', marginBottom: 12 }} />
            {file ? (
              <div>
                <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 4 }}>{file.name}</div>
                <div style={{ color: 'var(--text-muted)', fontSize: 12 }}>
                  {(file.size / 1024).toFixed(1)} KB — click or drop to change
                </div>
              </div>
            ) : (
              <div>
                <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 4 }}>
                  Drag & drop your file here
                </div>
                <div style={{ color: 'var(--text-muted)', fontSize: 12 }}>
                  or click to browse (.csv, .xlsx)
                </div>
              </div>
            )}
          </div>
          <input
            id="file-input"
            type="file"
            accept=".csv,.xlsx"
            style={{ display: 'none' }}
            onChange={handleFileChange}
          />

          {fileError && <Alert type="error">{fileError}</Alert>}

          <div style={{ display: 'flex', gap: 10 }}>
            <button onClick={() => setStep(0)} style={{
              padding: '8px 16px', background: 'var(--surface)', border: '1px solid var(--border)',
              borderRadius: 6, cursor: 'pointer', fontSize: 13, color: 'var(--text)',
            }}>
              Back
            </button>
            <button
              onClick={() => { if (file) setStep(2) }}
              disabled={!file}
              style={{
                display: 'flex', alignItems: 'center', gap: 8, padding: '9px 20px',
                background: file ? 'var(--accent)' : 'var(--border)', color: file ? '#fff' : 'var(--text-muted)',
                border: 'none', borderRadius: 6, cursor: file ? 'pointer' : 'not-allowed',
                fontWeight: 600, fontSize: 13,
              }}
            >
              Continue <ChevronRight size={14} />
            </button>
          </div>
        </Card>
      )}

      {/* ── Step 2: Validate ────────────────────────────────────────────────── */}
      {step === 2 && (
        <Card>
          <h3 style={{ marginTop: 0, fontSize: 15 }}>Step 3 — Validate</h3>
          <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>
            Run a dry-run check. Nothing is written to the database.
          </p>

          {file && (
            <div style={{
              display: 'flex', alignItems: 'center', gap: 10, padding: '10px 14px',
              background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 8,
              marginBottom: 16, fontSize: 13,
            }}>
              <FileText size={16} style={{ color: 'var(--accent)' }} />
              <span style={{ fontWeight: 600 }}>{file.name}</span>
              <span style={{ color: 'var(--text-muted)' }}>({(file.size / 1024).toFixed(1)} KB)</span>
            </div>
          )}

          {validateError && <Alert type="error">{validateError}</Alert>}

          {validating ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '20px 0', color: 'var(--text-muted)' }}>
              <Loader2 size={18} style={{ animation: 'spin 1s linear infinite' }} />
              Validating file…
            </div>
          ) : vr ? (
            <div>
              {/* Counts */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12, marginBottom: 16 }}>
                {[
                  { label: 'Sites', obj: vr.sites },
                  { label: 'Patients', obj: vr.patients },
                  { label: 'Visits', obj: vr.visits },
                ].map(({ label, obj }) => (
                  <div key={label} style={{
                    background: 'var(--bg)', border: '1px solid var(--border)',
                    borderRadius: 8, padding: '12px 14px',
                  }}>
                    <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 6 }}>{label}</div>
                    <CountRow label="New"     value={obj?.new}             accent="#22c55e" />
                    <CountRow label="Unchanged" value={obj?.existing_same}  />
                    <CountRow label="Changed"  value={obj?.existing_changed} accent="#f59e0b" />
                  </div>
                ))}
              </div>

              {/* Layout */}
              <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 10 }}>
                Layout detected: <strong style={{ color: 'var(--text)' }}>{vr.layout}</strong>
                {' · '}{fmt(vr.row_count)} data rows
              </div>

              {/* Ignored columns */}
              {vr.ignored_columns?.length > 0 && (
                <Alert type="warn">
                  <strong>Ignored columns ({vr.ignored_columns.length}):</strong>{' '}
                  {vr.ignored_columns.join(', ')}
                </Alert>
              )}

              {/* Server-computed found */}
              {vr.server_computed_found?.length > 0 && (
                <Alert type="info">
                  <strong>Server-computed columns ignored:</strong>{' '}
                  {vr.server_computed_found.join(', ')}.
                  These are always computed by TrialGuard's pipeline.
                </Alert>
              )}

              {/* Warnings */}
              {vr.warnings?.map((w, i) => (
                <Alert key={i} type="warn">{w}</Alert>
              ))}

              {/* Errors */}
              {hasErrors ? (
                <div>
                  <div style={{
                    display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8,
                  }}>
                    <div style={{ color: '#ef4444', fontWeight: 600, fontSize: 13, display: 'flex', alignItems: 'center', gap: 8 }}>
                      <AlertTriangle size={14} />
                      {fmt(vr.total_error_count)} blocking error{vr.total_error_count !== 1 ? 's' : ''}
                      {vr.total_error_count > vr.errors?.length
                        ? ` (showing first ${vr.errors?.length})`
                        : ''}
                    </div>
                    <button
                      onClick={downloadErrors}
                      style={{
                        display: 'flex', alignItems: 'center', gap: 6, padding: '5px 12px',
                        background: 'var(--surface)', border: '1px solid var(--border)',
                        borderRadius: 6, cursor: 'pointer', fontSize: 12, color: 'var(--text)',
                      }}
                    >
                      <Download size={12} /> Download error report (CSV)
                    </button>
                  </div>
                  <ErrorTable errors={vr.errors} />
                  <Alert type="error">
                    Fix all blocking errors before committing. Download the error report,
                    correct the file, and re-upload.
                  </Alert>
                </div>
              ) : (
                <Alert type="success">
                  Validation passed — no blocking errors found.
                </Alert>
              )}
            </div>
          ) : null}

          <div style={{ display: 'flex', gap: 10, marginTop: 16 }}>
            <button onClick={() => setStep(1)} style={{
              padding: '8px 16px', background: 'var(--surface)', border: '1px solid var(--border)',
              borderRadius: 6, cursor: 'pointer', fontSize: 13, color: 'var(--text)',
            }}>
              Back
            </button>
            {!vr ? (
              <button
                onClick={runValidate}
                disabled={validating}
                style={{
                  display: 'flex', alignItems: 'center', gap: 8, padding: '9px 20px',
                  background: 'var(--accent)', color: '#fff', border: 'none',
                  borderRadius: 6, cursor: 'pointer', fontWeight: 600, fontSize: 13,
                }}
              >
                {validating
                  ? <><Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} /> Validating…</>
                  : <><CheckCircle2 size={14} /> Validate file</>
                }
              </button>
            ) : (
              <div style={{ display: 'flex', gap: 10 }}>
                <button onClick={() => { setValidationResult(null); setValidateError(null) }} style={{
                  padding: '8px 16px', background: 'var(--surface)', border: '1px solid var(--border)',
                  borderRadius: 6, cursor: 'pointer', fontSize: 13, color: 'var(--text)',
                }}>
                  Re-validate
                </button>
                {!hasErrors && (
                  <button
                    onClick={() => setStep(3)}
                    style={{
                      display: 'flex', alignItems: 'center', gap: 8, padding: '9px 20px',
                      background: 'var(--accent)', color: '#fff', border: 'none',
                      borderRadius: 6, cursor: 'pointer', fontWeight: 600, fontSize: 13,
                    }}
                  >
                    Continue <ChevronRight size={14} />
                  </button>
                )}
              </div>
            )}
          </div>
        </Card>
      )}

      {/* ── Step 3: Options ─────────────────────────────────────────────────── */}
      {step === 3 && vr && (
        <Card>
          <h3 style={{ marginTop: 0, fontSize: 15 }}>Step 4 — Conflict option</h3>
          <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>
            What should happen when a visit already exists in the database?
          </p>

          {[
            {
              value: 'skip',
              label: 'Add new rows only (recommended)',
              desc: 'Existing visits are left completely unchanged. New sites, patients and visits are added.',
            },
            {
              value: 'update',
              label: 'Add new and update changed rows',
              desc: `Existing visits whose values differ from the file will be updated. ${fmt(vr.visits?.existing_changed)} visit(s) in this file differ from the database.`,
            },
          ].map(opt => (
            <div
              key={opt.value}
              onClick={() => setOnConflict(opt.value)}
              style={{
                border: `2px solid ${onConflict === opt.value ? 'var(--accent)' : 'var(--border)'}`,
                borderRadius: 8, padding: '14px 16px', marginBottom: 12, cursor: 'pointer',
                background: onConflict === opt.value ? 'rgba(59,130,212,0.04)' : 'var(--bg)',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontWeight: 600, fontSize: 13, marginBottom: 4 }}>
                <div style={{
                  width: 16, height: 16, borderRadius: '50%',
                  border: `2px solid ${onConflict === opt.value ? 'var(--accent)' : 'var(--border)'}`,
                  background: onConflict === opt.value ? 'var(--accent)' : 'transparent',
                  flexShrink: 0,
                }} />
                {opt.label}
              </div>
              <div style={{ fontSize: 12, color: 'var(--text-muted)', marginLeft: 24 }}>{opt.desc}</div>
            </div>
          ))}

          <div style={{ display: 'flex', gap: 10, marginTop: 8 }}>
            <button onClick={() => setStep(2)} style={{
              padding: '8px 16px', background: 'var(--surface)', border: '1px solid var(--border)',
              borderRadius: 6, cursor: 'pointer', fontSize: 13, color: 'var(--text)',
            }}>
              Back
            </button>
            <button
              onClick={() => setStep(4)}
              style={{
                display: 'flex', alignItems: 'center', gap: 8, padding: '9px 20px',
                background: 'var(--accent)', color: '#fff', border: 'none',
                borderRadius: 6, cursor: 'pointer', fontWeight: 600, fontSize: 13,
              }}
            >
              Review & confirm <ChevronRight size={14} />
            </button>
          </div>
        </Card>
      )}

      {/* ── Step 4: Confirm ─────────────────────────────────────────────────── */}
      {step === 4 && vr && (
        <Card>
          <h3 style={{ marginTop: 0, fontSize: 15 }}>Step 5 — Confirm import</h3>

          <div style={{
            background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 8,
            padding: '16px 18px', marginBottom: 16,
          }}>
            <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 12 }}>
              This will write to the PHOENIX-301 database:
            </div>
            <CountRow label="New sites"    value={totalSitesNew}    accent="#22c55e" />
            <CountRow label="New patients" value={totalPatientsNew} accent="#22c55e" />
            <CountRow label="New visits"   value={totalNew}         accent="#22c55e" />
            {onConflict === 'update' && (
              <CountRow label="Updated visits" value={vr.visits?.existing_changed} accent="#f59e0b" />
            )}
            <CountRow label="Skipped visits"  value={onConflict === 'skip' ? vr.visits?.existing_changed + vr.visits?.existing_same : vr.visits?.existing_same} />
          </div>

          <Alert type="info">
            After import, deviation detection and risk scoring will run automatically
            for the {totalSitesNew + (vr.sites?.existing_same ?? 0) + (vr.sites?.existing_changed ?? 0)} affected site(s).
            {vr.warnings?.length > 0 && ` Note: ${vr.warnings.length} warning(s) were found during validation.`}
          </Alert>

          {/* Partial import warning */}
          {(vr.rows_skipped_with_errors ?? 0) > 0 && (
            <Alert type="warn">
              <strong>{fmt(vr.rows_skipped_with_errors)} row(s) with errors will be skipped.</strong>{' '}
              Only the {fmt(vr.visits?.new ?? 0)} valid row(s) will be imported.
              The skipped rows had inconsistent patient attributes or missing site details.
            </Alert>
          )}

          {commitError && (
            <>
              <Alert type="error">{commitError}</Alert>
              {commitErrors?.length > 0 && (
                <div style={{ marginBottom: 12 }}>
                  <div style={{
                    fontSize: 12, fontWeight: 600, color: 'var(--text-muted)',
                    marginBottom: 6,
                  }}>
                    Re-validation errors (showing first {commitErrors.length}):
                  </div>
                  <ErrorTable errors={commitErrors} />
                  <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 8 }}>
                    Fix the errors above, re-upload and re-validate the corrected file.
                  </div>
                </div>
              )}
            </>
          )}

          <div style={{ display: 'flex', gap: 10, marginTop: 8 }}>
            <button onClick={() => setStep(3)} style={{
              padding: '8px 16px', background: 'var(--surface)', border: '1px solid var(--border)',
              borderRadius: 6, cursor: 'pointer', fontSize: 13, color: 'var(--text)',
            }}>
              Back
            </button>
            <button
              onClick={runCommit}
              disabled={committing}
              style={{
                display: 'flex', alignItems: 'center', gap: 8, padding: '9px 20px',
                background: committing ? 'var(--border)' : '#16a34a',
                color: '#fff', border: 'none', borderRadius: 6,
                cursor: committing ? 'not-allowed' : 'pointer',
                fontWeight: 600, fontSize: 13,
              }}
            >
              {committing
                ? <><Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} /> Importing…</>
                : <><ArrowRight size={14} /> Confirm import</>
              }
            </button>
          </div>
        </Card>
      )}

      {/* ── Step 5: Result ──────────────────────────────────────────────────── */}
      {step === 5 && commitResult && (
        <Card>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
            <CheckCircle2 size={22} style={{ color: '#22c55e' }} />
            <h3 style={{ margin: 0, fontSize: 16 }}>Import successful</h3>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 16 }}>
            <div style={{ background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 8, padding: '12px 14px' }}>
              <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 6 }}>Written</div>
              <CountRow label="Sites"    value={commitResult.sites_written}    accent="#22c55e" />
              <CountRow label="Patients" value={commitResult.patients_written} accent="#22c55e" />
              <CountRow label="Visits (new)"     value={commitResult.visits_written}  accent="#22c55e" />
              <CountRow label="Visits (updated)" value={commitResult.visits_updated}  accent="#f59e0b" />
              <CountRow label="Visits (skipped)" value={commitResult.visits_skipped} />
              {(commitResult.rows_skipped_with_errors ?? 0) > 0 && (
                <CountRow
                  label="Rows skipped (errors)"
                  value={commitResult.rows_skipped_with_errors}
                  accent="#ef4444"
                />
              )}
            </div>
            <div style={{ background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 8, padding: '12px 14px' }}>
              <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 6 }}>Re-analysis</div>
              <CountRow label="Deviations detected" value={commitResult.deviations_added}   accent="#22c55e" />
              <CountRow label="Deviations removed"  value={commitResult.deviations_removed} accent="#f59e0b" />
              <CountRow label="Sites re-scored" value={commitResult.affected_site_ids?.length} />
            </div>
          </div>

          {/* Tier changes */}
          {commitResult.tier_changes?.length > 0 && (
            <Alert type="warn">
              <strong>Risk tier changed</strong> for {commitResult.tier_changes.length} site(s):
              {commitResult.tier_changes.map(tc => (
                <span key={tc.site_id} style={{ marginLeft: 8 }}>
                  <Link to={`/sites/${tc.site_id}`} style={{ color: 'var(--accent)', fontWeight: 600 }}>{tc.site_id}</Link>
                  {' '}<TierBadge tier={tc.old_tier} /> → <TierBadge tier={tc.new_tier} />
                </span>
              ))}
            </Alert>
          )}

          {/* Affected sites links */}
          {commitResult.affected_site_ids?.length > 0 && (
            <div style={{ marginBottom: 12 }}>
              <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 8 }}>Affected sites:</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                {commitResult.affected_site_ids.map(sid => (
                  <Link key={sid} to={`/sites/${sid}`} style={{
                    padding: '4px 10px', borderRadius: 6, fontSize: 12,
                    background: 'var(--surface)', border: '1px solid var(--border)',
                    color: 'var(--accent)', textDecoration: 'none', fontWeight: 600,
                  }}>
                    {sid}
                  </Link>
                ))}
              </div>
            </div>
          )}

          {/* Stale CAPA notice */}
          {commitResult.stale_capa_site_ids?.length > 0 && (
            <Alert type="warn">
              <strong>CAPA reports may be out of date</strong> for the following sites (they were
              generated before this import): {' '}
              {commitResult.stale_capa_site_ids.map(sid => (
                <Link key={sid} to={`/capa/${sid}`} style={{ color: 'var(--accent)', marginRight: 8 }}>
                  {sid}
                </Link>
              ))}.
              The existing reports have not been deleted — regenerate them from the CAPA page.
            </Alert>
          )}

          {/* Recency note */}
          <Alert type="info" style={{ marginTop: 4 }}>
            {commitResult.recency_window_note}
          </Alert>

          <button
            onClick={reset}
            style={{
              display: 'flex', alignItems: 'center', gap: 8, padding: '9px 20px',
              background: 'var(--accent)', color: '#fff', border: 'none',
              borderRadius: 6, cursor: 'pointer', fontWeight: 600, fontSize: 13, marginTop: 8,
            }}
          >
            <RefreshCw size={14} /> Import another file
          </button>
        </Card>
      )}

      {/* ── Import History ──────────────────────────────────────────────────── */}
      <ImportHistory refresh={historyRefresh} />
    </div>
  )
}
