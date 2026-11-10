// One "Apply for" form covering both Leave and Work From Home — used by the
// Leave & WFH page and by the Attendance calendar's per-date quick-apply flow.
import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'
import { Field, localDateStr, titleCase, useToast } from './ui'
import MentionTextarea from './MentionTextarea'

const LEAVE_TYPES = ['casual', 'sick', 'earned', 'unpaid', 'maternity', 'paternity', 'optional_holiday']

export const searchPeople = (term) => api.get(
  `/conversations/people?${new URLSearchParams(term ? { search: term } : {})}`,
)

// Leave = red, WFH = orange, everywhere they are listed side by side.
export const KIND_META = {
  leave: { label: 'Leave', badge: 'leave' },
  wfh: { label: 'Work From Home', badge: 'wfh' },
  regularization: { label: 'Regularization', badge: 'neutral' },
}

export function KindBadge({ kind }) {
  const meta = KIND_META[kind] || { label: titleCase(kind), badge: 'neutral' }
  return <span className={`badge ${meta.badge}`}>{meta.label}</span>
}

export function ApplyRequestForm({ initialType = 'leave', initialStart = '', initialEnd = '', onDone, onCancel }) {
  const toast = useToast()
  const [type, setType] = useState(initialType)
  const [balances, setBalances] = useState(null)
  const [form, setForm] = useState({
    leave_type: 'casual', start_date: initialStart, end_date: initialEnd || initialStart, reason: '',
  })
  const [mentionedIds, setMentionedIds] = useState([])
  const [busy, setBusy] = useState(false)
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }))
  const search = useCallback(searchPeople, [])

  useEffect(() => { api.get('/leaves/balance').then(setBalances).catch(() => {}) }, [])

  const submitLeave = async () => {
    await api.post('/leaves', { ...form, mentioned_user_ids: mentionedIds })
    toast('Leave request sent to your manager', 'success')
  }

  const submitWfh = async () => {
    const start = new Date(`${form.start_date}T00:00`)
    const end = new Date(`${form.end_date}T00:00`)
    if (end < start) throw new Error('To date must be on or after the from date')
    const dates = []
    for (let d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) {
      if (d.getDay() !== 0 && d.getDay() !== 6) dates.push(localDateStr(d))
    }
    if (!dates.length) throw new Error('Selected range contains no weekdays')
    let ok = 0
    const failures = []
    for (const date of dates) {
      try {
        await api.post('/wfh', { date, reason: form.reason, mentioned_user_ids: mentionedIds })
        ok++
      } catch (err) {
        failures.push(`${date}: ${err.message}`)
      }
    }
    if (!ok) throw new Error(failures[0] || 'Could not submit WFH request')
    toast(`WFH requested for ${ok} day${ok === 1 ? '' : 's'}${failures.length ? ` — ${failures.length} skipped (${failures[0]})` : ''}`,
      failures.length ? 'error' : 'success')
  }

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true)
    try {
      if (type === 'leave') await submitLeave()
      else await submitWfh()
      onDone()
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setBusy(false)
    }
  }

  const wfh = balances?.wfh
  return (
    <form onSubmit={submit}>
      <Field label="Apply for" required>
        <div className="segmented" role="radiogroup" aria-label="Request type">
          {['leave', 'wfh'].map((k) => (
            <button type="button" key={k} role="radio" aria-checked={type === k}
              className={`seg ${KIND_META[k].badge}${type === k ? ' active' : ''}`}
              onClick={() => setType(k)}>{KIND_META[k].label}</button>
          ))}
        </div>
      </Field>
      {type === 'leave' && (
        <Field label="Leave type" required help={balances && form.leave_type !== 'unpaid'
          ? `${balances[form.leave_type]?.remaining ?? 0} day(s) remaining` : undefined}>
          <select className="input" value={form.leave_type} onChange={(e) => set('leave_type', e.target.value)}>
            {LEAVE_TYPES.map((t) => <option key={t} value={t}>{titleCase(t)}</option>)}
          </select>
        </Field>
      )}
      <div className="form-row">
        <Field label="From date" required>
          <input className="input" type="date" required value={form.start_date}
                 onChange={(e) => set('start_date', e.target.value)} />
        </Field>
        <Field label="To date" required help={type === 'wfh'
          ? `Weekends are skipped${wfh ? ` · ${wfh.remaining} WFH day(s) available` : ''}`
          : 'Inclusive of both dates'}>
          <input className="input" type="date" required value={form.end_date} min={form.start_date}
                 onChange={(e) => set('end_date', e.target.value)} />
        </Field>
      </div>
      <Field label="Reason" required help="Type @ to tag a colleague — they join the conversation and get an email.">
        <MentionTextarea className="input" required minLength={3} rows={3} value={form.reason}
          searchUsers={search} mentionedIds={mentionedIds} onMentionsChange={setMentionedIds}
          onChange={(value) => set('reason', value)}
          placeholder={type === 'leave' ? 'Briefly describe the reason for your leave.' : 'Why do you need to work from home?'} />
      </Field>
      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 18, paddingTop: 14, borderTop: '1px solid var(--border)' }}>
        <button type="button" className="btn secondary" onClick={onCancel} disabled={busy}>Cancel</button>
        <button className="btn" disabled={busy}>{busy ? 'Submitting…' : `Apply for ${KIND_META[type].label}`}</button>
      </div>
    </form>
  )
}
