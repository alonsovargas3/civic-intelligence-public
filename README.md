# Austin Civic Intelligence

Source code for a research project that combines Austin, Texas public-records data into a set
of sourced civic "data stories" and a read-only dashboard. The code ingests open data into
Postgres, builds aggregate metric tables, serves them through a small read API, and renders
them in a React/Vite frontend.

> **Status: code snapshot only.** This repository holds the source code as of **2026-10-05**.
> It contains **no data and no generated outputs**. A data refresh is still in progress in a
> separate, private environment. **This repository does not claim that all 19 stories are
> current.** There is **no public hosted version** of the app.

## What it was built for: 19 data stories

The project's original goal was 19 narrative reads, each built by crossing public datasets
and each carrying its own methodology and limits. The framing is research, not advocacy:
every figure is meant as a screening signal, not an accusation.

| Slug | Story | Topic |
|---|---|---|
| `animal-shelter` | Austin Animal Center outcomes | City services · Animals |
| `food-inspections` | Austin food inspection scores | City services · Food safety |
| `who-owns-austin` | Who Owns Austin | Property · Ownership |
| `homestead-cap` | The homestead cap | Property · Taxes |
| `short-term-rentals` | Austin's licensed short-term rentals | Housing · Rentals |
| `str-gap` | Short-term rental listings and licenses | Housing · Rentals |
| `investor-single-family` | Code complaints by owner type | Property · Code |
| `traffic-deaths` | Traffic crashes and deaths | Safety · Vision Zero |
| `who-lobbies` | Who lobbies City Hall | Influence · Lobbying |
| `council-dissent` | Austin City Council voting patterns | Governance · Council |
| `money-influence` | Campaign money, votes and contracts | Money · Influence |
| `ballot-money` | Who funds Austin's ballot campaigns | Money · Elections |
| `money-wins` | Campaign fundraising and ballot outcomes | Money · Elections |
| `home-builders` | Who's building Austin's homes | Growth · Housing |
| `district-divide` | Council district demographics and services | Equity · Districts |
| `service-equity` | 311 response times by district | Civic services · 311 |
| `local-money` | Where Austin campaign money comes from | Money · Elections |
| `who-pays` | Who pays for Austin politics | Money · Elections |
| `where-city-dollars-go` | Where city dollars go | Money · Spending |

Notes on the story code:
- Story titles and one-line summaries in `frontend/src/stories/index.jsx` and the front pages
  describe topics only. Figures come from the read API (`/v1/stories/<slug>`) or from static
  JSON snapshots that you generate yourself (see below).
- Narrative text inside individual story components was written during earlier private
  analysis and may describe results that a fresh data refresh does not reproduce. Treat
  it as draft copy, not as current findings.
- The `status: 'published'` field is an internal UI flag. It does not mean a public site exists.
- `BRAND_DOMAIN` in `frontend/src/brand.js` is the placeholder `example.org`. Set your own
  before deploying. Contact copy points readers to this repository's issue tracker.

## Repository layout

| Path | What it is |
|---|---|
| `atx_ingest/` | Incremental ingestion of City of Austin Socrata datasets and the Legistar council API into Postgres (`raw_*` JSONB tables). `atx_ingest/tcad/` loads Travis Central Appraisal District roll exports. |
| `atx_council/` | Council member normalization and sponsorship / representation builds. |
| `atx_deeds/` | Deed-record loader with a pluggable source; ships only a JSON-lines sample adapter. |
| `atx_entity/` | Owner entity resolution over appraisal-roll owner names and addresses. |
| `atx_ownership/` | Ownership concentration, owner-type differentials, parcel→district crosswalk. |
| `atx_anomaly/` | Screening detectors (assessment dispersion and related signals). |
| `atx_dashboard/` | Aggregate builders and the FastAPI read API (`/v1/...`) behind the dashboard and stories. |
| `scripts/` | Static snapshot export, story markdown export, Inside Airbnb loader, analysis helpers. |
| `frontend/` | React/Vite dashboard and story pages. |
| `config/sources.yaml` | Source registry (dataset IDs, cursors, enabled flags). |
| `data/ballot_crosswalk.csv` | Small hand-curated crosswalk of Austin ballot measures to campaign committees. Each row cites its source. |
| `docs/runbooks/static-dashboard-build.md` | How to build the database-free static dashboard. |
| `tests/` | Offline unit tests. Database tests are skipped unless you point them at a test DB. |

## Setup (local development only)

Requirements: Python 3.12, Docker (for Postgres), Node 18+ (for the frontend).

