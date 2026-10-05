import React, { useEffect, useState } from 'react'
import { getOwnerType } from './api.js'
import { Caveat, Icon } from './Primitives.jsx'

const fmt = (n) => Number(n).toLocaleString('en-US')
const KIND = {
  individual: { label: 'Individuals', icon: 'user' },
  institutional: { label: 'Institutional', icon: 'building' },
  government: { label: 'Government', icon: 'landmark' },
}
const label = (k) => (KIND[k] ? KIND[k].label : k)
const icon = (k) => (KIND[k] ? KIND[k].icon : 'user')

const TH = {
  font: '600 11.5px/1 var(--font-sans)', letterSpacing: '.04em', textTransform: 'uppercase',
  color: 'var(--fg-muted)', textAlign: 'right', padding: '0 0 10px',
}
const TD = {
  font: '500 13.5px/1.3 var(--font-mono)', fontVariantNumeric: 'tabular-nums',
  color: 'var(--ink)', textAlign: 'right', padding: '11px 0', borderTop: '1px solid var(--hairline)',
}
const TD_NAME = { ...TD, textAlign: 'left', font: '600 13.5px/1.2 var(--font-sans)', color: 'var(--ink)' }

export default function OwnerType() {
  const [propertyClass, setPropertyClass] = useState('A1')
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  useEffect(() => {
    setData(null)
    getOwnerType(propertyClass).then(setData).catch(() => setError('Could not load owner-type data.'))
  }, [propertyClass])

  if (error) return <p style={{ color: 'var(--flag)' }} className="cii-small">{error}</p>
  if (!data) return <p className="cii-small">Loading ownership by owner type…</p>

  const conc = data.concentration || []
  const treatment = data.treatment || []
  const classes = data.classes || []

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div>
        <div className="cii-eyebrow">Property ownership</div>
        <h2 className="cii-h2" style={{ marginTop: 4 }}>Who Owns Austin</h2>
      </div>
      <Caveat>{data.methodology}</Caveat>

      <div>
        <div className="cii-eyebrow" style={{ marginBottom: 6 }}>Concentration (all property)</div>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead><tr>
            <th style={{ ...TH, textAlign: 'left' }}>Owner type</th>
            <th style={TH}>Parcels</th><th style={TH}>% parcels</th><th style={TH}>% value</th>
          </tr></thead>
          <tbody>
            {conc.map((r) => (
              <tr key={r.owner_kind}>
                <td style={TD_NAME}>
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
                    <Icon name={icon(r.owner_kind)} size={15} color="var(--fg-muted)" />{label(r.owner_kind)}
                  </span>
                </td>
                <td style={TD}>{fmt(r.n_parcels)}</td>
                <td style={TD}>{(r.parcel_share * 100).toFixed(1)}%</td>
                <td style={TD}>{(r.value_share * 100).toFixed(1)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div>
        <div className="cii-eyebrow" style={{ marginBottom: 6, display: 'flex', alignItems: 'center', gap: 8 }}>
          Differential treatment
          <select value={propertyClass} onChange={(e) => setPropertyClass(e.target.value)}
            style={{
              appearance: 'none', WebkitAppearance: 'none', font: '600 12px/1 var(--font-mono)',
              color: 'var(--primary-ink)', background: 'var(--primary-tint)', border: '1px solid var(--hairline)',
              borderRadius: 'var(--r-pill)', padding: '3px 10px', cursor: 'pointer',
            }}>
            {(classes.length ? classes : [propertyClass]).map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
        <p className="cii-footnote" style={{ margin: '0 0 6px' }}>
          Within class {propertyClass}. Index ≈ 1 = no difference from comparable parcels.
        </p>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead><tr>
            <th style={{ ...TH, textAlign: 'left' }}>Owner type</th>
            <th style={TH}>Assess. idx</th><th style={TH}>Code idx</th><th style={TH}>Cases / 1k</th>
          </tr></thead>
          <tbody>
            {treatment.map((t) => (
              <tr key={t.owner_type}>
                <td style={TD_NAME}>{label(t.owner_type)}</td>
                <td style={{ ...TD, color: t.assessment_index != null && t.assessment_index < 1 ? 'var(--info)' : 'var(--ink)' }}>
                  {t.assessment_index != null ? Number(t.assessment_index).toFixed(2) : '—'}
                </td>
                <td style={{ ...TD, color: t.code_case_index != null && t.code_case_index > 1 ? 'var(--flag)' : 'var(--ink)' }}>
                  {t.code_case_index != null ? Number(t.code_case_index).toFixed(2) : '—'}
                </td>
                <td style={TD}>{t.code_cases_per_1k != null ? fmt(Math.round(t.code_cases_per_1k)) : '—'}</td>
              </tr>
            ))}
            {treatment.length === 0 && (
              <tr><td colSpan={4} style={{ ...TD, textAlign: 'left', color: 'var(--fg-subtle)', fontFamily: 'var(--font-sans)' }}>
                No stratum data for class {propertyClass}.
              </td></tr>
            )}
          </tbody>
        </table>
      </div>
      <p className="cii-footnote" style={{ color: 'var(--fg-subtle)' }}>Screening signals — research, not findings.</p>
    </div>
  )
}
