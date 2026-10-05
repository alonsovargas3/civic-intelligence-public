import React, { useEffect, useState } from 'react'
import StoryLayout, { Section, P, PullStat, StatStrip, Figure, StoryFooter } from './StoryLayout.jsx'
import { getStoryShortTermRentals } from '../api.js'

const fmt = (n) => Number(n).toLocaleString('en-US')

function HBars({ rows, hot }) {
  const max = Math.max(...rows.map((r) => r.value))
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {rows.map((r) => {
        const isHot = hot && hot(r)
        return (
          <div key={r.label} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ flex: '0 0 200px', font: '500 13px/1.25 var(--font-sans)', color: 'var(--ink)' }}>{r.label}</span>
            <div style={{ flex: 1, height: 14, background: 'var(--surface-3)', borderRadius: 'var(--r-sm)', overflow: 'hidden' }}>
              <div style={{ width: `${Math.max(2, (r.value / max) * 100)}%`, height: '100%', background: isHot ? 'var(--blue-7)' : 'var(--blue-4)', borderRadius: 'var(--r-sm)' }} />
            </div>
            <span style={{ flex: '0 0 48px', textAlign: 'right', font: '600 13px var(--font-mono)', color: 'var(--ink)', fontVariantNumeric: 'tabular-nums' }}>{fmt(r.value)}</span>
          </div>
        )
      })}
    </div>
  )
}

export default function ShortTermRentals() {
  const [d, setD] = useState(null)
  const [err, setErr] = useState(null)
  useEffect(() => { getStoryShortTermRentals().then(setD).catch(() => setErr('Could not load STR data.')) }, [])

  if (err) return <StoryLayout title="Austin's short-term rentals"><P style={{ color: 'var(--flag)' }}>{err}</P></StoryLayout>
  if (!d) return <StoryLayout title="Austin's short-term rentals"><P style={{ color: 'var(--fg-muted)' }}>Loading STR registry…</P></StoryLayout>

  const topD = d.by_district[0]
  const central = d.by_district.filter((r) => [9, 3, 1].includes(r.district)).reduce((a, b) => a + b.n, 0)

  return (
    <StoryLayout
      eyebrow="Housing · Rentals"
      title="Austin's short-term rentals are mostly not someone's home"
      dek="Nearly two-thirds of the city's licensed short-term rentals aren't the owner's residence — they're investor-run units, and they cluster in the urban core and East Austin."
      sources={['Short Term Rental Locations (license registry)', `${fmt(d.total)} licensed STRs`, 'Licensed only — a floor']}
    >
      <StatStrip items={[
        { value: fmt(d.total), label: 'Licensed short-term rentals', sub: 'a floor — many operate unlicensed' },
        { value: `${d.pct_non_owner}%`, label: 'Not owner-occupied', sub: `${fmt(d.non_owner)} investor/commercial units` },
        { value: `D${topD.district}`, label: 'Top district', sub: `${fmt(topD.n)} STRs` },
      ]} />

      <Section kicker="The mix" title="Most aren't a spare room">
        <P>The friendly image of a short-term rental — a host renting their spare room — is the city's
        Type 1 license. It's the minority. <strong>{d.pct_non_owner}%</strong> of Austin's
        {' '}{fmt(d.total)} licensed STRs are <em>not</em> owner-occupied: whole houses (Type 2) and
        multifamily units (Type 3) run as investment properties.</P>
        <Figure title="Licensed STRs by type" source="City of Austin STR registry">
          <HBars rows={d.by_type.map((t) => ({ label: t.type, value: t.n }))} hot={(r) => !d.by_type.find((t) => t.type === r.label).owner_occupied} />
        </Figure>
        <P className="cii-footnote" style={{ color: 'var(--fg-subtle)', fontSize: 13 }}>Darker bars are non-owner-occupied (Type 2/3).</P>
      </Section>

      <Section kicker="The map" title="Clustered in the core and East Austin">
        <P>STRs aren't spread evenly. They concentrate downtown and in East Austin — Districts
        {' '}{d.by_district.slice(0, 3).map((r) => r.district).join(', ')} alone hold
        {' '}<strong>{fmt(central)}</strong> of them, roughly {Math.round(100 * central / d.total)}% of
        the city's licensed total. These are the close-in, tourist-proximate and rapidly changing
        neighborhoods where a unit rented to visitors is a unit not rented to residents.</P>
        <Figure title="Licensed STRs by council district" source="City of Austin STR registry">
          <HBars rows={d.by_district.map((r) => ({ label: `District ${r.district}`, value: r.n }))} hot={(r) => r.label === `District ${topD.district}`} />
        </Figure>
      </Section>

      <StoryFooter
        methodology={d.methodology}
        sources={[
          { name: 'raw_short_term_rentals', detail: 'City of Austin Short Term Rental Locations (license registry) — case number, STR type, address, ZIP, council district.' },
        ]}
        limits={[
          'LICENSED STRs only — Austin has a documented gap between licensed and operating rentals; see the companion story "The STR licensing gap" for the operating-side count (2.5× the licenses).',
          'Because unlicensed rentals are likely disproportionately non-owner-occupied, the true non-owner share may be even higher than shown.',
          'No parcel-level owner join — the registry carries address and district, not a parcel id, so ownership entities can\'t be resolved here.',
          'Counts active licenses at load time, not historical or revoked ones.',
        ]}
        updated="the latest STR registry load"
      />
    </StoryLayout>
  )
}
