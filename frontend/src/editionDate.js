// Austin-local date (YYYY-MM-DD) of a live lake version stamp like `v=20261009T015201Z`.
// Frozen editions (`edition:...`) and anything else unparseable return null, so callers
// can simply omit the date.
export function editionDate(version) {
  const m = /^v=(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})Z$/.exec(version || '')
  if (!m) return null
  const utc = new Date(Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4], +m[5], +m[6]))
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Chicago' }).format(utc)
}
