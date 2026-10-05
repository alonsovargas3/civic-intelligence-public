import React, { useEffect, useState } from 'react'
import StoryLayout, { Section, P, PullStat, StatStrip, Figure, StoryFooter } from './StoryLayout.jsx'
import { getStoryWhoLobbies } from '../api.js'

const fmt = (n) => Number(n).toLocaleString('en-US')
const money = (v) => {
  const n = Number(v)
  if (n >= 1e6) return `$${(n / 1e6).toFixed(1)}M`
  if (n >= 1e3) return `$${Math.round(n / 1e3)}k`
  return `$${fmt(Math.round(n))}`
}

function HBars({ rows, hot }) {
  const max = Math.max(...rows.map((r) => r.value))
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {rows.map((r) => {
        const isHot = hot && hot(r)
        return (
          <div key={r.label} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ flex: '0 0 196px', font: '500 13px/1.25 var(--font-sans)', color: 'var(--ink)' }}>{r.label}</span>
            <div style={{ flex: 1, height: 14, background: 'var(--surface-3)', borderRadius: 'var(--r-sm)', overflow: 'hidden' }}>
              <div style={{ width: `${Math.max(1.5, (r.value / max) * 100)}%`, height: '100%', background: isHot ? 'var(--blue-7)' : 'var(--blue-4)', borderRadius: 'var(--r-sm)' }} />
            </div>
            <span style={{ flex: '0 0 52px', textAlign: 'right', font: `${isHot ? 700 : 500} 13px var(--font-mono)`, color: 'var(--ink)', fontVariantNumeric: 'tabular-nums' }}>{fmt(r.value)}</span>
          </div>
        )
      })}
    </div>
  )
}

const TD_L = { font: '600 13px/1.25 var(--font-sans)', color: 'var(--ink)', textAlign: 'left', padding: '9px 0', borderTop: '1px solid var(--hairline)' }
const TD_R = { font: '500 12.5px/1.3 var(--font-sans)', color: 'var(--fg-muted)', textAlign: 'right', padding: '9px 0', borderTop: '1px solid var(--hairline)' }

