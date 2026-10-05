import React, { useEffect, useState } from 'react'
import { getCouncilFunding, getCouncilRepresentation } from './api.js'
import { Caveat, Segmented } from './Primitives.jsx'

const money = (n) => '$' + Math.round(Number(n)).toLocaleString('en-US')
const num = (n) => Number(n).toLocaleString('en-US')

const TH = { font: '600 11.5px/1 var(--font-sans)', letterSpacing: '.04em', textTransform: 'uppercase',
  color: 'var(--fg-muted)', textAlign: 'right', padding: '0 0 10px' }
const TD = { font: '500 13px/1.3 var(--font-mono)', fontVariantNumeric: 'tabular-nums',
  color: 'var(--ink)', textAlign: 'right', padding: '10px 0', borderTop: '1px solid var(--hairline)' }
const TD_NAME = { ...TD, textAlign: 'left', font: '600 13.5px/1.2 var(--font-sans)' }

const VIEWS = [{ value: 'funding', label: 'Funding' }, { value: 'representation', label: 'Representation' }]

export default function CouncilPanel() {
  const [view, setView] = useState('funding')
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div>
        <div className="cii-eyebrow">Council</div>
        <h2 className="cii-h2" style={{ marginTop: 4 }}>
          {view === 'funding' ? 'Contributions & Sponsorship' : 'Representation Patterns'}
        </h2>
      </div>
      <Segmented value={view} onChange={setView} size="sm" options={VIEWS} />
      {view === 'funding' ? <Funding /> : <Representation />}
      <p className="cii-footnote" style={{ color: 'var(--fg-subtle)' }}>
        Sponsorship ≠ votes (not published) ≠ quid pro quo. Research, not advocacy.
      </p>
    </div>
  )
}

function Funding() {
  const [data, setData] = useState(null)
  const [err, setErr] = useState(null)
  useEffect(() => { getCouncilFunding().then(setData).catch(() => setErr('Could not load funding.')) }, [])
  if (err) return <p style={{ color: 'var(--flag)' }} className="cii-small">{err}</p>
  if (!data) return <p className="cii-small">Loading…</p>
  const members = data.members || []
  return (
    <>
      <Caveat>{data.methodology}</Caveat>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead><tr>
          <th style={{ ...TH, textAlign: 'left' }}>Council member</th>
          <th style={TH}>Contributions</th><th style={TH}>Matters sponsored</th>
        </tr></thead>
        <tbody>
          {members.map((r) => (
            <tr key={r.canonical_name}>
              <td style={TD_NAME}>{r.canonical_name}</td>
              <td style={TD}>{money(r.contributions_total)}
                <span style={{ display: 'block', font: '400 11px/1.2 var(--font-sans)', color: 'var(--fg-subtle)' }}>
                  {num(r.n_contributions)} gifts</span>
              </td>
              <td style={TD}>{num(r.n_matters_sponsored)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  )
}

function Representation() {
  const [data, setData] = useState(null)
  const [err, setErr] = useState(null)
  useEffect(() => { getCouncilRepresentation().then(setData).catch(() => setErr('Could not load representation.')) }, [])
  if (err) return <p style={{ color: 'var(--flag)' }} className="cii-small">{err}</p>
  if (!data) return <p className="cii-small">Loading…</p>
  const members = data.members || []
  const coalitions = data.coalitions || []
  return (
    <>
      <Caveat>{data.methodology}</Caveat>
      <div className="cii-eyebrow" style={{ marginBottom: 4 }}>Lead vs co-sponsor</div>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead><tr>
          <th style={{ ...TH, textAlign: 'left' }}>Council member</th>
          <th style={TH}>Leads</th><th style={TH}>Co-sponsors</th><th style={TH}>Total</th>
        </tr></thead>
        <tbody>
          {members.map((r) => (
            <tr key={r.canonical_name}>
              <td style={TD_NAME}>{r.canonical_name}</td>
              <td style={TD}>{num(r.n_lead)}</td>
              <td style={TD}>{num(r.n_cosponsor)}</td>
              <td style={TD}>{num(r.n_total)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="cii-eyebrow" style={{ margin: '14px 0 6px' }}>Top coalitions (shared matters)</div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {coalitions.map((p, i) => (
          <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            gap: 10, padding: '7px 10px', borderRadius: 'var(--r-sm)', background: 'var(--surface-2)' }}>
            <span style={{ font: '500 13px/1.3 var(--font-sans)', color: 'var(--ink)' }}>
              {p.name_a} <span style={{ color: 'var(--fg-subtle)' }}>+</span> {p.name_b}
            </span>
            <span className="cii-mono" style={{ color: 'var(--primary-deep)' }}>{num(p.shared_matters)}</span>
          </div>
        ))}
      </div>
    </>
  )
}
