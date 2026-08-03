// Admin: paginated system audit trail.
import { useEffect, useState } from 'react'
import { api } from '../api'
import { EmptyState, Pagination, Spinner, fmtDateTime, useToast } from '../components/ui'

const MODULES = ['auth', 'attendance', 'leaves', 'wfh', 'regularization',
                 'approvals', 'profile', 'hr', 'admin']

export default function AuditLogs() {
  const toast = useToast()
  const [module, setModule] = useState('')
  const [page, setPage] = useState(1)
  const [data, setData] = useState(null)

  useEffect(() => {
    setData(null)
    const p = new URLSearchParams({ page, page_size: 50 })
    if (module) p.append('module', module)
    api.get(`/admin/audit-logs?${p}`).then(setData).catch((e) => toast(e.message, 'error'))
  }, [module, page, toast])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div className="card pad toolbar">
        <select className="input" style={{ width: 180 }} value={module}
                onChange={(e) => { setModule(e.target.value); setPage(1) }}>
          <option value="">All modules</option>
          {MODULES.map((m) => <option key={m} value={m}>{m}</option>)}
        </select>
      </div>
      <div className="card">
        {data === null ? <Spinner /> : data.items.length === 0
          ? <EmptyState icon="🛡" title="No audit entries" />
          : (
            <>
              <div className="table-wrap"><table className="table">
                <thead><tr><th>When</th><th>User</th><th>Action</th><th>Module</th>
                  <th>Details</th><th>IP Address</th></tr></thead>
                <tbody>
                  {data.items.map((l) => (
                    <tr key={l.id}>
                      <td style={{ whiteSpace: 'nowrap' }}>{fmtDateTime(l.created_at)}</td>
                      <td>{l.user}</td>
                      <td><code style={{ fontSize: 12 }}>{l.action}</code></td>
                      <td><span className="badge neutral">{l.module}</span></td>
                      <td style={{ maxWidth: 320, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                          title={`${l.details || ''}\n${l.user_agent || ''}`}>{l.details || '—'}</td>
                      <td>{l.ip_address || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table></div>
              <Pagination page={data.page} pageSize={data.page_size} total={data.total} onPage={setPage} />
            </>
          )}
      </div>
    </div>
  )
}
