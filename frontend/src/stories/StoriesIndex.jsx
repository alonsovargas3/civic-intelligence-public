import React from 'react'
import { STORY_BY_SLUG } from './index.jsx'
import { Link } from '../router.jsx'
import { Icon, Badge } from '../Primitives.jsx'
import { TopNav, SiteFooter } from '../Shell.jsx'

/* Themed front door. Each theme lists story slugs; order here defines the page. */
const THEMES = [
  {
    name: 'Who owns Austin',
    intro: 'Property is the city’s deepest divide of wealth and power — who holds it, who’s taxed on it, and who builds it.',
    slugs: ['who-owns-austin', 'homestead-cap', 'investor-single-family', 'home-builders', 'short-term-rentals'],
  },
  {
    name: 'Money & influence',
    intro: 'Following the money through City Hall — contracts, votes, lobbying, ballot campaigns and the checkbook.',
    slugs: ['money-influence', 'who-lobbies', 'ballot-money', 'local-money', 'who-pays', 'where-city-dollars-go'],
  },
  {
    name: 'Equity & representation',
    intro: 'Whether the city treats its districts alike — in services, in policing, and in how the council votes.',
    slugs: ['district-divide', 'service-equity', 'council-dissent'],
  },
  {
    name: 'Streets & safety',
    intro: 'The human toll on Austin’s roads.',
    slugs: ['traffic-deaths'],
  },
  {
    name: 'City services',
    intro: 'The everyday machinery residents actually touch.',
    slugs: ['animal-shelter', 'food-inspections'],
  },
]

/* A few stories to lead with (topics only; figures load from the data). */
const HIGHLIGHTS = [
  { slug: 'homestead-cap', stat: 'Taxes', label: 'How the homestead cap affects taxable value' },
  { slug: 'who-lobbies', stat: 'Lobbying', label: 'Who registers to lobby City Hall, by industry' },
  { slug: 'traffic-deaths', stat: 'Safety', label: 'Crash and traffic-fatality trends' },
  { slug: 'money-influence', stat: 'Money', label: 'Contributions, council votes and city contracts' },
]

export default function StoriesIndex() {
  return (
    <div style={{ height: '100vh', overflowY: 'auto', background: 'var(--canvas)' }}>
      <TopNav variant="light" active="stories" />

      <div style={{ maxWidth: 1000, margin: '0 auto', padding: '56px 24px 96px' }}>
        {/* Hero */}
        <header style={{ maxWidth: 720 }}>
          <div className="cii-eyebrow" style={{ marginTop: 16 }}>Data stories</div>
          <h1 style={{ font: '800 42px/1.07 var(--font-sans)', letterSpacing: '-.02em', color: 'var(--ink)', margin: '12px 0 0' }}>
            What Austin&rsquo;s open data shows
          </h1>
          <p style={{ font: '400 19px/1.55 var(--font-sans)', color: 'var(--fg-muted)', margin: '18px 0 0', textWrap: 'pretty' }}>
            Sourced, narrative reads built by crossing Austin&rsquo;s public datasets — property, spending,
            permits, campaign finance, council votes, code complaints and more. Every number comes from a
            query against the open-data warehouse and carries its methodology and limits. We publish
            screening signals and the working behind them — not accusations.
          </p>
        </header>

        {/* Headline findings */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 14, marginTop: 36 }}>
          {HIGHLIGHTS.map((h) => {
            const s = STORY_BY_SLUG[h.slug]
            if (!s) return null
            return (
              <Link key={h.slug} to={`/stories/${h.slug}`} style={{
                display: 'flex', flexDirection: 'column', gap: 8, padding: '18px 18px 20px',
                borderRadius: 'var(--r-lg)', background: 'var(--surface)', border: '1px solid var(--hairline)',
                boxShadow: 'var(--shadow-sm)',
              }}>
                <div style={{ font: '700 32px/1 var(--font-mono)', letterSpacing: '-.02em', color: 'var(--accent-deep)', fontVariantNumeric: 'tabular-nums' }}>{h.stat}</div>
                <div style={{ font: '400 13px/1.45 var(--font-sans)', color: 'var(--fg-muted)', textWrap: 'pretty' }}>{h.label}</div>
                <span style={{ marginTop: 'auto', paddingTop: 4, font: '600 12px/1.3 var(--font-sans)', color: 'var(--ink)' }}>{s.title}</span>
              </Link>
            )
          })}
        </div>

        {/* Themed sections */}
        {THEMES.map((t) => (
          <section key={t.name} style={{ marginTop: 52 }}>
            <h2 style={{ font: '700 22px/1.2 var(--font-sans)', letterSpacing: '-.01em', color: 'var(--ink)', margin: 0 }}>{t.name}</h2>
            <p style={{ font: '400 15px/1.5 var(--font-sans)', color: 'var(--fg-muted)', margin: '6px 0 0', maxWidth: 680, textWrap: 'pretty' }}>{t.intro}</p>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 16, marginTop: 18 }}>
              {t.slugs.map((slug) => {
                const s = STORY_BY_SLUG[slug]
                if (!s) return null
                return <StoryCard key={slug} story={s} />
              })}
            </div>
          </section>
        ))}
      </div>
      <SiteFooter />
    </div>
  )
}

function StoryCard({ story }) {
  const planned = story.status !== 'published'
  const inner = (
    <div style={{
      height: '100%', display: 'flex', flexDirection: 'column', gap: 9,
      padding: '18px 20px 20px', borderRadius: 'var(--r-lg)',
      background: 'var(--surface)', border: '1px solid var(--hairline)',
      boxShadow: 'var(--shadow-sm)', opacity: planned ? 0.62 : 1,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span className="cii-eyebrow">{story.eyebrow}</span>
        {planned && <span style={{ marginLeft: 'auto' }}><Badge tone="muted">Coming soon</Badge></span>}
      </div>
      <div style={{ font: '700 19px/1.22 var(--font-sans)', letterSpacing: '-.01em', color: 'var(--ink)' }}>{story.title}</div>
      <div style={{ font: '400 14px/1.5 var(--font-sans)', color: 'var(--fg-muted)', textWrap: 'pretty' }}>{story.dek}</div>
      {!planned && (
        <span style={{ marginTop: 'auto', paddingTop: 6, display: 'inline-flex', alignItems: 'center', gap: 6, font: '600 13px/1 var(--font-sans)', color: 'var(--accent-deep)' }}>
          Read <Icon name="chevron-down" size={15} style={{ transform: 'rotate(-90deg)' }} />
        </span>
      )}
    </div>
  )
  if (planned) return inner
  return <Link to={`/stories/${story.slug}`}>{inner}</Link>
}
