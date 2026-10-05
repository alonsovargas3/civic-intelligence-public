import React, { useEffect, useState } from 'react'
import StoryLayout, { Section, P, PullStat, StatStrip, Figure, VBarChart, StoryFooter } from './StoryLayout.jsx'
import { getStoryHomesteadCap } from '../api.js'

const fmt = (n) => Number(n).toLocaleString('en-US')
const money = (v) => {
  const n = Number(v)
  if (n >= 1e9) return `$${(n / 1e9).toFixed(2)}B`
  if (n >= 1e6) return `$${(n / 1e6).toFixed(1)}M`
  if (n >= 1e3) return `$${Math.round(n / 1e3)}k`
  return `$${fmt(Math.round(n))}`
}
const pct = (x) => `${(Number(x) * 100).toFixed(1)}%`

const TH = { font: '600 11px/1 var(--font-sans)', letterSpacing: '.05em', textTransform: 'uppercase', color: 'var(--fg-muted)', textAlign: 'right', padding: '0 0 10px' }
const TD = { font: '500 13.5px/1.3 var(--font-mono)', fontVariantNumeric: 'tabular-nums', color: 'var(--ink)', textAlign: 'right', padding: '10px 0', borderTop: '1px solid var(--hairline)' }
const TD_L = { ...TD, textAlign: 'left', font: '600 13.5px/1.25 var(--font-sans)' }

const CAT = {
  A1: 'Single-family homes', A2: 'Residential (secondary)', A3: 'Residential',
  A4: 'Condominiums', B2: 'Duplex / multifamily', C1: 'Vacant residential lots',
  D1: 'Qualified ag land', E1: 'Rural homestead w/ improvement',
}

