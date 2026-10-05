// Pure route resolution for the hash router. Keeps App.jsx declarative and
// makes routing unit-testable without a DOM renderer.

export const NAV_ITEMS = [
  { key: 'home', label: 'Home', to: '/' },
  { key: 'dashboard', label: 'Dashboard', to: '/dashboard' },
  { key: 'stories', label: 'Stories', to: '/stories' },
  { key: 'methodology', label: 'Methodology', to: '/methodology' },
  { key: 'about', label: 'About', to: '/about' },
]

export function resolveRoute(route, isStatic) {
  const r = route || '/'
  if (r === '/') return { view: 'home' }
  if (r === '/dashboard') return { view: 'dashboard' }
  if (r === '/stories') return { view: 'stories' }
  if (r.startsWith('/stories/')) return { view: 'story', slug: r.slice('/stories/'.length) }
  if (r === '/methodology') return { view: 'methodology' }
  if (r === '/about') return { view: 'about' }
  if (r === '/you') return isStatic ? { view: 'dashboard' } : { view: 'you' }
  return { view: 'home' }
}
