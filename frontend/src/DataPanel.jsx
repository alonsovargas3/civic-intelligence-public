import React, { useEffect, useState } from 'react'
import { getIncidents, getDistrict } from './api.js'
import { StatTile, Badge, BarRow } from './Primitives.jsx'

const fmt = (n) => Number(n).toLocaleString('en-US')
const days1 = (d) => (Math.round(Number(d) * 10) / 10).toFixed(1)

function Ranking({ dataset, year, onSelect }) {
  const [rows, setRows] = useState(null)
  useEffect(() => { getIncidents(dataset, year).then(setRows) }, [dataset, year])
  const metricLabel = dataset === 'crime' ? 'Crime incidents' : '311 requests'
  if (!rows) return <p className="cii-small">Loading citywide ranking…</p>
  const sorted = [...rows].sort((a, b) => b.incident_count - a.incident_count)
  const max = sorted.length ? sorted[0].incident_count : 1
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div>
        <div className="cii-eyebrow">Citywide ranking</div>
        <p className="cii-small" style={{ marginTop: 4 }}>
          {metricLabel}, {year}. Select a district on the map or below for detail.
        </p>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column' }}>
        {sorted.map((r, i) => (
          <button key={r.council_district} onClick={() => onSelect(r.council_district)}
            style={{
              display: 'grid', gridTemplateColumns: '26px 1fr auto', alignItems: 'center', gap: 12,
              padding: '10px 8px', border: 'none', borderBottom: '1px solid var(--hairline)',
              background: 'transparent', cursor: 'pointer', textAlign: 'left', width: '100%',
              transition: 'background var(--dur) var(--ease)',
            }}
            onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--surface-2)' }}
            onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent' }}>
            <span className="cii-mono" style={{ color: 'var(--fg-subtle)' }}>{i + 1}</span>
            <span>
              <span style={{ font: '600 14px/1.2 var(--font-sans)', color: 'var(--ink)' }}>District {r.council_district}</span>
              <span style={{ display: 'block', height: 5, marginTop: 6, borderRadius: 'var(--r-pill)', background: 'var(--surface-3)' }}>
                <span style={{
                  display: 'block', height: '100%', borderRadius: 'var(--r-pill)',
                  width: `${Math.round((r.incident_count / max) * 100)}%`, background: 'var(--blue-6)',
                }} />
              </span>
            </span>
            <span className="cii-mono" style={{ color: 'var(--ink)' }}>{fmt(r.incident_count)}</span>
          </button>
        ))}
      </div>
    </div>
  )
}

function Detail({ district, dataset, year }) {
  const [data, setData] = useState(null)
  useEffect(() => { setData(null); getDistrict(district, year).then(setData) }, [district, year])
  if (!data) return <p className="cii-small">Loading district {district}…</p>

  const totalsBy = Object.fromEntries((data.totals_by_dataset || []).map((t) => [t.dataset, t.n]))
  const breakdown = (data.breakdown || [])
    .filter((b) => b.dataset === dataset)
    .sort((a, b) => b.value - a.value).slice(0, 8)
  const max = breakdown.length ? Math.max(...breakdown.map((b) => b.value)) : 1
  const rt = data.response_time

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <h2 className="cii-h2">District {district}</h2>
        <Badge tone="muted">{year}</Badge>
      </div>

      <div>
        <div className="cii-eyebrow" style={{ marginBottom: 8 }}>Totals</div>
        <div style={{ display: 'flex', gap: 10 }}>
          <StatTile label="311 requests" value={fmt(totalsBy['311'] ?? 0)} accent={dataset === '311'} />
          <StatTile label="Crime incidents" value={fmt(totalsBy.crime ?? 0)} accent={dataset === 'crime'} />
        </div>
      </div>

      {rt && rt.median_days != null && (
        <div style={{ padding: '14px 16px', borderRadius: 'var(--r-md)', background: 'var(--surface)', border: '1px solid var(--hairline)' }}>
          <div className="cii-eyebrow" style={{ marginBottom: 8 }}>311 median response</div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 6, whiteSpace: 'nowrap' }}>
            <span className="cii-stat" style={{ fontSize: 26 }}>{days1(rt.median_days)}</span>
            <span style={{ font: '500 14px/1 var(--font-sans)', color: 'var(--fg-muted)' }}>days</span>
          </div>
          <div className="cii-footnote" style={{ marginTop: 6 }}>
            {fmt(rt.closed_count)} closed · {fmt(rt.open_count)} open
          </div>
        </div>
      )}

      <div>
        <div className="cii-eyebrow" style={{ marginBottom: 4 }}>Top categories / types</div>
        {breakdown.length === 0
          ? <p className="cii-small" style={{ marginTop: 6 }}>No {dataset === 'crime' ? 'crime' : '311'} breakdown for this district / year.</p>
          : breakdown.map((b, i) => <BarRow key={i} label={b.label} value={b.value} max={max} active={i === 0} />)}
      </div>
    </div>
  )
}

export default function DataPanel({ dataset, year, selected, onSelect }) {
  if (selected == null) return <Ranking dataset={dataset} year={year} onSelect={onSelect} />
  return <Detail district={selected} dataset={dataset} year={year} />
}
