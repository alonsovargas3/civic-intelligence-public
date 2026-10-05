import React from 'react'
import MapView from './Map.jsx'
import { Segmented, YearSelect, Icon } from './Primitives.jsx'

const BLUE_RAMP = ['#f7fbff', '#deebf7', '#c6dbef', '#9ecae1', '#6baed6',
  '#4292c6', '#2171b5', '#08519c', '#08306b']

const GLASS = {
  background: 'rgba(255,255,255,.85)', backdropFilter: 'blur(8px)',
  WebkitBackdropFilter: 'blur(8px)', boxShadow: 'var(--shadow-md)',
}

function MapLegend({ dataset, year, view }) {
  const zips = view === 'zips'
  const title = zips ? 'Assessment dispersion (A1)'
    : `${dataset === 'crime' ? 'Crime incidents' : '311 requests'} by district`
  const sub = zips ? 'Coefficient of dispersion · percentile within class · 58 ZIPs'
    : `${year} · percentile rank across 10 districts`
  return (
    <div style={{
      position: 'absolute', left: 16, bottom: 16, zIndex: 5,
      padding: '12px 14px', borderRadius: 'var(--r-md)', maxWidth: 280,
      border: '1px solid var(--hairline)', ...GLASS,
    }}>
      <div style={{ font: '600 12.5px/1.2 var(--font-sans)', color: 'var(--ink)' }}>{title}</div>
      <div className="cii-footnote" style={{ marginTop: 2, marginBottom: 9 }}>{sub}</div>
      <div style={{
        height: 9, borderRadius: 'var(--r-pill)',
        background: `linear-gradient(90deg, ${BLUE_RAMP.join(',')})`,
        border: '1px solid var(--hairline)',
      }} />
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 5 }}>
        <span className="cii-footnote">{zips ? 'Uniform' : 'Lower'}</span>
        <span className="cii-footnote">{zips ? 'Inconsistent' : 'Higher'}</span>
      </div>
      {zips && (
        <div className="cii-footnote" style={{ marginTop: 7, color: 'var(--fg-subtle)' }}>
          Grey = no A1 stratum. Screening signal, not over-assessment.
        </div>
      )}
    </div>
  )
}

export default function MapStage({ dataset, setDataset, year, setYear, selected, onSelect, view, setView }) {
  return (
    <div style={{
      position: 'relative', height: '100%', width: '100%',
      background: 'var(--canvas)', overflow: 'hidden',
    }}>
      {/* The real MapLibre choropleth fills the stage */}
      <MapView dataset={dataset} period={year} onSelect={onSelect} selected={selected} view={view} />

      {/* Floating controls (top-left): geography toggle, then dataset + year */}
      <div style={{
        position: 'absolute', top: 16, left: 16, zIndex: 6,
        display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap',
      }}>
        <div style={{ display: 'inline-flex', alignItems: 'center', padding: 4, borderRadius: 'var(--r-pill)', ...GLASS }}>
          <Segmented value={view} onChange={setView} size="sm" options={[
            { value: 'districts', label: 'Districts' },
            { value: 'zips', label: 'ZIPs' },
          ]} />
        </div>
        {view === 'districts' && (
          <>
            <div style={{ display: 'inline-flex', alignItems: 'center', padding: 4, borderRadius: 'var(--r-pill)', ...GLASS }}>
              <Segmented value={dataset} onChange={setDataset} options={[
                { value: 'crime', label: 'Crime', icon: 'shield-alert' },
                { value: '311', label: '311 requests', icon: 'phone-call' },
              ]} />
            </div>
            <YearSelect value={year} onChange={setYear} />
          </>
        )}
      </div>

      <MapLegend dataset={dataset} year={year} view={view} />

      {/* Attribution */}
      <div style={{
        position: 'absolute', right: 12, bottom: 12, zIndex: 5,
        display: 'inline-flex', alignItems: 'center', gap: 6,
        font: '500 11px/1 var(--font-sans)', color: 'var(--fg-muted)',
        background: 'rgba(255,255,255,.8)', padding: '4px 9px',
        borderRadius: 'var(--r-pill)', border: '1px solid var(--hairline)',
      }}>
        MapLibre <Icon name="info" size={13} color="var(--fg-subtle)" />
      </div>
    </div>
  )
}
