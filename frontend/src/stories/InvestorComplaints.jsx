import React, { useEffect, useState } from 'react'
import StoryLayout, { Section, P, PullStat, StatStrip, Figure, StoryFooter } from './StoryLayout.jsx'
import { getStoryInvestorComplaints } from '../api.js'

const fmt = (n) => Number(n).toLocaleString('en-US')
const rate = (n) => Number(n).toLocaleString('en-US', { maximumFractionDigits: 0 })

const CLASS_LABEL = {
  A1: 'Single-family homes', C1: 'Vacant commercial/lots', F1: 'Commercial', O1: 'Residential inventory',
  A4: 'Condominiums', B2: 'Duplex / multifamily', E1: 'Rural w/ home', A2: 'Residential (secondary)',
  A3: 'Residential (other)', B1: 'Apartments', F3: 'Commercial', F5: 'Commercial',
}

const TH = { font: '600 11px/1 var(--font-sans)', letterSpacing: '.04em', textTransform: 'uppercase', color: 'var(--fg-muted)', textAlign: 'right', padding: '0 0 10px' }
const TD = { font: '500 13px/1.3 var(--font-mono)', fontVariantNumeric: 'tabular-nums', color: 'var(--ink)', textAlign: 'right', padding: '9px 0', borderTop: '1px solid var(--hairline)' }

/* Horizontal "index vs the class norm" bars with a dashed reference line at 1.0. */
function IndexBars({ rows, highlight }) {
  const max = Math.max(1.2, ...rows.map((r) => r.index || 0)) * 1.08
  const refX = (1 / max) * 100
  return (
    <div style={{ position: 'relative', display: 'flex', flexDirection: 'column', gap: 11, paddingTop: 6 }}>
      {/* 1.0 reference line */}
      <div style={{ position: 'absolute', left: `calc(${refX}% )`, top: 0, bottom: 18, width: 0, borderLeft: '2px dashed var(--hairline-strong)' }} />
      <div style={{ position: 'absolute', left: `${refX}%`, top: -4, transform: 'translateX(-50%)', font: '600 10px var(--font-sans)', color: 'var(--fg-subtle)', whiteSpace: 'nowrap' }}>
        class norm (1.0×)
      </div>
      {rows.map((r) => {
        const hot = r.property_class === highlight
        const w = Math.max(2, ((r.index || 0) / max) * 100)
        return (
          <div key={r.property_class} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ flex: '0 0 160px', font: '500 12.5px/1.2 var(--font-sans)', color: hot ? 'var(--ink)' : 'var(--fg-muted)', fontWeight: hot ? 700 : 500 }}>
              {CLASS_LABEL[r.property_class] || r.property_class}
              <span style={{ color: 'var(--fg-subtle)', fontWeight: 400 }}> · {fmt(r.parcels)}</span>
            </span>
            <div style={{ flex: 1, height: hot ? 18 : 13, background: 'var(--surface-3)', borderRadius: 'var(--r-sm)', overflow: 'hidden' }}>
              <div style={{ width: `${w}%`, height: '100%', background: hot ? 'var(--flag)' : 'var(--blue-4)', borderRadius: 'var(--r-sm)', transition: 'width 500ms var(--ease)' }} />
            </div>
            <span style={{ flex: '0 0 48px', textAlign: 'right', font: `${hot ? 700 : 500} 13px var(--font-mono)`, color: hot ? 'var(--flag)' : 'var(--fg)', fontVariantNumeric: 'tabular-nums' }}>
              {(r.index).toFixed(2)}×
            </span>
          </div>
        )
      })}
    </div>
  )
}

/* Two-bar per-1k comparison within single-family. */
function CompareBars({ items }) {
  const max = Math.max(...items.map((i) => i.value))
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {items.map((it) => (
        <div key={it.label}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 6 }}>
            <span style={{ font: `${it.hot ? 700 : 500} 14px/1 var(--font-sans)`, color: it.hot ? 'var(--ink)' : 'var(--fg)' }}>{it.label}</span>
            <span style={{ font: '600 14px var(--font-mono)', color: it.hot ? 'var(--flag)' : 'var(--fg-muted)', fontVariantNumeric: 'tabular-nums' }}>{rate(it.value)} <span className="cii-footnote" style={{ fontFamily: 'var(--font-sans)' }}>/ 1k</span></span>
          </div>
          <div style={{ height: 16, background: 'var(--surface-3)', borderRadius: 'var(--r-sm)', overflow: 'hidden' }}>
            <div style={{ width: `${Math.max(2, (it.value / max) * 100)}%`, height: '100%', background: it.hot ? 'var(--flag)' : 'var(--blue-5)', borderRadius: 'var(--r-sm)' }} />
          </div>
        </div>
      ))}
    </div>
  )
}

