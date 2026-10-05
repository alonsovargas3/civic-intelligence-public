import React, { useEffect, useRef } from 'react'
import maplibregl from 'maplibre-gl'
import { getIncidents, getDistrictsGeoJSON, getZipsGeoJSON } from './api.js'

// Blank, neutral basemap: a very-light-gray background with no world tiles, so
// only the Austin geography stands out. `glyphs` renders the labels (free demo
// font server, no token).
const STYLE = {
  version: 8,
  glyphs: 'https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf',
  sources: {},
  layers: [{ id: 'background', type: 'background', paint: { 'background-color': '#f0f1f2' } }],
}

// ColorBrewer Blues, interpolated by percentile (0..100). Verbatim from the design.
const BLUES = ['interpolate', ['linear'], ['get', 'percentile'],
  0, '#f7fbff', 50, '#6baed6', 100, '#08306b']
// ZIP percentile can be null (no A1 stratum) -> render neutral grey.
const ZIP_FILL = ['case', ['==', ['typeof', ['get', 'percentile']], 'number'], BLUES, '#e3e6e9']

const DISTRICT_LAYERS = ['fill', 'outline', 'labels', 'selected-outline']
const ZIP_LAYERS = ['zip-fill', 'zip-outline', 'zip-labels']

export default function MapView({ dataset, period, onSelect, selected, view = 'districts' }) {
  const ref = useRef(null)
  const map = useRef(null)
  const ready = useRef(false)

  useEffect(() => {
    map.current = new maplibregl.Map({
      container: ref.current, style: STYLE, center: [-97.74, 30.27], zoom: 9.5,
    })
    map.current.on('load', async () => { await addLayers(); ready.current = true; applyView() })
    return () => map.current.remove()
  }, [])

  useEffect(() => { if (ready.current) refreshDistricts() }, [dataset, period])
  useEffect(() => { if (ready.current) applyView() }, [view])
  useEffect(() => {
    if (ready.current && map.current.getLayer('selected-outline')) {
      map.current.setFilter('selected-outline', ['==', ['get', 'council_district'], selected ?? -1])
    }
  }, [selected])

  function setVis(ids, visible) {
    ids.forEach((id) => map.current.getLayer(id) &&
      map.current.setLayoutProperty(id, 'visibility', visible ? 'visible' : 'none'))
  }
  function applyView() {
    setVis(DISTRICT_LAYERS, view === 'districts')
    setVis(ZIP_LAYERS, view === 'zips')
  }

  async function refreshDistricts() {
    const [geo, metrics] = await Promise.all([getDistrictsGeoJSON(), getIncidents(dataset, period)])
    const byDistrict = Object.fromEntries(metrics.map((m) => [m.council_district, m]))
    for (const f of geo.features) {
      const m = byDistrict[f.properties.council_district]
      f.properties.count = m ? m.incident_count : 0
      f.properties.percentile = m ? m.percentile : 0
    }
    map.current.getSource('districts').setData(geo)
  }

  async function addLayers() {
    // --- districts ---
    const [geo, zips] = await Promise.all([getDistrictsGeoJSON(), getZipsGeoJSON('A1')])
    map.current.addSource('districts', { type: 'geojson', data: geo })
    map.current.addLayer({ id: 'fill', type: 'fill', source: 'districts',
      paint: { 'fill-color': BLUES, 'fill-opacity': 0.7 } })
    map.current.addLayer({ id: 'outline', type: 'line', source: 'districts',
      paint: { 'line-color': '#333', 'line-width': 1 } })
    map.current.addLayer({ id: 'labels', type: 'symbol', source: 'districts',
      layout: { 'text-field': ['to-string', ['get', 'council_district']], 'text-font': ['Open Sans Semibold'], 'text-size': 14 },
      paint: { 'text-color': '#1a1a1a', 'text-halo-color': '#fff', 'text-halo-width': 1.5 } })
    map.current.addLayer({ id: 'selected-outline', type: 'line', source: 'districts',
      paint: { 'line-color': '#08306b', 'line-width': 3 }, filter: ['==', ['get', 'council_district'], -1] })

    // --- ZIPs (assessment-dispersion COD percentile, A1) ---
    map.current.addSource('zips', { type: 'geojson', data: zips })
    map.current.addLayer({ id: 'zip-fill', type: 'fill', source: 'zips',
      paint: { 'fill-color': ZIP_FILL, 'fill-opacity': 0.7 } })
    map.current.addLayer({ id: 'zip-outline', type: 'line', source: 'zips',
      paint: { 'line-color': '#666', 'line-width': 0.8 } })
    map.current.addLayer({ id: 'zip-labels', type: 'symbol', source: 'zips',
      layout: { 'text-field': ['get', 'zip'], 'text-font': ['Open Sans Semibold'], 'text-size': 11 },
      paint: { 'text-color': '#14171a', 'text-halo-color': '#fff', 'text-halo-width': 1.4 } })

    // district click -> select; cursor affordance on whichever fill is active
    map.current.on('click', 'fill', (e) => onSelect(e.features[0].properties.council_district))
    for (const lyr of ['fill', 'zip-fill']) {
      map.current.on('mouseenter', lyr, () => { map.current.getCanvas().style.cursor = lyr === 'fill' ? 'pointer' : 'default' })
      map.current.on('mouseleave', lyr, () => { map.current.getCanvas().style.cursor = '' })
    }
    await refreshDistricts()
  }

  return <div ref={ref} style={{ position: 'absolute', inset: 0 }} />
}
