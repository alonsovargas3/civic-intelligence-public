import React from 'react'
import { TopNav, SiteFooter } from './Shell.jsx'
import { Link } from './router.jsx'

export default function PublicUnavailable() {
  return <div style={{ minHeight: '100vh', background: 'var(--canvas)' }}>
    <TopNav variant="light" active="stories" />
    <main style={{ maxWidth: 720, margin: '0 auto', padding: 36 }}>
      <h1 className="cii-h2">Story data unavailable</h1>
      <p role="status" className="cii-body">This source-code snapshot includes no approved public analytical data package. Story results are unavailable in this build.</p>
      <Link to="/stories">Browse story topics</Link>
    </main>
    <SiteFooter />
  </div>
}