export default function InvestorComplaints() {
  const [d, setD] = useState(null)
  const [err, setErr] = useState(null)
  useEffect(() => { getStoryInvestorComplaints().then(setD).catch(() => setErr('Could not load code-complaint data.')) }, [])

  if (err) return <StoryLayout title="Investor-owned homes draw more complaints"><P style={{ color: 'var(--flag)' }}>{err}</P></StoryLayout>
  if (!d) return <StoryLayout title="Investor-owned homes draw more complaints"><P style={{ color: 'var(--fg-muted)' }}>Loading code-complaint data…</P></StoryLayout>

  const ind = d.a1.find((r) => r.owner_type === 'individual')
  const inst = d.a1.find((r) => r.owner_type === 'institutional')
  const blendInst = d.blended.institutional
  const blendInd = d.blended.individual
  const blendRatio = (blendInst.per_1k / blendInd.per_1k).toFixed(1)
  const a1Ratio = (inst.per_1k / ind.per_1k).toFixed(1)
  // de-confound chart: classes with the most institutional parcels (high-n), so
  // the comparison isn't carried by tiny strata.
  const byClass = [...d.by_class].sort((a, b) => b.parcels - a.parcels).slice(0, 7)

  return (
    <StoryLayout
      eyebrow="Property · Code complaints"
      title="Investor-owned homes draw more complaints"
      dek="Single-family homes owned by companies and investors draw about 1.7× the code complaints of the typical home in their class — a gap that survives even after accounting for the fact that institutions also own most of the city's apartments and commercial property."
      sources={['Austin Code complaints (raw_code_cases)', 'TCAD 2025 ownership', 'Cases opened 2024 onward']}
    >
      <StatStrip items={[
        { value: `${inst.index.toFixed(1)}×`, label: 'Complaint rate vs class norm', sub: 'investor-owned single-family' },
        { value: `${rate(inst.per_1k)} / 1k`, label: 'Investor-owned homes', sub: `vs ${rate(ind.per_1k)}/1k owner-occupied` },
        { value: fmt(inst.parcels), label: 'Investor-owned A1 homes', sub: 'in the 2025 roll' },
      ]} />

      <Section>
        <P>Austin's code department logs complaints — tall grass, junked vehicles, unpermitted work,
        substandard structures. Match each complaint to the property it's about and to who owns that
        property, and a pattern appears: homes held by companies and investors draw complaints at a
        higher rate than owner-occupied ones. The trick is making sure the comparison is fair.</P>
      </Section>

      <Section kicker="The trap" title="A gap that looks bigger than it is">
        <P>Compare all institution-owned parcels to all individual-owned ones and the gap looks huge —
        about <strong>{blendRatio}×</strong>:</P>
        <Figure title="Complaints per 1,000 parcels — all property types pooled" source="metric_owner_treatment, all classes">
          <CompareBars items={[
            { label: 'Individual-owned (all types)', value: blendInd.per_1k },
            { label: 'Institution-owned (all types)', value: blendInst.per_1k, hot: true },
          ]} />
        </Figure>
        <P>But that's mostly an illusion of <em>what</em> institutions own. They hold a large share of
        apartments, commercial buildings and vacant lots — property types that generate far more
        complaints than a house, no matter who owns them. Pool everything together and you're really
        measuring the property mix, not the owner.</P>
      </Section>

      <Section kicker="The control" title="Comparing like with like">
        <P>So compare within each property class instead. For every class, we divide the institutional
        complaint rate by the rate for <em>all</em> owners of that same class — an index where 1.0×
        means "no different from its peers." In apartments, commercial and vacant lots, the index
        collapses to about 1.0: the raw gap there was pure property mix. In single-family homes, it
        does not.</P>
        <Figure title="Institutional complaint rate vs. the norm for the same property class"
          source="metric_owner_treatment (code_case_index), classes with ≥200 institution-owned parcels"
          note="Bars past the dashed line draw more complaints than the typical owner of that property type. Labels show the count of institution-owned parcels.">
          <IndexBars rows={byClass} highlight="A1" />
        </Figure>
      </Section>

      <Section kicker="The finding" title="Within single-family homes, the gap is real">
        <PullStat value={`${rate(inst.per_1k)} vs ${rate(ind.per_1k)} per 1,000`}
          label={`Among single-family homes, investor-owned ones draw roughly ${a1Ratio}× the complaints of owner-occupied ones — and ${inst.index.toFixed(2)}× the rate of the average single-family owner.`}
          accent="var(--flag)" />
        <Figure title="Single-family (class A1) complaints per 1,000 homes, by owner type" source="metric_owner_treatment, class A1">
          <CompareBars items={[
            { label: 'Owner-occupied (individual)', value: ind.per_1k },
            { label: 'Investor / company-owned', value: inst.per_1k, hot: true },
          ]} />
        </Figure>
        <P>These are <strong>complaints</strong>, not violations or city crackdowns — the city logs
        every one the same way. The most plausible reading isn't government bias but housing
        conditions: investor-owned single-family homes are far more likely to be rentals, where an
        absentee owner and a tenant who calls it in produce exactly this signal. Tellingly, the same
        homes show <strong>no</strong> assessment gap — institutional A1 parcels are appraised at
        {' '}{inst.assessment_index.toFixed(2)}× the class norm, essentially parity. They're not taxed
        differently; they just generate more complaints.</P>
      </Section>

      {d.repeat_offenders && d.repeat_offenders.properties > 0 && (
        <Section kicker="The extreme" title="The city's named repeat offenders are corporate landlords">
          <P>At the far end of this pattern sits the city's formal <strong>repeat-offender registry</strong>
          — properties whose owners have racked up enough code violations to be required to register.
          It holds <strong>{fmt(d.repeat_offenders.properties)} properties</strong> spanning
          {' '}<strong>{fmt(d.repeat_offenders.units)} units</strong> and
          {' '}<strong>{fmt(d.repeat_offenders.violations)} total violations</strong> — and
          {' '}<strong>{d.repeat_offenders.corporate_pct}%</strong> are owned by LLCs, LPs and
          corporations, not individuals. These are large apartment complexes, concentrated in Austin's
          lower-income districts: the same investor-ownership signal from the single-family data, at its
          multifamily extreme.</P>
          <Figure title="Most-cited registered repeat offenders" source="City of Austin Repeat Offender Registrations"
            note="Active violations are those still open; total is cumulative on the registry.">
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead><tr>
                <th style={{ ...TH, textAlign: 'left' }}>Owner</th>
                <th style={TH}>Units</th><th style={TH}>Total violations</th><th style={TH}>Active</th><th style={TH}>District</th>
              </tr></thead>
              <tbody>
                {d.repeat_offenders.top.map((r, i) => (
                  <tr key={i}>
                    <td style={{ ...TD, textAlign: 'left', fontFamily: 'var(--font-sans)', fontWeight: 600, fontSize: 13 }}>{r.owner}</td>
                    <td style={TD}>{fmt(r.units)}</td>
                    <td style={{ ...TD, fontWeight: 600 }}>{fmt(r.total_violations)}</td>
                    <td style={{ ...TD, color: r.active_violations > 0 ? 'var(--flag)' : 'var(--fg-muted)' }}>{fmt(r.active_violations)}</td>
                    <td style={{ ...TD, color: 'var(--fg-muted)' }}>D{r.district}</td>
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
          { name: 'raw_code_cases', detail: 'Austin Code complaint records, joined to parcels by parcel id (~94% match, de-duplicated). Source marks all cases "Complaints".' },
          { name: 'metric_owner_treatment', detail: 'Category-stratified owner-type treatment: complaint rate and assessment index per (property class × owner type), cases windowed from 2024-01-01, attributed to the current owner.' },
          { name: 'dim_entity / parcel_entity', detail: 'Entity-resolved ownership over the TCAD 2025 roll; owner "kind" is a name heuristic.' },
          { name: 'raw_repeat_offenders', detail: 'City of Austin Repeat Offender Registrations — owner, units, active/total violations, parcel id, district.' },
        ]}
        limits={[
          'Complaint-driven, NOT city-initiated — this counts complaints the city received, not violations found or enforcement actions taken.',
          'We cannot see tenure or occupancy directly; "rental" is the most plausible mechanism, not an observed field.',
          'Complaints are attributed to the current (2025) owner, who may not have owned the property when an older case opened.',
          'Owner "kind" (individual vs institutional) is a name heuristic with residual error.',
          'Government-owned A1 (135 parcels) is shown in the data but excluded from the headline — the sample is too small to read.',
          'A screening signal about housing conditions — not a statement about any owner or any government bias.',
        ]}
        updated="cases opened 2024-01-01 onward, against the 2025 roll"
      />
    </StoryLayout>
  )
}
