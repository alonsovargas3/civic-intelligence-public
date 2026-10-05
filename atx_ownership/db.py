"""Ownership-layer storage: connection + DDL for the parcel->district crosswalk
and the metric_ownership_* descriptive tables. Reads dim_entity / parcel_entity /
parcel / parcel_value / parcel_geo / district_boundary read-only; writes only the
tables defined here.
"""
from __future__ import annotations

import logging
import os
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row

log = logging.getLogger("atx.ownership.db")

DEFAULT_DSN = "postgresql://atx:atx@localhost:5432/atx_civic"

DDL = """
CREATE TABLE IF NOT EXISTS parcel_district (
    account_id       text PRIMARY KEY,
    council_district int NOT NULL
);

CREATE TABLE IF NOT EXISTS metric_ownership_concentration (
    dimension          text    NOT NULL,   -- overall | kind | category | district
    segment            text    NOT NULL,   -- segment value within the dimension
    n_entities         int     NOT NULL,
    n_parcels          int     NOT NULL,
    total_appraised    numeric NOT NULL,
    parcel_share       numeric NOT NULL,   -- of all entity-owned parcels
    value_share        numeric NOT NULL,   -- of all entity-owned appraised value
    top10_parcel_share numeric NOT NULL,   -- parcels held by the 10 largest owners in-segment
    hhi_parcels        numeric NOT NULL,   -- normalized HHI over in-segment owners
    PRIMARY KEY (dimension, segment)
);

CREATE TABLE IF NOT EXISTS metric_owner_ranking (
    scope           text    NOT NULL,      -- by_parcels | by_value
    rank            int     NOT NULL,
    entity_id       text    NOT NULL,
    canonical_name  text    NOT NULL,
    kind            text    NOT NULL,
    n_parcels       int     NOT NULL,
    total_appraised numeric NOT NULL,
    PRIMARY KEY (scope, rank)
);

-- Owner-type differential treatment (D4-variant), CATEGORY-STRATIFIED -----------
-- One row per (property_class, owner_type): institutional-vs-individual read
-- WITHIN a property class, not across a confounded mix. The de-confounded readouts
-- are the indices vs the category's all-owner rate:
--   assessment_index  = owner-type median appraised $/acre / all-owner median,
--                       within (class, zip), parcel-weighted (<1 = assessed lower)
--   code_case_index   = owner-type code-case rate / category all-owner rate
--                       (>1 = more enforcement than comparable; ~1 = the blended
--                        gap was pure property mix)
-- Code cases are windowed (opened_date >= window_start) and attributed to the
-- current owner via parcel.geo_id (~94%, deduped). Screening signal, not a finding.
CREATE TABLE IF NOT EXISTS metric_owner_treatment (
    property_class          text    NOT NULL,
    owner_type              text    NOT NULL,
    parcels                 int     NOT NULL,
    assessment_index        numeric,
    code_cases              int     NOT NULL,
    code_cases_per_1k       numeric NOT NULL,
    code_case_index         numeric,
    code_cases_per_1k_acres numeric,
    window_start            date    NOT NULL,
    PRIMARY KEY (property_class, owner_type, window_start)
);
"""


def dsn() -> str:
    return os.environ.get("DATABASE_URL", DEFAULT_DSN)


@contextmanager
def connect(dsn_str: str | None = None):
    conn = psycopg.connect(dsn_str or dsn(), autocommit=True, row_factory=dict_row)
    try:
        yield conn
    finally:
        conn.close()


def bootstrap(conn) -> None:
    """Create the crosswalk + metric_ownership_* tables if absent."""
    conn.execute(DDL)
