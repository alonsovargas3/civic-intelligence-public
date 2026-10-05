"""Thin read-only FastAPI over the metric_* tables. Versioned /v1, cacheable.

Reads pre-aggregated metric_* for everything except /v1/incidents/recent, which
reads raw_* directly with a bounded LIMIT (the live tracker passthrough).
"""
from __future__ import annotations

import re

import psycopg
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
from psycopg.rows import dict_row

from . import db
from .metrics import rank_and_percentile

_CACHE = "public, max-age=300"

# Owner 'kind' is a name heuristic that misreads some public bodies as 'individual'
# (e.g. "BOARD OF REGENTS OF THE", "PFLUGERVILLE I S D"). For the public/private
# split on the ownership story we apply an EXPLICIT, documented name override so a
# government body never lands in the "private holders" list. Display-only — it does
# not alter the underlying concentration metrics.
_PUBLIC_NAME_RE = re.compile(
    r"\b(I\s?S\s?D|INDEPENDENT SCHOOL|SCHOOL DIST|BOARD OF REGENTS|UNIVERSITY|"
    r"COLLEGE|CITY OF|COUNTY|STATE OF|UNITED STATES|FEDERAL|HOUSING AUTHORITY|"
    r"PUBLIC FINANCE|MUNICIPAL|TRANSIT AUTHORITY|DEPT OF|DEPARTMENT OF)\b",
    re.IGNORECASE,
)


def _owner_sector(kind: str | None, name: str | None) -> str:
    if kind == "government" or (name and _PUBLIC_NAME_RE.search(name)):
        return "public"
    return "private"

