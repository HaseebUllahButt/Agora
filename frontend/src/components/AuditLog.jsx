import { useEffect, useRef } from 'react'

export default function AuditLog({ entries }) {
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [entries])

  if (!entries.length) {
    return (
      <div className="empty-state">
        <div className="empty-icon">📋</div>
        <div>Audit entries appear as agents are hired</div>
      </div>
    )
  }

  return (
    <div className="audit-list">
      {[...entries].reverse().map((e, i) => (
        <div
          key={i}
          className={`audit-entry ${
            e.type === 'fraud'   ? 'fraud'   :
            e.type === 'payment' ? 'payment' :
            e.type === 'info'    ? 'info'    : ''
          }`}
        >
          <span className="audit-ts">{e.ts}</span>
          {e.msg}
        </div>
      ))}
      <div ref={bottomRef} />
    </div>
  )
}