```bash
cp .env.example .env            # optional: add a free Socrata app token
docker compose up -d db         # Postgres 16 on 127.0.0.1:5432 only
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python -m atx_ingest.cli init
python -m atx_ingest.cli run-once
```

**Database defaults are for local development only.** `docker-compose.yml` uses the
well-known placeholder credentials `atx` / `atx` and binds Postgres to `127.0.0.1`, so it is
not reachable from other machines. `.env.example` holds placeholders only, matching that
local database. Never deploy this stack as-is. Use your own credentials through environment
variables. `.env` is gitignored.

The optional `ingester` container is behind a compose profile
(`docker compose --profile ingest up`). It polls every 30 minutes.

### Ingester commands

| Command | Does |
|---|---|
| `init` | create the state table and a `raw_<table>` per source |
| `run-once` | one incremental pass over all enabled sources |
| `run --interval 1800` | poll forever |
| `discover <dataset_id>` | print a dataset's column names |
| `backfill <dataset_id\|all>` | reset the cursor and re-pull |

Several large sources in `config/sources.yaml` are set to `enabled: false`. In the original
deployment their bulk history was archived outside the working database and restored only when
needed for a refresh. Enable them deliberately if you have the disk space.

### Read API and dashboard

```bash
python -m atx_dashboard.cli load-boundaries    # council-district polygons
python -m atx_dashboard.cli refresh            # build metric_* aggregates from raw_* tables
python -m atx_dashboard.cli serve --port 8000  # read API on 127.0.0.1:8000

cd frontend
npm install
npm run dev                                    # Vite proxies /v1 → 127.0.0.1:8000
```

### Static (database-free) mode: data not included

`VITE_STATIC=1` makes the frontend read pre-baked JSON from `frontend/public/data/` instead of
calling `/v1`. **Those snapshots are not in this repository.** They are generated aggregates
and stay out of version control (`frontend/public/data/` is gitignored). To use static mode,
generate them from your own database first:

```bash
python scripts/export_static.py            # needs the DB; writes frontend/public/data/*.json
cd frontend && VITE_STATIC=1 npm run build
```

The food-inspections page can also read an optional `/data/story_refresh_status.json`
(refresh provenance). When it is missing, the page says that source accounting is
unavailable. That file is not included either.

Without generated snapshots, static mode builds, but the story and panel pages show a
"could not load" or pending state. This is expected. See
`docs/runbooks/static-dashboard-build.md`.

The story markdown exporter (`scripts/export_stories.py`) and the analysis scripts
(`scripts/analyze_*.py`) also write generated outputs (`docs/stories/`,
`docs/*-findings.md`). Those outputs are gitignored and not included here.

## Tests

```bash
python -m pytest -q          # offline tests; DB tests skip unless DASHBOARD_TEST_DSN is set
cd frontend && npm test      # vitest
```

Some DB-backed tests create and drop a scratch schema. Point `DASHBOARD_TEST_DSN` only at a
disposable local test database.

## Data, privacy and licensing

- **Code:** MIT. See [`LICENSE`](LICENSE).
- **Data:** third-party, under the publishers' own terms. The MIT license does **not** cover
  any data. See [`DATA-SOURCES.md`](DATA-SOURCES.md) for sources, attribution (including
  Inside Airbnb's CC BY 4.0 requirement) and caveats.
- **Appraisal-roll owner data:** the TCAD loaders process owner names and mailing addresses so
  they can produce **aggregate** ownership statistics. Under Texas Tax Code §25.025 some
  owners' addresses are confidential. Do not publish owner-level rows.
- `atx_dashboard` also has a row-level `/v1/incidents/recent` endpoint for local exploration.
  The static exporter does not include it, and it should not be exposed publicly.

## What this public snapshot leaves out

This repository was curated from a private working repository. On purpose, it does **not** include:

- any data: raw source extracts, database dumps, generated aggregate JSON, story markdown,
  findings write-ups, or built frontend output;
- 2026 refresh pipeline code that is tied to private infrastructure: snapshot/acquisition
  runners, supervision, deployment and control scripts, per-story refresh jobs, and their
  tests and fixtures. The `atx_ingest` package here is the general Socrata, Legistar and
  TCAD ingester;
- the private issue tracker, operational runbooks, planning and review archives, agent
  handoff notes, and design-tool mockups;
- internal design specs, the dataset catalog and analysis notes. Documentation here is kept to
  this README, `DATA-SOURCES.md` and `docs/runbooks/static-dashboard-build.md`. The source
  registry is `config/sources.yaml`.
