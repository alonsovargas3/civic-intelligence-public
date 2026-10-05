"""Address-level "you" layer: point -> parcel/district/nearby payload.

The browser geocodes the address via the US Census geocoder and sends us ONLY
coordinates (privacy posture — see the spec). This module resolves the point to
a parcel (parcel_bbox prefilter + exact point-in-polygon), the council district,
the ZIP, and nearby recent incidents.

PRIVACY: never log lat/lon in this module or its callers.
"""
from __future__ import annotations

import math
import re

from pyproj import Transformer

from atx_ownership.geom import bbox, point_in_bbox, point_in_polygon

RADIUS_M = 800                 # "nearby" = within ~half a mile
LAT_PAD = 0.0072               # RADIUS_M / 111320 m-per-degree, rounded up
LON_PAD = 0.0084               # RADIUS_M / (111320 * cos(30.3 deg)), rounded up

# Travis-area sanity bounds for incoming points (spec: reject outside with 400)
_LAT_MIN, _LAT_MAX = 29.5, 31.0
_LON_MIN, _LON_MAX = -98.5, -97.0

# WGS84 lon/lat -> Texas Central ftUS (the parcel_geo CRS). Module-level: the
# Transformer is expensive to build and thread-safe to reuse.
_TO_2277 = Transformer.from_crs(4326, 2277, always_xy=True)


def to_2277(lat: float, lon: float) -> tuple[float, float]:
    """WGS84 -> EPSG:2277 (x_ft, y_ft)."""
    return _TO_2277.transform(lon, lat)


def valid_point(lat: float, lon: float) -> bool:
    return _LAT_MIN <= lat <= _LAT_MAX and _LON_MIN <= lon <= _LON_MAX


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in meters (exact to well under 1% at city scale)."""
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def parcel_for_point(conn, lat: float, lon: float) -> str | None:
    """Resolve a WGS84 point to the parcel whose polygon contains it, or None."""
    x, y = to_2277(lat, lon)
    candidates = conn.execute(
        "SELECT b.account_id, g.geom FROM parcel_bbox b "
        "JOIN parcel_geo g USING (account_id) "
        "WHERE b.minx <= %s AND b.maxx >= %s AND b.miny <= %s AND b.maxy >= %s",
        (x, x, y, y)).fetchall()
    for row in candidates:
        if point_in_polygon((x, y), row["geom"]):
            return row["account_id"]
    return None


SNAP_FT = 300   # ~91m: Census geocodes to the street centerline (in the ROW), so an exact
                # point often misses the lot by half a right-of-way plus the setback; snap
                # to the nearest parcel within this radius. Beyond it, report no parcel.

# Street-type suffixes and directionals to strip from the ends when comparing a geocoded
# street to a parcel's situs street (the roll stores "LYNNBROOK", the geocoder returns
# "LYNNBROOK DR"; "W 2ND ST" and "2ND" should both reduce to "2ND").
_STREET_NOISE = {"ST", "STREET", "DR", "DRIVE", "LN", "LANE", "RD", "ROAD", "AVE", "AVENUE",
                 "BLVD", "CT", "COURT", "CIR", "CIRCLE", "TRL", "TRAIL", "PKWY", "PARKWAY",
                 "WAY", "PL", "PLACE", "COVE", "CV", "PASS", "PATH", "RUN", "BND", "BEND",
                 "LOOP", "TER", "TERRACE", "HWY", "N", "S", "E", "W", "NE", "NW", "SE", "SW"}


def _street_core(s: str | None) -> str:
    """Normalize a street to its core name for matching: drop the house number and strip
    street-type suffixes + directionals from both ends. Digits are preserved so numbered
    streets survive. 'LYNNBROOK DR' -> 'LYNNBROOK'; 'W 2ND ST' -> '2ND'; '2ND' -> '2ND'."""
    toks = [t for t in re.split(r"[^A-Za-z0-9]+", (s or "").upper()) if t and not t.isdigit()]
    while toks and toks[0] in _STREET_NOISE:
        toks.pop(0)
    while toks and toks[-1] in _STREET_NOISE:
        toks.pop()
    return " ".join(toks)


def nearest_parcel(conn, lat: float, lon: float, street: str | None = None,
                   max_ft: float = SNAP_FT):
    """Nearest parcel to a point when no polygon contains it (the geocoder returned a
    street-centerline point). Returns (account_id, distance_ft) within max_ft, or None.

    Distance is point-to-bounding-box (0 inside the bbox), index-friendly. When `street`
    is given, ONLY parcels whose situs street matches it are considered — this avoids
    snapping to a right-of-way / drainage sliver that hugs the road instead of the
    addressed lot, and returns None rather than a confidently-wrong parcel if the street
    doesn't match any nearby parcel. Without `street`, falls back to nearest-overall."""
    x, y = to_2277(lat, lon)
    rows = conn.execute(
        "SELECT b.account_id, b.minx, b.miny, b.maxx, b.maxy, p.situs->>'street' AS street "
        "FROM parcel_bbox b JOIN parcel p USING (account_id) "
        "WHERE b.minx <= %s AND b.maxx >= %s AND b.miny <= %s AND b.maxy >= %s",
        (x + max_ft, x - max_ft, y + max_ft, y - max_ft)).fetchall()
    core = _street_core(street) if street else None
    best, best_d = None, None
    for r in rows:
        if core and _street_core(r["street"]) != core:
            continue
        dx = max(r["minx"] - x, 0.0, x - r["maxx"])
        dy = max(r["miny"] - y, 0.0, y - r["maxy"])
        d = math.hypot(dx, dy)
        if d <= max_ft and (best_d is None or d < best_d):
            best, best_d = r["account_id"], d
    return (best, best_d) if best is not None else None