export default function WhoLobbies() {
  const [d, setD] = useState(null)
  const [err, setErr] = useState(null)
  useEffect(() => { getStoryWhoLobbies().then(setD).catch(() => setErr('Could not load lobbying data.')) }, [])

  if (err) return <StoryLayout title="Who lobbies City Hall?"><P style={{ color: 'var(--flag)' }}>{err}</P></StoryLayout>
  if (!d) return <StoryLayout title="Who lobbies City Hall?"><P style={{ color: 'var(--fg-muted)' }}>Loading lobbying disclosures…</P></StoryLayout>

  const s = d.scale
  // dedupe big clients by normalized name
  const seen = new Set()
  const bigClients = d.big_clients.filter((c) => {
    const k = c.client.toLowerCase().slice(0, 16)
    if (seen.has(k)) return false
    seen.add(k); return true
  }).slice(0, 8)

  return (
    <StoryLayout
      eyebrow="Influence · Lobbying"
      title="Who lobbies City Hall? Overwhelmingly, developers."
      dek="Austin's registered lobbyists work for some 2,630 clients — and nearly three-quarters are real estate and development. They work the council on the very thing it divides over most: land."
      sources={['Registered-lobbyist disclosures', `${fmt(s.lobbyists)} lobbyists · ${fmt(s.clients)} clients`, 'Self-reported']}
    >
      <StatStrip items={[
        { value: fmt(s.lobbyists), label: 'Registered lobbyists', sub: `for ${fmt(s.clients)} distinct clients` },
        { value: `${Math.round(d.re_dev_share * 100)}%`, label: 'Clients in real estate / development', sub: `${fmt(d.re_dev_clients)} of ${fmt(d.total_classified_clients)}` },
        { value: money(d.official_spend.total), label: 'Spent on officials, all years', sub: 'food, gifts, travel — combined' },
      ]} />

      <Section kicker="The finding" title="Austin's lobbying is a land business">
        <P>Sort the city's {fmt(d.total_classified_clients)} lobbying clients by what they do, and one
        industry swamps the rest. <strong>{Math.round(d.re_dev_share * 100)}%</strong> are real estate,
        development, land or construction interests. Technology — the sector Austin is famous for — is
        a rounding error by comparison.</P>
        <Figure title="Lobbying clients by industry" source="Registered-lobbyist client disclosures (business description, grouped)">
          <HBars rows={d.sectors.map((x) => ({ label: x.sector, value: x.clients }))} hot={(r) => r.label.startsWith('Real estate')} />
        </Figure>
        <P>It fits everything else the data shows: the council's rare disagreements are mostly over
        zoning, and the city's property is increasingly held by companies. The organized money that
        works City Hall is, above all, the development industry — and it's lobbying about land.</P>
      </Section>

      <Section kicker="The dollars" title="Modest fees, and almost no gifts">
        <P>Lobbying here isn't the seven-figure influence machine of Washington. Most engagements are
        small — the vast majority report <em>under $10,000</em> or no compensation at all; only
        {' '}{d.comp_bands.filter((b) => ['$50k–100k', '$100k–200k'].includes(b.band)).reduce((a, b) => a + b.n, 0)}
        {' '}of tens of thousands of filings reach $50,000 or more.</P>
        <Figure title="Reported lobbying compensation, by band" source="Client disclosures (compensation is a reported range, per filing)">
          <HBars rows={d.comp_bands.map((b) => ({ label: b.band, value: b.n }))} />
        </Figure>
        <PullStat value={money(d.official_spend.total)} accent="var(--positive)"
          label={`is the entire amount Austin's registered lobbyists report spending on officials — food and drink, gifts, entertainment and travel — across every filing on record. There is no lavish wining-and-dining culture in the disclosures.`} />
      </Section>

      <Section kicker="The big clients" title="Who pays the most">
        <P>The handful of clients in the top compensation bands ($50k+) are exactly who you'd expect:
        telecoms, the realtor and homebuilder trade groups, and a roster of developers.</P>
        <Figure title="Clients reporting $50,000+ in lobbying compensation" source="Client disclosures, top compensation bands">
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr>
              <th style={{ ...TD_L, borderTop: 'none', color: 'var(--fg-muted)', font: '600 11px/1 var(--font-sans)', letterSpacing: '.04em', textTransform: 'uppercase', padding: '0 0 10px' }}>Client</th>
              <th style={{ ...TD_R, borderTop: 'none', font: '600 11px/1 var(--font-sans)', letterSpacing: '.04em', textTransform: 'uppercase', padding: '0 0 10px' }}>Business</th>
            </tr></thead>
            <tbody>
              {bigClients.map((c, i) => (
                <tr key={i}><td style={TD_L}>{c.client}</td><td style={TD_R}>{c.business}</td></tr>
              ))}
            </tbody>
          </table>
        </Figure>
      </Section>

      <Section kicker="The takeaway" title="Organized influence, in plain sight">
        <P>Put it beside the rest of the money trail: campaign donations don't track city contracts,
        council votes are near-unanimous, and lobbyists barely spend on officials. What organized
        influence in Austin actually looks like isn't gifts or quiet payments — it's a development
        industry that registers, hires lobbyists, and works the land-use process out in the open.</P>
      </Section>

      <StoryFooter
        methodology={d.methodology}
        sources={[
          { name: 'raw_lobbyist_clients', detail: 'Lobbyist client disclosures — client name, business description, compensation band (124,933 filing rows across ~2,630 distinct clients).' },
          { name: 'raw_lobbyist_registrants / _master', detail: 'Registered lobbying firms and the individual lobbyists they employ.' },
          { name: 'raw_lobbyist_reports', detail: 'Per-filing reports of lobbyist spending on officials (food/beverage, gifts, entertainment, travel/lodging).' },
        ]}
        limits={[
          'Compensation is self-reported in broad bands (often "$0" or "less than $10,000"), so it cannot be summed into a precise total.',
          'Industry grouping is keyword-based on a free-text business description and approximate.',
          'Reported spending on officials covers only what these forms capture — not all lobbyist contact.',
          'Registration is not influence — this shows who is organized to lobby, not who prevails.',
          'A client recurs across filing periods, so filing-row counts exceed unique clients.',
        ]}
        updated="the latest lobbyist disclosure load"
      />
    </StoryLayout>
  )
}
