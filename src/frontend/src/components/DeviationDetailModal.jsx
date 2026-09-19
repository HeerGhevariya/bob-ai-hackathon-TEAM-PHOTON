import { useEffect, useRef, useState, useCallback } from 'react'
import { createPortal } from 'react-dom'
import { useNavigate } from 'react-router-dom'
import { X, ChevronLeft, ChevronRight, Copy, ExternalLink, Check } from 'lucide-react'
import { fetchDeviationDetail } from '../utils/api'

// ─── Severity colour helpers ──────────────────────────────────────────────────
const SEV_COLOR = {
  major: 'var(--severity-major)',
  minor: 'var(--severity-minor)',
  administrative: 'var(--severity-admin)',
}
const SEV_BG = {
  major: 'var(--severity-major-bg)',
  minor: 'var(--severity-minor-bg)',
  administrative: 'var(--severity-admin-bg)',
}

function fmt(v) {
  return v || 'Not recorded'
}
function fmtDate(d) {
  if (!d) return 'Not recorded'
  return d
}
function fmtType(t) {
  return t ? t.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()) : 'Not recorded'
}

// ─── Focus trap ───────────────────────────────────────────────────────────────
function useFocusTrap(ref, active) {
  useEffect(() => {
    if (!active || !ref.current) return
    const el = ref.current
    const focusable = () =>
      Array.from(el.querySelectorAll(
        'a[href],button:not([disabled]),input,select,textarea,[tabindex]:not([tabindex="-1"])'
      ))
    const first = () => focusable()[0]
    const last = () => { const all = focusable(); return all[all.length - 1] }

    const handler = (e) => {
      if (e.key !== 'Tab') return
      const all = focusable()
      if (all.length === 0) return
      if (e.shiftKey) {
        if (document.activeElement === first()) {
          e.preventDefault()
          last()?.focus()
        }
      } else {
        if (document.activeElement === last()) {
          e.preventDefault()
          first()?.focus()
        }
      }
    }
    el.addEventListener('keydown', handler)
    return () => el.removeEventListener('keydown', handler)
  }, [ref, active])
}

// ─── Skeleton ────────────────────────────────────────────────────────────────
function ModalSkeleton() {
  return (
    <div style={{ padding: '24px 28px' }}>
      {[80, 140, 60, 100, 120, 60].map((w, i) => (
        <div key={i} className="skeleton skeleton-text" style={{ width: w, height: 14, marginBottom: 12 }} />
      ))}
    </div>
  )
}

// ─── Section ─────────────────────────────────────────────────────────────────
function Section({ title, children }) {
  return (
    <div style={{ marginBottom: 20 }}>
      <div style={{
        fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', letterSpacing: '0.07em',
        textTransform: 'uppercase', marginBottom: 10, paddingBottom: 6,
        borderBottom: '1px solid var(--border)',
      }}>
        {title}
      </div>
      {children}
    </div>
  )
}

// ─── Field ───────────────────────────────────────────────────────────────────
function Field({ label, value, mono }) {
  return (
    <div style={{ display: 'flex', gap: 8, marginBottom: 7, flexWrap: 'wrap' }}>
      <span style={{ fontSize: 12, color: 'var(--text-muted)', minWidth: 130, flexShrink: 0 }}>
        {label}
      </span>
      <span style={{
        fontSize: 12, color: 'var(--text-primary)', flex: 1,
        fontFamily: mono ? 'monospace' : undefined, wordBreak: 'break-word',
      }}>
        {value}
      </span>
    </div>
  )
}

// ─── FieldRow (side by side) ──────────────────────────────────────────────────
function FieldRow({ pairs }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px 16px', marginBottom: 10 }}>
      {pairs.map(({ label, value }) => (
        <div key={label} style={{
          background: 'var(--bg-primary)', borderRadius: 6, padding: '8px 12px',
          border: '1px solid var(--border)',
        }}>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 3 }}>{label}</div>
          <div style={{ fontSize: 13, color: 'var(--text-primary)', wordBreak: 'break-word' }}>{value}</div>
        </div>
      ))}
    </div>
  )
}

// ─── SeverityBadge ────────────────────────────────────────────────────────────
function SeverityBadge({ severity }) {
  if (!severity) return <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>Not recorded</span>
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 5,
      background: SEV_BG[severity] || 'var(--bg-primary)',
      color: SEV_COLOR[severity] || 'var(--text-primary)',
      borderRadius: 999, padding: '3px 10px', fontSize: 12, fontWeight: 600,
    }}>
      <span style={{
        width: 7, height: 7, borderRadius: '50%',
        background: SEV_COLOR[severity] || 'var(--text-muted)', flexShrink: 0,
      }} />
      {severity.charAt(0).toUpperCase() + severity.slice(1)}
    </span>
  )
}

