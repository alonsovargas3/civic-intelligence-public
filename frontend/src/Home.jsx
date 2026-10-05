import React from 'react'
import { TopNav, SiteFooter } from './Shell.jsx'
import { Link } from './router.jsx'

const STATS = [
  { v: 'Property', l: 'Travis County appraisal roll' },
  { v: 'Spending', l: 'City of Austin checkbook' },
  { v: 'Lobbying', l: 'City Hall lobbyist registrations' },
  { v: '311', l: 'Austin 311 service requests' },
]

const ARCHIVE = [
  { slug: 'who-owns-austin', kicker: 'PROPERTY · OWNERSHIP', title: 'Who Owns Austin',
    dek: 'Property ownership on the Travis County appraisal roll, by owner type.', border: 'var(--slate-blue)' },
  { slug: 'who-pays', kicker: 'MONEY · ELECTIONS', title: 'Who pays for Austin politics',
    dek: 'How Austin campaign contributions are distributed by gift size.', border: 'var(--orange)' },
  { slug: 'animal-shelter', kicker: 'CITY SERVICES · ANIMALS', title: 'Austin Animal Center outcomes',
    dek: 'Intakes and outcomes at Austin Animal Center, including the live-release rate.', border: 'var(--sage)' },
]

export default function Home() {
  return (
    <div style={{ minHeight: '100vh', overflowY: 'auto', display: 'flex', flexDirection: 'column', background: 'var(--canvas)' }}>
      {/* Slate hero band (nav + hero + this-week strip) */}
      <div style={{ background: 'var(--slate)' }}>
        <div style={{ maxWidth: 1200, margin: '0 auto' }}>
          <TopNav variant="slate" active="home" />
        </div>
        <div style={{ position: 'relative', overflow: 'hidden' }}>
          <div style={{ maxWidth: 1200, margin: '0 auto', position: 'relative', padding: '64px 36px 56px' }}>
            <div style={{ position: 'relative', maxWidth: 760 }}>
              <p style={{ font: '600 12px/1 var(--font-sans)', letterSpacing: '.1em', textTransform: 'uppercase', color: 'var(--amber)', margin: '0 0 16px' }}>
                Non-partisan · independent · every method published
              </p>
              <h1 style={{ font: '800 56px/1.05 var(--font-sans)', letterSpacing: '-.02em', color: 'var(--on-slate)', margin: '0 0 20px', textWrap: 'pretty' }}>
                Public data, read without a thumb on the scale.
              </h1>
              <p style={{ font: '400 17px/1.6 var(--font-sans)', color: '#ccd2dd', margin: '0 0 28px', maxWidth: 600, textWrap: 'pretty' }}>
                Austin's open records — property, money, permits, 311, crime — crossed and published piece by piece. We show the working; you draw the conclusions.
              </p>
              <div style={{ display: 'flex', gap: 12 }}>
                <Link to="/dashboard" style={{ font: '700 14px/1 var(--font-sans)', color: 'var(--slate)', background: 'var(--amber)', padding: '12px 22px', borderRadius: 8 }}>Explore the dashboard</Link>
                <Link to="/methodology" style={{ font: '700 14px/1 var(--font-sans)', color: 'var(--on-slate)', border: '1px solid rgba(246,244,239,.4)', padding: '12px 22px', borderRadius: 8 }}>How we work</Link>
              </div>
            </div>
          </div>
        </div>
        <div style={{ background: 'rgba(0,0,0,.18)' }}>
          <div style={{ maxWidth: 1200, margin: '0 auto', display: 'flex', alignItems: 'center', gap: 14, padding: '14px 36px', flexWrap: 'wrap' }}>
            <span style={{ flex: 'none', font: '600 10.5px/1 var(--font-mono)', letterSpacing: '.07em', color: 'var(--slate)', background: 'var(--amber)', padding: '4px 9px', borderRadius: 999 }}>FEATURED</span>
            <span style={{ font: '600 14px/1 var(--font-sans)', color: 'var(--on-slate)' }}>The homestead cap</span>
            <span style={{ font: '400 13px/1 var(--font-sans)', color: '#8f99ac' }}>·</span>
            <span style={{ font: '400 13px/1 var(--font-sans)', color: 'var(--on-slate-muted)' }}>Also: Who lobbies City Hall</span>
            <Link to="/stories" style={{ marginLeft: 'auto', font: '700 13px/1 var(--font-sans)', color: 'var(--amber)' }}>Read →</Link>
          </div>
        </div>
      </div>

      {/* Stat band */}
      <div style={{ background: 'var(--surface)', borderBottom: '1px solid var(--hairline)' }}>
        <div style={{ maxWidth: 1200, margin: '0 auto', display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)' }}>
          {STATS.map((s, i) => (
            <div key={i} style={{ padding: '26px 28px', borderRight: i < 3 ? '1px solid var(--hairline)' : 'none' }}>
              <p style={{ font: '600 34px/1 var(--font-mono)', color: 'var(--ink)', margin: '0 0 8px', letterSpacing: '-.02em' }}>{s.v}</p>
              <p style={{ font: '400 13px/1.45 var(--font-sans)', color: 'var(--fg-muted)', margin: 0 }}>{s.l}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Promo row: dashboard + methodology */}
      <div style={{ maxWidth: 1200, margin: '0 auto', width: '100%', boxSizing: 'border-box', display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 20, padding: 36 }}>
        <Link to="/dashboard" style={{ background: 'var(--surface)', border: '1px solid var(--hairline)', borderRadius: 12, overflow: 'hidden', display: 'grid', gridTemplateColumns: '1fr' }}>
          <div style={{ padding: 28, display: 'flex', flexDirection: 'column', gap: 10, justifyContent: 'center' }}>
            <p className="cii-eyebrow" style={{ margin: 0 }}>The dashboard</p>
            <h3 style={{ font: '800 22px/1.2 var(--font-sans)', color: 'var(--ink)', margin: 0 }}>Every district, every ZIP</h3>
            <p style={{ font: '400 14px/1.55 var(--font-sans)', color: 'var(--fg)', margin: 0 }}>Crime and 311 mapped to council districts; assessment and ownership signals by ZIP.</p>
            <span style={{ font: '700 14px/1 var(--font-sans)', color: 'var(--accent-deep)' }}>Open the map →</span>
          </div>
        </Link>
        <Link to="/methodology" style={{ background: 'var(--surface)', border: '1px solid var(--hairline)', borderRadius: 12, padding: '26px 28px', display: 'flex', flexDirection: 'column', gap: 12 }}>
          <p className="cii-eyebrow" style={{ margin: 0 }}>How we work</p>
          <h3 style={{ font: '800 22px/1.2 var(--font-sans)', color: 'var(--ink)', margin: 0 }}>Methodology first</h3>
          <p style={{ font: '400 14px/1.55 var(--font-sans)', color: 'var(--fg)', margin: 0, textWrap: 'pretty' }}>Every number links to its source dataset, its query, and its limits. Screening signals are labeled as signals — never findings.</p>
          <span style={{ font: '700 14px/1 var(--font-sans)', color: 'var(--accent-deep)', marginTop: 'auto' }}>Read the methodology →</span>
        </Link>
      </div>

      {/* From the archive */}
      <div style={{ maxWidth: 1200, margin: '0 auto', width: '100%', boxSizing: 'border-box', padding: '0 36px 40px' }}>
        <p className="cii-eyebrow" style={{ margin: '0 0 14px' }}>From the archive</p>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16 }}>
          {ARCHIVE.map((a) => (
            <Link key={a.slug} to={`/stories/${a.slug}`} style={{ background: 'var(--surface)', border: '1px solid var(--hairline)', borderTop: `3px solid ${a.border}`, borderRadius: 12, padding: '20px 22px', display: 'flex', flexDirection: 'column', gap: 8 }}>
              <p style={{ font: '600 10.5px/1 var(--font-mono)', letterSpacing: '.06em', color: 'var(--fg-subtle)', margin: 0 }}>{a.kicker}</p>
              <p style={{ font: '700 17px/1.3 var(--font-sans)', color: 'var(--ink)', margin: 0 }}>{a.title}</p>
              <p style={{ font: '400 13px/1.5 var(--font-sans)', color: 'var(--fg-muted)', margin: 0 }}>{a.dek}</p>
              <span style={{ font: '700 13px/1 var(--font-sans)', color: 'var(--accent-deep)', marginTop: 4 }}>Read →</span>
            </Link>
          ))}
        </div>
      </div>

      <div style={{ marginTop: 'auto' }}><SiteFooter /></div>
    </div>
  )
}
