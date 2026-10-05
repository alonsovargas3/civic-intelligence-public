import React, { useEffect, useState } from 'react'
import StoryLayout, { Section, P, PullStat, StatStrip, Figure, StoryFooter } from './StoryLayout.jsx'
import { getStoryBallotMoney } from '../api.js'

const fmt = (n) => Number(n).toLocaleString('en-US')
const money = (v) => {
  const n = Number(v)
  if (n >= 1e6) return `$${(n / 1e6).toFixed(2)}M`
  if (n >= 1e3) return `$${Math.round(n / 1e3)}k`
  return `$${fmt(Math.round(n))}`
}

const TH = { font: '600 11px/1 var(--font-sans)', letterSpacing: '.05em', textTransform: 'uppercase', color: 'var(--fg-muted)', textAlign: 'right', padding: '0 0 10px' }
const TD = { font: '500 13px/1.3 var(--font-mono)', fontVariantNumeric: 'tabular-nums', color: 'var(--ink)', textAlign: 'right', padding: '9px 0', borderTop: '1px solid var(--hairline)' }
const TD_L = { ...TD, textAlign: 'left', font: '600 13px/1.25 var(--font-sans)' }

/* One bar per committee: how much of its money came from its single largest donor.
   ≥50% (a dominant single funder) is flagged. */
function ConcentrationBars({ rows }) {
  const sorted = [...rows].sort((a, b) => b.top_donor_pct - a.top_donor_pct)
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 13 }}>
      {sorted.map((r) => {
        const hot = r.top_donor_pct >= 50
        return (
          <div key={r.committee}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 12, marginBottom: 5 }}>
              <span style={{ font: '600 13px/1.25 var(--font-sans)', color: 'var(--ink)' }}>{r.committee}</span>
              <span className="cii-footnote" style={{ flex: '0 0 auto' }}>{money(r.total)} · {fmt(r.gifts)} gifts</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <div style={{ flex: 1, height: 16, background: 'var(--surface-3)', borderRadius: 'var(--r-sm)', overflow: 'hidden' }}>
                <div style={{ width: `${Math.max(1, r.top_donor_pct)}%`, height: '100%', background: hot ? 'var(--flag)' : 'var(--blue-5)', borderRadius: 'var(--r-sm)', transition: 'width 500ms var(--ease)' }} />
              </div>
              <span style={{ flex: '0 0 210px', font: '500 12px/1.3 var(--font-sans)', color: 'var(--fg-muted)' }}>
                <strong style={{ color: hot ? 'var(--flag)' : 'var(--ink)', fontVariantNumeric: 'tabular-nums' }}>{Math.round(r.top_donor_pct)}%</strong> from {r.top_donor}
              </span>
            </div>
          </div>
        )
      })}
    </div>
  )
}

