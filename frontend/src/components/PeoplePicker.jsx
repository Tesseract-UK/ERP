// Type-to-search people picker. Nobody is included until chosen; chosen
// people show as removable chips. Searching happens on the server, so it
// scales to any number of employees (results are capped server-side).
import { useEffect, useRef, useState } from 'react'
import { titleCase } from './ui'

export default function PeoplePicker({ search, value, onChange, max = 3, placeholder = 'Type a name…' }) {
  const [term, setTerm] = useState('')
  const [results, setResults] = useState([])
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)
  const [loading, setLoading] = useState(false)
  const seq = useRef(0)
  const full = value.length >= max

  useEffect(() => {
    if (!open) return undefined
    const mine = ++seq.current
    setLoading(true)
    const timer = setTimeout(() => {
      search(term.trim())
        .then((rows) => { if (mine === seq.current) { setResults(rows); setActive(0) } })
        .catch(() => { if (mine === seq.current) setResults([]) })
        .finally(() => { if (mine === seq.current) setLoading(false) })
    }, 200)
    return () => clearTimeout(timer)
  }, [term, open, search])

  const chosen = new Set(value.map((p) => p.id))
  const options = results.filter((p) => !chosen.has(p.id))

  const add = (person) => {
    if (full) return
    onChange([...value, person])
    setTerm('')
  }
  const remove = (id) => onChange(value.filter((p) => p.id !== id))

  const onKeyDown = (e) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); setActive((i) => Math.min(i + 1, options.length - 1)) }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setActive((i) => Math.max(i - 1, 0)) }
    else if (e.key === 'Enter' && open && options[active]) { e.preventDefault(); add(options[active]) }
    else if (e.key === 'Escape') setOpen(false)
    else if (e.key === 'Backspace' && !term && value.length) remove(value[value.length - 1].id)
  }

  return (
    <div style={{ position: 'relative' }}>
      <div className="input" style={{ display: 'flex', flexWrap: 'wrap', gap: 6, alignItems: 'center', minHeight: 42, height: 'auto' }}
           onClick={(e) => e.currentTarget.querySelector('input')?.focus()}>
        {value.map((p) => (
          <span key={p.id} className="badge neutral" style={{ display: 'inline-flex', gap: 6, alignItems: 'center' }}>
            {p.name}{p.role ? ` · ${titleCase(p.role)}` : ''}
            <button type="button" aria-label={`Remove ${p.name}`} onClick={() => remove(p.id)}
                    style={{ border: 0, background: 'none', color: 'inherit', cursor: 'pointer', padding: 0, fontSize: 14 }}>×</button>
          </span>
        ))}
        {!full && (
          <input value={term} placeholder={value.length ? '' : placeholder}
                 onChange={(e) => { setTerm(e.target.value); setOpen(true) }}
                 onFocus={() => setOpen(true)} onBlur={() => setTimeout(() => setOpen(false), 120)}
                 onKeyDown={onKeyDown}
                 style={{ flex: 1, minWidth: 140, border: 0, outline: 0, background: 'transparent', color: 'inherit', font: 'inherit' }} />
        )}
      </div>
      {open && !full && (
        <div role="listbox" style={{
          position: 'absolute', zIndex: 30, left: 0, right: 0, top: '100%', marginTop: 4,
          maxHeight: 240, overflowY: 'auto', background: 'var(--surface, #111827)',
          border: '1px solid var(--border)', borderRadius: 8, boxShadow: '0 8px 24px #0005',
        }}>
          {options.map((p, i) => (
            <button key={p.id} type="button" role="option" aria-selected={i === active}
                    onMouseDown={(e) => e.preventDefault()} onClick={() => add(p)}
                    style={{ display: 'flex', width: '100%', justifyContent: 'space-between', gap: 12,
                      padding: '9px 12px', border: 0, color: 'var(--ink)', textAlign: 'left', cursor: 'pointer',
                      background: i === active ? 'var(--surface-2, #1f2937)' : 'transparent' }}>
              <span>{p.name}</span>
              <small style={{ color: 'var(--ink-3)' }}>{p.email ? `${p.email} · ` : ''}{titleCase(p.role || '')}</small>
            </button>
          ))}
          {options.length === 0 && (
            <div className="notif-item">{loading ? 'Searching…' : term ? 'No one matches that name' : 'No one available'}</div>
          )}
        </div>
      )}
    </div>
  )
}
