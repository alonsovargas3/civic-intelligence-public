import React, { useEffect, useState } from 'react'
import StoryLayout, { Section, P, PullStat, StatStrip, Figure, StoryFooter } from './StoryLayout.jsx'
import { getStoryCouncilDissent } from '../api.js'

const fmt = (n) => Number(n).toLocaleString('en-US')

function HBars({ rows, hot }) {
  const max = Math.max(...rows.map((r) => r.value))
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {rows.map((r) => {
        const isHot = hot && hot(r)
        return (
          <div key={r.label} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ flex: '0 0 178px', font: '500 13px/1.25 var(--font-sans)', color: 'var(--ink)' }}>{r.label}{r.sub && <span className="cii-footnote"> {r.sub}</span>}</span>
            <div style={{ flex: 1, height: 14, background: 'var(--surface-3)', borderRadius: 'var(--r-sm)', overflow: 'hidden' }}>
              <div style={{ width: `${Math.max(2, (r.value / max) * 100)}%`, height: '100%', background: isHot ? 'var(--flag)' : 'var(--blue-5)', borderRadius: 'var(--r-sm)' }} />
            </div>
            <span style={{ flex: '0 0 44px', textAlign: 'right', font: `${isHot ? 700 : 500} 13px var(--font-mono)`, color: isHot ? 'var(--flag)' : 'var(--ink)', fontVariantNumeric: 'tabular-nums' }}>{fmt(r.value)}</span>
          </div>
        )
      })}
    </div>
  )
}

const TH = { font: '600 11px/1 var(--font-sans)', letterSpacing: '.04em', textTransform: 'uppercase', color: 'var(--fg-muted)', textAlign: 'right', padding: '0 0 10px' }
const TD = { font: '500 13px/1.3 var(--font-mono)', fontVariantNumeric: 'tabular-nums', color: 'var(--ink)', textAlign: 'right', padding: '9px 0', borderTop: '1px solid var(--hairline)' }

