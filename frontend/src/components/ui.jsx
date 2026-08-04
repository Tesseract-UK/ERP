// Small shared UI primitives.
import { createContext, useCallback, useContext, useState } from 'react'
import { ChevronLeft, ChevronRight, Eye, EyeOff, Inbox } from './icons'

export const Spinner = () => <div className="spinner" role="status" aria-label="Loading" />

export function EmptyState({ icon, title, hint }) {
  const Icon = icon || Inbox
  return (
    <div className="empty">
      <div className="big"><Icon size={30} strokeWidth={1.5} /></div>
      <h4>{title}</h4>
      {hint && <div>{hint}</div>}
    </div>
  )
}

const STATUS_BADGE = {
  pending: ['warn', 'Pending'], approved: ['ok', 'Approved'],
  rejected: ['danger', 'Rejected'], cancelled: ['neutral', 'Cancelled'],
  present: ['ok', 'Present'], absent: ['danger', 'Absent'],
  leave: ['warn', 'Leave'], wfh: ['info', 'WFH'],
  holiday: ['neutral', 'Holiday'], half_day: ['warn', 'Half Day'],
  weekend: ['neutral', 'Weekend'],
}

export function StatusBadge({ status }) {
  const [tone, label] = STATUS_BADGE[status] || ['neutral', status]
  return <span className={`badge ${tone}`}>{label}</span>
}

export function Modal({ title, onClose, children, footer, wide }) {
  return (
    <div className="modal-overlay" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className={`modal${wide ? ' wide' : ''}`} role="dialog" aria-modal="true">
        <div className="modal-head">
          <h3>{title}</h3>
          <button className="close-x" onClick={onClose} aria-label="Close">×</button>
        </div>
        <div className="modal-body">{children}</div>
        {footer && <div className="modal-foot">{footer}</div>}
      </div>
    </div>
  )
}

export function ConfirmDialog({ title, message, confirmLabel = 'Confirm', danger, onConfirm, onClose, busy }) {
  return (
    <Modal title={title} onClose={onClose} footer={
      <>
        <button className="btn secondary" onClick={onClose} disabled={busy}>Cancel</button>
        <button className={`btn${danger ? ' danger' : ''}`} onClick={onConfirm} disabled={busy}>
          {busy ? 'Working…' : confirmLabel}
        </button>
      </>
    }>
      <p>{message}</p>
    </Modal>
  )
}

// Password input with a show/hide toggle. Drop-in replacement for
// <input type="password" className="input" .../> — forwards all other props.
export function PasswordInput({ inputClassName = 'input', ...props }) {
  const [show, setShow] = useState(false)
  return (
    <div className="password-field">
      <input className={inputClassName} type={show ? 'text' : 'password'} {...props} />
      <button type="button" className="password-toggle" tabIndex={-1}
              onClick={() => setShow((s) => !s)}
              aria-label={show ? 'Hide password' : 'Show password'}>
        {show ? <EyeOff size={16} /> : <Eye size={16} />}
      </button>
    </div>
  )
}

export function Field({ label, required, children, error, help }) {
  return (
    <div className="field">
      {label && <label>{label} {required && <span className="req">*</span>}</label>}
      {children}
      {error && <div className="error-text">{error}</div>}
      {help && !error && <div className="help-text">{help}</div>}
    </div>
  )
}

export function Pagination({ page, pageSize, total, onPage }) {
  const pages = Math.max(Math.ceil(total / pageSize), 1)
  if (pages <= 1) return null
  return (
    <div className="pagination">
      <span>Page {page} of {pages} · {total} records</span>
      <button className="btn secondary sm" disabled={page <= 1} onClick={() => onPage(page - 1)}>
        <ChevronLeft size={14} /> Prev</button>
      <button className="btn secondary sm" disabled={page >= pages} onClick={() => onPage(page + 1)}>
        Next <ChevronRight size={14} /></button>
    </div>
  )
}

// ---- toast notifications ----
const ToastContext = createContext(() => {})

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])
  const push = useCallback((message, tone = 'info') => {
    const id = Date.now() + Math.random()
    setToasts((t) => [...t, { id, message, tone }])
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 4000)
  }, [])
  return (
    <ToastContext.Provider value={push}>
      {children}
      <div className="toast-stack">
        {toasts.map((t) => <div key={t.id} className={`toast ${t.tone}`}>{t.message}</div>)}
      </div>
    </ToastContext.Provider>
  )
}

export const useToast = () => useContext(ToastContext)

// ---- formatting helpers ----
export const fmtDate = (iso) => iso ? new Date(iso + (iso.length === 10 ? 'T00:00' : '')).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' }) : '—'
export const fmtTime = (iso) => iso ? new Date(iso).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' }) : '—'
export const fmtDateTime = (iso) => iso ? `${fmtDate(iso)} ${fmtTime(iso)}` : '—'
export const fmtHours = (h) => h == null ? '—' : `${Math.floor(h)}h ${Math.round((h % 1) * 60)}m`
export const titleCase = (s) => (s || '').replaceAll('_', ' ').replace(/\b\w/g, (c) => c.toUpperCase())
export const initials = (name) => (name || '?').split(' ').map((w) => w[0]).slice(0, 2).join('').toUpperCase()