def zip_for_point(lat: float, lon: float, zip_rows) -> str | None:
    """zip_rows: [(zip, geojson_geom)] in WGS84. Point is (lon, lat) = (x, y)."""
    p = (lon, lat)
    for z, geom in zip_rows:
        if point_in_bbox(p, bbox(geom)) and point_in_polygon(p, geom):
            return z
    return None


# --- payload assembly (DB-touching) ----------------------------------------


def _district_for_point(conn, lat, lon) -> int | None:
    rows = conn.execute(
        "SELECT council_district, geom FROM district_boundary").fetchall()
    p = (lon, lat)
    for r in rows:
        if point_in_bbox(p, bbox(r["geom"])) and point_in_polygon(p, r["geom"]):
            return int(r["council_district"])
    return None


def _parcel_block(conn, account_id) -> dict | None:
    base = conn.execute(
        "SELECT p.account_id, p.situs, p.legal, p.category, p.acreage::float8 AS acreage, "
        "       d.council_district "
        "FROM parcel p LEFT JOIN parcel_district d USING (account_id) "
        "WHERE p.account_id = %s", (account_id,)).fetchone()
    if not base:
        return None
    vals = conn.execute(
        "SELECT land_value::float8 AS land, improvement_value::float8 AS improvement, "
        "       market_value::float8 AS market, appraised_value::float8 AS appraised, "
        "       assessed_value::float8 AS assessed, capped_value::float8 AS capped "
        "FROM parcel_value_current WHERE account_id = %s "
        "ORDER BY informational ASC, roll_year DESC LIMIT 1", (account_id,)).fetchone()
    owner = conn.execute(
        "SELECT e.canonical_name AS name, e.kind, e.n_parcels "
        "FROM parcel_entity pe JOIN dim_entity e USING (entity_id) "
        "WHERE pe.account_id = %s ORDER BY pe.roll_year DESC LIMIT 1",
        (account_id,)).fetchone()
    cap = (vals or {}).get("capped") or 0.0
    return {
        "account_id": base["account_id"],
        "situs": {"street": (base["situs"] or {}).get("street", ""),
                  "zip": (base["situs"] or {}).get("zip", "")},
        "legal": base["legal"], "category": base["category"], "acreage": base["acreage"],
        "values": vals, "cap_shield": cap if cap > 0 else None,
        "owner": owner,
        "council_district": base["council_district"],
    }


def _district_block(conn, district: int) -> dict | None:
    member = conn.execute(
        "WITH per AS (SELECT payload->>'voter_name' AS name, payload->>'voter_district' AS d, "
        "  max(left(payload->>'meeting_date',10)::date) AS last_vote, "
        "  count(*) FILTER (WHERE payload->>'vote_cast'='No') AS no_votes, "
        "  count(*) FILTER (WHERE payload->>'vote_cast' IN ('Yes','No')) AS votes_cast "
        "  FROM raw_council_votes GROUP BY 1,2) "
        "SELECT name, no_votes, votes_cast, "
        "       round(100.0*no_votes/nullif(votes_cast,0), 1)::float8 AS no_rate_per_100 "
        "FROM per WHERE d = %s ORDER BY last_vote DESC LIMIT 1", (str(district),)).fetchone()
    demo = conn.execute(
        "SELECT (payload->>'total_population_2020_census')::int AS population, "
        "       (payload->>'median_age')::float8 AS median_age, "
        # hh_income_* bands are already percentage values (e.g. 11.4 = 11.4%), same as
        # story_district_divide sums them — so NO extra *100 (that double-scaled to 2640).
        "       round(((payload->>'hh_income_less_than_10000')::numeric"
        "         +(payload->>'hh_income_10000_to_14999')::numeric"
        "         +(payload->>'hh_income_15000_to_24999')::numeric"
        "         +(payload->>'hh_income_25000_to_34999')::numeric),1)::float8 AS pct_under35k, "
        "       round(((payload->>'hh_income_150000_to_199999')::numeric"
        "         +(payload->>'hh_income_200000_or_more')::numeric),1)::float8 AS pct_over150k "
        "FROM raw_district_demographics WHERE (payload->>'district')::int = %s",
        (district,)).fetchone()
    ratio = conn.execute(
        "SELECT disparity_ratio::float8 AS r FROM metric_311_equity "
        "WHERE council_district = %s AND window_year = 0", (district,)).fetchone()
    crime = conn.execute(
        "SELECT to_char(period_month,'YYYY-MM') AS month, sum(incident_count)::int AS count "
        "FROM metric_incidents_by_district WHERE dataset='crime' AND council_district=%s "
        "GROUP BY period_month ORDER BY period_month DESC LIMIT 12", (district,)).fetchall()
    return {
        "council_district": district,
        "member": member,
        "demographics": demo,
        "response_311_ratio": ratio["r"] if ratio else None,
        "crime_per_month": list(reversed(crime)),
    }


