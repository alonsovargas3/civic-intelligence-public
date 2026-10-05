import React from 'react'
import {
  Calendar, ChevronDown, ShieldAlert, PhoneCall, Info, TriangleAlert,
  User, Building2, Landmark,
} from 'lucide-react'

const ICONS = {
  calendar: Calendar, 'chevron-down': ChevronDown, 'shield-alert': ShieldAlert,
  'phone-call': PhoneCall, info: Info, 'triangle-alert': TriangleAlert,
  user: User, building: Building2, landmark: Landmark,
}

export function Icon({ name, size = 18, stroke = 1.75, color = 'currentColor', style }) {
  const C = ICONS[name] || Info
  return <C size={size} strokeWidth={stroke} color={color}
    style={{ display: 'inline-flex', flex: '0 0 auto', ...style }} aria-hidden="true" />
}

/* Brand mark — the ATX Civic Data logo: an "A" assembled from four polygon
   shards (apex, crossbar, left leg, right leg). Bare inline SVG, no badge. */
export function BrandMark({ size = 30 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 100 100" aria-hidden="true"
      style={{ display: 'block', flex: '0 0 auto' }}>
      <polygon points="50,14 64.2,44 35.8,44" fill="var(--accent)" />
      <polygon points="33.9,48 66.1,48 73.6,64 26.4,64" fill="var(--slate-blue)" />
      <polygon points="24.5,68 38,68 38,86 16,86" fill="var(--orange)" />
      <polygon points="61.5,68 75.5,68 84,86 62,86" fill="var(--amber)" />
    </svg>
  )
}

/* Segmented control (Dataset toggle, etc.) */
export function Segmented({ options, value, onChange, size = 'md' }) {
  const pad = size === 'sm' ? '5px 10px' : '7px 14px'
  const fs = size === 'sm' ? 12.5 : 13.5
  return (
    <div role="tablist" style={{
      display: 'inline-flex', gap: 2, padding: 3, borderRadius: 'var(--r-pill)',
      background: 'var(--surface-3)', border: '1px solid var(--hairline)',
    }}>
      {options.map((opt) => {
        const active = opt.value === value
        return (
          <button key={opt.value} role="tab" aria-selected={active}
            onClick={() => onChange(opt.value)}
            style={{
              display: 'inline-flex', alignItems: 'center', gap: 6, padding: pad,
              border: 'none', cursor: 'pointer', borderRadius: 'var(--r-pill)',
              font: `600 ${fs}px/1 var(--font-sans)`,
              color: active ? '#fff' : 'var(--fg-muted)',
              background: active ? 'var(--accent)' : 'transparent',
              boxShadow: active ? 'var(--shadow-sm)' : 'none',
              transition: 'color var(--dur) var(--ease), background var(--dur) var(--ease)',
              whiteSpace: 'nowrap',
            }}>
            {opt.icon && <Icon name={opt.icon} size={15} />}
            {opt.label}
          </button>
        )
      })}
    </div>
  )
}

/* Compact year select with custom chevron */
export function YearSelect({ value, onChange, years = ['2025', '2024', '2023'] }) {
  return (
    <label style={{
      display: 'inline-flex', alignItems: 'center', gap: 6,
      padding: '7px 10px 7px 12px', borderRadius: 'var(--r-pill)',
      background: 'var(--surface)', border: '1px solid var(--hairline)',
      boxShadow: 'var(--shadow-sm)', cursor: 'pointer', position: 'relative',
    }}>
      <Icon name="calendar" size={15} color="var(--fg-muted)" />
      <select value={value} onChange={(e) => onChange(e.target.value)}
        style={{
          appearance: 'none', WebkitAppearance: 'none', border: 'none',
          background: 'transparent', font: '600 13.5px/1 var(--font-sans)',
          color: 'var(--ink)', cursor: 'pointer', paddingRight: 16, outline: 'none',
        }}>
        {years.map((y) => <option key={y} value={y}>{y}</option>)}
      </select>
      <Icon name="chevron-down" size={14} color="var(--fg-muted)"
        style={{ position: 'absolute', right: 10, pointerEvents: 'none' }} />
    </label>
  )
}

