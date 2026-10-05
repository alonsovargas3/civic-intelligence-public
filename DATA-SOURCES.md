# Data sources, attribution and rights

## Code versus data

- **The code in this repository is MIT-licensed** (see [`LICENSE`](LICENSE)).
- **The MIT license covers no data.** The repository bundles no source data and no generated
  aggregates. When you run the code, you fetch data directly from the publishers below. That
  data, and anything you derive from it, stays under each publisher's own terms. You are
  responsible for following those terms and for the attribution each one requires.
- This file is a practical guide, not legal advice. Each publisher's current terms control.
  Check them before you republish anything.

## Primary sources

| Source | What the code uses | Where the code touches it | Terms / attribution |
|---|---|---|---|
| **City of Austin Open Data Portal** (`data.austintexas.gov`, Socrata) | 311 requests, construction permits, crime reports, crash and crash-victim records, code complaints, Austin Finance Online checkbook, campaign-finance contributions and expenditures, council voting record, contracts, council-district demographics, short-term-rental licenses, repeat-offender registrations, lobbyist registrations/clients/reports, Animal Center intakes/outcomes, food-establishment inspection scores, council-district boundaries | `config/sources.yaml`, `atx_ingest/socrata.py`, `atx_dashboard/boundaries.py` | Use is governed by the portal's Terms of Use, linked from the portal footer at <https://data.austintexas.gov>. Cite the City of Austin and the specific dataset (each dataset ID is listed in `config/sources.yaml`). Do not imply City endorsement. |
| **City of Austin Legistar Web API** (`webapi.legistar.com`, client `austintexas`) | Council events, matters, persons, bodies, event items, matter sponsors | `atx_ingest/legistar.py`, `config/sources.yaml` | Public meeting records published by the City of Austin through Granicus Legistar. Cite the City of Austin / Legistar and follow the API provider's terms. |
| **Inside Airbnb** (`insideairbnb.com`) | Austin "summary listings" CSV snapshots, used for the STR-licensing-gap analysis | `scripts/load_airbnb.py`, `atx_dashboard/str_gap.py` | Inside Airbnb states that its data "is licensed under a Creative Commons Attribution 4.0 International License" (<https://creativecommons.org/licenses/by/4.0/>). **Any published figure derived from it must credit Inside Airbnb** and indicate changes. The CSVs are not included. Download them yourself from <https://insideairbnb.com/get-the-data/>. |
| **Travis Central Appraisal District (TCAD)** (`traviscad.org`) | Certified/supplemental appraisal-roll exports (property and property-entity files) | `atx_ingest/tcad/` | Public records from TCAD's public-information downloads. **This repository contains code only and no owner rows.** The roll includes owner names and mailing addresses. Texas Tax Code §25.025 makes some owners' addresses confidential. Publish aggregates only, never owner-level rows. Follow TCAD's published terms for its downloads. |
| **Travis County GIS** (`gis.traviscountytx.gov`) | Parcel polygons for the parcel→district crosswalk | `atx_ingest/tcad/geo.py` | Public GIS service. Follow Travis County's terms for the service and cite Travis County. |
| **Travis County Clerk** | Deed-recording events (grantor/grantee, document type, recorded date) | `atx_deeds/` | The repository ships only a source-agnostic loader and a JSON-lines `SampleSource` adapter. **No deed records are included.** Bulk access is subject to the Clerk's terms and fees. |
| **Ballotpedia** (`ballotpedia.org`) | Citation links for Austin ballot-measure results | `data/ballot_crosswalk.csv` | The crosswalk holds hand-entered public election facts (measure, committee, side, vote totals, outcome) and a **link** to a Ballotpedia page for each row. No Ballotpedia text is reproduced. Check Ballotpedia's terms before reusing its content. |
| **U.S. Census Bureau** (TIGERweb, Geocoder) | ZCTA (ZIP) polygons; one-line address geocoding for the local "your address" view | `atx_dashboard/zip_boundaries.py`, `atx_dashboard/api.py` | Federal government services. Cite the U.S. Census Bureau. The geocoder sends whatever address a user types to the Census API. Treat that as user data. |

## Third-party software and assets loaded at runtime

- **npm dependencies** are listed in `frontend/package.json` and `frontend/package-lock.json`
  and carry their own licenses. Run a license checker before you redistribute a build.
- **Python dependencies** are listed in `requirements.txt` and carry their own licenses.
- **Google Fonts** (Public Sans, IBM Plex) are loaded at runtime from `fonts.googleapis.com`
  (`frontend/src/tokens.css`). These fonts are distributed under the SIL Open Font License.
- **MapLibre** stylesheet from `unpkg.com` and label glyphs from `demotiles.maplibre.org` are
  loaded at runtime. They are not vendored.
- The repository bundles no images or other media assets.

## Generated outputs are not included

All of the following come from your own database and are **gitignored**:

- static API snapshots (`frontend/public/data/*.json`) from `scripts/export_static.py`
- story markdown (`docs/stories/*.md`) from `scripts/export_stories.py`
- findings documents (`docs/str-gap-findings.md`, `docs/money-wins-findings.md`) from `scripts/analyze_*.py`

If you publish your own outputs, follow each source's terms above. In particular, credit
Inside Airbnb for STR figures, and keep TCAD-derived results at the aggregate level.
