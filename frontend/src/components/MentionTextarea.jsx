import { useEffect, useRef, useState } from 'react'

/** WhatsApp-style @name suggestions for a server-provided directory. */
export default function MentionTextarea({ value, onChange, searchUsers, mentionedIds, onMentionsChange, ...props }) {
  const inputRef = useRef(null)
  const selectedTokens = useRef([])
  const [trigger, setTrigger] = useState(null)
  const [activeIndex, setActiveIndex] = useState(0)
  const [matches, setMatches] = useState([])

  useEffect(() => {
    if (!trigger) { setMatches([]); return undefined }
    let current = true
    const timer = window.setTimeout(() => {
      searchUsers(trigger.query).then((people) => {
        if (current) setMatches(people.slice(0, 8))
      }).catch(() => { if (current) setMatches([]) })
    }, 120)
    return () => { current = false; window.clearTimeout(timer) }
  }, [trigger, searchUsers])

  const handleChange = (event) => {
    const next = event.target.value
    const caret = event.target.selectionStart
    onChange(next)
    const match = next.slice(0, caret).match(/(?:^|\s)@([^\s@]*)$/u)
    if (match) {
      setTrigger({ start: caret - match[1].length - 1, caret, query: match[1] })
      setActiveIndex(0)
    } else {
      setTrigger(null)
    }

    const stillPresent = selectedTokens.current.filter((mention) => next.includes(mention.token))
    selectedTokens.current = stillPresent
    const remainingIds = stillPresent.map((mention) => mention.id)
    if (remainingIds.length !== mentionedIds.length || remainingIds.some((id, index) => id !== mentionedIds[index])) {
      onMentionsChange(remainingIds)
    }
  }

  const choose = (person) => {
    if (!trigger) return
    const token = `@${person.full_name}`
    const next = `${value.slice(0, trigger.start)}${token} ${value.slice(trigger.caret)}`
    onChange(next)
    if (!selectedTokens.current.some((mention) => mention.id === person.id)) {
      selectedTokens.current = [...selectedTokens.current, { id: person.id, token }]
      onMentionsChange([...new Set([...mentionedIds, person.id])])
    }
    setTrigger(null)
    requestAnimationFrame(() => {
      const input = inputRef.current
      if (!input) return
      const caret = trigger.start + token.length + 1
      input.focus()
      input.setSelectionRange(caret, caret)
    })
  }

  const handleKeyDown = (event) => {
    if (!matches.length) return
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      setActiveIndex((index) => (index + 1) % matches.length)
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      setActiveIndex((index) => (index - 1 + matches.length) % matches.length)
    } else if (event.key === 'Enter' || event.key === 'Tab') {
      event.preventDefault()
      choose(matches[activeIndex])
    } else if (event.key === 'Escape') {
      setTrigger(null)
    }
  }

  return (
    <div style={{ position: 'relative' }}>
      <textarea {...props} ref={inputRef} value={value} onChange={handleChange} onKeyDown={handleKeyDown} />
      {trigger && (
        <div role="listbox" aria-label="Mention a colleague" style={{
          position: 'absolute', zIndex: 30, left: 0, right: 0, bottom: '100%',
          maxHeight: 240, overflowY: 'auto', background: 'var(--surface, #111827)',
          border: '1px solid var(--border)', borderRadius: 8, boxShadow: '0 8px 24px #0005',
        }}>
          {matches.map((person, index) => (
            <button key={person.id} type="button" role="option" aria-selected={index === activeIndex}
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => choose(person)}
              style={{ display: 'flex', width: '100%', justifyContent: 'space-between', gap: 12,
                padding: '9px 12px', border: 0, color: 'var(--ink)', textAlign: 'left',
                background: index === activeIndex ? 'var(--surface-2, #1f2937)' : 'transparent', cursor: 'pointer' }}>
              <span>{person.full_name}</span>
              <small style={{ color: 'var(--ink-3)' }}>{person.employee_code} · {person.role}</small>
            </button>
          ))}
          {matches.length === 0 && <div className="notif-item">No matching active colleagues</div>}
        </div>
      )}
    </div>
  )
}
