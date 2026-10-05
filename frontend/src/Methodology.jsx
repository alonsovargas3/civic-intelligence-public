import React from 'react'
import { TopNav, SiteFooter } from './Shell.jsx'

const PRINCIPLES = [
  { n: '01', t: 'Research, not advocacy', d: 'We publish methodology and let readers draw conclusions. No endorsements, no policy asks.' },
  { n: '02', t: 'Caveats live next to numbers', d: 'Every statistic carries its limits inline — join rates, heuristics, missing fields — not in fine print.' },
  { n: '03', t: 'Signals, never findings', d: 'Statistical anomalies are screening signals that warrant review — not accusations against anyone.' },
]

const SOURCES = [
  ['311 service requests', 'City of Austin Socrata · xwdj-i9he', 'Daily'],
  ['Crime reports', 'City of Austin Socrata · fdj4-gpfu', 'Weekly · rolling 2003–present'],
  ['Building permits', 'City of Austin Socrata · 3syk-w9eu', 'Daily'],
  ['Property roll', 'Travis Central Appraisal District', 'Annual certified roll'],
  ['Campaign finance', 'City Clerk filings', 'Per filing period'],
  ['Council agendas & sponsors', 'Austin Legistar API', 'Per meeting'],
]

const AGGREGATION = [
  'Incident counts are pre-aggregated per council district per month from the raw feeds; nothing is computed on the fly.',
  'Crime has no point coordinates in the source; it is shown only at district level.',
  'Crashes and code cases carry no council district; they appear as point or heatmap layers, never in district rankings.',
  'Code cases are attributed to the current owner via parcel geo_id (~94% join rate, deduplicated); owner "kind" is a name heuristic with residual error.',
  'Displayed values are rounded for readability; underlying tables keep full precision.',
]

export default function Methodology() {
  return (
    <div style={{ minHeight: '100vh', overflowY: 'auto', display: 'flex', flexDirection: 'column', background: 'var(--canvas)' }}>
      <TopNav variant="light" active="methodology" />
      <div style={{ maxWidth: 840, margin: '0 auto', width: '100%', boxSizing: 'border-box', padding: '52px 36px 56px', display: 'flex', flexDirection: 'column', gap: 36 }}>
        <div>
          <p style={{ font: '600 12px/1 var(--font-sans)', letterSpacing: '.1em', textTransform: 'uppercase', color: 'var(--orange)', margin: '0 0 12px' }}>Methodology</p>
          <h1 style={{ font: '800 40px/1.12 var(--font-sans)', letterSpacing: '-.02em', color: 'var(--ink)', margin: '0 0 14px' }}>How the numbers are made</h1>
          <p style={{ font: '400 16px/1.6 var(--font-sans)', color: 'var(--fg)', margin: 0, textWrap: 'pretty' }}>
            Everything published here comes from a query against public data. This page describes the sources, how they're joined and aggregated, and — most importantly — what they cannot tell us.
          </p>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16 }}>
          {PRINCIPLES.map((p) => (
            <div key={p.n} style={{ background: 'var(--surface)', border: '1px solid var(--hairline)', borderRadius: 12, padding: 22 }}>
              <p style={{ font: '600 22px/1 var(--font-mono)', color: 'var(--orange)', margin: '0 0 10px' }}>{p.n}</p>
              <p style={{ font: '700 15px/1.3 var(--font-sans)', color: 'var(--ink)', margin: '0 0 6px' }}>{p.t}</p>
              <p style={{ font: '400 13px/1.55 var(--font-sans)', color: 'var(--fg-muted)', margin: 0 }}>{p.d}</p>
            </div>
          ))}
        </div>

        <div>
          <h2 style={{ font: '700 22px/1.25 var(--font-sans)', color: 'var(--ink)', margin: '0 0 14px' }}>Sources</h2>
          <div style={{ background: 'var(--surface)', border: '1px solid var(--hairline)', borderRadius: 12, overflow: 'hidden' }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1.3fr 1.6fr 1fr', padding: '12px 22px', borderBottom: '1px solid var(--hairline)', background: 'var(--surface-2)' }}>
              {['Dataset', 'Source', 'Update cadence'].map((h) => (
                <span key={h} className="cii-eyebrow">{h}</span>
              ))}
            </div>
            {SOURCES.map((row, i) => (
              <div key={row[0]} style={{ display: 'grid', gridTemplateColumns: '1.3fr 1.6fr 1fr', padding: '14px 22px', borderBottom: i < SOURCES.length - 1 ? '1px solid var(--surface-3)' : 'none' }}>
                <span style={{ font: '600 14px/1.3 var(--font-sans)', color: 'var(--ink)' }}>{row[0]}</span>
                <span style={{ font: '500 12.5px/1.3 var(--font-mono)', color: 'var(--fg-muted)' }}>{row[1]}</span>
                <span style={{ font: '400 13px/1.3 var(--font-sans)', color: 'var(--fg-muted)' }}>{row[2]}</span>
              </div>
            ))}
          </div>
        </div>

        <div>
          <h2 style={{ font: '700 22px/1.25 var(--font-sans)', color: 'var(--ink)', margin: '0 0 14px' }}>Aggregation</h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {AGGREGATION.map((a, i) => (
              <div key={i} style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}>
                <span style={{ flex: 'none', width: 7, height: 7, marginTop: 7, background: 'var(--slate-blue)', transform: 'rotate(45deg)' }} />
                <p style={{ font: '400 15px/1.6 var(--font-sans)', color: 'var(--fg)', margin: 0 }}>{a}</p>
              </div>
            ))}
          </div>
        </div>

        <div style={{ background: 'var(--warn-bg)', border: '1px solid var(--warn-border)', borderRadius: 12, padding: '22px 26px', display: 'flex', gap: 14, alignItems: 'flex-start' }}>
          <span style={{ flex: 'none', width: 18, height: 18, marginTop: 2, border: '2px solid var(--warn-ink)', borderRadius: '50%', display: 'grid', placeItems: 'center', font: '700 11px/1 var(--font-sans)', color: 'var(--warn-ink)' }}>i</span>
          <div>
            <p style={{ font: '700 15px/1.3 var(--font-sans)', color: 'var(--warn-ink)', margin: '0 0 6px' }}>What this data cannot tell us</p>
            <p style={{ font: '400 14px/1.6 var(--font-sans)', color: 'var(--warn-ink)', margin: 0, textWrap: 'pretty' }}>
              Texas is a non-disclosure state: no sale prices or assessment ratios are ever shown, so assessment work measures value-density dispersion — explicitly not an IAAO ratio-based coefficient of dispersion. Owner-type comparisons do not control for lot quality, protest activity, or genuine value differences. Contribution-to-sponsorship links are approximate name matches and are one input to influence, not a vote; more money does not imply any quid pro quo.
            </p>
          </div>
        </div>

        <div>
          <h2 style={{ font: '700 22px/1.25 var(--font-sans)', color: 'var(--ink)', margin: '0 0 10px' }}>Corrections</h2>
          <p style={{ font: '400 15px/1.6 var(--font-sans)', color: 'var(--fg)', margin: 0, textWrap: 'pretty' }}>
            If a number is wrong, we want to know. Open an issue in this project's source repository — corrections are published on the story they amend, with a dated note.
          </p>
        </div>
      </div>
      <div style={{ marginTop: 'auto' }}><SiteFooter /></div>
    </div>
  )
}