export default function BallotMoney() {
  const [d, setD] = useState(null)
  const [err, setErr] = useState(null)
  useEffect(() => { getStoryBallotMoney().then(setD).catch(() => setErr('Could not load campaign-finance data.')) }, [])

  if (err) return <StoryLayout title="Who funds Austin's ballot fights"><P style={{ color: 'var(--flag)' }}>{err}</P></StoryLayout>
  if (!d) return <StoryLayout title="Who funds Austin's ballot fights"><P style={{ color: 'var(--fg-muted)' }}>Loading campaign finance…</P></StoryLayout>

  const s = d.summary
  const rideshare = d.committees.find((c) => /ridesharing/i.test(c.committee))
  const grassroots = [...d.committees].sort((a, b) => a.top_donor_pct - b.top_donor_pct)[0]
  const ratio = (s.committee_total_m / s.candidate_total_m).toFixed(1)

  return (
    <StoryLayout
      eyebrow="Money · Elections"
      title="Who funds Austin's ballot fights"
      dek="When Austin votes on a proposition — rideshare rules, park bonds, policing — the campaigns aren't bankrolled like candidate races. The committees behind them raise more money overall, and a single company or group often funds a measure almost by itself."
      sources={['Austin campaign-finance contributions', '~2014–2026', 'Committee / PAC filings']}
    >
      <StatStrip items={[
        { value: `$${s.committee_total_m.toFixed(0)}M`, label: 'Raised by committees & PACs', sub: `vs $${s.candidate_total_m.toFixed(0)}M by candidates` },
        { value: rideshare ? `${Math.round(rideshare.top_donor_pct)}%` : '—', label: 'Of one campaign from one company', sub: rideshare ? `${rideshare.top_donor} → ${rideshare.committee}` : '' },
        { value: `${ratio}×`, label: 'Committee vs candidate money', sub: 'committees out-raise candidates' },
      ]} />

      <Section>
        <P>Campaign-finance filings aren't just about candidates. Alongside the people running for
        council and mayor, Austin's ledger tracks the committees and political action committees that
        raise money to win — or kill — ballot propositions and to push issues. Add it up and these
        committees have raised <strong>${s.committee_total_m.toFixed(0)} million</strong>, roughly
        {' '}{ratio}× what all the candidates combined have raised (${s.candidate_total_m.toFixed(0)}
        {' '}million). Whether the money worked is its own question — see{' '}
        <a href="/stories/money-wins">Does money win Austin elections?</a>.</P>
      </Section>

      <Section kicker="The finding" title="One donor, one campaign">
        <P>Candidate money tends to come from many donors. Ballot-campaign money often doesn't: trace
        each committee back to its single largest donor and, for several of the biggest, that one
        donor supplied most — sometimes essentially all — of the money.</P>
        {rideshare && (
          <PullStat value={`${Math.round(rideshare.top_donor_pct)}%`} accent="var(--flag)"
            label={`of the ${money(rideshare.total)} raised by the "${rideshare.committee}" campaign came from a single company — ${rideshare.top_donor}.`} />
        )}
        <Figure title="Share of each committee's money from its single largest donor"
          source="Austin campaign-finance contributions, committees raising ≥ ~$1M (Greg Abbott state filing excluded)"
          note="Red bars mark committees where one donor supplied at least half the money. Grassroots committees (many small gifts) sit near the bottom.">
          <ConcentrationBars rows={d.committees} />
        </Figure>
        {grassroots && (
          <P>The contrast at the other end is just as sharp: <strong>{grassroots.committee}</strong>
          {' '}raised {money(grassroots.total)} across {fmt(grassroots.gifts)} contributions, its
          largest single donor just {Math.round(grassroots.top_donor_pct)}% of the total — a genuinely
          broad base rather than one writer of big checks.</P>
        )}
      </Section>

      <Section kicker="The big checks" title="The largest single contributions">
        <P>The individual gifts behind these campaigns dwarf anything in a candidate race, where
        Austin caps direct contributions. Committees face no such cap — so a single corporate check
        can run to seven figures.</P>
        <Figure title="Largest single contributions to Austin committees & PACs" source="Austin campaign-finance contributions (excl. state filings)">
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr>
              <th style={{ ...TH, textAlign: 'left' }}>Donor</th>
              <th style={{ ...TH, textAlign: 'left' }}>To committee</th>
              <th style={TH}>Amount</th><th style={TH}>Date</th>
            </tr></thead>
            <tbody>
              {d.mega_gifts.map((m, i) => (
                <tr key={i}>
                  <td style={TD_L}>{m.donor}</td>
                  <td style={{ ...TD_L, fontWeight: 500, color: 'var(--fg-muted)' }}>{m.committee}</td>
                  <td style={{ ...TD, fontWeight: 600 }}>{money(m.amount)}</td>
                  <td style={{ ...TD, color: 'var(--fg-muted)' }}>{m.date}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Figure>
      </Section>

      <StoryFooter
        methodology={d.methodology}
        sources={[
          { name: 'raw_campaign_contributions', detail: 'Austin campaign-finance contribution filings (donor → recipient, amount, date, type). Recipients split into candidate vs committee/PAC by name pattern.' },
        ]}
        limits={[
          d.caveat,
          'This shows WHO FUNDS each committee — not which side of a ballot measure it took, whether the measure passed, or that any donor received anything in return.',
          'Top-donor concentration uses the donor name exactly as filed (no entity resolution), so a parent company and a subsidiary could be counted separately.',
          'Contribution caps differ: candidate contributions are capped by city rule; committee/PAC contributions are not — part of why committee checks are larger.',
          'Donor employer/occupation and address are self-reported on the filing.',
        ]}
        updated="the latest campaign-finance filing load"
      />
    </StoryLayout>
  )
}
