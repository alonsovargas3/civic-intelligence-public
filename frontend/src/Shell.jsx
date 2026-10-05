import React from 'react'
import { BrandMark } from './Primitives.jsx'
import { Link } from './router.jsx'
import { NAV_ITEMS } from './routes.js'
import { BRAND_NAME, BRAND_DOMAIN, BRAND_TAGLINE, BRAND_FOOTER } from './brand.js'
import { STATIC } from './config.js'

/* Shared top navigation. variant 'slate' sits transparent over the Home hero
   band; variant 'light' is a white bar on inner pages. `active` is a NAV_ITEMS
   key that gets the underline. */
export function TopNav({ variant = 'light', active }) {
  const slate = variant === 'slate'
  const wordColor = slate ? 'var(--on-slate)' : 'var(--ink)'
  const linkColor = slate ? 'var(--on-slate-muted)' : 'var(--fg-muted)'
  const activeColor = slate ? 'var(--on-slate)' : 'var(--ink)'
  const underline = slate ? 'var(--amber)' : 'var(--accent)'
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 28, padding: '16px 36px',
      background: slate ? 'transparent' : 'var(--surface)',
      borderBottom: slate ? '1px solid rgba(246,244,239,.15)' : '1px solid var(--hairline)',
    }}>
      <Link to="/" style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <BrandMark size={26} />
        <span style={{ font: '800 16px/1 var(--font-sans)', letterSpacing: '-.01em', color: wordColor }}>
          {BRAND_NAME}
        </span>
      </Link>
      <nav style={{ display: 'flex', gap: 22, marginLeft: 20 }}>
        {NAV_ITEMS.map((item) => {
          const on = item.key === active
          return (
            <Link key={item.key} to={item.to} style={{
              font: `${on ? 700 : 600} 13px/1 var(--font-sans)`,
              color: on ? activeColor : linkColor,
              borderBottom: on ? `2px solid ${underline}` : '2px solid transparent',
              paddingBottom: 3, whiteSpace: 'nowrap',
            }}>{item.label}</Link>
          )
        })}
        {!STATIC && (
          <Link to="/you" style={{
            font: `${active === 'you' ? 700 : 600} 13px/1 var(--font-sans)`,
            color: active === 'you' ? activeColor : linkColor,
            borderBottom: active === 'you' ? `2px solid ${underline}` : '2px solid transparent',
            paddingBottom: 3, whiteSpace: 'nowrap',
          }}>Your address</Link>
        )}
      </nav>
      <span style={{
        marginLeft: 'auto', flex: 'none', display: 'inline-flex', alignItems: 'center', gap: 8,
        whiteSpace: 'nowrap', font: '600 12px/1 var(--font-sans)',
        color: slate ? 'var(--sage)' : 'var(--positive)',
      }}>
        <span style={{ width: 7, height: 7, borderRadius: '50%', background: 'currentColor' }} />
        {BRAND_TAGLINE}
      </span>
    </div>
  )
}

/* Shared slate footer band. */
export function SiteFooter() {
  return (
    <div style={{ background: 'var(--slate)' }}>
      <div style={{
        maxWidth: 1200, margin: '0 auto', display: 'flex', alignItems: 'center',
        gap: 24, padding: '20px 36px', flexWrap: 'wrap',
      }}>
        <span style={{ font: '700 13px/1 var(--font-sans)', color: 'var(--on-slate)' }}>{BRAND_NAME}</span>
        <span style={{ font: '400 12px/1.4 var(--font-sans)', color: 'var(--on-slate-muted)' }}>{BRAND_FOOTER}</span>
        <span style={{ marginLeft: 'auto', font: '500 11px/1 var(--font-mono)', color: 'var(--on-slate-muted)' }}>{BRAND_DOMAIN}</span>
      </div>
    </div>
  )
}
