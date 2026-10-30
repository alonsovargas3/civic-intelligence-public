export const DATASETS = ['crime', '311']
export const YEARS = ['2025', '2024', '2023']

export function availableYears(manifest, dataset) {
  return (manifest?.choices?.[dataset] || []).filter((year) => YEARS.includes(year))
}

export function firstChoice(manifest) {
  for (const dataset of DATASETS) {
    const year = availableYears(manifest, dataset)[0]
    if (year) return { dataset, year }
  }
  return null
}

export function rankingError(rows) {
  if (!Array.isArray(rows) || rows.length !== 10) return 'Ranking is missing district data.'
  const districts = new Set()
  for (const row of rows) {
    const d = row?.council_district
    if (!Number.isInteger(d) || d < 1 || d > 10 || districts.has(d)
      || !Number.isInteger(row.incident_count) || row.incident_count < 0
      || !Number.isFinite(row.percentile) || row.percentile < 0 || row.percentile > 100) {
      return 'Ranking contains invalid district data.'
    }
    districts.add(d)
  }
  return null
}

export function detailError(detail, row, dataset, year) {
  if (!detail || detail.district !== row?.council_district) return 'District detail is missing.'
  const totals = (detail.totals_by_dataset || []).filter((t) => t.dataset === dataset)
  const months = (detail.monthly_trend || []).filter((m) => m.dataset === dataset)
  const monthNames = new Set(months.map((m) => m.month))
  const expected = Array.from({ length: 12 }, (_, i) => `${year}-${String(i + 1).padStart(2, '0')}`)
  if (totals.length !== 1 || totals[0].n !== row.incident_count
    || months.length !== 12 || expected.some((month) => !monthNames.has(month))
    || months.some((m) => !Number.isInteger(m.incident_count) || m.incident_count < 0)
    || months.reduce((sum, m) => sum + m.incident_count, 0) !== row.incident_count) {
    return 'District detail does not agree with the map and ranking for this year.'
  }
  if (dataset === '311') {
    const rt = detail.response_time
    if (!rt || !Number.isInteger(rt.closed_count) || !Number.isInteger(rt.open_count)
      || rt.closed_count + rt.open_count !== row.incident_count) {
      return '311 response denominator does not agree with request count.'
    }
  }
  return null
}

export function districtFeatures(geo, rows) {
  const byDistrict = new Map((rows || []).map((row) => [row.council_district, row]))
  return { ...geo, features: geo.features.map((feature) => {
    const metric = byDistrict.get(Number(feature.properties.council_district))
    return { ...feature, properties: {
      ...feature.properties,
      count: metric?.incident_count ?? null,
      percentile: metric?.percentile ?? null,
    } }
  }) }
}
