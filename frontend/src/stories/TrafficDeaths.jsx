import React, { useEffect, useState } from 'react'
import StoryLayout, { Section, P, PullStat, StatStrip, Figure, StoryFooter } from './StoryLayout.jsx'
import { getStoryTrafficDeaths } from '../api.js'

const fmt = (n) => Number(n).toLocaleString('en-US')

/* Simple horizontal bar list. */
function VBars({ rows, hot }) {
  const max = Math.max(...rows.map((r) => r.value))
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 9 }}>
      {rows.map((r) => {
        const isHot = hot && hot(r.label)
        return (
          <div key={r.label} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ flex: '0 0 168px', font: '500 13px/1.25 var(--font-sans)', color: 'var(--ink)' }}>{r.label}</span>
            <div style={{ flex: 1, height: 14, background: 'var(--surface-3)', borderRadius: 'var(--r-sm)', overflow: 'hidden' }}>
              <div style={{ width: `${Math.max(2, (r.value / max) * 100)}%`, height: '100%', background: isHot ? 'var(--flag)' : 'var(--blue-5)', borderRadius: 'var(--r-sm)' }} />
            </div>
            <span style={{ flex: '0 0 48px', textAlign: 'right', font: `${isHot ? 700 : 500} 13px var(--font-mono)`, color: isHot ? 'var(--flag)' : 'var(--ink)', fontVariantNumeric: 'tabular-nums' }}>{fmt(r.value)}</span>
          </div>
        )
      })}
    </div>
  )
}

/* Dual-axis "scissors" chart: crashes as light bars (left scale), deaths as a red
   line (right scale). Complete years only. */
function CrashDeathChart({ years }) {
  const W = 700, H = 300
  const padL = 6, padR = 6, padT = 28, padB = 28
  const plotW = W - padL - padR, plotH = H - padT - padB
  const maxC = Math.max(...years.map((y) => y.crashes)) * 1.05
  const maxD = Math.max(...years.map((y) => y.deaths)) * 1.15
  const n = years.length
  const slot = plotW / n
  const bw = slot * 0.6
  const cx = (i) => padL + slot * i + slot / 2
  const cyC = (v) => padT + plotH - (v / maxC) * plotH
  const cyD = (v) => padT + plotH - (v / maxD) * plotH
  const deathPath = years.map((y, i) => `${i === 0 ? 'M' : 'L'} ${cx(i).toFixed(1)} ${cyD(y.deaths).toFixed(1)}`).join(' ')
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" style={{ display: 'block' }} role="img">
      {/* legend */}
      <g>
        <rect x={padL} y={6} width={11} height={11} rx={2} fill="var(--blue-3)" />
        <text x={padL + 16} y={15} style={{ font: '500 11px var(--font-sans)', fill: 'var(--fg-muted)' }}>Crashes (left)</text>
        <line x1={padL + 96} y1={11} x2={padL + 116} y2={11} stroke="var(--flag)" strokeWidth="2.5" />
        <circle cx={padL + 106} cy={11} r={3} fill="var(--flag)" />
        <text x={padL + 122} y={15} style={{ font: '500 11px var(--font-sans)', fill: 'var(--fg-muted)' }}>Deaths (right)</text>
      </g>
      {/* baseline */}
      <line x1={padL} y1={padT + plotH} x2={W - padR} y2={padT + plotH} stroke="var(--hairline-strong)" strokeWidth="1" />
      {/* crash bars */}
      {years.map((y, i) => {
        const h = (y.crashes / maxC) * plotH
        return <rect key={y.year} x={cx(i) - bw / 2} y={padT + plotH - h} width={bw} height={h} rx={2} fill="var(--blue-3)" />
      })}
      {/* deaths line + dots + labels */}
      <path d={deathPath} fill="none" stroke="var(--flag)" strokeWidth="2.5" />
      {years.map((y, i) => (
        <g key={y.year}>
          <circle cx={cx(i)} cy={cyD(y.deaths)} r={3.2} fill="var(--flag)" />
          {(i === 0 || i === n - 1 || y.deaths === Math.max(...years.map((z) => z.deaths))) && (
            <text x={cx(i)} y={cyD(y.deaths) - 8} textAnchor="middle" style={{ font: '700 11px var(--font-mono)', fill: 'var(--flag)' }}>{y.deaths}</text>
          )}
        </g>
      ))}
      {/* x labels (every other year) */}
      {years.map((y, i) => (i % 2 === 0 || i === n - 1) && (
        <text key={y.year} x={cx(i)} y={H - 9} textAnchor="middle" style={{ font: '500 10px var(--font-sans)', fill: 'var(--fg-subtle)' }}>{y.year.slice(2)}</text>
      ))}
    </svg>
  )
}

