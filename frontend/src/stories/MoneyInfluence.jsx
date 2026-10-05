import React, { useEffect, useState } from 'react'
import StoryLayout, { Section, P, PullStat, StatStrip, Figure, StoryFooter } from './StoryLayout.jsx'
import { getStoryMoneyInfluence } from '../api.js'
import { Badge } from '../Primitives.jsx'

const fmt = (n) => Number(n).toLocaleString('en-US')
const money = (v) => {
  const n = Number(v)
  if (Math.abs(n) >= 1e9) return `$${(n / 1e9).toFixed(2)}B`
  if (Math.abs(n) >= 1e6) return `$${(n / 1e6).toFixed(0)}M`
  if (Math.abs(n) >= 1e3) return `$${Math.round(n / 1e3)}k`
  return `$${Math.round(n).toLocaleString('en-US')}`
}

const TH = { font: '600 11px/1 var(--font-sans)', letterSpacing: '.05em', textTransform: 'uppercase', color: 'var(--fg-muted)', textAlign: 'right', padding: '0 0 10px' }
const TD = { font: '500 13px/1.3 var(--font-mono)', fontVariantNumeric: 'tabular-nums', color: 'var(--ink)', textAlign: 'right', padding: '9px 0', borderTop: '1px solid var(--hairline)' }
const TD_L = { ...TD, textAlign: 'left', font: '600 13px/1.25 var(--font-sans)' }

/* A single bar dominated by "Yes" — the near-unanimity, made visual. */
function UnanimityBar({ yes, no, other }) {
  const total = yes + no + other
  const seg = (v, c, label) => v > 0 && (
    <div title={`${label}: ${fmt(v)}`} style={{ width: `${(v / total) * 100}%`, background: c }} />
  )
  return (
    <div>
      <div style={{ display: 'flex', height: 26, borderRadius: 'var(--r-sm)', overflow: 'hidden', background: 'var(--surface-3)' }}>
        {seg(yes, 'var(--blue-5)', 'Yes')}
        {seg(no, 'var(--flag)', 'No')}
        {seg(other, 'var(--fg-subtle)', 'Abstain/Recused')}
      </div>
      <div style={{ display: 'flex', gap: 18, marginTop: 8 }}>
        <span className="cii-footnote"><b style={{ color: 'var(--blue-6)' }}>■</b> {fmt(yes)} Yes</span>
        <span className="cii-footnote"><b style={{ color: 'var(--flag)' }}>■</b> {fmt(no)} No</span>
        <span className="cii-footnote"><b style={{ color: 'var(--fg-subtle)' }}>■</b> {fmt(other)} Abstain / Recused</span>
      </div>
    </div>
  )
}

