import React, { useEffect, useState } from 'react'
import StoryLayout, { Section, P, PullStat, StatStrip, Figure, StoryFooter } from './StoryLayout.jsx'
import { getStoryDistrictDivide } from '../api.js'

const fmt = (n) => Number(n).toLocaleString('en-US')

const RACE = [
  { key: 'hispanic', label: 'Hispanic/Latinx', c: 'var(--blue-7)' },
  { key: 'white', label: 'White', c: 'var(--blue-4)' },
  { key: 'black', label: 'Black', c: 'var(--blue-8)' },
  { key: 'asian', label: 'Asian', c: 'var(--blue-2)' },
]

function RaceBar({ r }) {
  const known = RACE.reduce((a, x) => a + (r[x.key] || 0), 0)
  const other = Math.max(0, 100 - known)
  return (
    <div style={{ display: 'flex', height: 13, borderRadius: 3, overflow: 'hidden', minWidth: 120 }}>
      {RACE.map((x) => r[x.key] > 0 && (
        <div key={x.key} title={`${x.label}: ${r[x.key]}%`} style={{ width: `${r[x.key]}%`, background: x.c }} />
      ))}
      {other > 0 && <div title={`Other: ${other.toFixed(0)}%`} style={{ width: `${other}%`, background: 'var(--surface-3)' }} />}
    </div>
  )
}

/* Scatter of district dots with a least-squares trend line. */
function Scatter({ points, xLabel, yLabel, yFmt = (v) => v, flat }) {
  const W = 700, H = 300, padL = 48, padR = 16, padT = 16, padB = 40
  const pw = W - padL - padR, ph = H - padT - padB
  const xs = points.map((p) => p.x), ys = points.map((p) => p.y)
  const xmin = Math.min(...xs), xmax = Math.max(...xs)
  const ymin = Math.min(...ys), ymax = Math.max(...ys)
  const yLo = flat ? Math.min(ymin, 0.7) : 0
  const yHi = flat ? Math.max(ymax, 1.3) : ymax * 1.08
  const X = (v) => padL + ((v - xmin) / (xmax - xmin || 1)) * pw
  const Y = (v) => padT + ph - ((v - yLo) / (yHi - yLo || 1)) * ph
  // least squares
  const n = points.length, mx = xs.reduce((a, b) => a + b, 0) / n, my = ys.reduce((a, b) => a + b, 0) / n
  const b = xs.reduce((a, x, i) => a + (x - mx) * (ys[i] - my), 0) / (xs.reduce((a, x) => a + (x - mx) ** 2, 0) || 1)
  const a = my - b * mx
  const yticks = flat ? [0.75, 1.0, 1.25] : [0, ymax / 2, ymax].map((v) => Math.round(v))
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" style={{ display: 'block' }} role="img">
      {yticks.map((t) => (
        <g key={t}>
          <line x1={padL} y1={Y(t)} x2={W - padR} y2={Y(t)} stroke={flat && t === 1 ? 'var(--hairline-strong)' : 'var(--hairline)'} strokeWidth="1" strokeDasharray={flat && t === 1 ? '' : '3 3'} />
          <text x={padL - 8} y={Y(t) + 3} textAnchor="end" style={{ font: '500 10px var(--font-mono)', fill: 'var(--fg-subtle)' }}>{yFmt(t)}</text>
        </g>
      ))}
      {/* trend line */}
      <line x1={X(xmin)} y1={Y(a + b * xmin)} x2={X(xmax)} y2={Y(a + b * xmax)}
        stroke={flat ? 'var(--fg-subtle)' : 'var(--flag)'} strokeWidth="2" strokeDasharray={flat ? '5 4' : ''} opacity={flat ? 0.6 : 0.85} />
      {points.map((p) => (
        <g key={p.label}>
          <circle cx={X(p.x)} cy={Y(p.y)} r="5" fill="var(--blue-6)" />
          <text x={X(p.x)} y={Y(p.y) - 9} textAnchor="middle" style={{ font: '600 9.5px var(--font-mono)', fill: 'var(--fg-muted)' }}>{p.label}</text>
        </g>
      ))}
      <text x={padL + pw / 2} y={H - 6} textAnchor="middle" style={{ font: '500 11px var(--font-sans)', fill: 'var(--fg-muted)' }}>{xLabel}</text>
      <text x={14} y={padT + ph / 2} transform={`rotate(-90 14 ${padT + ph / 2})`} textAnchor="middle" style={{ font: '500 11px var(--font-sans)', fill: 'var(--fg-muted)' }}>{yLabel}</text>
    </svg>
  )
}

