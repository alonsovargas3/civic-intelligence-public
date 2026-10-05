# Runbook — build the static (database-free) dashboard

Produces a CDN-hostable `frontend/dist/` with no backend. The static variant also
hides the "Your address" link/`/you` flow and the "Equity" sidebar tab. All of this
is gated by `VITE_STATIC=1`; the default build is unchanged.

## 1. Bake the data snapshots (needs the DB up)

    # Postgres must be running (docker compose up db, or local PG the API points at)
    # Run from the repo root; no PYTHONPATH needed (the script bootstraps its own path).
    python scripts/export_static.py            # writes frontend/public/data/*.json
    python scripts/export_static.py --check     # verify all expected files present

The snapshots are a point-in-time freeze. Re-run the exporter to refresh. They are
gitignored — regenerate before each build.

## 2. Build the static site

    cd frontend
    VITE_STATIC=1 npm run build                 # -> frontend/dist/

## 3. Verify with NO backend (isolated ground truth)

Stop the API and DB, then:

    cd frontend && npm run preview

Confirm in the browser: every panel (Data, Stories, Methods, Ownership, Council) and
every story page renders from /data/*.json, and the "Your address" link, "Equity"
tab, and #/you page are all absent. Because nothing is fetching /v1, this proves the
build is database-free.

## Notes / limits

- Map label glyphs still load from demotiles.maplibre.org at runtime (fonts only,
  not data). Self-hosting them is an optional later polish.
- To restore the removed UI, build without VITE_STATIC — no code change needed.
