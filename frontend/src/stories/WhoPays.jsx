import React, { useEffect, useState } from 'react'
import StoryLayout, { Section, P, PullStat, StatStrip, Figure, StoryFooter } from './StoryLayout.jsx'
import { getStoryWhoPays } from '../api.js'

const fmt = (n) => Number(n).toLocaleString('en-US')
const money = (v) => {
  const n = Number(v)
  if (n >= 1e6) return `$${(n / 1e6).toFixed(1)}M`
  if (n >= 1e3) return `$${Math.round(n / 1e3)}k`
  return `$${Math.round(n)}`
}
const pct = (x) => `${(Number(x) * 100).toFixed(0)}%`

/* For each size bucket, share of GIFTS vs share of DOLLARS — the inversion. */
function GiftsVsDollars({ buckets, totalGifts, totalDollars }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div style={{ display: 'flex', gap: 16, font: '600 11px/1 var(--font-sans)', color: 'var(--fg-muted)', paddingLeft: 86 }}>
        <span style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 6 }}><i style={{ width: 10, height: 10, background: 'var(--blue-4)', borderRadius: 2, display: 'inline-block' }} />Share of gifts</span>
        <span style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 6 }}><i style={{ width: 10, height: 10, background: 'var(--primary-ink)', borderRadius: 2, display: 'inline-block' }} />Share of dollars</span>
      </div>
      {buckets.map((b) => {
        const g = b.gifts / totalGifts, dol = b.total / totalDollars
        return (
          <div key={b.bucket} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <span style={{ flex: '0 0 74px', font: '600 12.5px var(--font-mono)', color: 'var(--ink)', textAlign: 'right' }}>{b.bucket}</span>
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 4 }}>
              <Bar frac={g} color="var(--blue-4)" label={pct(g)} sub={`${fmt(b.gifts)} gifts`} />
              <Bar frac={dol} color="var(--primary-ink)" label={pct(dol)} sub={money(b.total)} />
            </div>
          </div>
        )
      })}
    </div>
  )
}
function Bar({ frac, color, label, sub }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <div style={{ flex: 1, height: 13, background: 'var(--surface-3)', borderRadius: 'var(--r-sm)', overflow: 'hidden' }}>
        <div style={{ width: `${Math.max(0.5, frac * 100)}%`, height: '100%', background: color, borderRadius: 'var(--r-sm)' }} />
      </div>
      <span style={{ flex: '0 0 116px', font: '500 11.5px var(--font-mono)', color: 'var(--fg-muted)' }}>
        <strong style={{ color: 'var(--ink)' }}>{label}</strong> · {sub}
      </span>
    </div>
  )
}