const TH = { font: '600 11px/1 var(--font-sans)', letterSpacing: '.04em', textTransform: 'uppercase', color: 'var(--fg-muted)', textAlign: 'right', padding: '0 0 10px' }
const TD = { font: '500 13px/1.3 var(--font-mono)', fontVariantNumeric: 'tabular-nums', color: 'var(--ink)', textAlign: 'right', padding: '9px 0', borderTop: '1px solid var(--hairline)' }

export default function DistrictDivide() {
  const [d, setD] = useState(null)
  const [err, setErr] = useState(null)
  useEffect(() => { getStoryDistrictDivide().then(setD).catch(() => setErr('Could not load district data.')) }, [])

  if (err) return <StoryLayout title="Two Austins, one service standard"><P style={{ color: 'var(--flag)' }}>{err}</P></StoryLayout>
  if (!d) return <StoryLayout title="Two Austins, one service standard"><P style={{ color: 'var(--fg-muted)' }}>Loading districts…</P></StoryLayout>

  const rs = d.districts
  const poorest = rs[0], richest = rs[rs.length - 1]
  const byIncome = [...rs].sort((a, b) => a.pct_under35k - b.pct_under35k)
  const crimePts = rs.map((r) => ({ x: r.pct_under35k, y: r.crime_per_1k, label: `${r.d}` }))
  const respPts = rs.filter((r) => r.resp_ratio != null).map((r) => ({ x: r.pct_under35k, y: r.resp_ratio, label: `${r.d}` }))

  return (
    <StoryLayout
      eyebrow="Equity · Districts"
      title="Two Austins, one service standard"
      dek="Austin's ten council districts are sharply divided by income and race. Crime reports track that divide steeply — but the city's 311 service response doesn't follow the money at all."
      sources={['2022 District Demographic Profiles', 'Crime reports (2025)', '311 mix-adjusted response (D7)']}
    >
      <StatStrip items={[
        { value: `${poorest.pct_under35k.toFixed(0)}% vs ${richest.pct_under35k.toFixed(0)}%`, label: 'Households under $35k', sub: `District ${poorest.d} vs District ${richest.d}` },
        { value: d.corr_crime_income.toFixed(2), label: 'Crime ↔ poverty correlation', sub: 'strong (r, across 10 districts)' },
        { value: d.corr_response_income.toFixed(2), label: '311 response ↔ poverty', sub: 'essentially none' },
      ]} />

      <Section kicker="The divide" title="Ten districts, two Austins">
        <P>Austin elects its council by district, and the districts are not alike. In District
        {' '}{poorest.d}, <strong>{poorest.pct_under35k.toFixed(0)}%</strong> of households earn under
        $35,000; in District {richest.d} it's <strong>{richest.pct_under35k.toFixed(0)}%</strong>. The
        racial map is just as divided — majority-Hispanic, lower-income districts on one side,
        majority-white, higher-income ones on the other.</P>
        <Figure title="Council districts by income and race" source="2022 Austin Council District Demographic Profiles (sorted by share of households under $35k)">
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr>
              <th style={{ ...TH, textAlign: 'left' }}>District</th>
              <th style={TH}>Under $35k</th><th style={TH}>Over $150k</th>
              <th style={{ ...TH, textAlign: 'left', paddingLeft: 14 }}>Race / ethnicity</th>
            </tr></thead>
            <tbody>
              {rs.map((r) => (
                <tr key={r.d}>
                  <td style={{ ...TD, textAlign: 'left', fontFamily: 'var(--font-sans)', fontWeight: 600 }}>District {r.d}</td>
                  <td style={TD}>{r.pct_under35k.toFixed(1)}%</td>
                  <td style={TD}>{r.pct_over150k.toFixed(1)}%</td>
                  <td style={{ ...TD, paddingLeft: 14, width: 160 }}><RaceBar r={r} /></td>
                </tr>
              ))}
            </tbody>
          </table>
          <div style={{ display: 'flex', gap: 14, marginTop: 10, flexWrap: 'wrap' }}>
            {RACE.map((x) => <span key={x.key} className="cii-footnote"><b style={{ color: x.c }}>■</b> {x.label}</span>)}
            <span className="cii-footnote"><b style={{ color: 'var(--surface-3)' }}>■</b> Other</span>
          </div>
        </Figure>
      </Section>

      <Section kicker="Crime reports" title="Crime reports follow the income line">
        <P>Reported crime tracks the divide almost in lockstep — the poorest districts report two to
        three times the rate of the wealthiest (correlation <strong>r = {d.corr_crime_income.toFixed(2)}</strong>).
        Read this carefully: these are <em>reported incidents</em>, which fold in differences in
        reporting and policing, not a clean measure of crime itself.</P>
        <Figure title="Reported crime per 1,000 residents vs. household poverty" source="Crime reports 2025 × district demographics">
          <Scatter points={crimePts} xLabel="% of households under $35k →" yLabel="Crime reports / 1k" />
        </Figure>
      </Section>

      <Section kicker="Service response" title="But the city's response doesn't">
        <P>If the city quietly under-served poorer districts, 311 response would slope the same way. It
        doesn't. Once you adjust for what each district asks for, the response ratio is flat across the
        income gradient — correlation <strong>r = {d.corr_response_income.toFixed(2)}</strong>, essentially
        zero. The poorest district is served as fast as its requests predict; so is the richest.</P>
        <PullStat value={`r = ${d.corr_response_income.toFixed(2)}`} accent="var(--positive)"
          label="Mix-adjusted 311 response shows no meaningful relationship to a district's income — the service standard holds across both Austins." />
        <Figure title="Mix-adjusted 311 response vs. household poverty" source="D7 detector (observed ÷ expected) × district demographics">
          <Scatter points={respPts} xLabel="% of households under $35k →" yLabel="311 response ratio" yFmt={(v) => `${v.toFixed(2)}×`} flat />
        </Figure>
      </Section>

      <Section kicker="The takeaway" title="A divided city, an even-handed service">
        <P>Austin is split — by income, by race, and in how much crime gets reported across that split.
        But on the one service-delivery measure we can hold to a fair standard, the city does not
        favor its wealthier districts. The divide is real; the 311 double standard isn't.</P>
      </Section>

      <StoryFooter
        methodology={d.methodology}
        sources={[
          { name: 'raw_district_demographics', detail: 'City of Austin 2022 Council District Demographic Profiles — population, household-income bands, race/ethnicity shares, one row per district.' },
          { name: 'metric_incidents_by_district', detail: 'Reported crime incidents per district per month (2025), divided by district population for the per-capita rate.' },
          { name: 'metric_311_equity', detail: 'D7 detector — mix-adjusted 311 days-to-close (observed ÷ expected) per district.' },
        ]}
        limits={[
          'Crime figures are REPORTED incidents, not crime — they fold in reporting-rate and policing differences, so a higher rate is not proof of more crime.',
          'Demographics are 2020-census-based (2022 profiles); crime is 2025 — a few years apart.',
          'Ten districts is a small sample; correlations are indicative, not precise estimates.',
          'Crime is district-level only (no finer geography); within-district variation is invisible.',
          'Descriptive — no causal claim about why crime is reported more in some districts.',
        ]}
        updated="2025 crime against the 2022 district profiles"
      />
    </StoryLayout>
  )
}
