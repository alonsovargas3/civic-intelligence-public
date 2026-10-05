import { describe, it, expect } from 'vitest'
import { resolveRoute, NAV_ITEMS } from './routes.js'

describe('resolveRoute', () => {
  it('roots at Home', () => {
    expect(resolveRoute('/', false)).toEqual({ view: 'home' })
    expect(resolveRoute('', false)).toEqual({ view: 'home' })
  })
  it('maps the primary surfaces', () => {
    expect(resolveRoute('/dashboard', false)).toEqual({ view: 'dashboard' })
    expect(resolveRoute('/stories', false)).toEqual({ view: 'stories' })
    expect(resolveRoute('/methodology', false)).toEqual({ view: 'methodology' })
    expect(resolveRoute('/about', false)).toEqual({ view: 'about' })
  })
  it('extracts a story slug', () => {
    expect(resolveRoute('/stories/who-owns-austin', false))
      .toEqual({ view: 'story', slug: 'who-owns-austin' })
  })
  it('gates /you behind static mode', () => {
    expect(resolveRoute('/you', false)).toEqual({ view: 'you' })
    expect(resolveRoute('/you', true)).toEqual({ view: 'dashboard' })
  })
  it('falls back to Home for unknown routes', () => {
    expect(resolveRoute('/nope', false)).toEqual({ view: 'home' })
  })
  it('exposes the five top-nav items in order', () => {
    expect(NAV_ITEMS.map((i) => i.key))
      .toEqual(['home', 'dashboard', 'stories', 'methodology', 'about'])
    expect(NAV_ITEMS.find((i) => i.key === 'dashboard').to).toBe('/dashboard')
  })
})
