"""STR licensing gap: shared computation for the refresh builder, the findings script and
the story endpoint.
"""
from __future__ import annotations

import re

from atx_ownership.geom import bbox, point_in_bbox, point_in_polygon

_DIGITS = re.compile(r"\d+")


def normalize_license(text: str | None) -> str:
    """Digit-sequence normal form: '2000-000001 OL' -> '2000000001'."""
    return "".join(_DIGITS.findall(text or ""))


def classify_license(text: str | None) -> str:
    """Host-entered license field -> missing | exempt | claims_number | other."""
    t = (text or "").strip()
    if not t:
        return "missing"
    if "exempt" in t.lower():
        return "exempt"
    return "claims_number" if normalize_license(t) else "other"


def is_active(payload: dict) -> bool:
    """Reviewed in the last 12 months (Inside Airbnb's activity convention)."""
    try:
        return int(payload.get("number_of_reviews_ltm") or 0) >= 1
    except ValueError:
        return False


def prepare_boundaries(rows) -> list[tuple[int, dict, tuple]]:
    """[(district, geom)] -> [(district, geom, bbox)] for the cheap prefilter."""
    return [(d, geom, bbox(geom)) for d, geom in rows]


def district_for_point(lon: float, lat: float, boundaries) -> int | None:
    """Point (lon, lat) -> council district, or None if outside all polygons."""
    p = (lon, lat)
    for d, geom, box in boundaries:
        if point_in_bbox(p, box) and point_in_polygon(p, geom):
            return d
    return None


def md_table(headers, rows) -> str:
    lines = ["| " + " | ".join(str(h) for h in headers) + " |",
             "|" + "|".join("---" for _ in headers) + "|"]
    lines += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(lines)


def compute_gap(conn) -> dict:
    """Every figure for the STR-gap story, from the live tables. Pure data — no prose."""
    listings = [r["payload"] for r in
                conn.execute("SELECT payload FROM raw_airbnb_listings").fetchall()]
    snap = conn.execute(
        "SELECT max(snapshot_date)::text AS d FROM raw_airbnb_listings").fetchone()["d"]
    registry = conn.execute(
        "SELECT payload->>'case_number' AS case_number, "
        "       payload->>'council_district' AS district, "
        "       payload->>'prop_zip' AS zip "
        "FROM raw_short_term_rentals").fetchall()
    bounds = prepare_boundaries(
        [(r["council_district"], r["geom"]) for r in
         conn.execute("SELECT council_district, geom FROM district_boundary").fetchall()])

    total = len(listings)
    active = [p for p in listings if is_active(p)]
    entire = [p for p in active if p.get("room_type") == "Entire home/apt"]
    licensed_n = len(registry)

    registry_keys = {normalize_license(r["case_number"]) for r in registry} - {""}
    cls = {"missing": 0, "exempt": 0, "claims_number": 0, "other": 0}
    verified = 0
    for p in active:
        c = classify_license(p.get("license"))
        cls[c] += 1
        if c == "claims_number" and normalize_license(p.get("license")) in registry_keys:
            verified += 1

    op_by_d, unlocated = {}, 0
    for p in active:
        try:
            d = district_for_point(float(p["longitude"]), float(p["latitude"]), bounds)
        except (KeyError, TypeError, ValueError):
            d = None
        if d is None:
            unlocated += 1
        else:
            op_by_d[d] = op_by_d.get(d, 0) + 1
    lic_by_d = {}
    for r in registry:
        if (r["district"] or "").isdigit():
            lic_by_d[int(r["district"])] = lic_by_d.get(int(r["district"]), 0) + 1

    op_by_zip, lic_by_zip = {}, {}
    for p in active:
        z = (p.get("neighbourhood") or "").strip()
        if z.isdigit():
            op_by_zip[z] = op_by_zip.get(z, 0) + 1
    for r in registry:
        z = (r["zip"] or "").strip()
        if z.isdigit():
            lic_by_zip[z] = lic_by_zip.get(z, 0) + 1
    top_zips = sorted(op_by_zip, key=op_by_zip.get, reverse=True)[:10]

    def host_count(p):
        try:
            return int(p.get("calculated_host_listings_count") or 0)
        except ValueError:
            return 0

    return {
        "snapshot_date": snap, "total": total, "active": len(active),
        "entire": len(entire), "in_district": sum(op_by_d.values()),
        "unlocated": unlocated, "licensed_n": licensed_n,
        "license_classes": {**cls, "verified": verified},
        "by_district": [{"district": d, "active_n": op_by_d.get(d, 0),
                         "licensed_n": lic_by_d.get(d, 0)} for d in range(1, 11)],
        "by_zip": [{"zip": z, "active_n": op_by_zip[z],
                    "licensed_n": lic_by_zip.get(z, 0)} for z in top_zips],
        "hosts": {"multi2": sum(1 for p in active if host_count(p) >= 2),
                  "multi5": sum(1 for p in active if host_count(p) >= 5),
                  "multi10": sum(1 for p in active if host_count(p) >= 10)},
    }
