import React, { useEffect, useState } from 'react'
import StoryLayout, { Section, P, StatStrip, Figure } from './StoryLayout.jsx'
import { getStoryFoodInspections } from '../api.js'

const fmt = (n) => Number(n).toLocaleString('en-US')

function HBars({ rows, hot }) {
  const max = Math.max(...rows.map((r) => r.value))
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {rows.map((r) => {
        const isHot = hot && hot(r.label)
        return (
          <div key={r.label} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ flex: '0 0 96px', font: '500 13px/1.25 var(--font-mono)', color: 'var(--ink)' }}>{r.label}</span>
            <div style={{ flex: 1, height: 16, background: 'var(--surface-3)', borderRadius: 'var(--r-sm)', overflow: 'hidden' }}>
              <div style={{ width: `${Math.max(1, (r.value / max) * 100)}%`, height: '100%', background: isHot ? 'var(--flag)' : 'var(--blue-5)', borderRadius: 'var(--r-sm)' }} />
            </div>
            <span style={{ flex: '0 0 60px', textAlign: 'right', font: '600 13px var(--font-mono)', color: 'var(--ink)', fontVariantNumeric: 'tabular-nums' }}>{fmt(r.value)}</span>
          </div>
        )
      })}
    </div>
  )
}

export function FoodInspectionStory({ d, refreshStatus = null }) {
  const good = d.distribution.find((b) => b.band === '90–100')
  const under70 = d.distribution.find((b) => b.band === 'Under 70')
  const share = good && d.total > 0 ? good.n / d.total : null
  const pctGood = share === null ? null : (100 * share).toFixed(1)
  // Pair provenance only with the payload it describes. A legacy API response
  // must never inherit an unrelated accepted snapshot's counts or currency.
  const reasonKeys = ['missing_score', 'non_finite_score', 'non_numeric_score', 'out_of_range_score']
  const missingValues = refreshStatus?.nonscored_rows && typeof refreshStatus.nonscored_rows === 'object'
    ? Object.values(refreshStatus.nonscored_rows) : []
  const missingCount = missingValues.reduce((sum, n) => sum + n, 0)
  const matched = refreshStatus?.status === 'accepted-counts-private'
    && refreshStatus?.fresh === false
    && refreshStatus.nonscored_rows && Object.keys(refreshStatus.nonscored_rows).length === reasonKeys.length
    && reasonKeys.every((key) => Object.prototype.hasOwnProperty.call(refreshStatus.nonscored_rows, key))
    && missingValues.length === 4 && missingValues.every((n) => Number.isInteger(n) && n >= 0)
    && Number.isInteger(refreshStatus.total_visits) && refreshStatus.total_visits === d.total + missingCount
    && refreshStatus?.name_groups?.role === 'name_group_proxy' && Number.isInteger(refreshStatus.name_groups.count)
    && refreshStatus.name_groups.count >= 0 && refreshStatus.name_groups.count <= refreshStatus.total_visits
    && refreshStatus?.scored_visits === d.total
    && refreshStatus?.event_window?.mn === d.window.mn
    && refreshStatus?.event_window?.mx === d.window.mx
  const provenance = matched ? refreshStatus : null
  const missing = provenance?.nonscored_rows
    ? Object.values(provenance.nonscored_rows).reduce((sum, n) => sum + n, 0) : null

  return (
    <StoryLayout
      eyebrow="City services · Food safety"
      title="Austin food inspection scores"
      dek={`The average among ${fmt(d.total)} scored inspection visits is ${d.avg_score}. Scores describe visits; repeat-low establishment rankings are unavailable from the accepted counts.`}
      sources={['Food Establishment Inspection Scores', `Event window: ${d.window.mn} – ${d.window.mx}`, `${fmt(d.total)} scored visits`]}
    >
      <StatStrip items={[
        { value: `${d.avg_score}`, label: 'Average scored visit', sub: 'out of 100' },
        { value: pctGood === null ? 'Unavailable' : `${pctGood}%`, label: 'Scored 90 or above', sub: `${fmt(good ? good.n : 0)} scored visits` },
        { value: fmt(under70 ? under70.n : 0), label: 'Scored under 70', sub: `of ${fmt(d.total)} scored visits` },
      ]} />

      <Section kicker="Inspection visits" title="Scores across the source event window">
        <P>The average score is <strong>{d.avg_score}</strong>. Of {fmt(d.total)} scored visits,
        <strong> {fmt(good ? good.n : 0)}</strong> scored 90 or above
        {pctGood !== null && <> — <strong>{pctGood}%</strong>{share < 2 / 3 ? ', below two-thirds' : ''}</>}.
        These percentages use scored visits as the denominator.</P>
        {provenance ? <>
          <P>The source contains {fmt(provenance.total_visits)} visits: {fmt(d.total)} scored visits and
          {' '}{fmt(missing)} visits without a usable score. The missing-score visits are excluded from score percentages.</P>
          <P>{fmt(provenance.name_groups.count)} reported name groups are a name-group proxy,
          rather than a count of restaurants, establishments, or unique businesses.</P>
        </> : <P>Total-visit accounting, missing-score counts and reported name-group counts are unavailable until matching accepted refresh metadata is supplied.</P>}
        <P>The full source event window is {d.window.mn} through {d.window.mx}.
        It is distinct from the source publication time and the export check time.</P>
        <Figure title="Scored inspection visits, by band" source="City of Austin food establishment inspections">
          <HBars rows={d.distribution.map((b) => ({ label: b.band, value: b.n }))} hot={(l) => l === 'Under 70'} />
        </Figure>
      </Section>

      <Section kicker="Unavailable analysis" title="Repeat-low establishment rankings">
        <P>The accepted counts do not provide establishment histories or repeat-low rankings.
        An empty repeat-low result does not establish that there were zero repeat low-scorers.
        These counts cannot identify failing restaurants or determine renewal eligibility.</P>
      </Section>

      <footer style={{ marginTop: 56, paddingTop: 28, borderTop: '2px solid var(--hairline-strong)' }}>
        <h2>Method and limits</h2>
        <P>Score percentages use visits with a finite numeric score from 0 through 100.
        Visits with missing or unusable scores are excluded. The 80–89 and 70–79 band labels
        mean scores from 80 up to 90, and from 70 up to 80, respectively.</P>
        {!provenance && <P>The displayed summaries have no matching accepted refresh metadata; source accounting and publication currency remain unavailable.</P>}
        <P>Inspection scores are point-in-time visit records, rather than current safety verdicts.
        Food establishments include groceries and markets.</P>
        <P>Source publication as-of: {provenance?.snapshot_as_of || 'unavailable'}.
        Export checked as-of: {provenance?.checked_as_of || 'unavailable'}.</P>
        <P>Inspection cadence is unmeasured. An event-to-publication date gap is a data-currency observation;
        it does not measure inspection frequency or reporting lag.</P>
      </footer>
    </StoryLayout>
  )
}

export default function FoodInspections() {
  const [d, setD] = useState(null)
  const [err, setErr] = useState(null)
  const [refreshStatus, setRefreshStatus] = useState(null)
  useEffect(() => {
    getStoryFoodInspections().then(setD).catch(() => setErr('Could not load inspection data.'))
    fetch('/data/story_refresh_status.json')
      .then((response) => response.ok ? response.json() : null)
      .then((index) => {
        if (index?.schema === 'private-story-refresh-status-v1' && Array.isArray(index.stories)) {
          setRefreshStatus(index.stories.find((story) => story.slug === 'food-inspections') || null)
        }
      }).catch(() => {})
  }, [])
  if (err) return <StoryLayout title="Austin food inspection scores"><P style={{ color: 'var(--flag)' }}>{err}</P></StoryLayout>
  if (!d) return <StoryLayout title="Austin food inspection scores"><P style={{ color: 'var(--fg-muted)' }}>Loading inspections…</P></StoryLayout>
  return <FoodInspectionStory d={d} refreshStatus={refreshStatus} />
}
