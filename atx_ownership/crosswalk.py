"""Build the parcel->district crosswalk.

parcel_geo stores parcel polygons in EPSG:2277 (NAD83 / Texas Central, ftUS) while
district_boundary is WGS84 lon/lat (EPSG:4326). For each parcel we take a
representative interior point (largest-ring area-weighted centroid), reproject it
to 4326 with pyproj, and find the district polygon that contains it (pure-Python
ray casting). Parcels with no geometry, or whose centroid falls in no district,
are left out of the crosswalk (the ~23% of parcels with no matched geometry are
thus 'unknown' downstream — a disclosed coverage gap).

One-time / on-demand build: full rebuild of parcel_district.
"""
from __future__ import annotations

import logging

from pyproj import Transformer

from .geom import bbox, point_in_bbox, point_in_polygon, polygon_centroid

log = logging.getLogger("atx.ownership.crosswalk")


def build_crosswalk(conn, source_srid: int = 2277, prefix: str = "") -> dict:
    """Reproject each parcel_geo centroid to 4326 and assign it to a district.

    Returns a summary: parcels seen, matched, unmatched. Rebuilds parcel_district.
    """
    transformer = Transformer.from_crs(source_srid, 4326, always_xy=True)

    # precompute each district's bbox (in 4326) as a cheap prefilter — parcels
    # number in the hundreds of thousands and the district polygons are detailed.
    districts = [
        (r["council_district"], r["geom"], bbox(r["geom"]))
        for r in conn.execute(
            "SELECT council_district, geom FROM district_boundary "
            "ORDER BY council_district").fetchall()
    ]

    conn.execute(f"TRUNCATE {prefix}parcel_district")

    seen = matched = 0
    for row in conn.execute(
            "SELECT account_id, geom FROM parcel_geo WHERE geom IS NOT NULL"):
        seen += 1
        try:
            cx, cy = polygon_centroid(row["geom"])
        except ValueError:
            continue                       # degenerate geometry -> leave unmatched
        lon, lat = transformer.transform(cx, cy)
        for district, geom, box in districts:
            if not point_in_bbox((lon, lat), box):
                continue
            if point_in_polygon((lon, lat), geom):
                conn.execute(
                    f"INSERT INTO {prefix}parcel_district (account_id, council_district) "
                    "VALUES (%s, %s) ON CONFLICT (account_id) DO UPDATE SET "
                    "council_district = EXCLUDED.council_district",
                    (row["account_id"], district))
                matched += 1
                break

    total_geo = conn.execute(
        "SELECT count(*) AS n FROM parcel_geo").fetchone()["n"]
    summary = {"parcels_with_geom": seen, "matched": matched,
               "unmatched": total_geo - matched, "districts": len(districts)}
    log.info("crosswalk build: %s", summary)
    return summary
