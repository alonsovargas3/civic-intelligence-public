import React, { useState } from 'react'
import { StatTile, Caveat, Badge } from './Primitives.jsx'
import { Link } from './router.jsx'
import { getYou } from './api.js'

const money = (v) => (v == null ? '—' : `$${Math.round(v).toLocaleString('en-US')}`)
const fmt = (n) => Number(n).toLocaleString('en-US')

// The US Census geocoder sends no CORS headers, so the browser can't call it directly.
// We geocode through our own /v1/geocode proxy, which forwards the address to Census
// in-memory and never logs or stores it. Returns [{matchedAddress, lat, lon}].
async function geocode(address) {
  const r = await fetch(`/v1/geocode?q=${encodeURIComponent(address)}`)
  if (!r.ok) throw new Error(`geocoder ${r.status}`)
  const d = await r.json()
  if (d && d.error) throw new Error(d.error)
  return Array.isArray(d) ? d : []
}

export default function You() {
  const [address, setAddress] = useState('')
  const [matches, setMatches] = useState(null)   // geocoder candidates
  const [picked, setPicked] = useState(null)     // {matchedAddress, coordinates}
  const [data, setData] = useState(null)
  const [err, setErr] = useState(null)
  const [busy, setBusy] = useState(false)

  async function lookup(e) {
    e.preventDefault()
    setErr(null); setData(null); setMatches(null); setPicked(null); setBusy(true)
    try {
      const ms = await geocode(address)
      if (!ms.length) { setErr('No match from the Census geocoder — check the address (include street + Austin, TX).'); return }
      if (ms.length === 1) await usePick(ms[0])
      else setMatches(ms)
    } catch {
      setErr('Could not reach the geocoder — please try again in a moment.')
    } finally { setBusy(false) }
  }

  async function usePick(m) {
    setPicked(m); setMatches(null); setBusy(true)
    try {
      // the street NAME (drop the house number) disambiguates which nearby parcel the
      // geocoder's street-centerline point belongs to — see the server's nearest_parcel.
      const street = (m.matchedAddress || '').split(',')[0].replace(/^\s*\d+\s*/, '')
      const d = await getYou(m.lat, m.lon, street)
      if (d.error) setErr(d.error); else setData(d)
    } catch { setErr('Lookup failed.') } finally { setBusy(false) }
  }

  const p = data && data.parcel
  const dd = data && data.district
  const nb = data && data.nearby

  return (
    <div style={{ maxWidth: 880, margin: '0 auto', padding: '32px 20px', color: 'var(--ink)' }}>
      <p style={{ margin: '0 0 4px', font: '600 12px var(--font-sans)', letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--fg-muted)' }}>
        Your address · <Link to="/" style={{ color: 'var(--fg-muted)' }}>back to dashboard</Link></p>
      <h1 style={{ margin: '0 0 8px', font: '700 30px/1.15 var(--font-sans)' }}>What the city's data says about your block</h1>
      <p style={{ margin: '0 0 20px', color: 'var(--fg-muted)' }}>Your appraisal, your council member, and what's happening near you.</p>

      <form onSubmit={lookup} style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
        <input value={address} onChange={(e) => setAddress(e.target.value)}
          placeholder="301 W 2nd St, Austin, TX" aria-label="street address"
          style={{ flex: 1, padding: '10px 12px', font: '15px var(--font-sans)', border: '1px solid var(--surface-3)', borderRadius: 'var(--r-sm)', background: 'var(--surface-1)', color: 'var(--ink)' }} />
        <button disabled={busy || !address.trim()} style={{ padding: '10px 18px', font: '600 14px var(--font-sans)', borderRadius: 'var(--r-sm)', border: 'none', background: 'var(--blue-7)', color: 'white', cursor: 'pointer' }}>
          {busy ? 'Looking…' : 'Look up'}</button>
      </form>
      <p style={{ margin: '0 0 24px', fontSize: 12, color: 'var(--fg-subtle)' }}>
        Privacy: your address is forwarded to the US Census geocoder to find its coordinates,
        then discarded — this site never logs or stores your address, and the resulting
        coordinates aren't saved either.</p>

      {err && <Caveat>{err}</Caveat>}

      {matches && (
        <div style={{ marginBottom: 24 }}>
          <p style={{ fontWeight: 600 }}>Did you mean:</p>
          {matches.slice(0, 5).map((m) => (
            <button key={m.matchedAddress} onClick={() => usePick(m)}
              style={{ display: 'block', margin: '4px 0', padding: '8px 12px', width: '100%', textAlign: 'left', border: '1px solid var(--surface-3)', borderRadius: 'var(--r-sm)', background: 'var(--surface-1)', color: 'var(--ink)', cursor: 'pointer' }}>
              {m.matchedAddress}</button>
          ))}
        </div>
      )}

      {picked && data && (
        <>
          <p style={{ color: 'var(--fg-muted)', marginBottom: 16 }}>Showing: <strong>{picked.matchedAddress}</strong></p>

          <h2 style={{ font: '700 20px var(--font-sans)', margin: '20px 0 10px' }}>Your parcel & taxes</h2>
          {p ? (
            <>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 10 }}>
                <StatTile label="Appraised value" value={money(p.values && p.values.appraised)} sub={`market ${money(p.values && p.values.market)}`} />
                <StatTile label="Taxable (assessed)" value={money(p.values && p.values.assessed)} sub={p.cap_shield ? `homestead cap shields ${money(p.cap_shield)}` : 'no cap shield on file'} />
                <StatTile label="Owner of record" value={p.owner ? p.owner.name : '—'} sub={p.owner ? `${p.owner.kind || ''} · ${fmt(p.owner.n_parcels || 1)} parcel(s) held` : ''} />
                <StatTile label="Property class" value={p.category || '—'} sub={`${p.situs.street || ''} · ${p.situs.zip || ''}`} />
              </div>
              {p.match === 'nearest' && (
                <Caveat compact>Matched to the nearest parcel on this street (~{p.match_distance_m}m
                  away) — the geocoder locates the address on the road, so we snap to the
                  closest lot with the same street name.</Caveat>
              )}
            </>
          ) : <Caveat>No parcel polygon contains this point (about a quarter of parcels have no
              geometry on file, and apartment buildings resolve to one shared parcel). The
              district and nearby panels below still apply.</Caveat>}

          <h2 style={{ font: '700 20px var(--font-sans)', margin: '24px 0 10px' }}>Your district & rep</h2>
          {dd ? (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 10 }}>
              <StatTile label="Council district" value={`D${dd.council_district}`} sub={dd.demographics ? `${fmt(dd.demographics.population)} residents` : ''} />
              <StatTile label="Your council member" value={dd.member ? dd.member.name : '—'} sub={dd.member ? `says No on ${dd.member.no_rate_per_100}% of votes (${fmt(dd.member.votes_cast)} cast)` : ''} />
              <StatTile label="311 response vs expected" value={dd.response_311_ratio ? `${dd.response_311_ratio.toFixed(2)}×` : '—'} sub="1.0× = as fast as your district's request mix predicts" />
              <StatTile label="Crime reports (last 12 mo of data)" value={fmt((dd.crime_per_month || []).reduce((a, m) => a + m.count, 0))} sub="district-wide; feed has no exact locations" />
            </div>
          ) : <Caveat>This point isn't inside any council district boundary.</Caveat>}

          <h2 style={{ font: '700 20px var(--font-sans)', margin: '24px 0 10px' }}>Near you</h2>
          {nb && (
            <>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 10 }}>
                <StatTile label="311 requests within ~½ mi" value={fmt(nb.incidents['311'])} />
                <StatTile label="Code cases within ~½ mi" value={fmt(nb.incidents.code)} />
                <StatTile label="Traffic crashes within ~½ mi" value={fmt(nb.incidents.crashes)} />
                <StatTile label="Licensed STRs in your ZIP" value={nb.strs ? fmt(nb.strs.total) : '—'} sub={nb.strs ? `${fmt(nb.strs.non_owner)} not owner-occupied · ZIP ${nb.strs.zip}` : ''} />
              </div>
              <Caveat compact>Data window {nb.window.from} – {nb.window.to}. {nb.window.frozen_note} {nb.crime_district_note}</Caveat>
            </>
          )}

          <p style={{ marginTop: 28, fontSize: 13, color: 'var(--fg-subtle)' }}>{data.methodology} {data.caveat}</p>
        </>
      )}
    </div>
  )
}
