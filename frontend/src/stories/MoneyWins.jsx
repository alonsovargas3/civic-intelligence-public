import React, { useEffect, useState } from 'react'
import StoryLayout, { Section, P, StatStrip, Figure, StoryFooter } from './StoryLayout.jsx'
import { getStoryMoneyWins } from '../api.js'

const money = (v) => (Math.abs(v) >= 1e6 ? `$${(v / 1e6).toFixed(1)}M` : `$${Math.round(v / 1e3)}k`)
const fmt = (n) => Number(n).toLocaleString('en-US')

export default function MoneyWins() {
  const [d, setD] = useState(null)
  const [err, setErr] = useState(null)
  useEffect(() => { getStoryMoneyWins().then((r) => (r.error ? setErr(r.error) : setD(r))).catch(() => setErr('Could not load money-wins data.')) }, [])

  if (err) return <StoryLayout title="Does money win Austin elections?"><P style={{ color: 'var(--flag)' }}>{err}</P></StoryLayout>
  if (!d) return <StoryLayout title="Does money win Austin elections?"><P style={{ color: 'var(--fg-muted)' }}>Loading…</P></StoryLayout>

  return (
    <StoryLayout
      eyebrow="Money · Elections"
      title="Does money win Austin elections?"
      dek={`The better-funded side won just ${d.won} of Austin's last ${d.scored} contested ballot fights — Uber's $2.2M and a $6.1M police-staffing campaign both lost.`}
      sources={[`${d.scored} ballot fights, 2016–2023`, 'Committee money from municipal filings', 'Sides hand-attributed, sourced per row']}
    >
      <StatStrip items={[
        { value: `${d.won} of ${d.scored}`, label: 'Fights won by the better-funded side', sub: 'a coin flip, not a purchase' },
        { value: money(d.fights.reduce((a, f) => a + f.money_for + f.money_against, 0)), label: 'Committee money across these fights', sub: '24-month windows before each election' },
        { value: String(d.losses.length), label: 'Big-money losses', sub: 'incl. Uber 2016, police staffing 2021' },
      ]} />

      <Section kicker="Fight by fight" title="The war chest is not the verdict">
        <Figure title="Money on each side vs the outcome" source="Campaign-finance filings · official canvasses">
          <table style={{ width: '100%', borderCollapse: 'collapse', font: '13px var(--font-sans)' }}>
            <thead>
              <tr style={{ textAlign: 'left', color: 'var(--fg-muted)' }}>
                <th style={{ padding: '6px 8px' }}>Election</th><th>Measure</th>
                <th style={{ textAlign: 'right' }}>$ for</th><th style={{ textAlign: 'right' }}>$ against</th>
                <th style={{ textAlign: 'right' }}>Votes for–against</th><th>Outcome</th><th>Money won?</th>
              </tr>
            </thead>
            <tbody>
              {d.fights.map((f) => (
                <tr key={`${f.election_date}-${f.measure}`} style={{ borderTop: '1px solid var(--surface-3)' }}>
                  <td style={{ padding: '6px 8px', whiteSpace: 'nowrap', fontFamily: 'var(--font-mono)' }}>{f.election_date}</td>
                  <td>{f.measure}</td>
                  <td style={{ textAlign: 'right', fontFamily: 'var(--font-mono)' }}>{money(f.money_for)}</td>
                  <td style={{ textAlign: 'right', fontFamily: 'var(--font-mono)' }}>{money(f.money_against)}</td>
                  <td style={{ textAlign: 'right', fontFamily: 'var(--font-mono)' }}>{fmt(f.votes_for)}–{fmt(f.votes_against)}</td>
                  <td>{f.outcome}</td>
                  <td style={{ fontWeight: 600, color: f.money_won ? 'var(--fg-muted)' : 'var(--flag)' }}>{f.money_won == null ? 'n/a' : f.money_won ? 'yes' : 'NO'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Figure>
      </Section>

      <Section kicker="The losses" title="When the big war chest lost">
        <P>{d.losses.join('; ')}. The funding side of these fights is broken down company-by-company
        in <a href="/stories/ballot-money">Who funds Austin's ballot fights</a>.</P>
      </Section>

      <StoryFooter
        methodology={d.methodology}
        sources={[
          { name: 'ref_ballot_measures', detail: 'Hand-curated crosswalk (data/ballot_crosswalk.csv) — one official source URL per row.' },
          { name: 'mv_campaign_contributions', detail: 'Austin campaign-finance filings, municipal filers.' },
        ]}
        limits={d.caveat.split('. ').map((s) => s.replace(/\.$/, '') + '.')}
        updated="the latest crosswalk load"
      />
    </StoryLayout>
  )
}
