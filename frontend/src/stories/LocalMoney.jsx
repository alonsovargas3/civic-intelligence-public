import React, { useEffect, useState } from 'react'
import StoryLayout, { Section, P, PullStat, StatStrip, Figure, StoryFooter } from './StoryLayout.jsx'
import { getStoryLocalMoney } from '../api.js'

const money = (v) => {
  const n = Number(v)
  if (n >= 1e6) return `$${(n / 1e6).toFixed(1)}M`
  if (n >= 1e3) return `$${Math.round(n / 1e3)}k`
  return `$${Math.round(n).toLocaleString('en-US')}`
}
const pct = (x) => `${(Number(x) * 100).toFixed(1)}%`

/* 100%-stacked Texas vs out-of-state bar. */
function SplitBar({ row, label }) {
  const t = row.total || 1
  const segs = [
    { k: 'In Texas', v: row.texas, c: 'var(--blue-5)' },
    { k: 'Out of state', v: row.out_of_state, c: 'var(--flag)' },
    { k: 'Unknown', v: row.unknown, c: 'var(--surface-3)' },
  ]
  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 6 }}>
        <span style={{ font: '600 14px/1 var(--font-sans)', color: 'var(--ink)' }}>{label}</span>
        <span style={{ font: '600 13px var(--font-mono)', color: 'var(--flag)' }}>{pct(row.oos_share)} out of state</span>
      </div>
      <div style={{ display: 'flex', height: 22, borderRadius: 'var(--r-sm)', overflow: 'hidden', background: 'var(--surface-3)' }}>
        {segs.map((s) => s.v > 0 && (
          <div key={s.k} title={`${s.k}: ${money(s.v)}`} style={{ width: `${(s.v / t) * 100}%`, background: s.c }} />
        ))}
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 5 }}>
        <span className="cii-footnote">{money(row.texas)} in Texas</span>
        <span className="cii-footnote">{money(row.out_of_state)} out of state</span>
      </div>
    </div>
  )
}

const TH = { font: '600 11px/1 var(--font-sans)', letterSpacing: '.05em', textTransform: 'uppercase', color: 'var(--fg-muted)', textAlign: 'right', padding: '0 0 10px' }
const TD = { font: '500 13px/1.3 var(--font-mono)', fontVariantNumeric: 'tabular-nums', color: 'var(--ink)', textAlign: 'right', padding: '9px 0', borderTop: '1px solid var(--hairline)' }

export default function LocalMoney() {
  const [d, setD] = useState(null)
  const [err, setErr] = useState(null)
  useEffect(() => { getStoryLocalMoney().then(setD).catch(() => setErr('Could not load contribution data.')) }, [])

  if (err) return <StoryLayout title="Local races, local money"><P style={{ color: 'var(--flag)' }}>{err}</P></StoryLayout>
  if (!d) return <StoryLayout title="Local races, local money"><P style={{ color: 'var(--fg-muted)' }}>Loading contributions…</P></StoryLayout>

  const cand = d.candidate, comm = d.committee
  const factor = (comm.oos_share / cand.oos_share).toFixed(0)

  return (
    <StoryLayout
      eyebrow="Money · Elections"
      title="Local races, local money — except the ballot fights"
      dek="A common worry is that outside cash floods local politics. In Austin's candidate races it mostly doesn't — about 95% of the money is in-state. The ballot-measure committees are a different story."
      sources={['Austin campaign-finance contributions', 'Municipal filings (state filing excluded)', 'Donor location as filed']}
    >
      <StatStrip items={[
        { value: pct(cand.oos_share), label: 'Out-of-state — candidate races', sub: `of ${money(cand.total)} to council/mayor candidates` },
        { value: pct(comm.oos_share), label: 'Out-of-state — ballot committees', sub: `of ${money(comm.total)} to committees/PACs` },
        { value: `${factor}×`, label: 'More outside reliance', sub: 'committees vs candidates' },
      ]} />

      <Section>
        <P>Split Austin's campaign money into the two things it funds — people running for city office,
        and committees fighting over ballot measures — and the "outside money" question gets two very
        different answers.</P>
      </Section>

      <Section kicker="Candidate races" title="Funded close to home">
        <P>Money going to Austin council and mayoral candidates is overwhelmingly in-state: only
        <strong> {pct(cand.oos_share)}</strong> comes from outside Texas. The out-of-state share that
        does exist is small-dollar and scattered across the usual national donor cities.</P>
        <Figure title="Candidate contributions by donor location" source="Austin municipal candidate filings (state filing excluded)">
          <SplitBar row={cand} label="Council & mayoral candidates" />
        </Figure>
        <Figure title="Top out-of-state origins of candidate money" source="Donor city/state as filed; out-of-Texas only">
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr>
              <th style={{ ...TH, textAlign: 'left' }}>Donor city</th><th style={TH}>Gifts</th><th style={TH}>Total</th>
            </tr></thead>
            <tbody>
              {d.top_oos_origins.map((o) => (
                <tr key={o.place}>
                  <td style={{ ...TD, textAlign: 'left', fontFamily: 'var(--font-sans)', fontWeight: 600 }}>{o.place.replace(/,\s*$/, '')}</td>
                  <td style={TD}>{o.gifts.toLocaleString('en-US')}</td>
                  <td style={{ ...TD, fontWeight: 600 }}>{money(o.total)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Figure>
      </Section>

      <Section kicker="Ballot committees" title="A different map">
        <P>The committees that bankroll ballot-measure campaigns look nothing like the candidate races.
        <strong> {pct(comm.oos_share)}</strong> of their money — about {factor} times the candidate
        rate — comes from outside Texas, because national corporations and advocacy groups fund Austin
        ballot fights from afar. (See <em>Who funds Austin's ballot fights</em> for the company-by-company
        breakdown.)</P>
        <Figure title="Committee/PAC contributions by donor location" source="Austin municipal committee filings (state filing excluded)">
          <SplitBar row={comm} label="Ballot & issue committees" />
        </Figure>
      </Section>

      <StoryFooter
        methodology={d.methodology}
        sources={[
          { name: 'raw_campaign_contributions', detail: 'Austin campaign-finance contributions. Candidate vs committee split by recipient name; donor state read from the filed city/state/ZIP text.' },
        ]}
        limits={[
          'Donor state is inferred from a free-text field; missing/malformed entries read as "unknown".',
          'In-state is not the same as in-Austin — this separates Texas from out-of-state, not Austin from the rest of Texas.',
          'The clearly non-municipal state (Greg Abbott) filing is excluded; other non-municipal filers may remain.',
          'Candidate/committee split is a name heuristic.',
        ]}
        updated="the latest campaign-finance load"
      />
    </StoryLayout>
  )
}
