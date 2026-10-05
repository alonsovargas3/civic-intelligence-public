import React, { useEffect, useState } from 'react'
import StoryLayout, { Section, P, PullStat, StatStrip, Figure, StoryFooter } from './StoryLayout.jsx'
import { getStoryServiceEquity } from '../api.js'
import { Badge } from '../Primitives.jsx'

const d1 = (n) => Number(n).toFixed(1)

/* Each district's disparity ratio plotted around a 1.0 center line, with the 1.5×
   flag threshold marked. Short bars = treated about as fast as its mix predicts. */
function DisparityChart({ districts, threshold }) {
  const W = 700, H = 320, padL = 30, padR = 14, padT = 24, padB = 26
  const plotW = W - padL - padR, plotH = H - padT - padB
  const lo = 0.5, hi = Math.max(1.6, threshold + 0.05)
  const x = (r) => padL + ((r - lo) / (hi - lo)) * plotW
  const rows = [...districts].sort((a, b) => a.council_district - b.council_district)
  const lane = plotH / rows.length
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" style={{ display: 'block' }} role="img">
      {/* gridlines at 0.5,1.0,1.5 */}
      {[0.5, 0.75, 1.0, 1.25, 1.5].map((g) => (
        <g key={g}>
          <line x1={x(g)} y1={padT - 6} x2={x(g)} y2={padT + plotH} stroke={g === 1 ? 'var(--hairline-strong)' : 'var(--hairline)'} strokeWidth={g === 1 ? 1.5 : 1} strokeDasharray={g === 1 ? '' : '3 3'} />
          <text x={x(g)} y={padT - 11} textAnchor="middle" style={{ font: '500 10px var(--font-sans)', fill: 'var(--fg-subtle)' }}>{g.toFixed(2)}×</text>
        </g>
      ))}
      {/* flag threshold */}
      <line x1={x(threshold)} y1={padT - 6} x2={x(threshold)} y2={padT + plotH} stroke="var(--flag)" strokeWidth={1.5} strokeDasharray="4 3" />
      <text x={x(threshold)} y={H - 8} textAnchor="middle" style={{ font: '600 10px var(--font-sans)', fill: 'var(--flag)' }}>flag at {threshold}×</text>
      {rows.map((r, i) => {
        const cy = padT + lane * i + lane / 2
        const x1 = x(1.0), x2 = x(r.disparity_ratio)
        return (
          <g key={r.council_district}>
            <text x={padL - 8} y={cy + 3} textAnchor="end" style={{ font: '600 11px var(--font-mono)', fill: 'var(--fg-muted)' }}>D{r.council_district}</text>
            <line x1={Math.min(x1, x2)} y1={cy} x2={Math.max(x1, x2)} y2={cy} stroke="var(--blue-4)" strokeWidth={5} strokeLinecap="round" />
            <circle cx={x2} cy={cy} r={4.5} fill="var(--blue-6)" />
            <text x={x2 + (r.disparity_ratio >= 1 ? 9 : -9)} y={cy + 3} textAnchor={r.disparity_ratio >= 1 ? 'start' : 'end'} style={{ font: '600 10.5px var(--font-mono)', fill: 'var(--fg)' }}>{r.disparity_ratio.toFixed(2)}×</text>
          </g>
        )
      })}
    </svg>
  )
}

