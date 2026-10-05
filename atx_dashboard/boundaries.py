"""One-time loader for Austin council-district boundary polygons.

We have council_district as an attribute on incidents but not the polygons; this
fetches the official "Council Districts" layer (GeoJSON) and loads district_boundary.
Network fetch is isolated from the pure parser so the parser is unit-tested offline.
"""
from __future__ import annotations

import logging

import requests
from psycopg.types.json import Json

from .metrics import district_or_none

log = logging.getLogger("atx.dashboard.boundaries")

# Austin open-data "Council Districts (Single Member Districts)" GeoJSON export.
BOUNDARY_URL = "https://data.austintexas.gov/resource/w3v2-cj58.geojson?$limit=50"

# Property names the district number may appear under, in priority order.
_DISTRICT_KEYS = ("council_district", "district_number", "district", "district_n", "council_di")


def _district_from_props(props: dict) -> int | None:
    for k in _DISTRICT_KEYS:
        if k in props:
            d = district_or_none(props[k])
            if d is not None:
                return d
    return None


def features_to_rows(feature_collection: dict) -> list[tuple[int, dict]]:
    """Map a GeoJSON FeatureCollection to [(council_district, geometry_dict)].

    Skips features whose district can't be parsed to 1..10. First win per district.
    """
    seen: dict[int, dict] = {}
    for feat in feature_collection.get("features", []):
        d = _district_from_props(feat.get("properties") or {})
        geom = feat.get("geometry")
        if d is not None and geom is not None and d not in seen:
            seen[d] = geom
    return sorted(seen.items())


def fetch() -> dict:
    """Fetch the boundary FeatureCollection from Austin open data."""
    resp = requests.get(BOUNDARY_URL, timeout=60)
    resp.raise_for_status()
    return resp.json()


def load(conn, feature_collection: dict) -> int:
    """Upsert district_boundary from a FeatureCollection. Returns rows written."""
    rows = features_to_rows(feature_collection)
    for district, geom in rows:
        conn.execute(
            "INSERT INTO district_boundary (council_district, geom) VALUES (%s, %s) "
            "ON CONFLICT (council_district) DO UPDATE SET geom = EXCLUDED.geom",
            (district, Json(geom)),
        )
    log.info("loaded %d district boundaries", len(rows))
    return len(rows)
