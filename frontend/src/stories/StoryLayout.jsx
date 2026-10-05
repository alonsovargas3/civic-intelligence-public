import React from 'react'
import { Icon } from '../Primitives.jsx'
import { TopNav } from '../Shell.jsx'

/* ============================================================================
   Story page framework — full-width narrative routes.
   A reading-column layout that reuses the design system (tokens + Primitives).
   The methodology / provenance / limits footer is deliberately heavyweight:
   every published number must show how it was derived and what it can't claim.
   ========================================================================== */

const COL = 768 // reading-column max width

export default function StoryLayout({ eyebrow, title, dek, sources, children }) {
  return (
    <div style={{ height: '100vh', overflowY: 'auto', background: 'var(--canvas)' }}>
      <TopNav variant="light" active="stories" />
      <article style={{ maxWidth: COL, margin: '0 auto', padding: '0 24px 112px' }}>
        <header style={{ padding: '52px 0 8px' }}>
          {eyebrow && <div className="cii-eyebrow">{eyebrow}</div>}
          <h1 style={{
            font: '800 41px/1.07 var(--font-sans)', letterSpacing: '-.02em',
            color: 'var(--ink)', margin: '12px 0 0', textWrap: 'balance',
          }}>{title}</h1>
          {dek && (
            <p style={{
              font: '400 20px/1.5 var(--font-sans)', color: 'var(--fg-muted)',
              margin: '18px 0 0', textWrap: 'pretty',
            }}>{dek}</p>
          )}
          {sources && sources.length > 0 && (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 22 }}>
              {sources.map((s) => <SourceTag key={s}>{s}</SourceTag>)}
            </div>
          )}
        </header>
        {children}
      </article>
    </div>
  )
}

export function SourceTag({ children }) {
  return (
    <span className="cii-tag" style={{
      display: 'inline-flex', alignItems: 'center', gap: 6, padding: '5px 10px',
      borderRadius: 'var(--r-pill)', color: 'var(--fg-muted)',
      background: 'var(--surface-3)', border: '1px solid var(--hairline)',
      textTransform: 'none', letterSpacing: 0, fontWeight: 500,
    }}>
      <Icon name="info" size={13} color="var(--fg-subtle)" />{children}
    </span>
  )
}

/* A narrative beat: optional kicker + heading, then prose / figures as children. */
export function Section({ kicker, title, children, style }) {
  return (
    <section style={{ marginTop: 44, ...style }}>
      {kicker && <div className="cii-eyebrow" style={{ marginBottom: 8 }}>{kicker}</div>}
      {title && <h2 style={{ font: '700 25px/1.2 var(--font-sans)', letterSpacing: '-.015em', color: 'var(--ink)', margin: '0 0 14px' }}>{title}</h2>}
      {children}
    </section>
  )
}

/* Body paragraph. */
export function P({ children, style }) {
  return <p style={{ font: '400 17px/1.62 var(--font-sans)', color: 'var(--fg)', margin: '0 0 16px', textWrap: 'pretty', ...style }}>{children}</p>
}

/* Big pull-stat callout (one hero number). */
export function PullStat({ value, label, accent }) {
  return (
    <div style={{ margin: '24px 0', padding: '4px 0 4px 20px', borderLeft: `3px solid ${accent || 'var(--accent)'}` }}>
      <div style={{ font: '700 46px/1 var(--font-mono)', letterSpacing: '-.02em', color: 'var(--ink)', fontVariantNumeric: 'tabular-nums' }}>{value}</div>
      {label && <div style={{ font: '400 15px/1.45 var(--font-sans)', color: 'var(--fg-muted)', marginTop: 10, maxWidth: 560, textWrap: 'pretty' }}>{label}</div>}
    </div>
  )
}

/* A row of compact stat tiles. items: [{value, label, sub}] */
export function StatStrip({ items }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: `repeat(${items.length}, 1fr)`, gap: 12, margin: '8px 0 4px' }}>
      {items.map((it, i) => (
        <div key={i} style={{ padding: '16px 16px', borderRadius: 'var(--r-md)', background: 'var(--surface)', border: '1px solid var(--hairline)' }}>
          <div style={{ font: '600 28px/1 var(--font-mono)', letterSpacing: '-.02em', color: 'var(--ink)', fontVariantNumeric: 'tabular-nums' }}>{it.value}</div>
          <div className="cii-eyebrow" style={{ marginTop: 10 }}>{it.label}</div>
          {it.sub && <div className="cii-footnote" style={{ marginTop: 6 }}>{it.sub}</div>}
        </div>
      ))}
    </div>
  )
}

/* Figure wrapper: a titled card around a chart/table, with a source caption. */
export function Figure({ title, source, note, children }) {
  return (
    <figure style={{ margin: '24px 0', padding: '18px 18px 14px', borderRadius: 'var(--r-lg)', background: 'var(--surface)', border: '1px solid var(--hairline)' }}>
      {title && <figcaption style={{ font: '700 14px/1.3 var(--font-sans)', color: 'var(--ink)', marginBottom: 14 }}>{title}</figcaption>}
      {children}
      {note && <div className="cii-footnote" style={{ marginTop: 12 }}>{note}</div>}
      {source && <div className="cii-footnote" style={{ marginTop: 6, color: 'var(--fg-subtle)' }}>Source: {source}</div>}
    </figure>
  )
}

