import React, { useEffect, useState } from 'react'
import { getFlags } from './api.js'
import { Caveat, Badge, Icon, Segmented } from './Primitives.jsx'

const fmt = (n) => Number(n).toLocaleString('en-US')

const DETECTORS = [
  { value: 'assessment_cod', label: 'Dispersion' },
  { value: 'd4_institutional_divergence', label: 'Institutional' },
]

// Assessment-equity flags. Two screening detectors behind a toggle:
//  - assessment_cod: within-stratum dispersion (HIGH DISPERSION, never over-assessed)
//  - d4: institutional owner entities diverging from category×ZIP fundamentals
export default function Flags() {
  const [detector, setDetector] = useState('assessment_cod')
  const [flags, setFlags] = useState(null)
  const [error, setError] = useState(null)
  useEffect(() => {
    setFlags(null); setError(null)
    getFlags(detector).then(setFlags).catch(() => setError('Could not load flags.'))
  }, [detector])

  const isCod = detector === 'assessment_cod'

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div>
        <div className="cii-eyebrow">{isCod ? 'Property assessment' : 'Ownership × assessment'}</div>
        <h2 className="cii-h2" style={{ marginTop: 4 }}>
          {isCod ? 'Assessment Uniformity' : 'Institutional Divergence'}
        </h2>
      </div>
      <Segmented value={detector} onChange={setDetector} size="sm" options={DETECTORS} />

      {error && <p style={{ color: 'var(--flag)' }} className="cii-small">{error}</p>}
      {!error && !flags && <p className="cii-small">Loading flags…</p>}
      {flags && flags.length === 0 && <p className="cii-small">No flags for the current roll.</p>}
      {flags && flags.length > 0 && <Caveat>{flags[0].methodology}</Caveat>}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {(flags || []).map((f) => {
          const d = f.detail || {}
          return isCod
            ? <CodCard key={f.cluster_id} f={f} d={d} />
            : <D4Card key={f.cluster_id} f={f} d={d} />
        })}
      </div>
    </div>
  )
}

function CardShell({ title, badge, lines, review }) {
  return (
    <div style={{ padding: '13px 15px', borderRadius: 'var(--r-md)', background: 'var(--surface)',
      border: '1px solid var(--hairline)', boxShadow: 'var(--shadow-sm)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10 }}>
        <span style={{ font: '700 15px/1.2 var(--font-sans)', color: 'var(--ink)' }}>{title}</span>
        {badge}
      </div>
      <div className="cii-footnote" style={{ marginTop: 6 }}>{lines}</div>
      <div className="cii-footnote" style={{ marginTop: 8, color: 'var(--fg-subtle)' }}>{review}</div>
    </div>
  )
}

function CodCard({ f, d }) {
  const [zip, klass] = String(f.cluster_id).split('|')
  return (
    <CardShell
      title={<>ZIP {zip}{klass ? <span style={{ color: 'var(--fg-subtle)', fontWeight: 500 }}> · {klass}</span> : null}</>}
      badge={<Badge tone="flag"><Icon name="triangle-alert" size={12} /> High dispersion</Badge>}
      lines={<>
        COD = {Number(f.score).toFixed(1)}%
        {d.median_value_per_unit != null && <> · ${fmt(Math.round(d.median_value_per_unit))}/acre</>}
        {d.n_parcels != null && <> · {fmt(d.n_parcels)} parcels</>}
        {d.cod_pctile_in_class != null && <> · {Math.round(d.cod_pctile_in_class * 100)}th pct</>}
      </>}
      review={`${f.review_state} — screening signal (inconsistency, not over-assessment)`}
    />
  )
}

function D4Card({ f, d }) {
  const below = f.direction === 'below'
  return (
    <CardShell
      title={d.canonical_name || f.cluster_id}
      badge={<Badge tone={below ? 'info' : 'flag'}>{below ? 'below' : 'above'} fundamentals</Badge>}
      lines={<>
        {Number(f.score).toFixed(2)}× comparable
        {d.n_parcels != null && <> · {fmt(d.n_parcels)} parcels</>}
        {d.kind && <> · {d.kind}</>}
      </>}
      review={`${f.review_state} — screening signal (property mix not controlled; review before drawing conclusions)`}
    />
  )
}