export default function HomesteadCap() {
  const [d, setD] = useState(null)
  const [err, setErr] = useState(null)
  useEffect(() => { getStoryHomesteadCap().then(setD).catch(() => setErr('Could not load homestead-cap data.')) }, [])

  if (err) return <StoryLayout title="The homestead cap shield"><P style={{ color: 'var(--flag)' }}>{err}</P></StoryLayout>
  if (!d) return <StoryLayout title="The homestead cap shield"><P style={{ color: 'var(--fg-muted)' }}>Loading the 2025 roll…</P></StoryLayout>

  const o = d.overall
  const top = d.deciles[d.deciles.length - 1]
  const bottom = d.deciles[0]
  const ratio = (top.avg_shield / bottom.avg_shield).toFixed(0)
  const a1 = d.by_category.find((c) => c.category === 'A1')

  const bars = d.deciles.map((x) => ({
    value: x.shield,
    valueText: `$${(x.shield / 1e9).toFixed(2)}B`,
    label: String(x.dec),
    highlight: x.dec === 10,
  }))

  return (
    <StoryLayout
      eyebrow="Property · Taxes"
      title="The homestead cap shields $10 billion — most of it from the priciest homes"
      dek="A Texas tax break caps how fast a home's taxable value can rise. It keeps about $10 billion off Austin's tax rolls — and nearly half of that benefit, in dollars, flows to the most valuable 10% of homes."
      sources={['TCAD 2025 certified roll', 'Residence-homestead 10% cap', 'Appraised vs. assessed value']}
    >
      <StatStrip items={[
        { value: money(o.total_shielded), label: 'Value shielded from tax', sub: `across ${fmt(o.homesteads)} homesteads` },
        { value: pct(top.share), label: 'Captured by the top 10%', sub: 'of homes by market value' },
        { value: money(top.avg_shield), label: 'Avg. break, top-decile home', sub: `vs ${money(bottom.avg_shield)} bottom-decile` },
      ]} />

      <Section>
        <P>Texas gives homeowners a quiet but powerful tax break. Once a property is your
        residence homestead, the <em>taxable</em> value the county can assess it at may rise no more
        than 10% a year — even if the home's market value jumps 30% or 40%. In a city where prices
        climbed fast, that gap compounds: the appraisal district still records what the home is
        worth, but taxes it on a lower, capped figure.</P>
        <P>The difference between a home's full appraised value and its capped taxable value is value
        shielded from taxation. Summed across every capped homestead on the 2025 roll, it comes to:</P>
        <PullStat value={money(o.total_shielded)}
          label={`held off the city's $${(d.context.assessed / 1e9).toFixed(0)}B taxable base by the 10% cap — the median capped home shields ${money(o.median_shield)}, but the average is ${money(o.avg_shield)}, pulled up by a long tail of very expensive homes.`} />
      </Section>

      <Section kicker="The finding" title="Who the cap shields">
        <P>Sort the {fmt(o.homesteads)} capped homes into ten equal groups by market value, from
        least to most valuable, and add up the shield in each group. The break isn't spread evenly:
        it climbs steeply with home value. The most valuable tenth of homes captures
        <strong> {pct(top.share)}</strong> of the entire $10 billion — more than the bottom seven
        deciles combined.</P>
        <Figure title="Value shielded by the homestead cap, by home-value decile"
          source="TCAD 2025 certified roll (parcel_value.capped_value), capped homesteads only"
          note={`Each group holds ${fmt(bottom.n)} homes. Decile 1 = homes under ${money(bottom.max_mkt)}; decile 10 = ${money(top.min_mkt)} to ${money(top.max_mkt)}.`}>
          <VBarChart bars={bars} axisLeft="◀ lower-value homes" axisRight="higher-value homes ▶" />
        </Figure>
        <P>Per home, the gap is starker still: the average top-decile homestead shields
        <strong> {money(top.avg_shield)}</strong> of value from tax, about <strong>{ratio}×</strong> the
        {' '}{money(bottom.avg_shield)} shielded for the average home in the bottom decile. The cap
        protects every homesteader, but in absolute dollars it does the most for those whose market
        value has run up the fastest and furthest.</P>
      </Section>

      <Section kicker="What's capped" title="Almost entirely single-family homes">
        {a1 && (
          <P>The shield is concentrated in ordinary single-family housing: class A1 homes account
          for <strong>{money(a1.shield)}</strong> of the {money(o.total_shielded)} total — about
          {' '}{pct(a1.shield / o.total_shielded)} of it. Condos, rural homesteads and other
          residence types make up the rest.</P>
        )}
        <Figure title="Value shielded by property category" source="parcel_value × parcel.category, TCAD 2025">
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr>
              <th style={{ ...TH, textAlign: 'left' }}>Category</th>
              <th style={TH}>Homes</th><th style={TH}>Shielded</th><th style={TH}>Avg / home</th>
            </tr></thead>
            <tbody>
              {d.by_category.map((c) => (
                <tr key={c.category}>
                  <td style={TD_L}>{CAT[c.category] || c.category} <span className="cii-footnote" style={{ fontFamily: 'var(--font-mono)' }}>{c.category}</span></td>
                  <td style={TD}>{fmt(c.n)}</td>
                  <td style={{ ...TD, fontWeight: 600 }}>{money(c.shield)}</td>
                  <td style={TD}>{money(c.avg_shield)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Figure>
      </Section>

      <StoryFooter
        methodology={d.methodology}
        sources={[
          { name: 'raw_tcad_roll → parcel_value', detail: 'Travis Central Appraisal District 2025 certified roll. capped_value is the homestead cap loss (appraised − assessed), verified equal to that difference for 99.5% of capped homes.' },
          { name: 'parcel', detail: 'Per-parcel category (A1 single-family, A4 condo, …) joined by account_id for the by-category cut.' },
        ]}
        limits={[
          'A horizontal-equity / who-is-shielded measure — NOT a claim that any home is mis-appraised or over- or under-valued.',
          'Not a verdict on the policy: the cap limits year-over-year tax increases for every homesteader, and absolute-dollar regressivity does not by itself make it good or bad.',
          'Appraised value only — Texas is a non-disclosure state, so no sale prices exist to check appraisals against.',
          'A single roll year (2025). The multi-year price run-up that creates the cap loss is not itself shown; year-over-year accumulation needs prior rolls.',
          'About 0.5% of capped parcels where capped_value ≠ appraised − assessed are included as-is (rounding / edge cases); the effect on the totals is negligible.',
        ]}
        updated="the 2025 certified roll"
      />
    </StoryLayout>
  )
}