/* Panel tabs with an underline thumb */
export function Tabs({ tabs, value, onChange }) {
  return (
    <div style={{ display: 'flex', gap: 2, borderBottom: '1px solid var(--hairline)' }}>
      {tabs.map((t) => {
        const active = t.value === value
        return (
          <button key={t.value} onClick={() => onChange(t.value)}
            style={{
              position: 'relative', flex: '0 0 auto', padding: '11px 12px 12px',
              border: 'none', background: 'transparent', cursor: 'pointer',
              font: `${active ? 600 : 500} 13.5px/1 var(--font-sans)`,
              color: active ? 'var(--ink)' : 'var(--fg-muted)',
              transition: 'color var(--dur) var(--ease)',
            }}>
            {t.label}
            <span style={{
              position: 'absolute', left: 8, right: 8, bottom: -1, height: 2.5,
              borderRadius: 2, background: active ? 'var(--accent)' : 'transparent',
              transition: 'background var(--dur) var(--ease)',
            }} />
          </button>
        )
      })}
    </div>
  )
}

/* Status badge */
export function Badge({ children, tone = 'flag' }) {
  const map = {
    flag: { c: 'var(--flag)', bg: 'var(--flag-bg)', b: 'var(--flag-border)' },
    info: { c: 'var(--info)', bg: 'var(--info-bg)', b: 'transparent' },
    muted: { c: 'var(--fg-muted)', bg: 'var(--surface-3)', b: 'transparent' },
    ok: { c: 'var(--positive)', bg: '#e8f3ec', b: 'transparent' },
  }[tone]
  return (
    <span className="cii-tag" style={{
      display: 'inline-flex', alignItems: 'center', gap: 5, whiteSpace: 'nowrap',
      padding: '4px 9px', borderRadius: 'var(--r-pill)',
      color: map.c, background: map.bg, border: `1px solid ${map.b}`,
    }}>{children}</span>
  )
}

/* Stat tile (big tabular number) */
export function StatTile({ label, value, sub, accent }) {
  return (
    <div style={{
      flex: 1, minWidth: 0, padding: '14px 16px', borderRadius: 'var(--r-md)',
      background: 'var(--surface)', border: '1px solid var(--hairline)',
    }}>
      <div className="cii-eyebrow" style={{ marginBottom: 8 }}>{label}</div>
      <div className="cii-stat" style={accent ? { color: 'var(--primary-deep)' } : null}>{value}</div>
      {sub && <div className="cii-footnote" style={{ marginTop: 6 }}>{sub}</div>}
    </div>
  )
}

/* Amber methodology / caveat callout */
export function Caveat({ children, compact }) {
  return (
    <div style={{
      display: 'flex', gap: 10, padding: compact ? '10px 12px' : '12px 14px',
      borderRadius: 'var(--r-md)', background: 'var(--warn-bg)',
      border: '1px solid var(--warn-border)',
    }}>
      <Icon name="info" size={16} color="var(--warn-ink)" style={{ marginTop: 2 }} />
      <p style={{ font: '400 12.5px/1.5 var(--font-sans)', color: 'var(--warn-ink)', margin: 0, textWrap: 'pretty' }}>
        {children}
      </p>
    </div>
  )
}

/* Horizontal breakdown bar */
export function BarRow({ label, value, max, active }) {
  const fmt = (n) => Number(n).toLocaleString('en-US')
  const pct = Math.max(2, Math.round((value / max) * 100))
  return (
    <div style={{ padding: '7px 0' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 12, marginBottom: 5 }}>
        <span style={{ font: '500 13px/1.3 var(--font-sans)', color: 'var(--fg)' }}>{label}</span>
        <span className="cii-mono" style={{ flex: '0 0 auto' }}>{fmt(value)}</span>
      </div>
      <div style={{ height: 6, borderRadius: 'var(--r-pill)', background: 'var(--surface-3)', overflow: 'hidden' }}>
        <div style={{
          width: `${pct}%`, height: '100%', borderRadius: 'var(--r-pill)',
          background: active ? 'var(--primary)' : 'var(--blue-4)',
          transition: 'width 400ms var(--ease)',
        }} />
      </div>
    </div>
  )
}
