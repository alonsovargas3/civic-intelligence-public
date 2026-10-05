"""One-time loader for ZIP (ZCTA) boundary polygons.

Our analytics carry a situs ZIP (e.g. metric_assessment_cod), but we have no ZIP
geometry to draw a ZIP-level map. This fetches the ZIPs we actually use from the
US Census TIGERweb 2020 ZCTA layer (GeoJSON) — which covers all of Travis County,
including the rural ZIPs an Austin-city dataset would miss — and loads zip_boundary.
Network fetch is isolated from the pure parsers so they unit-test offline.
"""
from __future__ import annotations

import logging

import requests
from psycopg.types.json import Json

log = logging.getLogger("atx.dashboard.zip_boundaries")

# Census TIGERweb 2020 ZIP Code Tabulation Areas (layer 2); query by BASENAME (the ZIP).
ZCTA_QUERY_URL = (
    "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/"
    "tigerWMS_Current/MapServer/2/query"
)
_CHUNK = 40   # ZIPs per request (keeps the where-clause / response sizes sane)


def valid_zips(raw) -> list[str]:
    """Dedup + sort the 5-digit numeric ZIPs, dropping blanks/junk and '00000'."""
    out = set()
    for z in raw:
        z = (z or "").strip()
        if len(z) == 5 and z.isdigit() and z != "00000":
            out.add(z)
    return sorted(out)


def zips_to_load(conn) -> list[str]:
    """The ZIPs our ZIP-level metrics reference (from metric_assessment_cod)."""
    rows = conn.execute("SELECT DISTINCT situs_zip FROM metric_assessment_cod").fetchall()
    return valid_zips(r[0] if not isinstance(r, dict) else r["situs_zip"] for r in rows)


def features_to_rows(feature_collection: dict) -> list[tuple[str, dict]]:
    """Map a GeoJSON FeatureCollection to [(zip, geometry_dict)] (first win per ZIP)."""
    seen: dict[str, dict] = {}
    for feat in feature_collection.get("features", []):
        props = feat.get("properties") or {}
        zip_ = (props.get("BASENAME") or props.get("GEOID") or "").strip()
        geom = feat.get("geometry")
        if zip_ and geom and zip_ not in seen:
            seen[zip_] = geom
    return sorted(seen.items())


def fetch(zips: list[str]) -> dict:
    """Fetch ZCTA polygons for `zips` from TIGERweb, chunked. Returns a FeatureCollection."""
    features: list[dict] = []
    for i in range(0, len(zips), _CHUNK):
        chunk = zips[i:i + _CHUNK]
        where = "BASENAME IN (" + ",".join(f"'{z}'" for z in chunk) + ")"
        resp = requests.get(ZCTA_QUERY_URL, params={
            "where": where, "outFields": "BASENAME,GEOID",
            "returnGeometry": "true", "f": "geojson",
        }, timeout=90)
        resp.raise_for_status()
        features.extend(resp.json().get("features", []))
    return {"type": "FeatureCollection", "features": features}


def load(conn, feature_collection: dict) -> int:
    """Upsert zip_boundary from a FeatureCollection. Returns rows written."""
    rows = features_to_rows(feature_collection)
    for zip_, geom in rows:
        conn.execute(
            "INSERT INTO zip_boundary (zip, geom) VALUES (%s, %s) "
            "ON CONFLICT (zip) DO UPDATE SET geom = EXCLUDED.geom",
            (zip_, Json(geom)),
        )
    log.info("loaded %d zip boundaries", len(rows))
    return len(rows)
