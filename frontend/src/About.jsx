import React from 'react'
import { TopNav, SiteFooter } from './Shell.jsx'
import { Link } from './router.jsx'
import { BRAND_NAME } from './brand.js'

const PILLARS = [
  { t: 'Independent & non-partisan', d: 'No party, campaign, candidate, or advocacy group funds or directs this work. We take no policy positions and endorse no one.' },
  { t: 'Public data only', d: 'Every number comes from records anyone can request: City of Austin open data, the Travis County appraisal roll, City Clerk campaign-finance filings, and the Legistar agenda system.' },
  { t: 'The working, published', d: 'Each figure links to its source dataset, the query behind it, and its limits. Statistical anomalies are screening signals for review — never accusations.' },
]

export default function About() {
  return (
    <div style={{ minHeight: '100vh', overflowY: 'auto', display: 'flex', flexDirection: 'column', background: 'var(--canvas)' }}>
      <TopNav variant="light" active="about" />
      <div style={{ maxWidth: 840, margin: '0 auto', width: '100%', boxSizing: 'border-box', padding: '52px 36px 56px', display: 'flex', flexDirection: 'column', gap: 36 }}>
        <div>
          <p style={{ font: '600 12px/1 var(--font-sans)', letterSpacing: '.1em', textTransform: 'uppercase', color: 'var(--orange)', margin: '0 0 12px' }}>About</p>
          <h1 style={{ font: '800 40px/1.12 var(--font-sans)', letterSpacing: '-.02em', color: 'var(--ink)', margin: '0 0 14px' }}>Austin's public record, read in the open</h1>
          <p style={{ font: '400 16px/1.6 var(--font-sans)', color: 'var(--fg)', margin: 0, textWrap: 'pretty' }}>
            {BRAND_NAME} crosses Austin's open datasets — property, spending, permits, campaign finance, 311, crime and council votes — and publishes the working alongside the number. One story a week, no sides taken. The goal is a civic record readers can check for themselves.
          </p>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16 }}>
          {PILLARS.map((p) => (
            <div key={p.t} style={{ background: 'var(--surface)', border: '1px solid var(--hairline)', borderRadius: 12, padding: 22 }}>
              <p style={{ font: '700 16px/1.3 var(--font-sans)', color: 'var(--ink)', margin: '0 0 8px' }}>{p.t}</p>
              <p style={{ font: '400 13.5px/1.55 var(--font-sans)', color: 'var(--fg-muted)', margin: 0, textWrap: 'pretty' }}>{p.d}</p>
            </div>
          ))}
        </div>

        <div>
          <h2 style={{ font: '700 22px/1.25 var(--font-sans)', color: 'var(--ink)', margin: '0 0 12px' }}>How to read the work</h2>
          <p style={{ font: '400 15px/1.6 var(--font-sans)', color: 'var(--fg)', margin: '0 0 12px', textWrap: 'pretty' }}>
            Start with the <Link to="/dashboard" style={{ color: 'var(--accent-deep)', fontWeight: 700 }}>dashboard</Link> to see crime and 311 by council district and ZIP, or browse the <Link to="/stories" style={{ color: 'var(--accent-deep)', fontWeight: 700 }}>stories</Link> for sourced narrative reads. Every story ends with its data provenance and a plain list of what it does not show. The full sourcing rules live in the <Link to="/methodology" style={{ color: 'var(--accent-deep)', fontWeight: 700 }}>methodology</Link>.
          </p>
        </div>

        <div>
          <h2 style={{ font: '700 22px/1.25 var(--font-sans)', color: 'var(--ink)', margin: '0 0 10px' }}>Contact</h2>
          <p style={{ font: '400 15px/1.6 var(--font-sans)', color: 'var(--fg)', margin: 0, textWrap: 'pretty' }}>
            Corrections and questions: open an issue in this project's source repository. If a number is wrong, we want to know — corrections are published on the story they amend, with a dated note.
          </p>
        </div>
      </div>
      <div style={{ marginTop: 'auto' }}><SiteFooter /></div>
    </div>
  )
}