export default function WhoPays() {
  const [d, setD] = useState(null)
  const [err, setErr] = useState(null)
  useEffect(() => { getStoryWhoPays().then(setD).catch(() => setErr('Could not load contribution data.')) }, [])

  if (err) return <StoryLayout title="Who pays for Austin politics"><P style={{ color: 'var(--flag)' }}>{err}</P></StoryLayout>
  if (!d) return <StoryLayout title="Who pays for Austin politics"><P style={{ color: 'var(--fg-muted)' }}>Loading contributions…</P></StoryLayout>

  const big = d.buckets[d.buckets.length - 1]          // $25k+
  const small = d.buckets[0]                            // <$50
  const ind = d.by_type.find((t) => t.dtype === 'individual')
  const ent = d.by_type.find((t) => t.dtype === 'entity')

  return (
    <StoryLayout
      eyebrow="Money · Elections"
      title="Who pays for Austin politics: the few big checks vs the many small ones"
      dek={`Austin's filings hold about ${fmt(d.total_gifts)} contributions totaling ${money(d.total_dollars)}. Most are small. Most of the money isn't: the largest 1% of gifts supply ${pct(d.top1pct_share)} of every dollar.`}
      sources={['Austin campaign-finance contributions', 'Municipal filings (state filing excluded)', 'By gift size']}
    >
      <StatStrip items={[
        { value: pct(d.top1pct_share), label: 'Of all money from the top 1% of gifts', sub: `top 10% = ${pct(d.top10pct_share)}` },
        { value: `${fmt(big.gifts)}`, label: `Gifts of $25k+`, sub: `supplied ${money(big.total)}` },
        { value: `${fmt(small.gifts)}`, label: 'Gifts under $50', sub: `supplied just ${money(small.total)}` },
      ]} />

      <Section>
        <P>Campaign money can come from a broad base of small donors or a narrow set of large ones.
        In Austin it's strikingly lopsided. Sort every contribution by size and the smallest gifts are
        the most numerous by far — but they barely move the totals, while a few very large checks carry
        most of the money.</P>
        <Figure title="Share of gifts vs. share of dollars, by contribution size" source="Austin municipal campaign-finance contributions (state filing excluded)"
          note="Each size band shows how much of all gifts (light) and all dollars (dark) it represents — the two invert as size rises.">
          <GiftsVsDollars buckets={d.buckets} totalGifts={d.total_gifts} totalDollars={d.total_dollars} />
        </Figure>
      </Section>

      <Section kicker="The concentration" title="The top 1% of gifts is most of the money">
        <PullStat value={pct(d.top1pct_share)} accent="var(--primary-deep)"
          label={`of all campaign dollars come from the largest 1% of contributions. The top 10% of gifts account for ${pct(d.top10pct_share)}. A broad base of small donors exists — it just isn't where the money is.`} />
      </Section>

      {ind && ent && (
        <Section kicker="Two kinds of donor" title="3,400 institutional checks rival 236,000 personal ones">
          <P>The same lopsidedness shows up by donor type. Individuals gave through about
          {' '}<strong>{fmt(ind.gifts)}</strong> contributions totaling {money(ind.total)}. Entities —
          companies, PACs, unions — needed only about <strong>{fmt(ent.gifts)}</strong> contributions to
          reach {money(ent.total)}, nearly the same sum from {Math.round(ind.gifts / ent.gifts)}× fewer
          gifts.</P>
          <Figure title="Contributions and dollars by donor type" source="Austin municipal filings, donor type as filed (state filing excluded)">
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead><tr>
                <th style={{ font: '600 11px/1 var(--font-sans)', letterSpacing: '.05em', textTransform: 'uppercase', color: 'var(--fg-muted)', textAlign: 'left', padding: '0 0 10px' }}>Donor type</th>
                <th style={{ font: '600 11px/1 var(--font-sans)', letterSpacing: '.05em', textTransform: 'uppercase', color: 'var(--fg-muted)', textAlign: 'right', padding: '0 0 10px' }}>Gifts</th>
                <th style={{ font: '600 11px/1 var(--font-sans)', letterSpacing: '.05em', textTransform: 'uppercase', color: 'var(--fg-muted)', textAlign: 'right', padding: '0 0 10px' }}>Total</th>
                <th style={{ font: '600 11px/1 var(--font-sans)', letterSpacing: '.05em', textTransform: 'uppercase', color: 'var(--fg-muted)', textAlign: 'right', padding: '0 0 10px' }}>Avg gift</th>
              </tr></thead>
              <tbody>
                {[ind, ent].map((t) => (
                  <tr key={t.dtype}>
                    <td style={{ font: '600 13.5px/1.2 var(--font-sans)', color: 'var(--ink)', textAlign: 'left', padding: '10px 0', borderTop: '1px solid var(--hairline)', textTransform: 'capitalize' }}>{t.dtype}</td>
                    <td style={{ font: '500 13.5px var(--font-mono)', fontVariantNumeric: 'tabular-nums', textAlign: 'right', padding: '10px 0', borderTop: '1px solid var(--hairline)' }}>{fmt(t.gifts)}</td>
                    <td style={{ font: '600 13.5px var(--font-mono)', fontVariantNumeric: 'tabular-nums', textAlign: 'right', padding: '10px 0', borderTop: '1px solid var(--hairline)' }}>{money(t.total)}</td>
                    <td style={{ font: '500 13.5px var(--font-mono)', fontVariantNumeric: 'tabular-nums', color: 'var(--fg-muted)', textAlign: 'right', padding: '10px 0', borderTop: '1px solid var(--hairline)' }}>{money(t.total / t.gifts)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Figure>
        </Section>
      )}

      <StoryFooter
        methodology={d.methodology}
        sources={[
          { name: 'raw_campaign_contributions', detail: 'Austin campaign-finance contributions, grouped by dollar size and ranked to measure the share of money from the largest gifts. Candidate and committee money combined.' },
        ]}
        limits={[
          'Counts contributions, not unique donors — one donor giving repeatedly is counted each time, so giver-level concentration may differ.',
          'Combines candidate and committee money; committee filings include the large corporate checks.',
          'Donor type (individual vs entity) is self-reported on the filing; casing variants are merged.',
          'The clearly non-municipal state (Greg Abbott) filing is excluded.',
        ]}
        updated="the latest campaign-finance load"
      />
    </StoryLayout>
  )
}
