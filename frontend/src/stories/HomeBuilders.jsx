import React, { useEffect, useState } from 'react'
import StoryLayout, { Section, P, PullStat, StatStrip, Figure, VBarChart, StoryFooter } from './StoryLayout.jsx'
import { getStoryHomeBuilders } from '../api.js'

const fmt = (n) => Number(n).toLocaleString('en-US')

function titleCase(s) {
  return String(s).toLowerCase().replace(/\*+main\**|\(main\)|\*+/gi, '').replace(/\s+/g, ' ').trim()
    .replace(/\b([a-z])/g, (m) => m.toUpperCase())
    .replace(/\b(Llc|Lp|Inc|Dba)\b/g, (m) => m.toUpperCase())
}

function BuilderBars({ rows }) {
  const max = Math.max(...rows.map((r) => r.permits))
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {rows.map((r, i) => (
        <div key={r.builder} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ flex: '0 0 210px', font: '500 13px/1.25 var(--font-sans)', color: 'var(--ink)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{titleCase(r.builder)}</span>
          <div style={{ flex: 1, height: 14, background: 'var(--surface-3)', borderRadius: 'var(--r-sm)', overflow: 'hidden' }}>
            <div style={{ width: `${Math.max(2, (r.permits / max) * 100)}%`, height: '100%', background: i < 4 ? 'var(--primary)' : 'var(--blue-4)', borderRadius: 'var(--r-sm)' }} />
          </div>
          <span style={{ flex: '0 0 56px', textAlign: 'right', font: '600 13px var(--font-mono)', color: 'var(--ink)', fontVariantNumeric: 'tabular-nums' }}>{fmt(r.permits)}</span>
        </div>
      ))}
    </div>
  )
}

export default function HomeBuilders() {
  const [d, setD] = useState(null)
  const [err, setErr] = useState(null)
  useEffect(() => { getStoryHomeBuilders().then(setD).catch(() => setErr('Could not load permit data.')) }, [])

  if (err) return <StoryLayout title="Who's building Austin's homes"><P style={{ color: 'var(--flag)' }}>{err}</P></StoryLayout>
  if (!d) return <StoryLayout title="Who's building Austin's homes"><P style={{ color: 'var(--fg-muted)' }}>Loading permits…</P></StoryLayout>

  const peak = d.years.reduce((a, b) => (b.permits > a.permits ? b : a))
  const first = d.years[0], last = d.years[d.years.length - 1]
  const top = d.builders[0]
  const bars = d.years.map((y) => ({
    value: y.permits, valueText: '', label: y.year.slice(2), highlight: y.year === peak.year,
  }))

  return (
    <StoryLayout
      eyebrow="Growth · Housing"
      title="Who's building Austin's homes"
      dek={`Since 2010 the city has issued about ${(d.total_since_2010 / 1000).toFixed(0)},000 permits to build new homes. Count them properly — one per house, not one per electrician — and a short list of national production builders is doing much of the work.`}
      sources={['Issued construction permits', 'New-residential building permits only', '2010–2025']}
    >
      <StatStrip items={[
        { value: `~${(d.total_since_2010 / 1000).toFixed(0)}k`, label: 'New-home permits since 2010', sub: `peak ${fmt(peak.permits)} in ${peak.year}` },
        { value: titleCase(top.builder).split(' ').slice(0, 3).join(' '), label: 'Most active builder', sub: `${fmt(top.permits)} new-home permits` },
        { value: `${Math.round(d.top10_share * 100)}%`, label: 'Pulled by the top 10 builders', sub: 'of permits naming a builder' },
      ]} />

      <Section kicker="Counting it right" title="One house, four permits">
        <P>Austin's permit file is enormous — millions of rows — but most of them aren't new buildings.
        Every new house generates a building permit <em>plus</em> separate electrical, plumbing and
        mechanical permits, so a naive count puts homebuilders shoulder-to-shoulder with electrical and
        plumbing subcontractors. To see who actually builds homes, we count only the
        {' '}<strong>building permit for new residential work</strong> — the general contractor's
        permit. That leaves about {fmt(d.total_since_2010)} new-home permits since 2010.</P>
      </Section>

      <Section kicker="The cycle" title="A boom that tripled, then cooled">
        <P>New-home permitting climbed from roughly {fmt(first.permits)} in {first.year} to a peak of
        {' '}<strong>{fmt(peak.permits)}</strong> in {peak.year}, then fell sharply as interest rates
        rose — to about {fmt(last.permits)} in {last.year}.</P>
        <Figure title="New-home building permits issued per year" source="Issued construction permits — permittype BP, work_class New, residential (2010–2025)">
          <VBarChart bars={bars} height={230} axisLeft={first.year} axisRight={last.year} />
        </Figure>
      </Section>

      <Section kicker="The builders" title="A handful of national builders dominate">
        <P>Rank builders by new-home permits and the list is almost entirely national and regional
        production homebuilders. The ten most active account for
        {' '}<strong>{Math.round(d.top10_share * 100)}%</strong> of every new-home permit that names a
        builder.</P>
        <Figure title="Most new-home building permits, 2010–present" source="Issued construction permits, by contractor of record (name as filed)"
          note="The top four are highlighted. Counts are permits, not finished homes; some entries (e.g. pool builders) hold residential building permits for accessory structures.">
          <BuilderBars rows={d.builders} />
        </Figure>
      </Section>

      <StoryFooter
        methodology={d.methodology}
        sources={[
          { name: 'raw_construction_permits → mv_home_permit_*', detail: 'City of Austin issued construction permits. Restricted to building permits (BP) for new residential work — the general contractor permit — to avoid double-counting the separate electrical/plumbing/mechanical trade permits.' },
        ]}
        limits={[
          'Counts permits issued, not homes completed or occupied.',
          'Builder names are used as filed (no entity resolution), so one builder under several registered names is split and undercounted.',
          'New-residential building permits include some accessory structures (e.g. swimming pools) that carry a residential building permit.',
          'We count permits, not valuation or housing units — those fields in the source contain unusable outliers.',
          '2026 is excluded as a partial year.',
        ]}
        updated="the latest permit load"
      />
    </StoryLayout>
  )
}
