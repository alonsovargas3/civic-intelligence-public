import { describe, it, expect } from 'vitest'
import { availableYears, firstChoice, rankingError, detailError, districtFeatures } from './dashboardData.js'

const rows = Array.from({ length: 10 }, (_, i) => ({
  council_district: i + 1, incident_count: 120 + i, percentile: i * 10,
}))
const detail = (dataset = 'crime', year = '2025') => ({
  district: 1,
  totals_by_dataset: [{ dataset, n: 120 }],
  monthly_trend: Array.from({ length: 12 }, (_, i) => ({
    dataset, month: `${year}-${String(i + 1).padStart(2, '0')}`, incident_count: 10,
  })),
  response_time: { median_days: 1.5, closed_count: 110, open_count: 10 },
})

describe('static dashboard choices', () => {
  it('selects only listed years and a supported default', () => {
    const manifest = { choices: { crime: [], '311': ['2024'] } }
    expect(availableYears(manifest, 'crime')).toEqual([])
    expect(firstChoice(manifest)).toEqual({ dataset: '311', year: '2024' })
    expect(firstChoice({ choices: { crime: [], '311': [] } })).toBeNull()
  })

  it('rejects missing or duplicated district rankings', () => {
    expect(rankingError(rows)).toBeNull()
    expect(rankingError(rows.slice(0, 9))).toMatch(/missing/)
    expect(rankingError([...rows.slice(0, 9), rows[0]])).toMatch(/invalid/)
  })
})

describe('map and district panel agreement', () => {
  it('maps the selected ranking count and leaves missing districts neutral', () => {
    const geo = { type: 'FeatureCollection', features: [
      { properties: { council_district: 1 } }, { properties: { council_district: 2 } },
    ] }
    const mapped = districtFeatures(geo, [rows[0]])
    expect(mapped.features[0].properties).toMatchObject({ count: 120, percentile: 0 })
    expect(mapped.features[1].properties).toMatchObject({ count: null, percentile: null })
    expect(geo.features[0].properties.count).toBeUndefined()
  })

  it('accepts matching year totals and separates 311 response duration', () => {
    expect(detailError(detail(), rows[0], 'crime', '2025')).toBeNull()
    expect(detailError(detail('311'), rows[0], '311', '2025')).toBeNull()
  })

  it('rejects stale, missing, or mismatched detail', () => {
    expect(detailError(null, rows[0], 'crime', '2025')).toMatch(/missing/)
    expect(detailError({ ...detail(), district: 2 }, rows[0], 'crime', '2025')).toMatch(/missing/)
    expect(detailError(detail(), rows[0], 'crime', '2024')).toMatch(/does not agree/)
    const wrongTotal = { ...detail(), totals_by_dataset: [{ dataset: 'crime', n: 119 }] }
    expect(detailError(wrongTotal, rows[0], 'crime', '2025')).toMatch(/does not agree/)
    const wrongResponse = { ...detail('311'), response_time: { closed_count: 109, open_count: 10 } }
    expect(detailError(wrongResponse, rows[0], '311', '2025')).toMatch(/denominator/)
  })
})
