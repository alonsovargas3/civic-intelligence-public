import React, { useEffect, useState } from 'react'
import StoryLayout, { Section, P, PullStat, StatStrip, Figure, StoryFooter } from './StoryLayout.jsx'
import { getStoryWhoOwnsAustin } from '../api.js'
import { Icon } from '../Primitives.jsx'

const fmt = (n) => Number(n).toLocaleString('en-US')
const money = (v) => {
  const n = Number(v)
  if (n >= 1e9) return `$${(n / 1e9).toFixed(n >= 1e10 ? 1 : 2)}B`
  if (n >= 1e6) return `$${Math.round(n / 1e6)}M`
  return `$${fmt(Math.round(n))}`
}
const pct = (x) => `${(Number(x) * 100).toFixed(1)}%`

const KIND = {
  individual: { label: 'Individuals', icon: 'user', color: 'var(--blue-6)' },
  institutional: { label: 'Companies & institutions', icon: 'building', color: 'var(--blue-4)' },
  government: { label: 'Government', icon: 'landmark', color: 'var(--blue-8)' },
}

const TH = { font: '600 11px/1 var(--font-sans)', letterSpacing: '.05em', textTransform: 'uppercase', color: 'var(--fg-muted)', textAlign: 'right', padding: '0 0 10px' }
const TD = { font: '500 13.5px/1.3 var(--font-mono)', fontVariantNumeric: 'tabular-nums', color: 'var(--ink)', textAlign: 'right', padding: '10px 0', borderTop: '1px solid var(--hairline)' }
const TD_NAME = { ...TD, textAlign: 'left', font: '600 14px/1.25 var(--font-sans)' }

function RankTable({ rows, valueLabel = 'Appraised value' }) {
  return (
    <table style={{ width: '100%', borderCollapse: 'collapse' }}>
      <thead><tr>
        <th style={{ ...TH, textAlign: 'left' }}>Owner</th>
        <th style={TH}>Parcels</th>
        <th style={TH}>{valueLabel}</th>
      </tr></thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.rank}>
            <td style={TD_NAME}>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 9 }}>
                <Icon name={(KIND[r.kind] || KIND.individual).icon} size={15} color="var(--fg-subtle)" />
                <span>{titleCase(r.name)}</span>
              </span>
            </td>
            <td style={TD}>{fmt(r.n_parcels)}</td>
            <td style={{ ...TD, fontWeight: 600 }}>{money(r.total_appraised)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function titleCase(s) {
  // roll names are ALL CAPS; soften to Title Case while keeping short tokens (LLC, UT) upper
  return String(s).toLowerCase().replace(/\b([a-z])/g, (m) => m.toUpperCase())
    .replace(/\b(Llc|Lp|Ltd|Inc|Coa|Ut|Aisd|Usa)\b/g, (m) => m.toUpperCase())
}

function ShareBars({ byKind }) {
  // sort by value share desc for visual order
  const rows = [...byKind].sort((a, b) => b.value_share - a.value_share)
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
      {rows.map((r) => {
        const k = KIND[r.kind] || { label: r.kind, icon: 'user', color: 'var(--blue-5)' }
        return (
          <div key={r.kind}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
              <Icon name={k.icon} size={15} color="var(--fg-muted)" />
              <span style={{ font: '600 14px/1 var(--font-sans)', color: 'var(--ink)' }}>{k.label}</span>
              <span className="cii-footnote" style={{ marginLeft: 'auto' }}>{fmt(r.n_entities)} owners</span>
            </div>
            <TwinBar label="of parcels" share={r.parcel_share} color={k.color} sub={`${fmt(r.n_parcels)} parcels`} />
            <TwinBar label="of value" share={r.value_share} color={k.color} sub={money(r.total_appraised)} strong />
          </div>
        )
      })}
    </div>
  )
}

function TwinBar({ label, share, color, sub, strong }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '3px 0' }}>
      <span style={{ flex: '0 0 64px', font: '400 12px/1 var(--font-sans)', color: 'var(--fg-muted)' }}>{label}</span>
      <div style={{ flex: 1, height: strong ? 14 : 10, borderRadius: 'var(--r-pill)', background: 'var(--surface-3)', overflow: 'hidden' }}>
        <div style={{ width: `${Math.max(1.5, share * 100)}%`, height: '100%', borderRadius: 'var(--r-pill)', background: color, transition: 'width 500ms var(--ease)' }} />
      </div>
      <span style={{ flex: '0 0 96px', textAlign: 'right', font: `${strong ? 600 : 500} 12.5px/1 var(--font-mono)`, color: strong ? 'var(--ink)' : 'var(--fg-muted)', fontVariantNumeric: 'tabular-nums' }}>
        {pct(share)}
      </span>
    </div>
  )
}

