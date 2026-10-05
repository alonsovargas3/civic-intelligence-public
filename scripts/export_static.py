"""Bake the dashboard's /v1 API responses into static JSON snapshots.

Run with the database up (uses FastAPI TestClient against the live app):

    python scripts/export_static.py           # write frontend/public/data/*.json
    python scripts/export_static.py --check    # verify every expected file exists

The slug produced by static_filename() MUST match the JS staticPath() in
frontend/src/api.js (locked by tests/fixtures/static_slug_pairs.json).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
OUT_DIR = ROOT / "frontend" / "public" / "data"

DATASETS = ["crime", "311"]
PERIODS = ["2025", "2024", "2023"]
DISTRICTS = [str(d) for d in range(1, 11)]
METHOD_METRICS = ["crime", "311"]
STORY_SLUGS = [
    "who-owns-austin", "homestead-cap", "investor-complaints", "city-dollars",
    "ballot-money", "money-wins", "traffic-deaths", "home-builders",
    "service-equity", "local-money", "who-pays", "money-influence",
    "district-divide", "council-dissent", "short-term-rentals", "who-lobbies",
    "animal-shelter", "food-inspections", "str-gap",
]


def static_filename(url: str) -> str:
    """Mirror of frontend/src/api.js staticPath(), minus the /data/ prefix."""
    s = url[len("/v1/"):] if url.startswith("/v1/") else url
    s = re.sub(r"[^a-zA-Z0-9]+", "_", s).strip("_")
    return f"{s}.json"


def base_urls() -> list[str]:
    urls = ["/v1/districts.geojson", "/v1/council/funding-activity", "/v1/council/representation"]
    urls += [f"/v1/metric/incidents?dataset={d}&period={p}" for d in DATASETS for p in PERIODS]
    urls += [f"/v1/place/district/{d}?period={p}" for d in DISTRICTS for p in PERIODS]
    urls += [f"/v1/methods/{m}" for m in METHOD_METRICS]
    urls += [f"/v1/stories/{s}" for s in STORY_SLUGS]
    return urls


def _client():
    from fastapi.testclient import TestClient
    from atx_dashboard.api import app
    return TestClient(app)


def _get_json(client, url: str):
    resp = client.get(url)
    if resp.status_code != 200:
        raise SystemExit(f"ABORT: {url} -> HTTP {resp.status_code}: {resp.text[:200]}")
    return resp.json()


def all_urls(client) -> list[str]:
    """Base URLs plus one owner-type/zips URL per discovered property class."""
    urls = list(base_urls())
    classes = _get_json(client, "/v1/ownership/owner-type?property_class=A1").get("classes") or ["A1"]
    for c in classes:
        urls.append(f"/v1/ownership/owner-type?property_class={c}")
        urls.append(f"/v1/zips.geojson?property_class={c}")
    return urls


def export() -> None:
    client = _client()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    urls = all_urls(client)
    for url in urls:
        data = _get_json(client, url)
        (OUT_DIR / static_filename(url)).write_text(json.dumps(data, separators=(",", ":")))
    print(f"Wrote {len(urls)} snapshots to {OUT_DIR}")


def check() -> None:
    client = _client()
    missing, empty = [], []
    for url in all_urls(client):
        f = OUT_DIR / static_filename(url)
        if not f.exists():
            missing.append(f.name)
            continue
        try:
            if not json.loads(f.read_text()):
                empty.append(f.name)
        except Exception:
            empty.append(f.name)
    if missing or empty:
        raise SystemExit(f"CHECK FAILED. missing={missing} empty/invalid={empty}")
    print("CHECK OK: all expected snapshots present and non-empty.")


if __name__ == "__main__":
    (check if "--check" in sys.argv[1:] else export)()