/* Lightweight responsive vertical bar chart (pure SVG, no chart lib).
   bars: [{ value, label, valueText, highlight }]. Value labels sit above bars;
   labels below. axisLeft / axisRight render a "low → high" caption under the axis. */
export function VBarChart({ bars, height = 260, axisLeft, axisRight }) {
  const W = 700
  const padTop = 26, padBottom = axisLeft || axisRight ? 46 : 28
  const plotH = height - padTop - padBottom
  const max = Math.max(...bars.map((b) => b.value), 1)
  const n = bars.length
  const gap = 10
  const bw = (W - gap * (n - 1)) / n
  return (
    <svg viewBox={`0 0 ${W} ${height}`} width="100%" style={{ display: 'block' }} role="img">
      {/* baseline */}
      <line x1={0} y1={padTop + plotH} x2={W} y2={padTop + plotH} stroke="var(--hairline-strong)" strokeWidth="1" />
      {bars.map((b, i) => {
        const h = Math.max(2, (b.value / max) * plotH)
        const x = i * (bw + gap)
        const y = padTop + plotH - h
        const fill = b.highlight ? 'var(--flag)' : 'var(--blue-5)'
        return (
          <g key={i}>
            <rect x={x} y={y} width={bw} height={h} rx="4" fill={fill} />
            <text x={x + bw / 2} y={y - 7} textAnchor="middle"
              style={{ font: `${b.highlight ? 700 : 500} 12px var(--font-mono)`, fill: b.highlight ? 'var(--flag)' : 'var(--fg-muted)' }}>
              {b.valueText}
            </text>
            <text x={x + bw / 2} y={padTop + plotH + 16} textAnchor="middle"
              style={{ font: '500 11px var(--font-sans)', fill: 'var(--fg-subtle)' }}>
              {b.label}
            </text>
          </g>
        )
      })}
      {(axisLeft || axisRight) && (
        <text x={0} y={height - 8} style={{ font: '400 11px var(--font-sans)', fill: 'var(--fg-subtle)' }}>{axisLeft}</text>
      )}
      {axisRight && (
        <text x={W} y={height - 8} textAnchor="end" style={{ font: '400 11px var(--font-sans)', fill: 'var(--fg-subtle)' }}>{axisRight}</text>
      )}
    </svg>
  )
}

/* The serious-journalist footer: how we know, provenance, limits, freshness.
   Pass methodology (string|node), sources [{name, detail}], limits [string], updated. */
export function StoryFooter({ methodology, sources, limits, updated }) {
  return (
    <footer style={{ marginTop: 56, paddingTop: 28, borderTop: '2px solid var(--hairline-strong)' }}>
      <FooterBlock icon="info" title="How we reached this">
        <p style={{ font: '400 14.5px/1.6 var(--font-sans)', color: 'var(--fg)', margin: 0, textWrap: 'pretty' }}>{methodology}</p>
      </FooterBlock>

      {sources && sources.length > 0 && (
        <FooterBlock icon="landmark" title="Data & provenance">
          <ul style={{ margin: 0, paddingLeft: 0, listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 10 }}>
            {sources.map((s, i) => (
              <li key={i} style={{ display: 'flex', gap: 10, alignItems: 'baseline' }}>
                <span style={{ font: '600 12.5px/1.4 var(--font-mono)', color: 'var(--primary-ink)', background: 'var(--primary-tint)', padding: '2px 8px', borderRadius: 'var(--r-sm)', flex: '0 0 auto' }}>{s.name}</span>
                <span style={{ font: '400 13.5px/1.5 var(--font-sans)', color: 'var(--fg-muted)' }}>{s.detail}</span>
              </li>
            ))}
          </ul>
        </FooterBlock>
      )}

      {limits && limits.length > 0 && (
        <FooterBlock icon="triangle-alert" title="Limits — what this does NOT show">
          <ul style={{ margin: 0, paddingLeft: 18, display: 'flex', flexDirection: 'column', gap: 7 }}>
            {limits.map((l, i) => (
              <li key={i} style={{ font: '400 13.5px/1.55 var(--font-sans)', color: 'var(--fg-muted)', textWrap: 'pretty' }}>{l}</li>
            ))}
          </ul>
        </FooterBlock>
      )}

      <div className="cii-footnote" style={{ marginTop: 22, color: 'var(--fg-subtle)' }}>
        {updated ? `Figures current as of ${updated}. ` : ''}
        Every number on this page comes from a query against the project's open-data warehouse;
        the exact query is recorded in the project's findings log.
      </div>
    </footer>
  )
}

function FooterBlock({ icon, title, children }) {
  return (
    <div style={{ marginBottom: 22 }}>
      <div style={{ display: 'inline-flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
        <Icon name={icon} size={16} color="var(--fg-muted)" />
        <span className="cii-eyebrow">{title}</span>
      </div>
      {children}
    </div>
  )
}
