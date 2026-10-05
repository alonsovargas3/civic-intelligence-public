import React, { useState, useEffect } from 'react'

/* Zero-dependency hash router. Hash routing keeps story pages working on plain
   static hosting (no server rewrite for deep links) and needs no new dependency. */

export function useHashRoute() {
  const read = () => window.location.hash.replace(/^#/, '') || '/'
  const [route, setRoute] = useState(read)
  useEffect(() => {
    const on = () => {
      setRoute(read())
      window.scrollTo(0, 0)
    }
    window.addEventListener('hashchange', on)
    return () => window.removeEventListener('hashchange', on)
  }, [])
  return route
}

export function navigate(to) {
  window.location.hash = to
}

export function Link({ to, children, style, className, onClick }) {
  return (
    <a href={`#${to}`} className={className} style={{ textDecoration: 'none', ...style }}
      onClick={onClick}>
      {children}
    </a>
  )
}
