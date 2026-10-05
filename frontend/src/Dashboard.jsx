import React, { useState, useRef } from 'react'
import MapStage from './MapStage.jsx'
import DataPanel from './DataPanel.jsx'
import Methods from './Methods.jsx'
import Flags from './Flags.jsx'
import OwnerType from './OwnerType.jsx'
import CouncilPanel from './CouncilPanel.jsx'
import { Tabs, Icon } from './Primitives.jsx'
import { TopNav } from './Shell.jsx'
import { Link } from './router.jsx'
import { STORIES } from './stories/index.jsx'
import { STATIC } from './config.js'
import { visibleTabs } from './nav.js'

/* Compact list of published data stories for the dashboard side panel. */
function StoriesPanel() {
  const published = STORIES.filter((s) => s.status === 'published')
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div>
        <div className="cii-eyebrow">Data stories</div>
        <h2 className="cii-h2" style={{ marginTop: 4 }}>What the data shows</h2>
        <p className="cii-small" style={{ marginTop: 6 }}>
          Sourced narrative reads built by crossing Austin's open datasets. Each opens as a full page.
        </p>
      </div>
      {published.map((s) => (
        <Link key={s.slug} to={`/stories/${s.slug}`} style={{
          display: 'block', padding: '12px 14px', borderRadius: 'var(--r-md)',
          background: 'var(--surface)', border: '1px solid var(--hairline)',
        }}>
          <div className="cii-eyebrow" style={{ marginBottom: 4 }}>{s.eyebrow}</div>
          <div style={{ font: '700 14.5px/1.25 var(--font-sans)', color: 'var(--ink)', marginBottom: 4 }}>{s.title}</div>
          <div className="cii-footnote" style={{ color: 'var(--fg-muted)' }}>{s.dek}</div>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, marginTop: 8, font: '600 12px/1 var(--font-sans)', color: 'var(--accent-deep)' }}>
            Read <Icon name="chevron-down" size={13} style={{ transform: 'rotate(-90deg)' }} />
          </span>
        </Link>
      ))}
    </div>
  )
}

export default function Dashboard() {
  const [dataset, setDataset] = useState('crime')
  const [year, setYear] = useState('2025')
  const [selected, setSelected] = useState(null)
  const [tab, setTab] = useState('data')
  const [view, setView] = useState('districts')   // map geography: 'districts' | 'zips'
  const panelRef = useRef(null)

  function handleSelect(d) {
    setSelected((prev) => (prev === d ? null : d))
    setTab('data')
    if (panelRef.current) panelRef.current.scrollTop = 0
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', background: 'var(--canvas)' }}>
      <TopNav variant="light" active="dashboard" />
      <div style={{ flex: 1, minHeight: 0, display: 'grid', gridTemplateColumns: '1fr 384px' }}>
        <div style={{ minWidth: 0, position: 'relative' }}>
          <MapStage dataset={dataset} setDataset={setDataset} year={year} setYear={setYear}
            selected={selected} onSelect={handleSelect} view={view} setView={setView} />
        </div>
        <aside style={{ display: 'flex', flexDirection: 'column', minHeight: 0, background: 'var(--surface)', borderLeft: '1px solid var(--hairline)' }}>
          <div style={{ flex: '0 0 auto', padding: '0 16px' }}>
            <Tabs tabs={visibleTabs(STATIC)} value={tab} onChange={setTab} />
          </div>
          <div ref={panelRef} style={{ flex: 1, minHeight: 0, overflowY: 'auto', padding: 20 }}>
            {tab === 'data' && <DataPanel dataset={dataset} year={year} selected={selected} onSelect={handleSelect} />}
            {tab === 'stories' && <StoriesPanel />}
            {tab === 'methods' && <Methods metric={dataset} />}
            {tab === 'equity' && <Flags />}
            {tab === 'owners' && <OwnerType />}
            {tab === 'council' && <CouncilPanel />}
          </div>
        </aside>
      </div>
    </div>
  )
}
