import React, { useState, useRef, useEffect } from 'react'
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
import { getDashboardAvailability, getIncidents } from './api.js'
import { availableYears, firstChoice, rankingError } from './dashboardData.js'

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
  const [availability, setAvailability] = useState(STATIC ? null : { choices: { crime: ['2025', '2024', '2023'], '311': ['2025', '2024', '2023'] }, features: { methods: true, owners: true, council: true, zips: true } })
  const [availabilityError, setAvailabilityError] = useState(null)
  const [ranking, setRanking] = useState({ key: null, rows: null, error: null, loading: true })

  useEffect(() => {
    if (!STATIC) return
    let active = true
    getDashboardAvailability().then((manifest) => {
      if (!active) return
      if (!manifest || !manifest.choices || !manifest.features) throw new Error('Invalid dashboard availability manifest')
      setAvailability(manifest)
      const choice = firstChoice(manifest)
      if (choice) { setDataset(choice.dataset); setYear(choice.year) }
    }).catch(() => { if (active) setAvailabilityError('Dashboard data availability could not be verified for this edition.') })
    return () => { active = false }
  }, [])

  const choiceAvailable = availability && availableYears(availability, dataset).includes(year)
  const rankingKey = `${dataset}:${year}`
  const currentRanking = ranking.key === rankingKey ? ranking : { rows: null, error: null, loading: true }
  useEffect(() => {
    if (!choiceAvailable) { setRanking({ key: rankingKey, rows: null, error: null, loading: false }); return }
    let active = true
    setRanking({ key: rankingKey, rows: null, error: null, loading: true })
    getIncidents(dataset, year).then((rows) => {
      if (!active) return
      const error = rankingError(rows)
      setRanking({ key: rankingKey, rows: error ? null : rows, error, loading: false })
    }).catch(() => { if (active) setRanking({ key: rankingKey, rows: null, error: 'District ranking could not be loaded.', loading: false }) })
    return () => { active = false }
  }, [dataset, year, choiceAvailable])

  function changeDataset(next) {
    const nextYears = availableYears(availability, next)
    if (!nextYears.length) return
    setDataset(next)
    if (!nextYears.includes(year)) setYear(nextYears[0])
    setSelected(null)
  }

  function changeYear(next) {
    if (!availableYears(availability, dataset).includes(next)) return
    setYear(next)
    setSelected(null)
  }

  function handleSelect(d) {
    setSelected((prev) => (prev === d ? null : d))
    setTab('data')
    if (panelRef.current) panelRef.current.scrollTop = 0
  }

  const tabs = visibleTabs(STATIC, availability?.features)
  const disabledReasons = tabs.filter((item) => item.disabled).map((item) => item.reason)

  return (
    <div className="cii-dashboard" style={{ display: 'flex', flexDirection: 'column', height: '100vh', background: 'var(--canvas)' }}>
      <TopNav variant="light" active="dashboard" />
      <div className="cii-dashboard-grid" style={{ flex: 1, minHeight: 0, display: 'grid', gridTemplateColumns: '1fr 384px' }}>
        <div className="cii-dashboard-map" style={{ minWidth: 0, position: 'relative' }}>
          <MapStage dataset={dataset} setDataset={changeDataset} year={year} setYear={changeYear}
            selected={selected} onSelect={handleSelect} view={view} setView={setView}
            availability={availability} rows={currentRanking.rows}
            dataError={availabilityError || currentRanking.error} />
        </div>
        <aside className="cii-dashboard-panel" style={{ display: 'flex', flexDirection: 'column', minHeight: 0, background: 'var(--surface)', borderLeft: '1px solid var(--hairline)' }}>
          <div style={{ flex: '0 0 auto', padding: '0 16px' }}>
            <Tabs tabs={tabs} value={tab} onChange={setTab} />
            {STATIC && <p className="cii-footnote" style={{ margin: '4px 0 8px' }}>
              {disabledReasons.join(' ')} Address lookup requires offline geocoding and is unavailable.
              {' '}Council shows sponsorship, not votes.
            </p>}
          </div>
          <div ref={panelRef} style={{ flex: 1, minHeight: 0, overflowY: 'auto', padding: 20 }}>
            {tab === 'data' && <DataPanel dataset={dataset} year={year} selected={selected} onSelect={handleSelect}
              rows={currentRanking.rows} loading={currentRanking.loading || (STATIC && !availability && !availabilityError)}
              error={availabilityError || currentRanking.error || (STATIC && availability && !choiceAvailable ? 'No complete annual district data is available in this edition.' : null)} />}
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
