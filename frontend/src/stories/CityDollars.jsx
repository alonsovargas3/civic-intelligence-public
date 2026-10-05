import React, { useEffect, useState } from 'react'
import StoryLayout, { Section, P, PullStat, StatStrip, Figure, VBarChart, StoryFooter } from './StoryLayout.jsx'
import { getStoryCityDollars } from '../api.js'

const billions = (b) => `$${Number(b).toFixed(b >= 10 ? 1 : 2)}B`
const millions = (m) => (m >= 1000 ? `$${(m / 1000).toFixed(2)}B` : `$${Math.round(m)}M`)

const TH = { font: '600 11px/1 var(--font-sans)', letterSpacing: '.05em', textTransform: 'uppercase', color: 'var(--fg-muted)', textAlign: 'right', padding: '0 0 10px' }
const TD = { font: '500 13.5px/1.3 var(--font-mono)', fontVariantNumeric: 'tabular-nums', color: 'var(--ink)', textAlign: 'right', padding: '10px 0', borderTop: '1px solid var(--hairline)' }
const TD_L = { ...TD, textAlign: 'left', font: '600 13.5px/1.25 var(--font-sans)' }

function DeptBars({ rows }) {
  const max = Math.max(...rows.map((r) => r.amount_b))
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 9 }}>
      {rows.map((r) => {
        const isDebt = /debt service/i.test(r.dept)
        return (
          <div key={r.dept} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ flex: '0 0 220px', font: '500 13px/1.25 var(--font-sans)', color: isDebt ? 'var(--ink)' : 'var(--fg)', fontWeight: isDebt ? 700 : 500 }}>{r.dept}</span>
            <div style={{ flex: 1, height: 14, background: 'var(--surface-3)', borderRadius: 'var(--r-sm)', overflow: 'hidden' }}>
              <div style={{ width: `${Math.max(2, (r.amount_b / max) * 100)}%`, height: '100%', background: isDebt ? 'var(--primary-ink)' : 'var(--blue-4)', borderRadius: 'var(--r-sm)' }} />
            </div>
            <span style={{ flex: '0 0 54px', textAlign: 'right', font: '600 13px var(--font-mono)', color: 'var(--ink)', fontVariantNumeric: 'tabular-nums' }}>{billions(r.amount_b)}</span>
          </div>
        )
      })}
    </div>
  )
}

export default function CityDollars() {
  const [d, setD] = useState(null)
  const [err, setErr] = useState(null)
  useEffect(() => { getStoryCityDollars().then(setD).catch(() => setErr('Could not load spending data.')) }, [])

  if (err) return <StoryLayout title="Where your city dollars actually go"><P style={{ color: 'var(--flag)' }}>{err}</P></StoryLayout>
  if (!d) return <StoryLayout title="Where your city dollars actually go"><P style={{ color: 'var(--fg-muted)' }}>Loading the checkbook…</P></StoryLayout>

  const t = d.totals
  const debtShare = (t.debt_b / t.total_b)
  const latest = d.by_year[d.by_year.length - 1]
  const y2010 = d.by_year.find((y) => y.year === '2010') || d.by_year[0]
  const growth = (latest.amount_b / y2010.amount_b).toFixed(1)
  const bars = d.by_year.map((y) => ({
    value: y.amount_b,
    valueText: '',
    label: y.year.slice(2),
    highlight: y.year === latest.year,
  }))

  return (
    <StoryLayout
      eyebrow="Money · Spending"
      title="Where your city dollars actually go"
      dek="Austin has written more than $37 billion in checks since 2008. Follow the biggest flows and a lot of it isn't day-to-day services at all — it's debt repayment and a short list of large construction and engineering firms."
      sources={['Austin Finance Online eCheckbook', '2008–present', 'Department + vendor legal name']}
    >
      <StatStrip items={[
        { value: billions(t.total_b), label: 'Total disbursed', sub: `${t.min_year}–${t.max_year}` },
        { value: billions(t.debt_b), label: 'Debt service', sub: `${(debtShare * 100).toFixed(0)}% of all spending` },
        { value: billions(latest.amount_b), label: `Spent in ${latest.year}`, sub: `up from ${billions(y2010.amount_b)} in 2010` },
      ]} />

      <Section>
        <P>The city of Austin publishes every check and electronic payment it sends, going back to
        2008 — a public ledger of more than $37 billion. Add it up by where it went, and the picture
        is less about police, parks and potholes than you might expect.</P>
      </Section>

      <Section kicker="The trend" title="Spending has nearly tripled in fifteen years">
        <P>Annual disbursements rose from about {billions(y2010.amount_b)} in 2010 to
        {' '}{billions(latest.amount_b)} in {latest.year} — roughly <strong>{growth}×</strong> — as the
        city grew, borrowed and built.</P>
        <Figure title="City disbursements per calendar year ($ billions)" source="Austin eCheckbook, calendar-year totals (2008–2025)"
          note="2026 is excluded as a partial year.">
          <VBarChart bars={bars} height={230} axisLeft="2008" axisRight={latest.year} />
        </Figure>
      </Section>

      <Section kicker="The biggest line" title="More goes to debt than to any department">
        <P>The single largest slice isn't an operating department — it's <strong>debt service</strong>,
        the principal and interest on the bonds that fund water mains, roads and the airport. It
        totals {billions(t.debt_b)}, about {(debtShare * 100).toFixed(0)}% of all spending, and the two
        debt-service funds top the department ranking outright.</P>
        <Figure title="Top departments by total disbursed, 2008–present" source="Austin eCheckbook, by paying department">
          <DeptBars rows={d.by_department} />
        </Figure>
      </Section>

      <Section kicker="The recipients" title="Behind the debt, who the city pays">
        <P>Set debt service aside and the largest payments go to a recognizable cast: heavy
        construction and engineering firms building the capital program, a title company handling land
        acquisition, the regional transit partnership, and technology vendors. (Financial institutions
        still appear here as card and banking settlements, and some recipients are other governments
        on joint projects.)</P>
        <Figure title="Largest non-debt-service vendors, 2008–present" source="Austin eCheckbook, vendor legal name, excluding debt-service departments">
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr>
              <th style={{ ...TH, textAlign: 'left' }}>Vendor (legal payee)</th>
              <th style={TH}>Total paid</th>
            </tr></thead>
            <tbody>
              {d.top_vendors_operating.map((v) => (
                <tr key={v.vendor}>
                  <td style={TD_L}>{v.vendor}</td>
                  <td style={{ ...TD, fontWeight: 600 }}>{millions(v.amount_m)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Figure>
      </Section>

      <StoryFooter
        methodology={d.methodology}
        sources={[
          { name: 'raw_afo_checkbook', detail: 'Austin Finance Online eCheckbook (Socrata dataset 8c6z-qnmj) — every city disbursement since 2008, with paying department, fund, object code and vendor legal name.' },
        ]}
        limits={[
          d.caveat,
          '"Vendor" is the legal payee: banks appear as bond trustees or card/settlement processors, not as suppliers.',
          'Some recipients are other governments (Travis County, TxDOT) paid for joint projects.',
          'Descriptive only — this shows where money flows, not whether any individual payment was proper or competitively bid.',
        ]}
        updated="the latest eCheckbook refresh"
      />
    </StoryLayout>
  )
}
