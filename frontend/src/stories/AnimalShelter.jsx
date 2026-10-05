import React, { useEffect, useState } from 'react'
import StoryLayout, { Section, P, PullStat, StatStrip, Figure, StoryFooter } from './StoryLayout.jsx'
import { getStoryAnimalShelter } from '../api.js'

const fmt = (n) => Number(n).toLocaleString('en-US')
const pct = (x) => `${(Number(x) * 100).toFixed(1)}%`

function HBars({ rows, dead }) {
  const max = Math.max(...rows.map((r) => r.value))
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {rows.map((r) => {
        const isDead = dead && dead(r.label)
        return (
          <div key={r.label} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ flex: '0 0 200px', font: '500 13px/1.25 var(--font-sans)', color: 'var(--ink)' }}>{r.label}</span>
            <div style={{ flex: 1, height: 14, background: 'var(--surface-3)', borderRadius: 'var(--r-sm)', overflow: 'hidden' }}>
              <div style={{ width: `${Math.max(1.5, (r.value / max) * 100)}%`, height: '100%', background: isDead ? 'var(--flag)' : 'var(--blue-5)', borderRadius: 'var(--r-sm)' }} />
            </div>
            <span style={{ flex: '0 0 52px', textAlign: 'right', font: '600 13px var(--font-mono)', color: 'var(--ink)', fontVariantNumeric: 'tabular-nums' }}>{fmt(r.value)}</span>
          </div>
        )
      })}
    </div>
  )
}

export default function AnimalShelter() {
  const [d, setD] = useState(null)
  const [err, setErr] = useState(null)
  useEffect(() => { getStoryAnimalShelter().then(setD).catch(() => setErr('Could not load shelter data.')) }, [])

  if (err) return <StoryLayout title="Austin's animal shelter"><P style={{ color: 'var(--flag)' }}>{err}</P></StoryLayout>
  if (!d) return <StoryLayout title="Austin's animal shelter"><P style={{ color: 'var(--fg-muted)' }}>Loading shelter outcomes…</P></StoryLayout>

  const adopted = d.outcomes.find((o) => o.grp === 'Adopted')

  return (
    <StoryLayout
      eyebrow="City services · Animals"
      title="Austin's no-kill shelter, by the numbers"
      dek={`Austin runs one of the country's largest no-kill animal shelters. Over the past year, about ${pct(d.live_release_rate)} of the animals that came through left alive.`}
      sources={['Austin Animal Center outcomes', `${d.window.mn} – ${d.window.mx}`, `${fmt(d.intakes)} intakes`]}
    >
      <StatStrip items={[
        { value: pct(d.live_release_rate), label: 'Live-release rate', sub: 'no-kill threshold is 90%' },
        { value: fmt(adopted ? adopted.n : 0), label: 'Adopted', sub: `of ${fmt(d.total)} outcomes` },
        { value: fmt(d.euthanized), label: 'Euthanized', sub: `${pct(d.euthanized / d.total)} of outcomes` },
      ]} />

      <Section kicker="The headline" title="Most animals leave alive">
        <P>"No-kill" doesn't mean no animal is ever euthanized — it's a benchmark: at least 90% of
        shelter animals leaving alive. Austin, a pioneer of the movement, clears it. Of the
        {' '}{fmt(d.total)} outcomes in the past year, <strong>{pct(d.live_release_rate)}</strong> were
        live — adopted, sent to a rescue partner, or returned to an owner — against
        {' '}<strong>{fmt(d.euthanized)}</strong> euthanized.</P>
        <Figure title="What happens to animals at the shelter" source="Austin Animal Center outcomes (recent window)">
          <HBars rows={d.outcomes.map((o) => ({ label: o.grp, value: o.n }))} dead={(l) => /euthan|died|doa/i.test(l)} />
        </Figure>
      </Section>

      <Section kicker="The mix" title="Cats outnumber dogs">
        <P>The shelter takes in more than just cats and dogs — rabbits, guinea pigs, the occasional
        goat — but cats are the largest group, narrowly ahead of dogs.</P>
        <Figure title="Outcomes by animal type" source="Austin Animal Center outcomes">
          <HBars rows={d.by_type.map((t) => ({ label: t.type, value: t.n }))} />
        </Figure>
      </Section>

      <StoryFooter
        methodology={d.methodology}
        sources={[
          { name: 'raw_animal_outcomes', detail: 'Austin Animal Center outcome records — outcome status, type, euthanasia reason. Live-release = live outcomes ÷ (all outcomes − dead-on-arrival).' },
          { name: 'raw_animal_intakes', detail: 'Companion intake feed (count shown for context).' },
        ]}
        limits={[
          'A recent rolling window (the live feed), not the shelter\'s full history.',
          'Outcome categories are grouped from the source status text by keyword.',
          'Euthanasia is not split into medical / owner-requested vs other.',
          'The source days-in-shelter field looked unreliable and is not shown.',
        ]}
        updated={`${d.window.mn} – ${d.window.mx}`}
      />
    </StoryLayout>
  )
}