export default function ServiceEquity() {
  const [d, setD] = useState(null)
  const [err, setErr] = useState(null)
  useEffect(() => { getStoryServiceEquity().then(setD).catch(() => setErr('Could not load 311 equity data.')) }, [])

  if (err) return <StoryLayout title="Does the city answer some neighborhoods slower?"><P style={{ color: 'var(--flag)' }}>{err}</P></StoryLayout>
  if (!d) return <StoryLayout title="Does the city answer some neighborhoods slower?"><P style={{ color: 'var(--fg-muted)' }}>Loading 311 data…</P></StoryLayout>

  const rs = d.districts
  const obs = rs.map((r) => r.observed_days)
  const ratios = rs.map((r) => r.disparity_ratio)
  const oMin = Math.min(...obs), oMax = Math.max(...obs)
  const rMin = Math.min(...ratios), rMax = Math.max(...ratios)
  const totalClosed = rs.reduce((a, b) => a + b.n_closed, 0)

  return (
    <StoryLayout
      eyebrow="Civic services · 311"
      title="Does the city answer some neighborhoods slower? We checked."
      dek="Raw 311 response times vary almost two-fold across council districts. But once you account for the fact that districts ask for different things, the gaps nearly vanish — no district is treated systematically worse. We're publishing the non-finding on purpose."
      sources={['Austin 311 service requests', `${(totalClosed / 1e6).toFixed(1)}M closed cases`, 'Mix-adjusted (indirect standardization)']}
    >
      <StatStrip items={[
        { value: `${d1(oMin)}–${d1(oMax)}`, label: 'Raw median days to close', sub: 'across the 10 districts' },
        { value: `${rMin.toFixed(2)}–${rMax.toFixed(2)}×`, label: 'After adjusting for request mix', sub: 'of each district’s expected time' },
        { value: `${d.n_flagged} of ${rs.length}`, label: 'Districts flagged', sub: `threshold ${d.threshold}×` },
      ]} />

      <Section>
        <P>It's a fair question to ask of any city: do some neighborhoods wait longer for a pothole to
        be filled or a complaint to be handled? Austin logs millions of 311 service requests with the
        council district attached, so we can check. The raw numbers do vary — median days-to-close
        ranges from about {d1(oMin)} days in the fastest district to {d1(oMax)} in the slowest.</P>
      </Section>

      <Section kicker="Why the raw gap misleads" title="Districts ask for different things">
        <P>That spread mostly reflects <em>what</em> each district reports, not how fast it's served. A
        downed-limb or loose-dog call closes in a day; a code-compliance or drainage case can take
        months. A district that files more slow-by-nature requests will look "slower" even if every
        single request type is handled at exactly the citywide pace.</P>
        <P>So we adjust for it. For each district we compute the average days-to-close we'd
        <em> expect</em> if its own mix of ~290 request types were each handled at the citywide speed,
        and compare that to what actually happened. The ratio — observed ÷ expected — is 1.0 when a
        district is served exactly as fast as its request mix predicts.</P>
      </Section>

      <Section kicker="The result" title="Every district lands near 1.0">
        <PullStat value={`${rMin.toFixed(2)}–${rMax.toFixed(2)}×`}
          label={`Adjusted for request mix, all ten districts fall in this narrow band around their expected response time. None approaches the ${d.threshold}× screening threshold. There is no systematic district-level disparity in 311 response.`} />
        <Figure title="Mix-adjusted 311 response by district (observed ÷ expected)"
          source="metric_311_equity (D7 detector), all closed 311 cases — indirect standardization across request types"
          note="Each dot is one district; the bar shows its distance from 1.0 (as-fast-as-expected). Left of 1.0 = faster than its mix predicts, right = slower. The red line is the 1.5× flag threshold.">
          <DisparityChart districts={rs} threshold={d.threshold} />
        </Figure>
      </Section>

      <Section kicker="Why publish a non-finding" title="The null result is the point">
        <P>It would be easy to publish only the alarming charts. But a research tool earns trust by
        reporting what it <em>doesn't</em> find as plainly as what it does. We went looking for the
        obvious inequity — a city that answers wealthier or whiter districts faster — and, measured
        carefully, it isn't there in the 311 data. That result is the baseline against which the
        findings elsewhere on this site should be read.</P>
        <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
          <Badge tone="ok">No disparity flagged</Badge>
          <Badge tone="muted">Coarse, district-level screen</Badge>
        </div>
      </Section>

      <StoryFooter
        methodology={d.methodology}
        sources={[
          { name: 'raw_austin_311', detail: 'Austin 311 service requests with council district, created and closed dates. Days-to-close computed per case.' },
          { name: 'metric_311_equity', detail: 'D7 detector: per-district observed vs. mix-expected days-to-close via indirect standardization across ~290 request types; disparity ratio and 1.5× flag.' },
        ]}
        limits={[
          'District is the finest geography 311 attaches — a coarse screen that cannot see disparities within a district.',
          'Adjusts for request TYPE only, not crew staffing, geography, differing reporting rates between neighborhoods, or seasonality.',
          '"Days to close" measures when a case was marked closed, not the quality of the resolution.',
          'A district reporting fewer requests overall could still mask under-reporting; this measures speed, not whether residents call at all.',
          'Observational — no causal claim.',
        ]}
        updated="all closed 311 cases on file"
      />
    </StoryLayout>
  )
}
