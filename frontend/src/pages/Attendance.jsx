// My attendance: monthly color-coded calendar.
import { useEffect, useState } from 'react'
import { api } from '../api'
import MonthCalendar, { MonthNav } from '../components/MonthCalendar'
import { Spinner, useToast } from '../components/ui'

export default function Attendance() {
  const now = new Date()
  const [ym, setYm] = useState({ year: now.getFullYear(), month: now.getMonth() + 1 })
  const [data, setData] = useState(null)
  const toast = useToast()

  useEffect(() => {
    setData(null)
    api.get(`/attendance/calendar?year=${ym.year}&month=${ym.month}`)
      .then(setData)
      .catch((e) => toast(e.message, 'error'))
  }, [ym, toast])

  return (
    <div className="card">
      <div className="card-head">
        <h3>Monthly Attendance</h3>
        <MonthNav year={ym.year} month={ym.month} onChange={(year, month) => setYm({ year, month })} />
      </div>
      <div className="card-body">
        {data ? <MonthCalendar data={data} /> : <Spinner />}
        <p className="help-text" style={{ marginTop: 12 }}>
          Click any date to see login time, logout time, working hours, breaks and status.
          Forgot to check in or out? Submit a request from the Regularization page.
        </p>
      </div>
    </div>
  )
}
