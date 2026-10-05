import React, { useEffect, useState } from 'react'
import { getMethods } from './api.js'
import { Caveat } from './Primitives.jsx'

export default function Methods({ metric }) {
  const [m, setM] = useState(null)
  useEffect(() => { getMethods(metric).then(setM) }, [metric])
  if (!m) return <p className="cii-small">Loading methods…</p>
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <h2 className="cii-h2">Methods — {metric === 'crime' ? 'Crime' : '311 requests'}</h2>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {m.notes.map((n, i) => (
          <div key={i} style={{ display: 'flex', gap: 10 }}>
            <span style={{ flex: '0 0 auto', width: 6, height: 6, marginTop: 8, borderRadius: '50%', background: 'var(--primary)' }} />
            <p className="cii-body" style={{ fontSize: 14 }}>{n}</p>
          </div>
        ))}
      </div>
      <Caveat compact>Research, not advocacy — methodology is published so users can draw their own conclusions.</Caveat>
    </div>
  )
}