// ─── Main component ───────────────────────────────────────────────────────────
export default function DeviationDetailModal({
  deviation,       // base deviation object (already on client)
  deviations,      // full list (for prev/next)
  currentIndex,    // index of `deviation` in `deviations`
  onClose,
  onNavigate,      // (index) => void
}) {
  const navigate = useNavigate()
  const cardRef = useRef(null)
  const [detail, setDetail] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [copied, setCopied] = useState(false)

  useFocusTrap(cardRef, true)

  // Fetch enriched detail
  useEffect(() => {
    if (!deviation) return
    setLoading(true)
    setError(null)
    setDetail(null)
    fetchDeviationDetail(deviation.deviation_id)
      .then(setDetail)
      .catch(e => setError(e.message || 'Failed to load details'))
      .finally(() => setLoading(false))
  }, [deviation?.deviation_id])

  // Focus first focusable element when modal opens
  useEffect(() => {
    const timer = setTimeout(() => {
      const el = cardRef.current?.querySelector(
        'button,[tabindex]:not([tabindex="-1"])'
      )
      el?.focus()
    }, 20)
    return () => clearTimeout(timer)
  }, [deviation?.deviation_id])

  // Esc to close
  useEffect(() => {
    const handler = (e) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [onClose])

  // Lock scroll behind modal
  useEffect(() => {
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => { document.body.style.overflow = prev }
  }, [])

  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(deviation.deviation_id).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    })
  }, [deviation?.deviation_id])

  const hasPrev = currentIndex > 0
  const hasNext = currentIndex < deviations.length - 1

  const d = detail || deviation // use enriched data when available, fallback to base

  return createPortal(
    <div
      className="dev-modal-backdrop"
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
      role="presentation"
    >
      <div
        ref={cardRef}
        className="dev-modal-card"
        role="dialog"
        aria-modal="true"
        aria-label={`Deviation ${deviation.deviation_id} details`}
      >
        {/* ── Header ──────────────────────────────────────────────────── */}
        <div className="dev-modal-header">
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12, flex: 1, minWidth: 0 }}>
            <div style={{ minWidth: 0, flex: 1 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 4 }}>
                <span style={{
                  fontFamily: 'monospace', fontSize: 13, fontWeight: 700,
                  color: 'var(--text-primary)', letterSpacing: '-0.01em',
                }}>
                  {deviation.deviation_id}
                </span>
                <SeverityBadge severity={deviation.severity} />
              </div>
              <div style={{ fontSize: 13, color: 'var(--text-secondary)', fontWeight: 500 }}>
                {fmtType(deviation.deviation_type)}
              </div>
              <div style={{ fontSize: 11.5, color: 'var(--text-muted)', marginTop: 2 }}>
                Detected: {fmtDate(deviation.detected_date)}
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', gap: 4, flexShrink: 0, alignItems: 'center' }}>
            <button
              className="dev-modal-nav-btn"
              onClick={() => hasPrev && onNavigate(currentIndex - 1)}
              disabled={!hasPrev}
              aria-label="Previous deviation"
              title="Previous"
            >
              <ChevronLeft size={15} />
            </button>
            <span style={{ fontSize: 11, color: 'var(--text-muted)', padding: '0 2px' }}>
              {currentIndex + 1}/{deviations.length}
            </span>
            <button
              className="dev-modal-nav-btn"
              onClick={() => hasNext && onNavigate(currentIndex + 1)}
              disabled={!hasNext}
              aria-label="Next deviation"
              title="Next"
            >
              <ChevronRight size={15} />
            </button>
            <button
              className="dev-modal-close-btn"
              onClick={onClose}
              aria-label="Close deviation detail"
              title="Close (Esc)"
            >
              <X size={15} />
            </button>
          </div>
        </div>

        {/* ── Body ──────────────────────────────────────────────────────── */}
        <div className="dev-modal-body">
          {loading && <ModalSkeleton />}

          {!loading && error && (
            <div style={{ padding: '32px 28px', textAlign: 'center', color: 'var(--severity-major)' }}>
              <div style={{ fontSize: 20, marginBottom: 8 }}>⚠</div>
              <div style={{ fontSize: 13 }}>{error}</div>
              <button className="btn btn-ghost" style={{ marginTop: 16, fontSize: 12 }}
                onClick={() => { setLoading(true); setError(null); fetchDeviationDetail(deviation.deviation_id).then(setDetail).catch(e => setError(e.message)).finally(() => setLoading(false)) }}>
                Retry
              </button>
            </div>
          )}

          {!loading && !error && (
            <div style={{ padding: '20px 28px 36px' }}>

              {/* 1. What happened */}
              <Section title="What Happened">
                <div style={{
                  fontSize: 13, color: 'var(--text-primary)', lineHeight: 1.65,
                  background: 'var(--bg-primary)', borderRadius: 6, padding: '10px 14px',
                  border: '1px solid var(--border)', marginBottom: 12, wordBreak: 'break-word',
                }}>
                  {fmt(d.description)}
                </div>
                <FieldRow pairs={[
                  { label: 'Expected', value: fmt(d.expected_value) },
                  { label: 'Actual', value: fmt(d.actual_value) },
                ]} />
              </Section>

              {/* 2. Context */}
              <Section title="Context">
                {detail?.site && (
                  <>
                    <Field label="Site ID" value={fmt(detail.site.site_id)} mono />
                    <Field label="Site name" value={fmt(detail.site.site_name)} />
                    <Field label="Location" value={
                      detail.site.city && detail.site.country
                        ? `${detail.site.city}, ${detail.site.country}`
                        : 'Not recorded'
                    } />
                    <Field label="Principal Investigator" value={fmt(detail.site.principal_investigator)} />
                  </>
                )}
                {!detail?.site && <Field label="Site" value={fmt(d.site_id)} mono />}
                <Field label="Patient ID" value={fmt(d.patient_id)} mono />
                <Field label="Visit" value={fmt(d.visit_name)} />

                {detail?.visit_dates && (
                  <>
                    <Field label="Scheduled date" value={fmtDate(detail.visit_dates.scheduled_date)} />
                    {detail.visit_dates.is_missed ? (
                      <Field label="Actual date" value="Visit not completed (missed)" />
                    ) : (
                      <Field label="Actual date" value={fmtDate(detail.visit_dates.actual_date)} />
                    )}
                  </>
                )}
                <Field label="Detected date" value={fmtDate(d.detected_date)} />
              </Section>

              {/* 3. Protocol basis */}
              <Section title="Protocol Basis">
                <Field label="Protocol reference" value={fmt(d.protocol_reference)} />
                {detail?.severity_reason && (
                  <Field label="Severity classification" value={detail.severity_reason} />
                )}
              </Section>

              {/* 4. Related information */}
              <Section title="Related Information">
                {detail?.related ? (
                  <>
                    <div style={{ marginBottom: 10 }}>
                      <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>
                        Other deviations for this patient ({detail.related.patient_other_deviations.count})
                      </div>
                      {detail.related.patient_other_deviations.count === 0 ? (
                        <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>None</div>
                      ) : (
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                          {detail.related.patient_other_deviations.items.map(rel => (
                            <button
                              key={rel.deviation_id}
                              className="dev-modal-related-btn"
                              onClick={() => {
                                const idx = deviations.findIndex(x => x.deviation_id === rel.deviation_id)
                                if (idx >= 0) onNavigate(idx)
                              }}
                              title={`${fmtType(rel.deviation_type)} — ${rel.visit_name}`}
                            >
                              <span style={{
                                width: 6, height: 6, borderRadius: '50%', flexShrink: 0,
                                background: SEV_COLOR[rel.severity] || 'var(--text-muted)',
                                display: 'inline-block',
                              }} />
                              {rel.deviation_id}
                            </button>
                          ))}
                          {detail.related.patient_other_deviations.count > 5 && (
                            <span style={{ fontSize: 11.5, color: 'var(--text-muted)', alignSelf: 'center' }}>
                              +{detail.related.patient_other_deviations.count - 5} more
                            </span>
                          )}
                        </div>
                      )}
                    </div>
                    <Field
                      label="Same type at site"
                      value={`${detail.related.same_type_at_site_count} other ${fmtType(d.deviation_type)} deviation${detail.related.same_type_at_site_count !== 1 ? 's' : ''} at this site`}
                    />
                  </>
                ) : (
                  <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>Loading…</div>
                )}

                {/* CAPA templates */}
                {detail?.capa_templates?.corrective_actions?.length > 0 && (
                  <div style={{ marginTop: 10 }}>
                    <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 6 }}>
                      Standard corrective action templates ({detail.capa_templates.corrective_actions.length})
                    </div>
                    {detail.capa_templates.corrective_actions.map((a, i) => (
                      <div key={i} style={{
                        fontSize: 12, color: 'var(--text-secondary)', padding: '5px 10px',
                        background: 'var(--bg-primary)', borderRadius: 4, marginBottom: 4,
                        border: '1px solid var(--border)',
                      }}>
                        <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>[{a.priority}] </span>
                        {a.description}
                        <span style={{ color: 'var(--text-muted)', fontSize: 11 }}> — {a.responsible_party}</span>
                      </div>
                    ))}
                  </div>
                )}
              </Section>

              {/* 5. Actions */}
              <Section title="Actions">
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  <button
                    className="btn btn-ghost"
                    style={{ fontSize: 12, display: 'flex', alignItems: 'center', gap: 5 }}
                    onClick={handleCopy}
                  >
                    {copied ? <Check size={13} /> : <Copy size={13} />}
                    {copied ? 'Copied!' : 'Copy ID'}
                  </button>

                  <button
                    className="btn btn-ghost"
                    style={{ fontSize: 12, display: 'flex', alignItems: 'center', gap: 5 }}
                    onClick={() => { onClose(); navigate(`/sites/${d.site_id}`) }}
                  >
                    <ExternalLink size={13} />
                    Open site detail
                  </button>

                  <button
                    className="btn btn-primary"
                    style={{ fontSize: 12 }}
                    onClick={() => { onClose(); navigate(`/capa/${d.site_id}`) }}
                  >
                    Generate CAPA Report for {d.site_id}
                  </button>
                </div>
              </Section>

            </div>
          )}
        </div>
      </div>
    </div>,
    document.body
  )
}