def _nearby_block(conn, lat, lon, zip_code) -> dict:
    window = conn.execute(
        "SELECT min(ts)::date::text AS from_d, max(ts)::date::text AS to_d "
        "FROM recent_incidents").fetchone() or {"from_d": None, "to_d": None}
    rows = conn.execute(
        "SELECT dataset, ts::text AS ts, lat, lon FROM recent_incidents "
        "WHERE dataset <> 'crime' AND lat BETWEEN %s AND %s AND lon BETWEEN %s AND %s",
        (lat - LAT_PAD, lat + LAT_PAD, lon - LON_PAD, lon + LON_PAD)).fetchall()
    with_dist = [(r, haversine_m(lat, lon, r["lat"], r["lon"])) for r in rows]
    hits = [(r, d) for r, d in with_dist if d <= RADIUS_M]
    counts = {"311": 0, "code": 0, "crashes": 0}
    for r, _ in hits:
        counts[r["dataset"]] = counts.get(r["dataset"], 0) + 1
    samples = [{"dataset": r["dataset"], "ts": r["ts"], "lat": r["lat"], "lon": r["lon"],
                "distance_m": round(d)} for r, d in sorted(hits, key=lambda t: t[1])[:10]]
    strs = None
    if zip_code:
        s = conn.execute(
            "SELECT count(*) AS total, "
            "count(*) FILTER (WHERE payload->>'str_type' !~* 'Type 1') AS non_owner "
            "FROM raw_short_term_rentals WHERE payload->>'prop_zip' = %s", (zip_code,)).fetchone()
        strs = {"zip": zip_code, "total": s["total"], "non_owner": s["non_owner"]}
    return {
        "window": {"from": window["from_d"], "to": window["to_d"],
                   "frozen_note": "Live incident feeds are paused; this window reflects "
                                  "the last archived data."},
        "incidents": counts,
        "samples": samples,
        "crime_district_note": "Crime reports carry no coordinates in the public feed — "
                               "see the district panel for district-level crime.",
        "strs": strs,
    }


def build_payload(conn, lat: float, lon: float, street: str | None = None) -> dict:
    account_id = parcel_for_point(conn, lat, lon)
    match, snap_m = "exact", None
    if account_id is None:                      # geocoder likely returned a centerline point
        snap = nearest_parcel(conn, lat, lon, street)
        if snap:
            account_id, dist_ft = snap
            match, snap_m = "nearest", round(dist_ft * 0.3048)
    parcel = _parcel_block(conn, account_id) if account_id else None
    if parcel is not None:
        parcel["match"] = match
        parcel["match_distance_m"] = snap_m
    district_no = (parcel or {}).get("council_district") or _district_for_point(conn, lat, lon)
    district = _district_block(conn, int(district_no)) if district_no else None
    zip_rows = [(r["zip"], r["geom"]) for r in
                conn.execute("SELECT zip, geom FROM zip_boundary").fetchall()]
    zip_code = (parcel or {}).get("situs", {}).get("zip") or zip_for_point(lat, lon, zip_rows)
    return {
        "parcel": parcel,
        "district": district,
        "nearby": _nearby_block(conn, lat, lon, zip_code),
        "methodology": (
            "The address is geocoded via the US Census geocoder — forwarded through this "
            "site, which does not store it — to a coordinate. The point is matched to a "
            "TCAD parcel polygon (exact point-in-polygon, or the nearest lot on the same "
            "street when the geocoder lands the point in the roadway), to the council-"
            "district and ZIP boundary polygons, and to recent incidents within ~800m. "
            "Appraisal values are the current TCAD roll; the owner is the resolved owner "
            "entity."),
        "caveat": (
            "The geocoder locates addresses on the street centerline, so about a quarter "
            "of lookups snap to the nearest parcel on the street (labeled with its "
            "distance) rather than an exact polygon hit; some have no parcel geometry at "
            "all and show district-level panels only. Nearby incidents come from a frozen "
            "archive window (live feeds paused). Crime has no public coordinates. This is "
            "descriptive lookup, not advice; nothing is stored."),
    }
