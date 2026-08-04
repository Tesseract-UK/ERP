// Per-employee month calendar for managers.
import { useEffect, useState } from 'react'
import { api } from '../api'
import MonthCalendar, { MonthNav } from '../components/MonthCalendar'
import { EmptyState, Spinner, useToast } from '../components/ui'
import { Users } from '../components/icons'

export default function TeamCalendar() {
  const toast = useToast()
  const now = new Date()
  const [members, setMembers] = useState(null)
  const [selected, setSelected] = useState('')
  const [ym, setYm] = useState({ year: now.getFullYear(), month: now.getMonth() + 1 })
  const [data, setData] = useState(null)

  useEffect(() => {
    api.get('/team/members').then((m) => {
      setMembers(m)
      if (m.length) setSelected(String(m[0].id))
    }).catch((e) => toast(e.message, 'error'))
  }, [toast])

  useEffect(() => {
    if (!selected) return
    setData(null)
    api.get(`/team/calendar/${selected}?year=${ym.year}&month=${ym.month}`)
      .then(setData).catch((e) => toast(e.message, 'error'))
  }, [selected, ym, toast])

  if (members === null) return <Spinner />
  if (members.length === 0) {
    return <div className="card"><EmptyState icon={Users} title="No team members"
      hint="Employees reporting to you will appear here." /></div>
  }

  return (
    <div className="card">
      <div className="card-head">
        <select className="input" style={{ width: 220 }} value={selected}
                onChange={(e) => setSelected(e.target.value)}>
          {members.map((m) => <option key={m.id} value={m.id}>{m.full_name}</option>)}
        </select>
        <MonthNav year={ym.year} month={ym.month} onChange={(year, month) => setYm({ year, month })} />
      </div>
      <div className="card-body">
        {data ? <MonthCalendar data={data} /> : <Spinner />}
      </div>
    </div>
  )
}
