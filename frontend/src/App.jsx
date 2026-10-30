import React, { lazy, Suspense } from 'react'
import Home from './Home.jsx'
import Methodology from './Methodology.jsx'
import About from './About.jsx'
import StoriesIndex from './stories/StoriesIndex.jsx'
import { STORY_BY_SLUG } from './stories/index.jsx'
import { useHashRoute } from './router.jsx'
import { resolveRoute } from './routes.js'
import You from './You.jsx'
import { STATIC } from './config.js'
import PublicUnavailable from './PublicUnavailable.jsx'

// Keep the map and its dependencies off the initial page; /dashboard remains
// available in both static and live builds.
const Dashboard = lazy(() => import('./Dashboard.jsx'))

export default function App() {
  const route = useHashRoute()
  const { view, slug } = resolveRoute(route, STATIC)

  switch (view) {
    case 'home': return <Home />
    case 'dashboard': return <Suspense fallback={<div role="status">Loading dashboard…</div>}><Dashboard /></Suspense>
    case 'methodology': return <Methodology />
    case 'about': return <About />
    case 'stories': return <StoriesIndex />
    case 'you': return <You />
    case 'story': {
      if (STATIC) return <PublicUnavailable />
      const story = STORY_BY_SLUG[slug]
      if (story && story.Component) {
        const Page = story.Component
        return <Page />
      }
      return <StoriesIndex />
    }
    default: return <Home />
  }
}
