import { STATIC } from './config.js'

// In static mode, /v1 API calls are served from pre-baked JSON snapshots under
// /data (produced by scripts/export_static.py). Slug MUST match the Python
// static_filename() in that exporter — see tests/fixtures/static_slug_pairs.json.
export const staticPath = (url) =>
  '/data/' + url.replace(/^\/v1\//, '').replace(/[^a-zA-Z0-9]+/g, '_').replace(/^_|_$/g, '') + '.json'

const j = (url) => fetch(STATIC ? staticPath(url) : url).then((r) => r.json())

export const getIncidents = (dataset, period) =>
  j(`/v1/metric/incidents?dataset=${dataset}&period=${period}`)
export const getDistrict = (district, period) =>
  j(`/v1/place/district/${district}?period=${period}`)
export const getDistrictsGeoJSON = () => j('/v1/districts.geojson')
export const getZipsGeoJSON = (propertyClass = 'A1') =>
  j(`/v1/zips.geojson?property_class=${propertyClass}`)
export const getMethods = (metric) => j(`/v1/methods/${metric}`)
export const getFlags = (detector = 'd3a_assessment_equity') =>
  j(`/v1/flags?detector=${detector}`)
export const getOwnerType = (propertyClass = 'A1') =>
  j(`/v1/ownership/owner-type?property_class=${propertyClass}`)
export const getCouncilFunding = () => j('/v1/council/funding-activity')
export const getCouncilRepresentation = () => j('/v1/council/representation')
export const getYou = (lat, lon, street) =>
  j(`/v1/you?lat=${lat}&lon=${lon}${street ? `&street=${encodeURIComponent(street)}` : ''}`)

// Narrative story pages
export const getStoryWhoOwnsAustin = () => j('/v1/stories/who-owns-austin')
export const getStoryHomesteadCap = () => j('/v1/stories/homestead-cap')
export const getStoryInvestorComplaints = () => j('/v1/stories/investor-complaints')
export const getStoryCityDollars = () => j('/v1/stories/city-dollars')
export const getStoryBallotMoney = () => j('/v1/stories/ballot-money')
export const getStoryMoneyWins = () => j('/v1/stories/money-wins')
export const getStoryTrafficDeaths = () => j('/v1/stories/traffic-deaths')
export const getStoryHomeBuilders = () => j('/v1/stories/home-builders')
export const getStoryServiceEquity = () => j('/v1/stories/service-equity')
export const getStoryLocalMoney = () => j('/v1/stories/local-money')
export const getStoryWhoPays = () => j('/v1/stories/who-pays')
export const getStoryMoneyInfluence = () => j('/v1/stories/money-influence')
export const getStoryDistrictDivide = () => j('/v1/stories/district-divide')
export const getStoryCouncilDissent = () => j('/v1/stories/council-dissent')
export const getStoryShortTermRentals = () => j('/v1/stories/short-term-rentals')
export const getStoryWhoLobbies = () => j('/v1/stories/who-lobbies')
export const getStoryAnimalShelter = () => j('/v1/stories/animal-shelter')
export const getStoryFoodInspections = () => j('/v1/stories/food-inspections')
export const getStoryStrGap = () => j('/v1/stories/str-gap')