def create_app(dsn: str | None = None) -> FastAPI:
    app = FastAPI(title="ATX Civic Dashboard API", version="1.0")
    _dsn = dsn or db.dsn()

    def q(sql: str, params=()):
        with psycopg.connect(_dsn, row_factory=dict_row) as c:
            return c.execute(sql, params).fetchall()

    def cached(payload):
        return JSONResponse(payload, headers={"Cache-Control": _CACHE})

    @app.get("/v1/metric/incidents")
    def incidents(dataset: str = Query("crime"), period: str = Query(...)):
        rows = q(
            "SELECT council_district, sum(incident_count)::int AS incident_count "
            "FROM metric_incidents_by_district "
            "WHERE dataset = %s AND to_char(period_month,'YYYY') = %s "
            "GROUP BY council_district ORDER BY council_district",
            (dataset, period),
        )
        return cached(rank_and_percentile(rows))

    @app.get("/v1/place/district/{district}")
    def place(district: int, period: str = Query(...)):
        totals = q(
            "SELECT dataset, sum(incident_count)::int AS n FROM metric_incidents_by_district "
            "WHERE council_district = %s AND to_char(period_month,'YYYY') = %s GROUP BY dataset",
            (district, period),
        )
        trend = q(
            "SELECT to_char(period_month,'YYYY-MM') AS month, dataset, incident_count "
            "FROM metric_incidents_by_district WHERE council_district = %s "
            "AND to_char(period_month,'YYYY') = %s ORDER BY period_month",
            (district, period),
        )
        breakdown = q(
            "SELECT dataset, dimension, label, value FROM metric_district_breakdown "
            "WHERE council_district = %s AND period = %s ORDER BY value DESC LIMIT 20",
            (district, period),
        )
        resp = q(
            "SELECT median_days::float8 AS median_days, closed_count, open_count "
            "FROM metric_311_response WHERE council_district = %s AND period = %s",
            (district, period),
        )
        return cached({
            "district": district,
            "totals_by_dataset": totals,
            "monthly_trend": trend,
            "breakdown": breakdown,
            "response_time": resp[0] if resp else None,
        })

    @app.get("/v1/incidents/recent")
    def recent(dataset: str = Query("311"), district: int | None = None,
               limit: int = Query(50, ge=1, le=200)):
        where, params = "WHERE dataset = %s", [dataset]
        if district is not None:
            where += " AND council_district = %s"
            params.append(district)
        rows = q(f"SELECT payload FROM recent_incidents {where} "
                 f"ORDER BY ts DESC LIMIT %s", (*params, limit))
        return cached([r["payload"] for r in rows])

    @app.get("/v1/districts.geojson")
    def districts_geojson():
        rows = q("SELECT council_district, geom FROM district_boundary ORDER BY council_district")
        return cached({
            "type": "FeatureCollection",
            "features": [
                {"type": "Feature", "properties": {"council_district": r["council_district"]},
                 "geometry": r["geom"]}
                for r in rows
            ],
        })

    @app.get("/v1/zips.geojson")
    def zips_geojson(property_class: str = Query("A1")):
        rows = q(
            "SELECT z.zip, z.geom, m.cod::float8 AS cod, "
            "       m.cod_pctile_in_class::float8 AS pctile, m.high_dispersion, m.n_parcels "
            "FROM zip_boundary z "
            "LEFT JOIN metric_assessment_cod m ON m.situs_zip = z.zip "
            "  AND m.property_class = %s "
            "  AND m.roll_year = (SELECT max(roll_year) FROM metric_assessment_cod) "
            "ORDER BY z.zip",
            (property_class,))
        return cached({
            "type": "FeatureCollection",
            "features": [
                {"type": "Feature",
                 "properties": {
                     "zip": r["zip"], "cod": r["cod"],
                     "percentile": (r["pctile"] * 100) if r["pctile"] is not None else None,
                     "high_dispersion": r["high_dispersion"], "n_parcels": r["n_parcels"],
                 },
                 "geometry": r["geom"]}
                for r in rows
            ],
        })

    @app.get("/v1/meta")
    def meta():
        # cast timestamp -> text so JSONResponse can serialize it
        rows = q("SELECT dataset_id, rows_ingested, last_run_at::text AS last_run_at "
                 "FROM ingestion_state ORDER BY rows_ingested DESC")
        return cached({"freshness": rows})

    @app.get("/v1/methods/{metric}")
    def methods(metric: str):
        return cached({
            "metric": metric,
            "notes": [
                "Counts are pre-aggregated per council district per month from the raw incident feeds.",
                "Crime has no point coordinates in the source; it is shown only at district level.",
                "Crashes and code cases carry no council district; they appear as point/heatmap layers, not in district rankings.",
                "No sale prices or assessment ratios are shown — Texas is a non-disclosure state.",
                "Research, not advocacy: we publish methodology and let users draw conclusions.",
            ],
        })

    @app.get("/v1/council/funding-activity")
    def council_funding():
        rows = q(
            "SELECT canonical_name, n_matters_sponsored, "
            "       contributions_total::float8 AS contributions_total, n_contributions "
            "FROM metric_member_funding_activity ORDER BY contributions_total DESC")
        return cached({
            "members": rows,
            "methodology": (
                "Contribution -> sponsorship — a SCREENING SIGNAL, not a causal or vote "
                "claim. Austin's Legistar API does not expose per-member votes, so this "
                "links campaign contributions a council member RECEIVED to the matters they "
                "SPONSORED. Members come from the Legistar sponsor roster; contributions are "
                "matched by name (last + first initial) across the 'Last, First' and "
                "'Council Member First Last' formats, so matching is approximate and "
                "contributions include some non-municipal filings. Sponsorship is one input "
                "to influence, not a vote; more money does not imply any quid pro quo."),
        })

    @app.get("/v1/council/representation")
    def council_representation():
        members = q(
            "SELECT canonical_name, n_lead, n_cosponsor, n_total "
            "FROM metric_member_sponsorship ORDER BY n_lead DESC")
        coalitions = q(
            "SELECT name_a, name_b, shared_matters FROM metric_cosponsorship "
            "ORDER BY shared_matters DESC LIMIT 15")
        return cached({
            "members": members,
            "coalitions": coalitions,
            "methodology": (
                "Representation patterns from SPONSORSHIP. Per member: matters LED (sponsor "
                "sequence 0) vs co-sponsored. Coalitions = how often a pair of members sponsor "
                "the same matter (~96% of matters are co-sponsored). Descriptive — co-sponsorship "
                "reflects collaboration/agenda alignment, not a vote or an endorsement. NOTE: "
                "per-member ROLL-CALL VOTES are now ingested (raw_council_votes, 2023-present) — "
                "for actual voting patterns and real-vote coalitions see the 'What Austin Council "
                "fights about' story; this panel remains sponsorship-based for the full 2017-2026 "
                "span the votes don't cover."),
        })

    @app.get("/v1/ownership/owner-type")
    def owner_type(property_class: str = Query("A1")):
        concentration = q(
            "SELECT segment AS owner_kind, n_entities, n_parcels, "
            "       parcel_share::float8 AS parcel_share, value_share::float8 AS value_share "
            "FROM metric_ownership_concentration WHERE dimension = 'kind' "
            "ORDER BY n_parcels DESC")
        # category-stratified differential treatment for the selected class
        treatment = q(
            "SELECT owner_type, parcels, assessment_index::float8 AS assessment_index, "
            "       code_cases, code_cases_per_1k::float8 AS code_cases_per_1k, "
            "       code_case_index::float8 AS code_case_index "
            "FROM metric_owner_treatment WHERE property_class = %s "
            "ORDER BY parcels DESC",
            (property_class,))
        classes = [r["property_class"] for r in q(
            "SELECT DISTINCT property_class FROM metric_owner_treatment ORDER BY property_class")]
        return cached({
            "property_class": property_class,
            "classes": classes,
            "concentration": concentration,
            "treatment": treatment,
            "methodology": (
                "Owner-type differential treatment, STRATIFIED BY PROPERTY CLASS — "
                "institutional vs individual is compared within a class (e.g. A1 single-"
                "family), not across a confounded mix. Lead with the indices: "
                "assessment_index = the owner type's median appraised value/acre vs the "
                "all-owner median within (class, ZIP); code_case_index = its code-case rate "
                "vs the class's all-owner rate (~1 means a blended gap was pure property "
                "mix). Code cases are counted only from a recent window and attributed to "
                "the current owner via parcel geo_id (~94% join, deduped). Per-acre is a "
                "crude size control (no living-sqft in the roll). Owner 'kind' is a name "
                "heuristic with residual error. No sale prices (Texas non-disclosure). "
                "SCREENING SIGNALS, not findings."),
        })

    @app.get("/v1/stories/who-owns-austin")
    def story_who_owns_austin():
        """Narrative page #4 — ownership concentration over the 2025 certified roll.

        Splits the headline list into PUBLIC (government bodies, expected to dominate
        by value) vs PRIVATE holders — the private concentration is the actual finding.
        """
        overall = q(
            "SELECT n_entities, n_parcels, total_appraised::float8 AS total_appraised "
            "FROM metric_ownership_concentration WHERE dimension='overall'")
        by_kind = q(
            "SELECT segment AS kind, n_entities, n_parcels, "
            "       parcel_share::float8 AS parcel_share, value_share::float8 AS value_share, "
            "       total_appraised::float8 AS total_appraised "
            "FROM metric_ownership_concentration WHERE dimension='kind' "
            "ORDER BY n_parcels DESC")
        # 'government' kind = public; plus an explicit name override (_owner_sector)
        # so public bodies the kind-heuristic misreads as 'individual' (school
        # districts, the Board of Regents) don't surface in the private list.
        def rank(scope, limit):
            rows = q(
                "SELECT rank, canonical_name AS name, kind, n_parcels, "
                "       total_appraised::float8 AS total_appraised "
                "FROM metric_owner_ranking WHERE scope=%s ORDER BY rank LIMIT %s",
                (scope, limit))
            for r in rows:
                r["sector"] = _owner_sector(r["kind"], r["name"])
            return rows
        return cached({
            "roll_year": 2025,
            "overall": overall[0] if overall else None,
            "by_kind": by_kind,
            "top_by_value": rank("by_value", 30),
            "top_by_parcels": rank("by_parcels", 20),
            "methodology": (
                "Ownership is resolved with connected-components entity resolution over the "
                "2025 TCAD certified roll: owner names + mailing addresses are linked into "
                "entities (so an LLC's many parcels, or a trust and its variants, roll up to "
                "one owner). Concentration and rankings are computed over those entities. "
                "Owner 'kind' (individual / institutional / government) is a NAME HEURISTIC "
                "with residual error — a rare personal name can be misread, so kind shares "
                "are good-not-exact. For the public/private split here we additionally apply "
                "an explicit name rule so government bodies the heuristic misreads (school "
                "districts, the Board of Regents) are shown as public, not private. "
                "Government bodies are expected to top the value list; "
                "the private concentration beneath them is the finding. Values are TCAD "
                "APPRAISED value — no sale prices (Texas is a non-disclosure state). A single "
                "roll year (2025), so no year-over-year change is shown. Descriptive — who "
                "owns what, not an anomaly claim."),
        })

    @app.get("/v1/stories/homestead-cap")
    def story_homestead_cap():
        """Narrative page #6 — the homestead 10% cap as a tax shield, and its
        regressivity by home value.

        VALIDATED FIELD SEMANTICS: TCAD's parcel_value.capped_value is the homestead
        "cap loss" itself (appraised - assessed), i.e. the amount shielded — NOT a
        value to subtract from market. Confirmed equal to appraised-assessed for
        ~99.5% of capped homes. The shield is therefore sum(capped_value).
        """
        overall = q(
            "SELECT count(*) AS homesteads, "
            "       sum(capped_value)::float8 AS total_shielded, "
            "       avg(capped_value)::float8 AS avg_shield, "
            "       percentile_cont(0.5) WITHIN GROUP (ORDER BY capped_value)::float8 AS median_shield, "
            "       max(capped_value)::float8 AS max_shield, "
            "       count(*) FILTER (WHERE capped_value = appraised_value - assessed_value) AS matches_caploss "
            "FROM parcel_value WHERE roll_year=2025 AND capped_value>0")
        context = q(
            "SELECT sum(market_value)::float8 AS market, sum(appraised_value)::float8 AS appraised, "
            "       sum(assessed_value)::float8 AS assessed "
            "FROM parcel_value WHERE roll_year=2025")
        deciles = q(
            "WITH h AS (SELECT capped_value, market_value, "
            "             ntile(10) OVER (ORDER BY market_value) AS dec "
            "           FROM parcel_value WHERE roll_year=2025 AND capped_value>0) "
            "SELECT dec, count(*) AS n, min(market_value)::float8 AS min_mkt, "
            "       max(market_value)::float8 AS max_mkt, sum(capped_value)::float8 AS shield, "
            "       avg(capped_value)::float8 AS avg_shield "
            "FROM h GROUP BY dec ORDER BY dec")
        by_category = q(
            "SELECT p.category, count(*) AS n, sum(pv.capped_value)::float8 AS shield, "
            "       avg(pv.capped_value)::float8 AS avg_shield "
            "FROM parcel_value pv JOIN parcel p ON p.account_id = pv.account_id "
            "WHERE pv.roll_year=2025 AND pv.capped_value>0 AND p.category <> '' "
            "GROUP BY 1 ORDER BY 3 DESC NULLS LAST LIMIT 6")
        total = overall[0]["total_shielded"] or 1
        for d in deciles:
            d["share"] = (d["shield"] or 0) / total
        return cached({
            "roll_year": 2025,
            "overall": overall[0] if overall else None,
            "context": context[0] if context else None,
            "deciles": deciles,
            "by_category": by_category,
            "methodology": (
                "The Texas residence-homestead cap limits the taxable (assessed) value of a "
                "homesteaded property to a 10% increase per year, even when its market value "
                "rises faster. The gap between full appraised value and the capped assessed "
                "value is the amount shielded from taxation. We read that directly from the "
                "TCAD 2025 certified roll: the roll's capped_value field is that cap-loss "
                "amount (it equals appraised - assessed for 99.5% of capped homes — verified), "
                "so the total shield is the sum of capped_value across all capped homesteads. "
                "To show who benefits, capped homes are sorted into ten equal groups by market "
                "value and the shield is summed within each. This is a HORIZONTAL-EQUITY / "
                "who-is-shielded measure, not a claim that any home is mis-appraised, and not a "
                "claim the cap is good or bad — it limits year-over-year increases for every "
                "homesteader regardless of value. No sale prices are used (Texas non-"
                "disclosure). A single roll year (2025), so the multi-year accumulation that "
                "produces the cap loss is not itself shown."),
        })

    @app.get("/v1/stories/investor-complaints")
    def story_investor_complaints():
        """Narrative page #8 — investor-owned single-family homes draw more code
        COMPLAINTS than owner-occupied ones, after de-confounding property mix.

        Reframe (required): raw_code_cases.case_type is uniformly 'Complaints', so
        these are complaint-DRIVEN cases, not city-INITIATED enforcement. The honest
        read is a housing-conditions signal (plausibly tenant-occupied rentals with
        absentee maintenance), not a claim of government bias.
        """
        a1 = q(
            "SELECT owner_type, parcels, assessment_index::float8 AS assessment_index, "
            "       code_cases, code_cases_per_1k::float8 AS per_1k, "
            "       code_case_index::float8 AS index "
            "FROM metric_owner_treatment WHERE property_class='A1' ORDER BY parcels DESC")
        # institutional index across classes — the de-confounding view
        by_class = q(
            "SELECT property_class, parcels, code_cases_per_1k::float8 AS per_1k, "
            "       code_case_index::float8 AS index "
            "FROM metric_owner_treatment "
            "WHERE owner_type='institutional' AND parcels>=200 "
            "ORDER BY code_case_index DESC NULLS LAST")
        # blended (all-class) rates — shows the confound the stratification removes
        blended = q(
            "SELECT owner_type, sum(parcels) AS parcels, sum(code_cases) AS code_cases, "
            "       round(1000.0*sum(code_cases)/NULLIF(sum(parcels),0),1)::float8 AS per_1k "
            "FROM metric_owner_treatment WHERE owner_type IN ('institutional','individual') "
            "GROUP BY 1")
        window = q("SELECT min(window_start)::text AS w FROM metric_owner_treatment")
        # The city's formal repeat-offender registry — the extreme end of the pattern.
        ro_sum = q(
            "SELECT count(*) properties, sum((payload->>'numberofunits')::numeric)::int units, "
            "  sum((payload->>'totalviolations')::numeric)::int violations, "
            "  count(*) FILTER (WHERE payload->>'owner' ~* 'LLC|LP|INC|CORP|LTD|HOLDINGS|REALTY|PARTNERS') corporate "
            "FROM raw_repeat_offenders")[0]
        ro_top = q(
            "SELECT payload->>'owner' owner, (payload->>'numberofunits')::int units, "
            "  (payload->>'totalviolations')::int total_violations, "
            "  (payload->>'activeviolations')::int active_violations, payload->>'councildistrict' district "
            "FROM raw_repeat_offenders ORDER BY (payload->>'totalviolations')::numeric DESC NULLS LAST LIMIT 8")
        return cached({
            "a1": a1,
            "by_class": by_class,
            "blended": {r["owner_type"]: r for r in blended},
            "window_start": window[0]["w"] if window else None,
            "repeat_offenders": {
                "properties": ro_sum["properties"], "units": ro_sum["units"],
                "violations": ro_sum["violations"], "corporate": ro_sum["corporate"],
                "corporate_pct": round(100.0 * ro_sum["corporate"] / ro_sum["properties"]) if ro_sum["properties"] else None,
                "top": ro_top,
            },
            "methodology": (
                "Code cases come from Austin Code complaint records, joined to parcels by "
                "parcel id (≈94% match, de-duplicated) and attributed to the parcel's CURRENT "
                "owner from the 2025 roll. Every case here is a COMPLAINT the city received — "
                "the source marks them all 'Complaints' — so this measures complaint volume, "
                "not city-initiated enforcement, and not a violation finding. Rates are cases "
                "per 1,000 parcels counted from a recent window (cases opened on/after the "
                "window date). The code_case_index divides an owner type's rate by the "
                "ALL-OWNER rate within the SAME property class, so a value near 1.0 means a "
                "raw gap was just property mix. Owner type (individual / institutional) is a "
                "name heuristic with residual error. A screening signal about housing "
                "conditions — most plausibly tenant-occupied rentals with absentee "
                "maintenance — not a statement about any owner or any government bias."),
        })

    @app.get("/v1/stories/city-dollars")
    def story_city_dollars():
        """Narrative page #2 — where the city's $37B in disbursements actually goes.
        Descriptive context layer: debt service vs. operating, top departments, and
        the largest non-debt vendors.
        """
        # Reads pre-aggregated materialized views (mv_afo_*), refreshed by
        # atx_dashboard.cli refresh — a live scan of the 2M-row checkbook per request
        # is too slow (the high-cardinality vendor GROUP BY alone runs ~15s).
        totals = q(
            "SELECT round(sum(amount)/1e9,2)::float8 AS total_b, "
            "       round(sum(amount) FILTER (WHERE dept ILIKE '%%debt service%%')/1e9,2)::float8 AS debt_b, "
            "       (SELECT min(cal_year) FROM mv_afo_year WHERE cal_year ~ '^[0-9]{4}$') AS min_year, "
            "       (SELECT max(cal_year) FROM mv_afo_year WHERE cal_year ~ '^[0-9]{4}$') AS max_year "
            "FROM mv_afo_dept")
        by_year = q(
            "SELECT cal_year AS year, round(amount/1e9,2)::float8 AS amount_b "
            "FROM mv_afo_year WHERE cal_year ~ '^20(0[89]|1[0-9]|2[0-5])$' ORDER BY 1")
        by_department = q(
            "SELECT dept, round(amount/1e9,2)::float8 AS amount_b "
            "FROM mv_afo_dept ORDER BY amount DESC NULLS LAST LIMIT 10")
        top_vendors = q(
            "SELECT vendor, round(amount/1e6,1)::float8 AS amount_m "
            "FROM mv_afo_vendor_ops ORDER BY amount DESC NULLS LAST LIMIT 12")
        return cached({
            "totals": totals[0] if totals else None,
            "by_year": by_year,
            "by_department": by_department,
            "top_vendors_operating": top_vendors,
            "methodology": (
                "Every row is a disbursement (check or electronic payment) from the City of "
                "Austin's eCheckbook, 2008 to present, summed by the fields the city publishes: "
                "paying department and vendor legal name. 'Debt service' is identified by "
                "department name. Note two things when reading vendor totals: (1) a 'vendor' is "
                "the legal payee, so banks appear as bond trustees (debt) or as card/settlement "
                "processors, not as suppliers; (2) some recipients are other governments "
                "(Travis County, TxDOT) for joint projects. Descriptive only — this shows where "
                "money flows, not whether any payment was proper."),
            "caveat": (
                "The eCheckbook EXCLUDES some Austin Energy transactions that are confidential "
                "under Texas Government Code 552.133 (competitive electric matters), so totals "
                "do not fully reconcile with the city's complete spend."),
        })

    @app.get("/v1/stories/ballot-money")
    def story_ballot_money():
        """Narrative page (pivot from #1) — who funds Austin's ballot/issue campaigns.

        The defensible money-in-politics story the data DOES support: not contracts
        for donations, but the funding structure of committees/PACs. A candidate is
        identified by a 'Last, First' recipient name; everything else is a
        committee/PAC. The clearly non-municipal Greg Abbott (state) filing is
        excluded from committee figures (the dataset mixes filing levels).
        """
        # comma-name = candidate; else committee. Abbott = state, excluded.
        # Reads the flat mv_campaign_contributions (refreshed by cli refresh) rather
        # than the 400k-row JSONB table — the per-committee top-donor + classification
        # were ~2s live.
        CAND = "is_candidate"          # precomputed in mv_campaign_contributions
        NOT_STATE = "is_municipal"      # precomputed (recipient not ILIKE abbott)
        summary = q(
            f"SELECT "
            f"  round(sum(amt) FILTER (WHERE NOT is_cand)/1e6,2)::float8 AS committee_total_m, "
            f"  round(sum(amt) FILTER (WHERE is_cand)/1e6,2)::float8 AS candidate_total_m, "
            f"  count(DISTINCT rec) FILTER (WHERE NOT is_cand) AS committees, "
            f"  count(DISTINCT rec) FILTER (WHERE is_cand) AS candidates, "
            f"  round(avg(amt) FILTER (WHERE NOT is_cand))::float8 AS committee_avg_gift, "
            f"  round(avg(amt) FILTER (WHERE is_cand))::float8 AS candidate_avg_gift "
            f"FROM (SELECT {CAND} AS is_cand, recipient rec, amount amt "
            f"      FROM mv_campaign_contributions WHERE {NOT_STATE}) s")
        committees = q(
            f"WITH c AS (SELECT recipient rec, donor, amount amt "
            f"           FROM mv_campaign_contributions WHERE NOT ({CAND}) AND {NOT_STATE}), "
            f"tot AS (SELECT rec, sum(amt) total, count(*) gifts FROM c GROUP BY 1), "
            f"byd AS (SELECT rec, donor, sum(amt) dtot FROM c GROUP BY 1,2), "
            f"topd AS (SELECT DISTINCT ON (rec) rec, donor, dtot FROM byd ORDER BY rec, dtot DESC) "
            f"SELECT t.rec AS committee, round(t.total)::float8 AS total, t.gifts, "
            f"       round(t.total/t.gifts)::float8 AS avg_gift, topd.donor AS top_donor, "
            f"       round(topd.dtot)::float8 AS top_donor_amt, "
            f"       round(100.0*topd.dtot/t.total)::float8 AS top_donor_pct "
            f"FROM tot t JOIN topd ON topd.rec=t.rec ORDER BY t.total DESC LIMIT 12")
        mega = q(
            f"SELECT recipient AS committee, donor, amount::float8 AS amount, "
            f"       left(contribution_date,10) AS date "
            f"FROM mv_campaign_contributions WHERE NOT ({CAND}) AND {NOT_STATE} "
            f"ORDER BY amount DESC LIMIT 8")
        return cached({
            "summary": summary[0] if summary else None,
            "committees": committees,
            "mega_gifts": mega,
            "methodology": (
                "Austin's campaign-finance filings include money raised by committees and "
                "political action committees (PACs), not just candidates. We split recipients "
                "by name — a 'Last, First' recipient is treated as a candidate, everything else "
                "as a committee/PAC — and, for each committee, sum contributions and find its "
                "single largest donor's share. 'Top donor' is by donor name as filed (no "
                "entity resolution), so a parent and subsidiary may appear separately. This "
                "describes WHO FUNDS each committee; it does NOT say which side of a ballot "
                "measure a committee took, whether the measure passed, or that any donor got "
                "anything in return."),
            "caveat": (
                "The dataset mixes filing levels. We exclude the clearly non-municipal Greg "
                "Abbott (state) filing ($7.75M); other state/non-municipal filers may remain. "
                "Some committees are ongoing industry PACs (Realtors, Real Estate Council), "
                "not single-ballot campaigns. The candidate/committee split is a name heuristic."),
        })

    @app.get("/v1/stories/money-wins")
    def story_money_wins():
        """Money — does the bigger war chest win Austin's ballot fights? Live join of
        the user-curated crosswalk (ref_ballot_measures) with windowed committee money."""
        ok = q("SELECT to_regclass('ref_ballot_measures') IS NOT NULL AS ok")[0]["ok"]
        if not ok:
            return cached({"error": "ref_ballot_measures absent — run "
                                    "scripts/analyze_money_wins.py to load the crosswalk."})
        from .money_wins import compute_fights
        with psycopg.connect(_dsn, row_factory=dict_row) as c:
            data = compute_fights(c)
        return cached({**data,
            "methodology": (
                "Fights and sides come from a hand-curated, source-cited crosswalk "
                "(data/ballot_crosswalk.csv): one row per (committee, measure), the committee "
                "name exactly as filed, the side it took, official FOR/AGAINST vote counts and "
                "the outcome. Committee money is summed from the campaign-finance filings "
                "windowed to the 24 months before election day, so ongoing PACs don't drag "
                "unrelated years into one fight."),
            "caveat": (
                "Side attribution is editorial, documented and sourced per crosswalk row. "
                "Committee money ≠ all campaign spending — no independent-expenditure or "
                "in-kind data. A committee backing multiple same-day measures counts its full "
                "total toward each. The 24-month window approximates cycle money. Small n — "
                "a tally, not a statistical claim."),
        })

    @app.get("/v1/stories/traffic-deaths")
    def story_traffic_deaths():
        """Narrative page #3 — traffic deaths rose while crashes fell from their peak.

        Reads mv_crash_yearly, which DEDUPES the Vision Zero/CRIS feed by cris_crash_id
        (the raw table serves ~2 rows per real crash). Fatalities are reliably recorded;
        the most recent partial year (2026) is flagged and excluded from headline claims,
        and serious-injury coding lags so the latest year's injury count is incomplete.
        """
        rows = q(
            "SELECT yr AS year, crashes, fatal_crashes, deaths, serious_inj, "
            "       ped_deaths, moto_deaths, bike_deaths "
            "FROM mv_crash_yearly ORDER BY yr")
        # Who dies — per-victim demographics (sev_id 4 = killed), deduped on id.
        vmode = q(
            "WITH v AS (SELECT DISTINCT ON (payload->>'id') payload->>'mode_desc' mode "
            "  FROM raw_crash_victims WHERE payload->>'is_deleted'='false' AND payload->>'prsn_injry_sev_id'='4') "
            "SELECT coalesce(nullif(mode,''),'Unknown') mode, count(*) killed FROM v GROUP BY 1 ORDER BY 2 DESC")
        vage = q(
            "WITH v AS (SELECT DISTINCT ON (payload->>'id') (payload->>'prsn_age')::numeric age "
            "  FROM raw_crash_victims WHERE payload->>'is_deleted'='false' AND payload->>'prsn_injry_sev_id'='4') "
            "SELECT CASE WHEN age IS NULL THEN 'Unknown' WHEN age<25 THEN 'Under 25' WHEN age<40 THEN '25–39' "
            "  WHEN age<55 THEN '40–54' WHEN age<70 THEN '55–69' ELSE '70+' END band, count(*) killed "
            "FROM v GROUP BY 1 ORDER BY 1")
        victims = {"by_mode": vmode, "by_age": vage,
                   "total": sum(r["killed"] for r in vmode)}
        years = []
        for r in rows:
            yr = r["year"]
            years.append({
                **r,
                "fatal_per_1k": round(1000.0 * r["fatal_crashes"] / r["crashes"], 2) if r["crashes"] else None,
                "vru_deaths": (r["ped_deaths"] or 0) + (r["moto_deaths"] or 0) + (r["bike_deaths"] or 0),
                "partial": yr >= "2026",
            })
        return cached({
            "years": years,
            "victims": victims,
            "methodology": (
                "Crash records are from the City of Austin Vision Zero feed, which republishes "
                "Texas DOT CRIS (Crash Records Information System) data for crashes inside "
                "Austin's Full-Purpose jurisdiction. The raw feed serves about two rows per real "
                "crash (a duplicate system id sharing one CRIS crash id), so counts here are "
                "DE-DUPLICATED by CRIS crash id. Deaths are the count of people killed "
                "(death_cnt); 'fatal rate' is fatal crashes per 1,000 crashes. Fatalities are "
                "recorded promptly and reliably; counts are by the year the crash occurred."),
            "caveat": (
                "The current year (2026) is partial (year-to-date) and excluded from headline "
                "trends. Serious-injury severity is coded with a lag, so the most recent year's "
                "injury count understates the eventual total — read injuries as provisional. The "
                "2020 crash drop coincides with the pandemic; crashes have since plateaued below "
                "their 2019 peak rather than steadily fallen. Full-Purpose jurisdiction excludes "
                "some outlying roads."),
        })

    @app.get("/v1/stories/home-builders")
    def story_home_builders():
        """Narrative page #5 — who's building Austin's new homes.

        Counts NEW-residential BUILDING permits only (permittype BP, work_class New),
        i.e. the general contractor's permit — not the separate electrical/plumbing/
        mechanical trade permits, which would conflate builders with subcontractors.
        Reads pre-aggregated mv_home_permit_* (the source table is ~9M rows).
        """
        years = q(
            "SELECT yr AS year, permits FROM mv_home_permit_year "
            "WHERE yr ~ '^20(1[0-9]|2[0-5])$' ORDER BY yr")
        builders = q(
            "SELECT builder, permits FROM mv_home_permit_builder ORDER BY permits DESC LIMIT 14")
        named_total = q("SELECT sum(permits)::int AS t FROM mv_home_permit_builder")[0]["t"]
        top10 = q("SELECT sum(permits)::int AS t FROM (SELECT permits FROM mv_home_permit_builder "
                  "ORDER BY permits DESC LIMIT 10) s")[0]["t"]
        return cached({
            "years": years,
            "total_since_2010": sum(y["permits"] for y in years),
            "builders": builders,
            "named_builder_total": named_total,
            "top10_share": round(top10 / named_total, 3) if named_total else None,
            "methodology": (
                "A 'new-home permit' here is a BUILDING permit (permittype BP) for NEW "
                "residential work — the general contractor's permit to build. Austin issues "
                "separate electrical, plumbing and mechanical permits for the same house; those "
                "trade permits are EXCLUDED so a homebuilder isn't double-counted with its "
                "subcontractors. Builders are ranked by the contractor name as filed (no entity "
                "resolution, so a builder's variant spellings may split). 'Top-10 share' is over "
                "permits that name a builder. We count PERMITS, not finished homes or dollars — "
                "the roll's valuation and housing-unit fields contain unusable outliers."),
            "caveat": (
                "Counts permits issued, not homes completed. New-residential building permits "
                "include some accessory structures (e.g. pools) that carry a residential building "
                "permit. Contractor names are unresolved, so a single builder using multiple "
                "registered names is undercounted. 2026 is excluded as partial."),
        })

    @app.get("/v1/stories/service-equity")
    def story_service_equity():
        """Narrative page #10 — a NULL result, kept as a credibility anchor: once 311
        response time is adjusted for each district's request mix, no district is
        treated systematically worse. Reads the pre-built metric_311_equity (D7)."""
        rows = q(
            "SELECT council_district, n_closed, n_types, "
            "       observed_days::float8 AS observed_days, expected_days::float8 AS expected_days, "
            "       disparity_ratio::float8 AS disparity_ratio, flagged "
            "FROM metric_311_equity WHERE window_year = 0 ORDER BY council_district")
        return cached({
            "threshold": 1.5,
            "districts": rows,
            "n_flagged": sum(1 for r in rows if r["flagged"]),
            "methodology": (
                "We test whether the city closes 311 service requests more slowly in some "
                "council districts. A raw comparison would be unfair: districts ask for "
                "different things, and a pothole closes in days while a code case can take "
                "months. So we use indirect standardization — for each district we compute the "
                "average days-to-close we'd EXPECT if its specific mix of ~290 request types "
                "were handled at the citywide pace for each type, and compare that to OBSERVED. "
                "The disparity ratio is observed ÷ expected; 1.0 means exactly as fast as its "
                "request mix predicts. A district is flagged only above 1.5×."),
            "caveat": (
                "District is the finest geography 311 attaches, so this is a coarse screen — it "
                "cannot see disparities within a district. Mix adjustment controls for request "
                "TYPE only, not crew staffing, geography, differing reporting rates, or "
                "seasonality. 'Days to close' measures case closure, not resolution quality. "
                "Observational — no causal claim. A null result is still reported, on purpose."),
        })

    @app.get("/v1/stories/local-money")
    def story_local_money():
        """Narrative page #7 (corrected) — local races are locally funded, but ballot
        committees draw far more from out of state. Municipal universe excludes the
        clearly state Greg Abbott filing; candidate vs committee by recipient name;
        donor state inferred from the filed city_state_zip text."""
        rows = q(
            "SELECT is_candidate AS is_cand, loc, count(*) gifts, sum(amount)::float8 total "
            "FROM mv_campaign_contributions WHERE is_municipal GROUP BY 1,2")
        def side(is_cand):
            d = {r["loc"]: r for r in rows if r["is_cand"] == is_cand}
            tx = (d.get("texas") or {}).get("total", 0) or 0
            oos = (d.get("out_of_state") or {}).get("total", 0) or 0
            unk = (d.get("unknown") or {}).get("total", 0) or 0
            tot = tx + oos + unk
            return {"texas": tx, "out_of_state": oos, "unknown": unk, "total": tot,
                    "oos_share": round(oos / tot, 4) if tot else None}
        origins = q(
            r"SELECT regexp_replace(city_state_zip,'\s*\d{5}(-\d{4})?\s*$','') AS place, "
            "       count(*) gifts, sum(amount)::float8 total "
            "FROM mv_campaign_contributions WHERE is_candidate AND is_municipal AND loc='out_of_state' "
            "GROUP BY 1 ORDER BY 3 DESC NULLS LAST LIMIT 8")
        return cached({
            "candidate": side(True),
            "committee": side(False),
            "top_oos_origins": origins,
            "methodology": (
                "Contributions are split by recipient: a 'Last, First' recipient is an Austin "
                "candidate (council/mayor), everything else a committee/PAC. Donor location is "
                "read from the filed city/state/ZIP text — 'out of state' means a US state other "
                "than Texas appears. The clearly non-municipal Greg Abbott (state) filing is "
                "excluded. This measures where the MONEY comes from, by where donors say they are."),
            "caveat": (
                "State is inferred from a free-text field; a missing or malformed state reads as "
                "'unknown'. The candidate/committee split is a name heuristic. Some non-municipal "
                "filers beyond Abbott may remain. In-state ≠ in-Austin — this separates Texas from "
                "out-of-state, not Austin from the rest of Texas."),
        })

    @app.get("/v1/stories/who-pays")
    def story_who_pays():
        """Narrative page #9 — the few big checks vs the many small ones. Municipal
        universe (excludes the state Abbott filing)."""
        NOT_STATE = "is_municipal"
        POS = "amount > 0"
        buckets = q(
            f"WITH c AS (SELECT amount amt FROM mv_campaign_contributions WHERE {NOT_STATE} AND {POS}) "
            f"SELECT CASE WHEN amt<50 THEN '<$50' WHEN amt<250 THEN '$50–250' WHEN amt<1000 THEN '$250–1k' "
            f"            WHEN amt<5000 THEN '$1k–5k' WHEN amt<25000 THEN '$5k–25k' ELSE '$25k+' END bucket, "
            f"       count(*) gifts, sum(amt)::float8 total FROM c "
            f"GROUP BY 1 ORDER BY min(amt)")
        conc = q(
            f"WITH c AS (SELECT amount amt, ntile(100) OVER (ORDER BY amount DESC) p "
            f"           FROM mv_campaign_contributions WHERE {NOT_STATE} AND {POS}) "
            f"SELECT count(*) total_gifts, sum(amt)::float8 total_dollars, "
            f"       sum(amt) FILTER (WHERE p=1)::float8 top1, sum(amt) FILTER (WHERE p<=10)::float8 top10 "
            f"FROM c")[0]
        by_type = q(
            f"SELECT donor_type dtype, count(*) gifts, sum(amount)::float8 total "
            f"FROM mv_campaign_contributions WHERE {NOT_STATE} "
            f"GROUP BY 1 ORDER BY 3 DESC NULLS LAST")
        return cached({
            "buckets": buckets,
            "total_gifts": conc["total_gifts"],
            "total_dollars": conc["total_dollars"],
            "top1pct_dollars": conc["top1"],
            "top1pct_share": round(conc["top1"] / conc["total_dollars"], 4) if conc["total_dollars"] else None,
            "top10pct_share": round(conc["top10"] / conc["total_dollars"], 4) if conc["total_dollars"] else None,
            "by_type": [r for r in by_type if r["dtype"] in ("individual", "entity")],
            "methodology": (
                "Every contribution in the municipal filings (excluding the state Abbott filing), "
                "grouped by dollar size, and ranked to find the share of all money supplied by the "
                "largest gifts. Donor type (individual vs entity) is as filed; casing variants are "
                "merged. This measures the distribution of giving, not who received it."),
            "caveat": (
                "Counts contributions, not unique donors — one donor giving many times appears many "
                "times. Includes candidate and committee money together. Donor type is self-reported "
                "on the filing."),
        })

    @app.get("/v1/stories/money-influence")
    def story_money_influence():
        """Capstone — the money->influence chain, now traceable. Austin's Legistar
        hides per-member votes, but they're published separately (raw_council_votes,
        3c89-i35a); paired with award-level contracts (raw_city_contracts) the full
        chain is visible: contribution -> member -> vote -> contract. Reports the
        honest result (no pay-to-play at the visible decision point)."""
        AUTH = "payload->>'item_description' ILIKE '%%authorize negotiation and execution%%'"
        votes = q(
            f"SELECT count(*) all_votes, "
            f"  round(100.0*count(*) FILTER (WHERE payload->>'vote_cast'='Yes')/count(*),1)::float8 pct_yes, "
            f"  count(*) FILTER (WHERE payload->>'vote_cast'='No') no_votes, "
            f"  count(*) FILTER (WHERE payload->>'vote_cast'='Recused') recused, "
            f"  count(DISTINCT payload->>'voter_name') voters, "
            f"  left(min(payload->>'meeting_date'),4) min_yr, left(max(payload->>'meeting_date'),4) max_yr "
            f"FROM raw_council_votes")[0]
        cvotes = q(
            f"SELECT payload->>'vote_cast' vote, count(*) n FROM raw_council_votes "
            f"WHERE {AUTH} AND payload->>'vote_cast' IN ('Yes','No','Abstain','Recused') "
            f"GROUP BY 1 ORDER BY 2 DESC")
        overlap = q(
            "WITH con AS (SELECT upper(regexp_replace(payload->>'lgl_nm','[^A-Za-z0-9]','','g')) nm, "
            "                    max(payload->>'lgl_nm') name, sum((payload->>'ma_prch_lmt_am')::numeric) amt, "
            "                    min(('20'||substr(payload->>'brd_awd_dt',3,2))::int) FILTER (WHERE payload->>'brd_awd_dt' ~ '^00') award_yr "
            "             FROM raw_city_contracts GROUP BY 1), "
            "don AS (SELECT upper(regexp_replace(donor,'[^A-Za-z0-9]','','g')) nm, "
            "               sum(amount) gave, min(left(contribution_date,4)::int) gift_yr "
            "        FROM mv_campaign_contributions WHERE donor_type = 'entity' GROUP BY 1) "
            "SELECT count(*) firms, sum(c.amt)::float8 contract_total, sum(d.gave)::float8 donated_total, "
            "  count(*) FILTER (WHERE d.gift_yr < c.award_yr) gift_before, "
            "  count(*) FILTER (WHERE c.award_yr IS NOT NULL AND d.gift_yr >= c.award_yr) gift_after "
            "FROM con c JOIN don d ON c.nm=d.nm WHERE length(c.nm)>4")[0]
        firms = q(
            "WITH con AS (SELECT upper(regexp_replace(payload->>'lgl_nm','[^A-Za-z0-9]','','g')) nm, "
            "                    max(payload->>'lgl_nm') name, sum((payload->>'ma_prch_lmt_am')::numeric) amt "
            "             FROM raw_city_contracts GROUP BY 1), "
            "don AS (SELECT upper(regexp_replace(donor,'[^A-Za-z0-9]','','g')) nm, "
            "               sum(amount) gave "
            "        FROM mv_campaign_contributions WHERE donor_type = 'entity' GROUP BY 1) "
            "SELECT c.name AS vendor, c.amt::float8 contract_amt, d.gave::float8 donated "
            "FROM con c JOIN don d ON c.nm=d.nm WHERE length(c.nm)>4 ORDER BY c.amt DESC LIMIT 10")
        recusals = q(
            "SELECT payload->>'voter_name' member, count(*) n FROM raw_council_votes "
            "WHERE payload->>'vote_cast'='Recused' GROUP BY 1 ORDER BY 2 DESC")
        contracts_total = q("SELECT count(*) n, sum((payload->>'ma_prch_lmt_am')::numeric)::float8 amt "
                            "FROM raw_city_contracts")[0]
        return cached({
            "votes": votes,
            "contract_votes": cvotes,
            "overlap": overlap,
            "matched_firms": firms,
            "recusals": recusals,
            "contracts_total": contracts_total,
            "methodology": (
                "The chain is contribution -> council member -> their recorded vote -> the "
                "contract. Votes are the City of Austin Council Voting Record (per-member "
                "roll-call, 2023-present) — the votes Austin's Legistar API does not expose. "
                "Contracts are the city's award-level Contracts dataset (vendor, amount, board "
                "award date). Vendor-donors are firms whose normalized legal name appears as both "
                "a contract holder and an entity campaign donor. 'Donation precedes award' "
                "compares the firm's first contribution year to its earliest board-award year. "
                "Contract-vote unanimity is measured on 'authorize negotiation and execution' "
                "items."),
            "caveat": (
                "A SCREENING analysis, not proof of anything. Votes only go back to 2023, so the "
                "donation<->vote overlap is recent. The Contracts dataset is a bounded set of "
                "~625 contracts, not every award in city history. Firms are name-matched (no "
                "entity resolution). Vote items are not reliably linkable to a specific private "
                "vendor (many 'authorize' items are agreements with other governments), so the "
                "vote analysis is at the aggregate unanimity level. Near-unanimous voting means "
                "the vote has little power to reveal favoritism. Award dates carry a century-digit "
                "quirk, corrected on read. No causal claim."),
        })

    @app.get("/v1/stories/district-divide")
    def story_district_divide():
        """Equity layer — Austin's 10 council districts differ sharply by income and
        race; crime REPORTS track that divide steeply, but mix-adjusted 311 response
        does not. Joins district demographics (puux-7swp) to crime + the D7 311 metric.
        """
        rows = q(
            "WITH dem AS (SELECT (payload->>'district')::int d, "
            "   (payload->>'total_population_2020_census')::numeric pop, "
            "   (payload->>'hh_income_less_than_10000')::numeric+(payload->>'hh_income_10000_to_14999')::numeric"
            "   +(payload->>'hh_income_15000_to_24999')::numeric+(payload->>'hh_income_25000_to_34999')::numeric pct_under35k, "
            "   (payload->>'hh_income_150000_to_199999')::numeric+(payload->>'hh_income_200000_or_more')::numeric pct_over150k, "
            "   (payload->>'total_white')::numeric white, (payload->>'total_hispanic_latinx')::numeric hispanic, "
            "   (payload->>'total_black')::numeric black, (payload->>'total_asian')::numeric asian "
            "   FROM raw_district_demographics), "
            "crime AS (SELECT council_district d, sum(incident_count) c FROM metric_incidents_by_district "
            "   WHERE dataset='crime' AND to_char(period_month,'YYYY')='2025' GROUP BY 1) "
            "SELECT dem.d, dem.pop::int, dem.pct_under35k::float8, dem.pct_over150k::float8, "
            "   dem.white::float8, dem.hispanic::float8, dem.black::float8, dem.asian::float8, "
            "   round(1000.0*crime.c/dem.pop,1)::float8 crime_per_1k, "
            "   eq.disparity_ratio::float8 resp_ratio "
            "FROM dem JOIN crime ON crime.d=dem.d "
            "LEFT JOIN metric_311_equity eq ON eq.council_district=dem.d AND eq.window_year=0 "
            "ORDER BY dem.pct_under35k DESC")

        def pearson(xs, ys):
            pts = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
            n = len(pts)
            if n < 3:
                return None
            sx = sum(p[0] for p in pts); sy = sum(p[1] for p in pts)
            mx, my = sx / n, sy / n
            cov = sum((p[0]-mx)*(p[1]-my) for p in pts)
            vx = sum((p[0]-mx)**2 for p in pts); vy = sum((p[1]-my)**2 for p in pts)
            return round(cov / (vx*vy)**0.5, 2) if vx and vy else None

        inc = [r["pct_under35k"] for r in rows]
        return cached({
            "districts": rows,
            "corr_crime_income": pearson(inc, [r["crime_per_1k"] for r in rows]),
            "corr_response_income": pearson(inc, [r["resp_ratio"] for r in rows]),
            "methodology": (
                "Council-district demographics are the city's 2022 district profiles (population, "
                "household-income bands, race/ethnicity shares). '% under $35k' sums the lowest four "
                "household-income bands. Crime is reported incidents per 1,000 residents (2025). 311 "
                "response is the mix-adjusted disparity ratio from the D7 detector (observed ÷ "
                "expected days-to-close, controlling for each district's request mix). Correlation "
                "is Pearson's r across the 10 districts."),
            "caveat": (
                "Crime figures are REPORTED incidents, not crime itself — they fold in differences "
                "in reporting rates and policing, so a higher rate is not proof of more crime. "
                "Demographics are 2020-census-based (2022 profiles); crime is 2025. Ten districts is "
                "a small n — correlations are indicative, not precise. Reported crime is district-"
                "level only (no finer geography). Descriptive — no causal claim."),
        })

    @app.get("/v1/stories/council-dissent")
    def story_council_dissent():
        """Governance — what Austin Council actually fights about, from REAL votes
        (raw_council_votes), 2023-present. Most items are unanimous; dissent is rare,
        concentrated in one member, and not a stable bloc."""
        summ = q(
            "WITH it AS (SELECT payload->>'item_id' iid, "
            "  count(*) FILTER (WHERE payload->>'vote_cast'='No') no_n, "
            "  count(*) FILTER (WHERE payload->>'vote_cast' IN ('Yes','No','Abstain')) cast_n "
            "  FROM raw_council_votes GROUP BY 1) "
            "SELECT count(*) FILTER (WHERE cast_n>0) items, "
            "  count(*) FILTER (WHERE no_n>0) contested, "
            "  (SELECT count(*) FROM raw_council_votes WHERE payload->>'vote_cast'='No') total_no "
            "FROM it")[0]
        summ["pct_contested"] = round(100.0 * summ["contested"] / summ["items"], 1) if summ["items"] else None
        summ["pct_agree"] = round(100.0 - summ["pct_contested"], 1) if summ["pct_contested"] is not None else None
        dissent = q(
            "WITH per AS (SELECT payload->>'voter_name' member, payload->>'voter_district' district, "
            "  count(*) FILTER (WHERE payload->>'vote_cast'='No') no_votes, "
            "  count(*) FILTER (WHERE payload->>'vote_cast' IN ('Yes','No')) votes_cast, "
            "  max(left(payload->>'meeting_date',10)::date) last_vote "
            "  FROM raw_council_votes GROUP BY 1,2), "
            "mx AS (SELECT max(left(payload->>'meeting_date',10)::date) d FROM raw_council_votes) "
            "SELECT member, district, no_votes, votes_cast, "
            "       round(100.0*no_votes/votes_cast, 1)::float8 AS no_rate_per_100, "
            "       to_char(last_vote,'Mon YYYY') AS last_vote_label, "
            "       (last_vote >= (SELECT d - 90 FROM mx)) AS current "
            "FROM per WHERE votes_cast >= 100 ORDER BY no_rate_per_100 DESC LIMIT 12")
        topics = q(
            "SELECT CASE WHEN payload->>'item_description' ~ '^C14|zoning|rezon' THEN 'Zoning / land use' "
            "  WHEN payload->>'item_description' ILIKE '%%authorize negotiation%%' THEN 'Contracts / agreements' "
            "  WHEN payload->>'item_description' ILIKE '%%appoint%%' THEN 'Appointments' "
            "  WHEN payload->>'item_description' ILIKE '%%ordinance%%' THEN 'Other ordinances' "
            "  ELSE 'Other' END topic, count(*) no_votes "
            "FROM raw_council_votes WHERE payload->>'vote_cast'='No' GROUP BY 1 ORDER BY 2 DESC")
        coalitions = q(
            "WITH nv AS (SELECT payload->>'item_id' iid, payload->>'voter_name' m "
            "  FROM raw_council_votes WHERE payload->>'vote_cast'='No') "
            "SELECT a.m member_a, b.m member_b, count(*) co_dissents "
            "FROM nv a JOIN nv b ON a.iid=b.iid AND a.m < b.m "
            "GROUP BY 1,2 ORDER BY 3 DESC LIMIT 8")
        return cached({
            "summary": summ,
            "dissent_by_member": dissent,
            "topics": topics,
            "coalitions": coalitions,
            "methodology": (
                "From the City of Austin Council Voting Record (per-member roll-call, 2023-present). "
                "An 'item' is one agenda item (item_id); it is 'contested' if any member voted No. "
                "Members are ranked by No-RATE — No votes per 100 Yes/No votes cast — so a member "
                "who served two years isn't compared against one who served four. Members with fewer "
                "than 100 recorded Yes/No votes are excluded from the ranking. A member is 'current' "
                "if they voted within 90 days of the newest meeting in the data; departed members "
                "are labeled with their last vote month. Co-dissent pairs count how often two members "
                "both voted No on the same item."),
            "caveat": (
                "Votes cover 2023-present only. 'No' is explicit dissent; abstentions, recusals and "
                "absences are separate. Council membership changed over the window, so a member "
                "present for fewer meetings has fewer chances to dissent. Descriptive — it shows "
                "where disagreement is recorded, not why."
                " Rates are per recorded Yes/No vote; abstentions, recusals and absences are excluded "
                "from the denominator."),
        })

    @app.get("/v1/stories/short-term-rentals")
    def story_short_term_rentals():
        """Housing — Austin's licensed short-term rentals: most are not owner-occupied,
        and they cluster in the urban core and East Austin."""
        total = q("SELECT count(*) n, count(*) FILTER (WHERE payload->>'str_type' !~* 'Type 1') non_owner "
                  "FROM raw_short_term_rentals")[0]
        by_type = q(
            "SELECT replace(payload->>'str_type','Short Term Rental ','') AS type, count(*) n, "
            "       bool_or(payload->>'str_type' ~* 'Type 1') AS owner_occupied "
            "FROM raw_short_term_rentals GROUP BY 1 ORDER BY 2 DESC")
        by_district = q(
            "SELECT (payload->>'council_district')::int AS district, count(*) n "
            "FROM raw_short_term_rentals WHERE payload->>'council_district' ~ '^[0-9]+$' "
            "GROUP BY 1 ORDER BY 2 DESC")
        return cached({
            "total": total["n"], "non_owner": total["non_owner"],
            "pct_non_owner": round(100.0 * total["non_owner"] / total["n"]) if total["n"] else None,
            "by_type": by_type,
            "by_district": by_district,
            "methodology": (
                "Licensed short-term rentals from the city's STR registry. Austin licenses three "
                "types: Type 1 is the owner's own home (owner-occupied); Type 2 is a "
                "non-owner-occupied house; Type 3 is multifamily. 'Not owner-occupied' is everything "
                "that isn't Type 1. District is the licensed property's council district."),
            "caveat": (
                "LICENSED STRs only. Austin has a well-documented gap between licensed and operating "
                "STRs — many run without a license — so these counts are a FLOOR, and the "
                "owner-occupied share may be overstated if unlicensed rentals skew non-owner. No "
                "parcel-level owner join (the feed carries address + district, not a parcel id)."),
        })

    @app.get("/v1/stories/who-lobbies")
    def story_who_lobbies():
        """Influence — who lobbies Austin City Hall. Overwhelmingly real estate &
        development; modest dollars; near-zero reported spending on officials."""
        RE = "business_desc ~* 'real estate|develop|\\mland\\M|property|builder|construct|realtor|home build'"
        scale = q(
            "SELECT (SELECT count(*) FROM raw_lobbyist_registrants) registrants, "
            "  (SELECT count(DISTINCT payload->>'lobbyist') FROM raw_lobbyist_master "
            "   WHERE payload->>'lobbyist' <> '') lobbyists, "
            "  (SELECT count(DISTINCT lower(trim(payload->>'client_last_name'))) "
            "   FROM raw_lobbyist_clients WHERE payload->>'client_last_name' <> '') clients")[0]
        redev = q(
            f"WITH c AS (SELECT lower(trim(payload->>'client_last_name')) cl, payload->>'business_desc' business_desc "
            f"           FROM raw_lobbyist_clients WHERE payload->>'client_last_name' <> '' AND payload->>'business_desc' <> '') "
            f"SELECT count(DISTINCT cl) total, count(DISTINCT cl) FILTER (WHERE {RE}) re_dev FROM c")[0]
        sectors = q(
            f"WITH c AS (SELECT lower(trim(payload->>'client_last_name')) cl, payload->>'business_desc' business_desc "
            f"           FROM raw_lobbyist_clients WHERE payload->>'client_last_name' <> '' AND payload->>'business_desc' <> '') "
            f"SELECT CASE WHEN {RE} THEN 'Real estate & development' "
            f"  WHEN business_desc ~* 'tech|software|semic' THEN 'Technology' "
            f"  WHEN business_desc ~* 'health|hospital|medical' THEN 'Healthcare' "
            f"  WHEN business_desc ~* 'energy|utilit|water|solar' THEN 'Energy / utilities' "
            f"  WHEN business_desc ~* 'transport|mobility|rideshar|transit' THEN 'Transportation' "
            f"  WHEN business_desc ~* 'nonprofit|advocacy|coalition|association' THEN 'Nonprofit / advocacy' "
            f"  ELSE 'Other' END sector, count(DISTINCT cl) clients "
            f"FROM c GROUP BY 1 ORDER BY 2 DESC")
        bands = q(
            "SELECT CASE WHEN payload->>'comp_category' ~* 'no compensation|^\\$0' THEN '$0 / none' "
            "  WHEN payload->>'comp_category' ~* 'less than' THEN 'Under $10k' "
            "  WHEN payload->>'comp_category' = '$10,000 - $24,999' THEN '$10k–25k' "
            "  WHEN payload->>'comp_category' = '$25,000 - $49,999' THEN '$25k–50k' "
            "  WHEN payload->>'comp_category' = '$50,000 - $99,999' THEN '$50k–100k' "
            "  WHEN payload->>'comp_category' ~ '100,000' THEN '$100k–200k' ELSE 'Other' END band, "
            "  count(*) n FROM raw_lobbyist_clients "
            "WHERE payload->>'comp_category' <> '' AND payload->>'comp_category' !~* 'decline' GROUP BY 1")
        big = q(
            "SELECT DISTINCT trim(payload->>'client_last_name') client, payload->>'business_desc' business "
            "FROM raw_lobbyist_clients WHERE payload->>'comp_category' ~ '\\$(50,000|100,000)' "
            "  AND payload->>'client_last_name' <> '' ORDER BY 1 LIMIT 14")
        spend = q(
            "SELECT round(sum((payload->>'total_foodbev')::numeric))::float8 food_bev, "
            "  round(sum((payload->>'total_gifts')::numeric))::float8 gifts, "
            "  round(sum((payload->>'total_entertainment')::numeric))::float8 entertainment, "
            "  round(sum((payload->>'total_translodg')::numeric))::float8 travel "
            "FROM raw_lobbyist_reports WHERE payload->>'total_foodbev' ~ '^[0-9]'")[0]
        spend["total"] = sum((spend[k] or 0) for k in ("food_bev", "gifts", "entertainment", "travel"))
        BAND_ORDER = {"$0 / none": 0, "Under $10k": 1, "$10k–25k": 2, "$25k–50k": 3, "$50k–100k": 4, "$100k–200k": 5}
        return cached({
            "scale": scale,
            "re_dev_clients": redev["re_dev"], "total_classified_clients": redev["total"],
            "re_dev_share": round(redev["re_dev"] / redev["total"], 3) if redev["total"] else None,
            "sectors": sectors,
            "comp_bands": sorted(bands, key=lambda r: BAND_ORDER.get(r["band"], 9)),
            "big_clients": big,
            "official_spend": spend,
            "methodology": (
                "Austin's registered-lobbyist disclosures: registrants (lobbying firms), the "
                "lobbyists they employ, their clients (with a self-reported business description and "
                "a compensation BAND), and per-filing reports of spending on officials. 'Real estate "
                "& development' groups client business descriptions matching real-estate, "
                "development, land, property, builder or construction terms. Compensation is a "
                "disclosed range, not an exact figure; a client recurs across filing periods, so "
                "band counts are of engagements, not unique clients."),
            "caveat": (
                "Compensation is self-reported in broad bands (often '$0' or 'less than $10,000'), so "
                "totals can't be summed precisely. Business-sector grouping is keyword-based on a "
                "free-text field. Reported spending on officials covers only what lobbyists disclose "
                "on these forms — it is not all contact. Registration ≠ influence; this shows who is "
                "organized to lobby, not who succeeds."),
        })

    @app.get("/v1/stories/animal-shelter")
    def story_animal_shelter():
        """Resident-interest — Austin Animal Center outcomes: the no-kill live-release
        rate, what happens to animals, and the cat/dog mix (recent window)."""
        c = q(
            "WITH o AS (SELECT payload->>'outcome_status' s FROM raw_animal_outcomes) "
            "SELECT count(*) FILTER (WHERE s ~* 'adopt|transfer|reclaim|return to|foster|rto') live, "
            "  count(*) FILTER (WHERE s ~* 'euthan') euthanized, "
            "  count(*) FILTER (WHERE s ~* 'unassisted|^died') died_natural, "
            "  count(*) FILTER (WHERE s ~* 'doa|dead on') doa, count(*) total FROM o")[0]
        outcomes = q(
            "SELECT CASE WHEN payload->>'outcome_status' ~* 'adopt' THEN 'Adopted' "
            "  WHEN payload->>'outcome_status' ~* 'transfer' THEN 'Transferred to rescue' "
            "  WHEN payload->>'outcome_status' ~* 'reclaim|return to owner|rto' THEN 'Returned to owner' "
            "  WHEN payload->>'outcome_status' ~* 'return to habitat|foster' THEN 'Returned to habitat / foster' "
            "  WHEN payload->>'outcome_status' ~* 'euthan' THEN 'Euthanized' "
            "  WHEN payload->>'outcome_status' ~* 'doa|unassisted|died' THEN 'Died / DOA' "
            "  ELSE 'Other' END grp, count(*) n FROM raw_animal_outcomes GROUP BY 1 ORDER BY 2 DESC")
        by_type = q(
            "SELECT CASE WHEN payload->>'type' ~* 'cat|kitten' THEN 'Cats' "
            "  WHEN payload->>'type' ~* 'dog|puppy' THEN 'Dogs' ELSE 'Other animals' END type, count(*) n "
            "FROM raw_animal_outcomes GROUP BY 1 ORDER BY 2 DESC")
        window = q("SELECT left(min(payload->>'outcome_date'),10) mn, left(max(payload->>'outcome_date'),10) mx FROM raw_animal_outcomes")[0]
        intakes = q("SELECT count(*) n FROM raw_animal_intakes")[0]["n"]
        denom = (c["total"] or 0) - (c["doa"] or 0)
        return cached({
            "window": window, "intakes": intakes,
            "live": c["live"], "euthanized": c["euthanized"], "died_natural": c["died_natural"],
            "doa": c["doa"], "total": c["total"],
            "live_release_rate": round(c["live"] / denom, 3) if denom else None,
            "outcomes": outcomes, "by_type": by_type,
            "methodology": (
                "Austin Animal Center outcome records for the recent window shown. The live-release "
                "rate is animals leaving alive (adopted, transferred to rescue, returned to owner or "
                "habitat) divided by all outcomes EXCEPT dead-on-arrival — the standard no-kill "
                "denominator. The widely used 'no-kill' threshold is a 90% live-release rate."),
            "caveat": (
                "A recent rolling window (the live feed), not the full shelter history. Outcome "
                "categories are grouped from the source status by keyword. The source's "
                "days-in-shelter field looked unreliable and is not shown. Euthanasia here is not "
                "split into medical / owner-requested vs other."),
        })

    @app.get("/v1/stories/food-inspections")
    def story_food_inspections():
        """Resident-interest — Austin food establishment inspection scores: most score
        well; a handful are chronic low-scorers. Public health-inspection records."""
        summ = q(
            "SELECT count(*) n, round(avg((payload->>'score')::numeric),1)::float8 avg_score, "
            "  left(min(payload->>'inspection_date'),10) mn, left(max(payload->>'inspection_date'),10) mx "
            "FROM raw_food_inspections WHERE payload->>'score' ~ '^[0-9]'")[0]
        dist = q(
            "SELECT CASE WHEN (payload->>'score')::numeric>=90 THEN '90–100' "
            "  WHEN (payload->>'score')::numeric>=80 THEN '80–89' "
            "  WHEN (payload->>'score')::numeric>=70 THEN '70–79' ELSE 'Under 70' END band, count(*) n "
            "FROM raw_food_inspections WHERE payload->>'score' ~ '^[0-9]' GROUP BY 1")
        order = {"90–100": 0, "80–89": 1, "70–79": 2, "Under 70": 3}
        repeat_low = q(
            "SELECT payload->>'restaurant_name' name, count(*) low_inspections, "
            "  round(min((payload->>'score')::numeric))::int worst "
            "FROM raw_food_inspections WHERE (payload->>'score')::numeric < 75 "
            "GROUP BY 1 HAVING count(*)>=3 ORDER BY 2 DESC, 3 ASC LIMIT 10")
        return cached({
            "total": summ["n"], "avg_score": summ["avg_score"],
            "window": {"mn": summ["mn"], "mx": summ["mx"]},
            "distribution": sorted(dist, key=lambda r: order.get(r["band"], 9)),
            "repeat_low": repeat_low,
            "methodology": (
                "City of Austin food-establishment inspection scores (0–100) for the window shown. "
                "The distribution buckets every inspection by score. 'Repeat low-scorers' are "
                "establishments with three or more inspections below 75. These are public health "
                "records published by the city expressly for residents."),
            "caveat": (
                "A score is a POINT-IN-TIME snapshot; inspections exist to drive fixes, and an "
                "establishment's score typically changes between visits. Some listed names are flagged "
                "by the city as ineligible-for-renewal or out-of-business. 'Food establishment' "
                "includes groceries and markets, not only restaurants. Not a current safety verdict."),
        })

    @app.get("/v1/stories/str-gap")
    def story_str_gap():
        """Housing — the STR licensing gap: Inside Airbnb operating listings vs the
        city registry. Precomputed into mv_str_gap by `cli refresh`."""
        ok = q("SELECT to_regclass('mv_str_gap') IS NOT NULL AS ok")[0]["ok"]
        rows = q("SELECT payload, built_at::text AS built_at FROM mv_str_gap LIMIT 1") if ok else []
        if not rows:
            return cached({"error": "mv_str_gap absent — load an Inside Airbnb snapshot "
                                    "(scripts/load_airbnb.py) and run `cli refresh`."})
        d = rows[0]["payload"]
        return cached({**d, "built_at": rows[0]["built_at"],
            "methodology": (
                "Operating universe is the Inside Airbnb Austin summary snapshot; 'recently "
                "active' means at least one review in the trailing 12 months (Inside Airbnb's "
                "own activity convention). Licensed universe is the city STR registry. District "
                "assignment is point-in-polygon of listing coordinates against the council-"
                "district boundaries — listings outside all 10 districts are the metro-area "
                "share of the export, wider than city licensing jurisdiction. License "
                "verification normalizes the host-entered license field against registry case "
                "numbers and matches on the digit sequence — in this snapshot a share of "
                "listings display a number and some match the registry (see license_classes), a "
                "change from the 2025 snapshots, which carried no license text at all. Data by "
                "Inside Airbnb (insideairbnb.com), CC BY 4.0."),
            "caveat": (
                "Airbnb only — no VRBO or other platforms, so the operating count is a FLOOR. "
                "Inside Airbnb anonymizes locations by up to ~150m (fine at district grain). "
                "Snapshot date differs from the registry pull date. Inside Airbnb's 'Austin' "
                "scope is the metro area, wider than city limits — the in-district figures are "
                "the jurisdiction-fair comparison. Some listings are hotels licensed under "
                "other regimes."),
        })

    @app.get("/v1/you")
    def you(lat: float = Query(...), lon: float = Query(...),
            street: str | None = Query(None, max_length=120)):
        """Address-level 'you' payload. `street` is the geocoded street NAME (no house
        number) used only to disambiguate which nearby parcel the point belongs to.
        PRIVACY: lat/lon/street are processed in-memory only — do not add logging here
        or in atx_dashboard.you."""
        from .you import build_payload, valid_point
        if not valid_point(lat, lon):
            return JSONResponse(
                {"error": "point outside the supported area (Travis County vicinity)"},
                status_code=400)
        with psycopg.connect(_dsn, row_factory=dict_row) as c:
            return cached(build_payload(c, lat, lon, street))

    @app.get("/v1/geocode")
    def geocode(q: str = Query(..., min_length=3, max_length=200)):
        """Server-side proxy to the US Census geocoder. The Census API sends no CORS
        headers, so the browser can't call it directly; we forward the query and return
        the matches. PRIVACY: the address is used in-memory only and is NEVER logged or
        stored — do not add logging of `q` here. Returns [{matchedAddress, lat, lon}]."""
        import requests
        try:
            r = requests.get(
                "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress",
                params={"address": q, "benchmark": "Public_AR_Current", "format": "json"},
                timeout=15)
            r.raise_for_status()
            matches = (r.json().get("result") or {}).get("addressMatches") or []
        except (requests.RequestException, ValueError):
            return JSONResponse({"error": "geocoder unavailable"}, status_code=502)
        out = [{"matchedAddress": m.get("matchedAddress"),
                "lat": (m.get("coordinates") or {}).get("y"),
                "lon": (m.get("coordinates") or {}).get("x")}
               for m in matches
               if (m.get("coordinates") or {}).get("y") is not None]
        return JSONResponse(out, headers={"Cache-Control": "no-store"})

    @app.get("/v1/flags")
    def flags(detector: str = Query("d3a_assessment_equity")):
        rows = q(
            "SELECT f.cluster_kind, f.cluster_id, f.direction, f.score::float8 AS score, "
            "       f.roll_year, f.review_state, f.methodology, f.evidence, "
            "       m.n_parcels, m.median_per_acre::float8 AS median_per_acre, "
            "       m.median_appraised::float8 AS median_appraised, "
            "       m.percentile::float8 AS percentile "
            "FROM anomaly_flag f "
            "LEFT JOIN metric_assessment_equity m "
            "  ON m.zip = f.cluster_id AND m.roll_year = f.roll_year AND m.class = 'A1' "
            "WHERE f.detector = %s "
            "ORDER BY f.score DESC",
            (detector,),
        )
        out = []
        for r in rows:
            # d3a carries its detail in the metric_assessment_equity join (and degrades
            # to null when there's no matching row); every other detector carries its
            # detail in the flag's evidence jsonb (detector-agnostic).
            if r["n_parcels"] is not None:
                detail = {
                    "n_parcels": r["n_parcels"],
                    "median_per_acre": r["median_per_acre"],
                    "median_appraised": r["median_appraised"],
                    "percentile": r["percentile"],
                }
            elif detector == "d3a_assessment_equity":
                detail = None
            else:
                detail = r["evidence"]
            out.append({
                "cluster_kind": r["cluster_kind"],
                "cluster_id": r["cluster_id"],
                "direction": r["direction"],
                "score": r["score"],
                "roll_year": r["roll_year"],
                "review_state": r["review_state"],
                "methodology": r["methodology"],
                "detail": detail,
            })
        return cached(out)

    return app


app = create_app()