export default function TrafficDeaths() {
  const [d, setD] = useState(null)
  const [err, setErr] = useState(null)
  useEffect(() => { getStoryTrafficDeaths().then(setD).catch(() => setErr('Could not load crash data.')) }, [])

  if (err) return <StoryLayout title="Fewer crashes, more deaths"><P style={{ color: 'var(--flag)' }}>{err}</P></StoryLayout>
  if (!d) return <StoryLayout title="Fewer crashes, more deaths"><P style={{ color: 'var(--fg-muted)' }}>Loading crash records…</P></StoryLayout>

  const complete = d.years.filter((y) => !y.partial)
  const by = Object.fromEntries(complete.map((y) => [y.year, y]))
  const first = complete[0], last = complete[complete.length - 1]
  const peakCrash = complete.reduce((a, b) => (b.crashes > a.crashes ? b : a))
  const peakDeath = complete.reduce((a, b) => (b.deaths > a.deaths ? b : a))
  const deathRatio = (last.deaths / first.deaths).toFixed(1)
  const rateRatio = (last.fatal_per_1k / first.fatal_per_1k).toFixed(1)
  const vruShare = Math.round(100 * last.vru_deaths / last.deaths)

  return (
    <StoryLayout
      eyebrow="Safety · Vision Zero"
      title="Fewer crashes, more deaths"
      dek={`Austin, like many cities, set a "Vision Zero" goal of eliminating traffic deaths. Reported crashes have fallen from their 2019 peak — but deaths have climbed the other way, from about ${first.deaths} a year early last decade to ${last.deaths} in ${last.year}.`}
      sources={['Austin Vision Zero / TxDOT CRIS crash records', '2010–present', 'De-duplicated by CRIS crash id']}
    >
      <StatStrip items={[
        { value: `${first.deaths} → ${last.deaths}`, label: `Annual traffic deaths`, sub: `${first.year} → ${last.year} (peak ${peakDeath.deaths} in ${peakDeath.year})` },
        { value: fmt(peakCrash.crashes), label: `Crashes at the ${peakCrash.year} peak`, sub: `down to ${fmt(last.crashes)} in ${last.year}` },
        { value: `${rateRatio}×`, label: 'Fatal rate per crash', sub: `${first.fatal_per_1k} → ${last.fatal_per_1k} per 1,000` },
      ]} />

      <Section>
        <P>The intuition is that safer roads mean both fewer crashes and fewer deaths. In Austin over
        the past fifteen years those two lines have pulled apart. Total reported crashes rose into the
        late 2010s, dropped during the pandemic, and have settled below their {peakCrash.year} peak.
        Deaths did the opposite.</P>
        <Figure title="Reported crashes vs. people killed, by year"
          source="Austin Vision Zero / TxDOT CRIS, de-duplicated by crash id (complete years; 2026 year-to-date excluded)">
          <CrashDeathChart years={complete} />
        </Figure>
        <P>Deaths roughly <strong>{deathRatio}×</strong>'d — from {first.deaths} in {first.year} to a
        high of {peakDeath.deaths} in {peakDeath.year}, and {last.deaths} in {last.year} — while
        crashes fell by roughly {Math.round(100 * (1 - last.crashes / peakCrash.crashes))}% from the
        {' '}{peakCrash.year} peak.</P>
      </Section>

      <Section kicker="The rate, not just the count" title="A crash is far likelier to be deadly now">
        <P>Because deaths rose while crashes fell, the share of crashes that kill someone climbed
        steadily. It isn't a single bad year — the elevated rate holds across the whole post-2019
        period.</P>
        <PullStat value={`${first.fatal_per_1k} → ${last.fatal_per_1k}`} accent="var(--flag)"
          label={`fatal crashes per 1,000 crashes, ${first.year} to ${last.year} — roughly ${rateRatio} times deadlier per crash. (Read this as suggestive: it pairs a reliably recorded numerator, deaths, with a crash count that has its own reporting nuances.)`} />
      </Section>

      <Section kicker="Who is dying" title="Over half are pedestrians, cyclists and riders">
        <P>The rise isn't only people in cars. Of the {last.deaths} people killed in {last.year},
        {' '}<strong>{last.vru_deaths}</strong> — about {vruShare}% — were vulnerable road users:
        {' '}{last.ped_deaths} pedestrians, {last.moto_deaths} motorcyclists and {last.bike_deaths}
        {' '}cyclists. These are the road users a crash is most likely to kill.</P>
        <Figure title="Traffic deaths by road user, recent years" source="Vision Zero / CRIS death counts by mode, de-duplicated">
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr>
              <th style={{ font: '600 11px/1 var(--font-sans)', letterSpacing: '.05em', textTransform: 'uppercase', color: 'var(--fg-muted)', textAlign: 'left', padding: '0 0 10px' }}>Year</th>
              {['Total deaths', 'Pedestrian', 'Motorcycle', 'Bicycle'].map((h) => (
                <th key={h} style={{ font: '600 11px/1 var(--font-sans)', letterSpacing: '.05em', textTransform: 'uppercase', color: 'var(--fg-muted)', textAlign: 'right', padding: '0 0 10px' }}>{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {complete.slice(-5).reverse().map((y) => (
                <tr key={y.year}>
                  <td style={{ font: '600 13.5px/1.2 var(--font-sans)', color: 'var(--ink)', textAlign: 'left', padding: '10px 0', borderTop: '1px solid var(--hairline)' }}>{y.year}</td>
                  {[y.deaths, y.ped_deaths, y.moto_deaths, y.bike_deaths].map((v, i) => (
                    <td key={i} style={{ font: `${i === 0 ? 600 : 500} 13.5px/1.2 var(--font-mono)`, fontVariantNumeric: 'tabular-nums', color: i === 0 ? 'var(--ink)' : 'var(--fg)', textAlign: 'right', padding: '10px 0', borderTop: '1px solid var(--hairline)' }}>{v}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </Figure>
      </Section>

      {d.victims && d.victims.total > 0 && (
        <Section kicker="Who dies" title="Pedestrians are the largest single group">
          <P>The per-victim records sharpen the picture. Across {fmt(d.victims.total)} people killed on
          Austin roads in the data, <strong>{fmt(d.victims.by_mode[0].killed)} were pedestrians</strong>
          {' '}— more than any other category, including people in passenger cars. Most victims are
          working-age adults, but the toll runs across every age.</P>
          <Figure title="Traffic deaths by road user" source="Austin crash victim records (killed), de-duplicated">
            <VBars rows={d.victims.by_mode.map((m) => ({ label: m.mode, value: m.killed }))} hot={(l) => l === 'Pedestrian'} />
          </Figure>
          <Figure title="Traffic deaths by age" source="Austin crash victim records (killed)">
            <VBars rows={d.victims.by_age.filter((a) => a.band !== 'Unknown').map((a) => ({ label: a.band, value: a.killed }))} />
          </Figure>
        </Section>
      )}

      <StoryFooter
        methodology={d.methodology}
        sources={[
          { name: 'raw_traffic_crashes → mv_crash_yearly', detail: 'Austin Vision Zero feed of TxDOT CRIS crash records (Full-Purpose jurisdiction). The feed serves ~2 rows per crash; the view de-duplicates by CRIS crash id before aggregating by year.' },
          { name: 'raw_crash_victims', detail: 'Per-person crash victim records (age, mode, severity) — the "who dies" breakdown counts victims with severity = killed.' },
        ]}
        limits={[
          '2026 is partial (year-to-date) and excluded from every headline figure.',
          'Serious-injury severity is coded with a lag, so the most recent year understates eventual injuries — injuries are provisional.',
          'The 2020 crash drop coincides with the pandemic; crashes have plateaued below the 2019 peak rather than steadily fallen.',
          'The per-crash fatal rate pairs reliably recorded deaths with a crash count subject to reporting nuances — treat it as suggestive, not exact.',
          'Full-Purpose jurisdiction excludes some outlying roads; this is not every crash in the metro.',
          'Causation is not claimed — the page shows what the records say, not why.',
        ]}
        updated="the latest CRIS crash load"
      />
    </StoryLayout>
  )
}
