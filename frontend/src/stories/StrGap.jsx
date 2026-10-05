import React, { useEffect, useState } from 'react'
import StoryLayout, { Section, P, StatStrip, Figure, StoryFooter } from './StoryLayout.jsx'
import { getStoryStrGap } from '../api.js'

const fmt = (n) => Number(n).toLocaleString('en-US')

function PairBars({ rows }) {
  const max = Math.max(...rows.map((r) => Math.max(r.active_n, r.licensed_n)))
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {rows.map((r) => (
        <div key={r.label} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ flex: '0 0 110px', font: '500 13px/1.25 var(--font-sans)', color: 'var(--ink)' }}>{r.label}</span>
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 3 }}>
            <div style={{ height: 10, background: 'var(--surface-3)', borderRadius: 'var(--r-sm)', overflow: 'hidden' }}>
              <div style={{ width: `${Math.max(2, (r.active_n / max) * 100)}%`, height: '100%', background: 'var(--blue-7)' }} />
            </div>
            <div style={{ height: 10, background: 'var(--surface-3)', borderRadius: 'var(--r-sm)', overflow: 'hidden' }}>
              <div style={{ width: `${Math.max(2, (r.licensed_n / max) * 100)}%`, height: '100%', background: 'var(--blue-4)' }} />
            </div>
          </div>
          <span style={{ flex: '0 0 96px', textAlign: 'right', font: '600 12px var(--font-mono)', color: 'var(--ink)' }}>
            {fmt(r.active_n)} / {fmt(r.licensed_n)}
          </span>
        </div>
      ))}
    </div>
  )
}

export default function StrGap() {
  const [d, setD] = useState(null)
  const [err, setErr] = useState(null)
  useEffect(() => { getStoryStrGap().then((r) => (r.error ? setErr(r.error) : setD(r))).catch(() => setErr('Could not load STR-gap data.')) }, [])

  if (err) return <StoryLayout title="The STR licensing gap"><P style={{ color: 'var(--flag)' }}>{err}</P></StoryLayout>
  if (!d) return <StoryLayout title="The STR licensing gap"><P style={{ color: 'var(--fg-muted)' }}>Loading…</P></StoryLayout>

  const ratioCity = (d.in_district / d.licensed_n).toFixed(1)
  const ratioMetro = (d.active / d.licensed_n).toFixed(1)
  const pctEntire = Math.round((100 * d.entire) / d.active)
  const pctMulti = Math.round((100 * d.hosts.multi2) / d.active)

  return (
    <StoryLayout
      eyebrow="Housing · Rentals"
      title="The STR licensing gap"
      dek={`Austin has ${ratioCity}× more active Airbnb listings than STR licenses — and most listings still show no license number.`}
      sources={[`Inside Airbnb snapshot ${d.snapshot_date} (CC BY 4.0)`, `${fmt(d.licensed_n)} licensed STRs`, 'Airbnb only — a floor']}
    >
      <StatStrip items={[
        { value: fmt(d.active), label: 'Recently active Airbnb listings', sub: `${fmt(d.total)} listed in total` },
        { value: fmt(d.licensed_n), label: 'Licensed STRs, all types', sub: 'city registry' },
        { value: `${ratioCity}×`, label: 'Active listings per license, in-district', sub: `${ratioMetro}× metro-wide` },
      ]} />

      <Section kicker="The gap" title="Far more operate than are licensed">
        <P>Inside Airbnb's {d.snapshot_date} snapshot lists <strong>{fmt(d.total)}</strong> Austin
        short-term rentals on Airbnb alone, of which <strong>{fmt(d.active)}</strong> had a guest
        review in the last 12 months. The city's registry holds <strong>{fmt(d.licensed_n)}</strong>{' '}
        licenses of any type. Restricting to the {fmt(d.in_district)} active listings that geolocate
        inside the 10 council districts — the city's licensing jurisdiction — there are still{' '}
        <strong>{ratioCity}×</strong> more active listings than licenses. {pctEntire}% of active
        listings are entire homes, not spare rooms.</P>
      </Section>

      <Section kicker="Verification" title="Most listings still show no license number">
        <P>Austin requires operators to hold a license. In this snapshot{' '}
        <strong>{fmt(d.license_classes.claims_number)}</strong> of {fmt(d.active)} active listings
        ({Math.round((100 * d.license_classes.claims_number) / d.active)}%) display a license number,
        and <strong>{fmt(d.license_classes.verified)}</strong> match a case number in the city
        registry — up from zero in the 2025 snapshot, as Airbnb began surfacing a license field. The
        remaining <strong>{fmt(d.license_classes.missing)}</strong> show none: a blank field isn't
        proof of non-compliance, but it does mean enforcement can't lean on the listing side alone.</P>
      </Section>

      <Section kicker="The map" title="Operating vs licensed, by district">
        <P>Dark bars are active Airbnb listings; light bars are licenses on the registry.</P>
        <Figure title="Active listings vs licenses by council district" source="Inside Airbnb · city STR registry">
          <PairBars rows={d.by_district.map((r) => ({ label: `District ${r.district}`, ...r }))} />
        </Figure>
        <P style={{ color: 'var(--fg-subtle)', fontSize: 13 }}>{fmt(d.unlocated)} active listings sit outside all 10
        districts — Inside Airbnb's "Austin" export covers the metro area, wider than city jurisdiction.</P>
      </Section>

      <Section kicker="Who" title="Mostly multi-listing hosts">
        <P>{pctMulti}% of active listings belong to hosts running two or more —{' '}
        {fmt(d.hosts.multi5)} listings belong to hosts with five-plus, {fmt(d.hosts.multi10)} to
        hosts with ten-plus. The operating market skews commercial, matching what the registry's
        own Type 2/3 split shows for <a href="/stories/short-term-rentals">licensed rentals</a>.</P>
      </Section>

      <StoryFooter
        methodology={d.methodology}
        sources={[
          { name: 'raw_airbnb_listings', detail: `Inside Airbnb Austin summary snapshot ${d.snapshot_date} — data by Inside Airbnb (insideairbnb.com), licensed CC BY 4.0.` },
          { name: 'raw_short_term_rentals', detail: 'City of Austin STR license registry.' },
        ]}
        limits={d.caveat.split('. ').map((s) => s.replace(/\.$/, '') + '.')}
        updated="the latest `cli refresh` after an Inside Airbnb snapshot load"
      />
    </StoryLayout>
  )
}
