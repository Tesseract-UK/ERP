// Every request conversation the user is part of — requests they raised,
// their team's requests, and ones they were @-tagged in. Admins can switch to
// every conversation in the company. Email links open /conversations?open=kind:id.
import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useAuth } from '../AuthContext'
import { ConversationList, ConversationModal } from '../components/Conversation'

export default function Conversations() {
  const { user } = useAuth()
  const [params, setParams] = useSearchParams()
  const [scope, setScope] = useState(user.role === 'admin' ? 'all' : 'mine')
  const [open, setOpen] = useState(null) // { kind, id, reload }

  useEffect(() => {
    const target = params.get('open')
    const match = target && /^(leave|wfh|regularization):(\d+)$/.exec(target)
    if (match) setOpen({ kind: match[1], id: Number(match[2]) })
  }, [params])

  const close = () => {
    open?.reload?.()
    setOpen(null)
    if (params.get('open')) setParams({}, { replace: true })
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div className="page-head" style={{ marginBottom: 0 }}>
        <div><h2>Conversations</h2>
          <div className="sub">{scope === 'all'
            ? 'Every request conversation in the company — open any one to read or join it.'
            : 'Requests you raised, your team’s requests, and conversations you were tagged in.'}</div></div>
        {user.role === 'admin' && <div className="toolbar">
          <button className={`btn sm ${scope === 'all' ? '' : 'secondary'}`} onClick={() => setScope('all')}>All conversations</button>
          <button className={`btn sm ${scope === 'mine' ? '' : 'secondary'}`} onClick={() => setScope('mine')}>Mine</button>
        </div>}
      </div>
      <div className="card"><ConversationList key={scope} scope={scope}
        onOpen={(kind, id, reload) => setOpen({ kind, id, reload })} /></div>
      {open && <ConversationModal kind={open.kind} id={open.id} onClose={close} onChanged={open.reload} />}
    </div>
  )
}
