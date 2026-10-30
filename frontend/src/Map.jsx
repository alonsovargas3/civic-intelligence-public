import React, { useEffect, useRef, useState } from 'react'
import maplibregl from 'maplibre-gl'
import { getDistrictsGeoJSON, getZipsGeoJSON } from './api.js'
import { districtFeatures } from './dashboardData.js'

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
const DISTRICT_FILL = ['case', ['==', ['typeof', ['get', 'percentile']], 'number'], BLUES, '#e3e6e9']
// ZIP percentile can be null (no A1 stratum) -> render neutral grey.
const ZIP_FILL = ['case', ['==', ['typeof', ['get', 'percentile']], 'number'], BLUES, '#e3e6e9']

const DISTRICT_LAYERS = ['fill', 'outline', 'labels', 'selected-outline']
const ZIP_LAYERS = ['zip-fill', 'zip-outline', 'zip-labels']

export default function MapView({ rows, onSelect, selected, view = 'districts', zipsEnabled = true }) {
  const ref = useRef(null)
  const map = useRef(null)
  const ready = useRef(false)
  const geo = useRef(null)
  const rowsRef = useRef(rows)
  const [mapError, setMapError] = useState(null)
  rowsRef.current = rows

  useEffect(() => {
    map.current = new maplibregl.Map({
      container: ref.current, style: STYLE, center: [-97.74, 30.27], zoom: 9.5,
    })
    map.current.on('load', async () => {
      try { await addLayers(); ready.current = true; applyView() }
      catch { setMapError('District map geometry could not be loaded.') }
    })
    return () => map.current.remove()
  }, [])

  useEffect(() => { if (ready.current) refreshDistricts() }, [rows])
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
    if (geo.current && map.current?.getSource('districts')) {
      map.current.getSource('districts').setData(districtFeatures(geo.current, rowsRef.current))
    }
  }

  async function addLayers() {
    // --- districts ---
    const [districtGeo, zips] = await Promise.all([
      getDistrictsGeoJSON(), zipsEnabled ? getZipsGeoJSON('A1') : Promise.resolve(null),
    ])
    geo.current = districtGeo
    map.current.addSource('districts', { type: 'geojson', data: districtFeatures(districtGeo, rowsRef.current) })
    map.current.addLayer({ id: 'fill', type: 'fill', source: 'districts',
      paint: { 'fill-color': DISTRICT_FILL, 'fill-opacity': 0.7 } })
    map.current.addLayer({ id: 'outline', type: 'line', source: 'districts',
      paint: { 'line-color': '#333', 'line-width': 1 } })
    map.current.addLayer({ id: 'labels', type: 'symbol', source: 'districts',
      layout: { 'text-field': ['to-string', ['get', 'council_district']], 'text-font': ['Open Sans Semibold'], 'text-size': 14 },
      paint: { 'text-color': '#1a1a1a', 'text-halo-color': '#fff', 'text-halo-width': 1.5 } })
    map.current.addLayer({ id: 'selected-outline', type: 'line', source: 'districts',
      paint: { 'line-color': '#08306b', 'line-width': 3 }, filter: ['==', ['get', 'council_district'], -1] })

    // --- ZIPs (assessment-dispersion COD percentile, A1) ---
    if (zips) {
      map.current.addSource('zips', { type: 'geojson', data: zips })
      map.current.addLayer({ id: 'zip-fill', type: 'fill', source: 'zips',
        paint: { 'fill-color': ZIP_FILL, 'fill-opacity': 0.7 } })
      map.current.addLayer({ id: 'zip-outline', type: 'line', source: 'zips',
        paint: { 'line-color': '#666', 'line-width': 0.8 } })
      map.current.addLayer({ id: 'zip-labels', type: 'symbol', source: 'zips',
        layout: { 'text-field': ['get', 'zip'], 'text-font': ['Open Sans Semibold'], 'text-size': 11 },
        paint: { 'text-color': '#14171a', 'text-halo-color': '#fff', 'text-halo-width': 1.4 } })
    }

    // district click -> select; cursor affordance on whichever fill is active
    map.current.on('click', 'fill', (e) => onSelect(e.features[0].properties.council_district))
    for (const lyr of ['fill', 'zip-fill']) {
      map.current.on('mouseenter', lyr, () => { map.current.getCanvas().style.cursor = lyr === 'fill' ? 'pointer' : 'default' })
      map.current.on('mouseleave', lyr, () => { map.current.getCanvas().style.cursor = '' })
    }
    await refreshDistricts()
  }

  return <>
    <div ref={ref} style={{ position: 'absolute', inset: 0 }} />
    {mapError && <p role="status" className="cii-small" style={{ position: 'absolute', top: 120, left: 16,
      zIndex: 8, background: 'var(--surface)', padding: 10 }}>{mapError}</p>}
  </>
}