export default function MoneyInfluence() {
  const [d, setD] = useState(null)
  const [err, setErr] = useState(null)
  useEffect(() => { getStoryMoneyInfluence().then(setD).catch(() => setErr('Could not load the analysis.')) }, [])

  if (err) return <StoryLayout title="Does money buy influence at City Hall?"><P style={{ color: 'var(--flag)' }}>{err}</P></StoryLayout>
  if (!d) return <StoryLayout title="Does money buy influence at City Hall?"><P style={{ color: 'var(--fg-muted)' }}>Loading the analysis…</P></StoryLayout>

  const v = d.votes, o = d.overlap
  const cv = Object.fromEntries(d.contract_votes.map((r) => [r.vote, r.n]))
  const yes = cv.Yes || 0, no = cv.No || 0, other = (cv.Abstain || 0) + (cv.Recused || 0)
  const castTotal = yes + no + other
  const donShare = o.donated_total / o.contract_total
  const totalRecusals = d.recusals.reduce((a, b) => a + b.n, 0)

  return (
    <StoryLayout
      eyebrow="Money · Influence"
      title="Does campaign money buy influence at City Hall? We can finally check."
      dek="We long treated this as unprovable — Austin's legislative API hides council votes. But the votes were published elsewhere all along. With them, plus award-level contracts, the whole chain is traceable: contribution → council member → their vote → the contract. Here's what it shows."
      sources={['Council Voting Record (2023–present)', 'City Contracts', 'Campaign contributions']}
    >
      <StatStrip items={[
        { value: fmt(v.all_votes), label: 'Per-member votes now traceable', sub: `${v.min_yr}–${v.max_yr}, ${v.voters} members` },
        { value: `${v.pct_yes}%`, label: 'Of all council votes are "Yes"', sub: `just ${fmt(v.no_votes)} "No" votes in 3+ years` },
        { value: money(o.donated_total), label: 'Donated by contract-holding firms', sub: `against ${money(o.contract_total)} in contracts` },
      ]} />

      <Section kicker="The missing link, found" title="The votes were public all along">
        <P>Throughout this project we said the money→influence question was out of reach: Austin's
        Legistar API exposes no per-member votes. It turns out the city publishes the roll call as a
        separate open dataset — <strong>{fmt(v.all_votes)} individual member-votes</strong> since
        {' '}{v.min_yr}. Paired with the city's award-level contracts file, we can finally follow the
        whole chain instead of guessing at it.</P>
      </Section>

      <Section kicker="The decision point" title="The council vote is a near-unanimous rubber stamp">
        <P>Here's the first thing the votes reveal: the council almost never says no. Across every
        recorded contract authorization since {v.min_yr}, of {fmt(castTotal)} position votes,
        {' '}<strong>{fmt(yes)} were Yes and just {fmt(no)} were No</strong>. There is essentially no
        dissent at the dais for a donation to "buy" — the variance simply isn't there.</P>
        <Figure title="Votes on contract authorizations since 2023" source="City of Austin Council Voting Record, 'authorize negotiation and execution' items">
          <UnanimityBar yes={yes} no={no} other={other} />
        </Figure>
      </Section>

      <Section kicker="The overlap" title="Tiny dollars — and the timing runs backwards">
        <P>Of the {fmt(d.contracts_total.n)} contracts in the city's file ({money(d.contracts_total.amt)}
        {' '}in value), <strong>{o.firms}</strong> went to firms that are also campaign donors. Those
        firms hold <strong>{money(o.contract_total)}</strong> in contracts while having donated
        {' '}<strong>{money(o.donated_total)}</strong> — about <strong>{(donShare * 100).toFixed(2)}%</strong>
        {' '}of their contract value.</P>
        <PullStat value={`${o.gift_after} of ${o.firms}`} accent="var(--positive)"
          label="of these firms made their first campaign contribution in or after the year their contract was awarded — you can't buy a contract you've already won. Only a handful gave beforehand." />
        <Figure title="Firms that both hold city contracts and donate" source="raw_city_contracts × raw_campaign_contributions (name-matched)"
          note="Donations are a fraction of a percent of contract value; most postdate the award.">
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr>
              <th style={{ ...TH, textAlign: 'left' }}>Firm</th><th style={TH}>City contracts</th><th style={TH}>Donated</th>
            </tr></thead>
            <tbody>
              {d.matched_firms.map((f) => (
                <tr key={f.vendor}>
                  <td style={TD_L}>{f.vendor}</td>
                  <td style={{ ...TD, fontWeight: 600 }}>{money(f.contract_amt)}</td>
                  <td style={TD}>{money(f.donated)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Figure>
      </Section>

      <Section kicker="The safeguard" title="When members have a conflict, they step out">
        <P>The votes also show the conflict mechanism working: <strong>{totalRecusals} recusals</strong>
        {' '}across {d.recusals.length} members, where a member formally steps out of a vote rather than
        cast it.</P>
        <Figure title="Recusals by council member, 2023–present" source="City of Austin Council Voting Record (vote_cast = Recused)">
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr><th style={{ ...TH, textAlign: 'left' }}>Member</th><th style={TH}>Recusals</th></tr></thead>
            <tbody>
              {d.recusals.map((r) => (
                <tr key={r.member}><td style={TD_L}>{r.member}</td><td style={TD}>{r.n}</td></tr>
              ))}
            </tbody>
          </table>
        </Figure>
      </Section>

      <Section kicker="The honest conclusion" title="No pay-to-play at the points we can see">
        <P>With the full chain finally visible, the picture is consistent: the donor–contractor overlap
        is small, the dollars are trivial next to the contracts, most donations come <em>after</em> the
        award, and the council vote itself is a near-unanimous formality with a working recusal
        safeguard. There is no detectable pay-to-play pattern at any decision point the public data
        exposes.</P>
        <P>That doesn't mean influence is impossible — only that, if it operates, it does so
        <em> upstream</em> of the vote, in procurement scoring and agenda-setting that no open dataset
        records. We report the result we can actually support: at City Hall's visible decision points,
        the money-buys-the-vote story isn't there.</P>
        <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
          <Badge tone="ok">No pay-to-play detected</Badge>
          <Badge tone="muted">Votes near-unanimous — low statistical power</Badge>
          <Badge tone="muted">Upstream procurement not in the data</Badge>
        </div>
      </Section>

      <StoryFooter
        methodology={d.methodology}
        sources={[
          { name: 'raw_council_votes', detail: 'City of Austin Council Voting Record (Socrata 3c89-i35a) — per-member roll-call votes, 2023–present. The votes Austin’s Legistar API does not expose.' },
          { name: 'raw_city_contracts', detail: 'City of Austin Contracts (Socrata 84ih-p28j) — vendor, amount, board award date (century-digit quirk corrected on read).' },
          { name: 'raw_campaign_contributions', detail: 'Austin campaign-finance contributions; entity donors name-matched to contract vendors.' },
        ]}
        limits={[
          'A screening analysis, not proof of anything — and a near-null result has limited power: when ~99% of votes are Yes, a vote can’t reveal favoritism.',
          'Votes only go back to 2023, so the donation↔vote overlap is recent.',
          'The Contracts dataset is a bounded ~625-contract file, not every award in city history.',
          'Firms are matched by normalized name (no entity resolution); a parent and subsidiary may split.',
          'Vote items are not reliably linkable to a specific private vendor (many "authorize" items are agreements with other governments), so the vote analysis is at the aggregate unanimity level.',
          'Upstream procurement scoring and agenda-setting — where influence would more plausibly operate — are not in any public dataset.',
          'Observational; no causal claim.',
        ]}
        updated="the latest votes + contracts load"
      />
    </StoryLayout>
  )
}
