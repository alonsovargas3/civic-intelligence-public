"""TCAD slice 2: parcel geometry from the Travis County public ArcGIS REST API.

Pulls parcel polygons as GeoJSON (paginated, 2000/page) and upserts them into parcel_geo,
keyed on PROP_ID (= parcel.account_id). GeoJSON is stored as-is in a jsonb column (no PostGIS).
Geometry is a current snapshot, so this upserts rather than versioning append-only like the roll.
"""
import logging
import time

import requests
from psycopg.types.json import Json
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

log = logging.getLogger("atx.tcad.geo")

DEFAULT_URL = (
    "https://gis.traviscountytx.gov/server1/rest/services/"
    "Boundaries_and_Jurisdictions/TCAD_public/MapServer/0"
)
GEO_FIELDS = "PROP_ID,geo_id,tcad_acres,situs_address"
PAGE_SIZE = 2000          # the layer's maxRecordCount
DEFAULT_SRID = 2277       # NAD83 / Texas Central (ftUS)


class ArcgisError(Exception):
    """Raised for HTTP errors from the ArcGIS REST API."""


def feature_to_row(feature: dict, srid: int = DEFAULT_SRID) -> dict | None:
    """Map a GeoJSON parcel feature to a parcel_geo row dict.

    Returns None when PROP_ID is missing (can't key the row) so the caller skips it.
    """
    props = feature.get("properties") or {}
    prop_id = props.get("PROP_ID")
    if prop_id is None:
        return None
    return {
        "account_id": str(prop_id),
        "geo_id": props.get("geo_id"),
        "geom": feature.get("geometry"),
        "srid": srid,
        "acres": props.get("tcad_acres"),
        "situs": props.get("situs_address"),
    }


class ArcgisClient:
    def __init__(self, base_url: str = DEFAULT_URL, timeout: int = 60,
                 page_delay: float = 0.2):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.page_delay = page_delay        # politeness between pages
        self.session = requests.Session()
        self.session.headers["User-Agent"] = (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        )

    @retry(
        reraise=True,
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type(ArcgisError),
    )
    def _get(self, url: str, params: dict) -> dict:
        resp = self.session.get(url, params=params, timeout=self.timeout)
        if resp.status_code in (429, 500, 502, 503, 504):
            raise ArcgisError(f"retryable {resp.status_code}: {resp.text[:200]}")
        if resp.status_code >= 400:
            raise ArcgisError(f"status {resp.status_code}: {resp.text[:300]}")
        return resp.json()

    def fetch_features(self, out_fields: str = GEO_FIELDS, page_size: int = PAGE_SIZE,
                       out_sr: int = DEFAULT_SRID):
        """Yield GeoJSON feature dicts, paging the layer's /query endpoint.

        Stops when a page returns fewer than page_size features (or none). ArcGIS sets
        `exceededTransferLimit: true` on a full page; we page until that's no longer the case
        (i.e. the page came back short).
        """
        url = f"{self.base_url}/query"
        offset = 0
        while True:
            params = {
                "where": "1=1",
                "outFields": out_fields,
                "f": "geojson",
                "outSR": out_sr,
                "resultOffset": offset,
                "resultRecordCount": page_size,
            }
            data = self._get(url, params)
            feats = data.get("features") or []
            if not feats:
                break
            yield from feats
            if len(feats) < page_size:
                break
            offset += page_size
            if self.page_delay:
                time.sleep(self.page_delay)


def load_parcel_geo(conn, base_url: str = DEFAULT_URL, srid: int = DEFAULT_SRID) -> dict:
    """Stream parcels from ArcGIS and upsert each into parcel_geo. Returns a summary.

    Upsert (not append-only): parcel geometry is a current snapshot, so re-running refreshes
    rows idempotently and a partial run simply overwrites on the next pass.
    """
    client = ArcgisClient(base_url)
    rows = skipped = 0
    for feature in client.fetch_features():
        row = feature_to_row(feature, srid=srid)
        if row is None:
            skipped += 1
            continue
        conn.execute(
            """
            INSERT INTO parcel_geo (account_id, geo_id, geom, srid, acres, situs, loaded_at)
            VALUES (%(account_id)s, %(geo_id)s, %(geom)s, %(srid)s, %(acres)s, %(situs)s, now())
            ON CONFLICT (account_id) DO UPDATE
                SET geo_id    = EXCLUDED.geo_id,
                    geom      = EXCLUDED.geom,
                    srid      = EXCLUDED.srid,
                    acres     = EXCLUDED.acres,
                    situs     = EXCLUDED.situs,
                    loaded_at = now()
            """,
            {**row, "geom": Json(row["geom"])},
        )
        rows += 1
    log.info("parcel_geo: upserted %d rows (%d skipped)", rows, skipped)
    return {"rows": rows, "skipped": skipped}