export default function WhoOwnsAustin() {
  const [d, setD] = useState(null)
  const [err, setErr] = useState(null)
  useEffect(() => { getStoryWhoOwnsAustin().then(setD).catch(() => setErr('Could not load ownership data.')) }, [])

  if (err) return <StoryLayout title="Who Owns Austin"><P style={{ color: 'var(--flag)' }}>{err}</P></StoryLayout>
  if (!d) return <StoryLayout title="Who Owns Austin"><P style={{ color: 'var(--fg-muted)' }}>Loading the 2025 roll…</P></StoryLayout>

  const o = d.overall
  const priv = d.top_by_value.filter((r) => r.sector === 'private').slice(0, 10)
  const pub = d.top_by_value.filter((r) => r.sector === 'public').slice(0, 8)
  const privParcels = d.top_by_parcels.filter((r) => r.sector === 'private').slice(0, 10)
  const tesla = priv.find((r) => /TESLA/i.test(r.name))

  return (
    <StoryLayout
      eyebrow="Property · Ownership"
      title="Who Owns Austin"
      dek="The county lists 364,903 separate owners on the 2025 tax roll. Link the LLCs, trusts and public bodies back together and the picture concentrates fast — a handful of names hold a striking share of the city's $453 billion in property."
      sources={['TCAD 2025 certified roll', 'Entity resolution (atx_entity)', 'Appraised value — no sale prices']}
    >
      <StatStrip items={[
        { value: fmt(o.n_entities), label: 'Resolved owners', sub: 'after linking LLCs / trusts / agencies' },
        { value: fmt(o.n_parcels), label: 'Parcels on the roll' },
        { value: money(o.total_appraised), label: 'Total appraised value' },
      ]} />

      <Section>
        <P>Open the Travis County appraisal roll and you'll find hundreds of thousands of owner
        names — one per deed, each a separate line. But a single company can hold property under
        dozens of LLCs, and a family trust can appear in a half-dozen spellings. We link those
        records back together by owner name and mailing address, so an owner that controls many
        parcels counts as <em>one</em> owner. What's left is a much sharper map of who actually
        holds Austin.</P>
      </Section>

      <Section kicker="The split" title="Three kinds of owner">
        <P>Sort every resolved owner into individuals, companies/institutions, and government. Most
        parcels belong to individuals — but companies and institutions punch far above their parcel
        count in <em>value</em>, and a few hundred government bodies hold a tenth of all value on
        just 1.4% of parcels.</P>
        <Figure title="Share of parcels vs. share of value, by owner type" source="TCAD 2025 certified roll, entity-resolved (metric_ownership_concentration)">
          <ShareBars byKind={d.by_kind} />
        </Figure>
      </Section>

      <Section kicker="The names at the top" title="The public bodies you'd expect">
        <P>By total appraised value the largest owners are public: the City of Austin itself, the
        University of Texas, the State, the Housing Authority and the school district. That's the
        expected backdrop — the interesting part is who sits among them privately.</P>
        <Figure title="Largest public owners by appraised value" source="metric_owner_ranking (by_value), TCAD 2025">
          <RankTable rows={pub} />
        </Figure>
      </Section>

      <Section kicker="The finding" title="The private holders among them">
        {tesla && (
          <PullStat value={`${money(tesla.total_appraised)} · ${fmt(tesla.n_parcels)} parcels`}
            label="Tesla's Austin footprint is appraised higher than entire neighborhoods — concentrated on just a few dozen parcels." />
        )}
        <P>Strip out the government bodies and the largest private owners come into focus: a single
        manufacturer, a Domain-area holding company, a chipmaker, a hospital system. Each holds
        enormous value on a tiny number of parcels.</P>
        <Figure title="Largest private owners by appraised value" source="metric_owner_ranking (by_value), TCAD 2025">
          <RankTable rows={priv} />
        </Figure>
      </Section>

      <Section kicker="Counting differently" title="Who's accumulating the most parcels">
        <P>Rank by <em>number of parcels</em> instead of value and a different cast appears: national
        production homebuilders, holding hundreds of lots each. Their per-parcel value is low because
        many are still raw or partially built lots — an inventory of future subdivisions sitting on
        the roll today.</P>
        <Figure title="Largest private owners by parcel count" source="metric_owner_ranking (by_parcels), TCAD 2025"
          note="Low appraised totals against high parcel counts indicate undeveloped or partially built lot inventory.">
          <RankTable rows={privParcels} valueLabel="Appraised value" />
        </Figure>
      </Section>

      <StoryFooter
        methodology={d.methodology}
        sources={[
          { name: 'raw_tcad_roll', detail: 'Travis Central Appraisal District 2025 certified roll (bulk EARS export). Owner PII is isolated; only public canonical names appear here.' },
          { name: 'dim_entity', detail: 'Connected-components entity resolution over owner names + mailing addresses (atx_entity) — links an owner’s many parcels into one entity.' },
          { name: 'metric_ownership_concentration / metric_owner_ranking', detail: 'Pre-aggregated concentration shares and top-owner rankings derived in-database from the roll + entity layer.' },
        ]}
        limits={[
          'Appraised value only — Texas is a non-disclosure state, so no sale prices exist in any public dataset.',
          'A single roll year (2025 certified). No year-over-year change can be shown until prior-year rolls are loaded.',
          'Owner "kind" (individual / company / government) is a name heuristic and misreads some owners; kind shares are good, not exact.',
          'Entity resolution can over- or under-merge in edge cases (shared mailing addresses, common names).',
          'TCAD covers all of Travis County, which is larger than the City of Austin proper.',
        ]}
        updated="the 2025 certified roll"
      />
    </StoryLayout>
  )
}
