import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { it, expect, vi } from 'vitest'
vi.mock('./config.js', () => ({ STATIC: true }))
vi.mock('./router.jsx', async (original) => ({ ...await original(), useHashRoute: () => '/stories/str-gap' }))
import App from './App.jsx'
import PublicUnavailable from './PublicUnavailable.jsx'
import MapStage from './MapStage.jsx'
import manifest from '../public/data/dashboard_availability.json'
import { firstChoice } from './dashboardData.js'

it('leaves all analytical controls unavailable without approved fixtures', () => {
  expect(firstChoice(manifest)).toBeNull()
  expect(Object.values(manifest.features).every((value) => value === false)).toBe(true)
})
it('renders an explicit story unavailable state', () => {
  const html = renderToStaticMarkup(<PublicUnavailable />)
  expect(html).toContain('Story data unavailable')
  expect(html).toContain('no approved public analytical data package')
})

it('guards static story routes before rendering analytical copy', () => {
  expect(renderToStaticMarkup(<App />)).toContain('Story data unavailable')
})

it('does not present a map legend when no analytical layer is available', () => {
  const html = renderToStaticMarkup(<MapStage dataset="crime" setDataset={() => {}} year="2025"
    setYear={() => {}} selected={null} onSelect={() => {}} view="districts" setView={() => {}}
    availability={manifest} rows={null} dataError={null} />)
  expect(html).toContain('no complete annual district snapshot')
  expect(html).not.toContain('Crime incidents by district')
  expect(html).not.toContain('MapLibre')
})