export default function CouncilDissent() {
  const [d, setD] = useState(null)
  const [err, setErr] = useState(null)
  useEffect(() => { getStoryCouncilDissent().then(setD).catch(() => setErr('Could not load voting data.')) }, [])

  if (err) return <StoryLayout title="What Austin City Council fights about"><P style={{ color: 'var(--flag)' }}>{err}</P></StoryLayout>
  if (!d) return <StoryLayout title="What Austin City Council fights about"><P style={{ color: 'var(--fg-muted)' }}>Loading votes…</P></StoryLayout>

  const s = d.summary
  const pctUnanimous = s.pct_agree != null ? s.pct_agree : (100 - s.pct_contested).toFixed(0)
  const top = d.dissent_by_member[0]
  const topCo = d.coalitions[0]

  return (
    <StoryLayout
      eyebrow="Governance · Council"
      title="What Austin City Council actually fights about"
      dek="The council agrees on almost everything. The slim minority of items it splits on — zoning, contracts, a handful of ordinances — is where the real politics lives. Ranked by No-rate per 100 votes cast, so tenure doesn't distort who looks like the opposition."
      sources={['Council Voting Record (per-member roll call)', '2023–present', `${fmt(s.items)} agenda items`]}
    >
      <StatStrip items={[
        { value: `${pctUnanimous}%`, label: 'Of everything the council votes on', sub: `only ${fmt(s.contested)} of ${fmt(s.items)} drew a No` },
        { value: `${top.no_rate_per_100}%`, label: `No-rate — ${top.member}`, sub: `${top.current ? 'currently serving' : `through ${top.last_vote_label}`} · D${top.district}` },
        { value: fmt(s.total_no), label: 'Total "No" votes', sub: 'across 3+ years' },
      ]} />

      <Section kicker="The norm" title="Consensus is the rule">
        <P>Scroll the roll call and the same word repeats: <em>Yes</em>. Of {fmt(s.items)} agenda items
        since 2023, just <strong>{fmt(s.contested)}</strong> — about <strong>{s.pct_contested}%</strong>
        {' '}— drew even a single No vote. Austin's council governs overwhelmingly by consensus; the
        disagreements are the exception, which is exactly what makes them worth finding.</P>
      </Section>

      <Section kicker="The opposition" title="Who dissents, per vote cast">
        <P>Ranking by No-votes <em>per 100 votes cast</em> — so a member who served two years isn't
        compared against one who served four — dissent is still concentrated: <strong>{top.member}</strong>
        {' '}(D{top.district}) said No on <strong>{top.no_rate_per_100}%</strong> of votes cast
        {top.current ? '' : `, through ${top.last_vote_label} before leaving office`} — but that's the
        ceiling, not the norm. Members with fewer than 100 recorded votes are excluded so short
        tenures don't produce noisy rates.</P>
        <Figure title="No-votes per 100 votes cast (min 100 votes)" source="Austin Council Voting Record">
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {d.dissent_by_member.map((r) => (
              <div key={r.member} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <span style={{ flex: '0 0 220px', font: '500 13px/1.25 var(--font-sans)', color: 'var(--ink)' }}>
                  {r.member} <span style={{ color: 'var(--fg-subtle)' }}>
                    D{r.district}{r.current ? '' : ` · through ${r.last_vote_label}`}</span>
                </span>
                <div style={{ flex: 1, height: 14, background: 'var(--surface-3)', borderRadius: 'var(--r-sm)', overflow: 'hidden' }}>
                  <div style={{ width: `${Math.max(2, (r.no_rate_per_100 / d.dissent_by_member[0].no_rate_per_100) * 100)}%`, height: '100%', background: r.current ? 'var(--blue-7)' : 'var(--blue-4)' }} />
                </div>
                <span style={{ flex: '0 0 56px', textAlign: 'right', font: '600 13px var(--font-mono)' }}>{r.no_rate_per_100}%</span>
              </div>
            ))}
          </div>
        </Figure>
      </Section>

      <Section kicker="The flashpoints" title="What they split on">
        <P>When the council does divide, it's mostly over land. Zoning and rezoning cases draw more
        dissent than almost anything else, alongside specific contracts and ordinances — the
        site-by-site fights over how Austin grows.</P>
        <Figure title='"No" votes by item type' source="Council Voting Record, item descriptions classified by keyword">
          <HBars rows={d.topics.map((t) => ({ label: t.topic, value: t.no_votes }))}
            hot={(r) => r.label.startsWith('Zoning')} />
        </Figure>
      </Section>

      <Section kicker="The blocs that aren't" title="No stable opposition coalition">
        <P>You might expect the dissenters to vote as a bloc. They mostly don't. The pair that most
        often votes No <em>together</em> — {topCo.member_a} and {topCo.member_b} — did so only
        {' '}<strong>{topCo.co_dissents}</strong> times. Beyond that, co-dissent is rare and shifts by
        issue: a different handful objects to a zoning case than to a contract. The council isn't
        two camps; it's a broad consensus with occasional, individual objections.</P>
        <Figure title="Members who most often vote No on the same item" source="Council Voting Record, co-dissent pairs">
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr>
              <th style={{ ...TH, textAlign: 'left' }}>Member pair</th><th style={TH}>Shared "No" votes</th>
            </tr></thead>
            <tbody>
              {d.coalitions.map((c) => (
                <tr key={c.member_a + c.member_b}>
                  <td style={{ ...TD, textAlign: 'left', fontFamily: 'var(--font-sans)', fontWeight: 600 }}>{c.member_a} &amp; {c.member_b}</td>
                  <td style={TD}>{c.co_dissents}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Figure>
        <P className="cii-footnote" style={{ color: 'var(--fg-subtle)', fontSize: 13 }}>
          (This is a <em>real-vote</em> measure of voting blocs — distinct from the co-sponsorship
          coalitions on the Council dashboard panel, which reflect collaboration on legislation, not
          how members actually voted.)</P>
      </Section>

      <StoryFooter
        methodology={d.methodology}
        sources={[
          { name: 'raw_council_votes', detail: 'City of Austin Council Voting Record (Socrata 3c89-i35a) — per-member roll-call votes, 2023–present. The votes Austin’s Legistar API does not expose.' },
        ]}
        limits={[
          'Votes cover 2023–present only; council membership changed over the window, so members present for fewer meetings have fewer chances to dissent.',
          '"No" is explicit dissent — abstentions, recusals and absences are counted separately and not shown here.',
          'Ranking is by No-rate per 100 recorded Yes/No votes, minimum 100 votes cast; abstentions, recusals and absences are excluded from the denominator.',
          'Item-type classification is keyword-based on the item description and approximate.',
          'Descriptive — it shows where disagreement is recorded, not why a member objected.',
        ]}
        updated="the latest Council Voting Record load"
      />
    </StoryLayout>
  )
}
