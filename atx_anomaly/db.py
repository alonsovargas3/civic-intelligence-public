"""Anomaly storage: connection + DDL for the shared anomaly_flag stream and the
D3a detail table. Reads parcel/parcel_value read-only; writes only these tables.
"""
from __future__ import annotations

import logging
import os
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row

log = logging.getLogger("atx.anomaly.db")

DEFAULT_DSN = "postgresql://atx:atx@localhost:5432/atx_civic"

DDL = """
CREATE TABLE IF NOT EXISTS anomaly_flag (
    flag_id      bigserial PRIMARY KEY,
    detector     text    NOT NULL,
    cluster_kind text    NOT NULL,
    cluster_id   text    NOT NULL,
    roll_year    int,
    score        numeric NOT NULL,
    direction    text,
    evidence     jsonb   NOT NULL,
    methodology  text    NOT NULL,
    review_state text    NOT NULL DEFAULT 'unreviewed',
    created_at   timestamptz NOT NULL DEFAULT now(),
    UNIQUE (detector, cluster_kind, cluster_id, roll_year)
);

CREATE TABLE IF NOT EXISTS metric_assessment_equity (
    roll_year        int     NOT NULL,
    class            text    NOT NULL,
    zip              text    NOT NULL,
    n_parcels        int     NOT NULL,
    n_total          int     NOT NULL,
    median_per_acre  numeric NOT NULL,
    median_appraised numeric,
    modified_z       numeric NOT NULL,
    percentile       numeric NOT NULL,
    flagged          boolean NOT NULL,
    PRIMARY KEY (roll_year, class, zip)
);

CREATE TABLE IF NOT EXISTS metric_d4_divergence (
    roll_year        int     NOT NULL,
    entity_id        text    NOT NULL,
    canonical_name   text    NOT NULL,
    kind             text    NOT NULL,
    n_parcels        int     NOT NULL,   -- valued parcels in a (category,zip) stratum
    divergence_ratio numeric NOT NULL,   -- entity median (appraised/acre ÷ stratum all-owner median)
    modified_z       numeric NOT NULL,   -- robust z of the ratio across same-kind entities (context)
    percentile       numeric NOT NULL,
    flagged          boolean NOT NULL,
    PRIMARY KEY (roll_year, entity_id)
);

CREATE TABLE IF NOT EXISTS metric_assessment_cod (
    roll_year           int     NOT NULL,
    situs_zip           text    NOT NULL,
    property_class      text    NOT NULL,
    n_parcels           int     NOT NULL,
    median_value_per_unit numeric NOT NULL,   -- median appraised $/acre in the stratum
    cod                 numeric NOT NULL,      -- coefficient of dispersion (%) about the median
    cod_pctile_in_class numeric NOT NULL,      -- rank of cod within the same class (primary screen)
    high_dispersion     boolean NOT NULL,
    PRIMARY KEY (roll_year, situs_zip, property_class)
);

CREATE TABLE IF NOT EXISTS metric_311_equity (
    window_year      int     NOT NULL,   -- analysis-window anchor year (0 = all history)
    council_district int     NOT NULL,
    n_closed         int     NOT NULL,   -- closed cases in the included request types
    n_types          int     NOT NULL,   -- request types contributing (>= min_type_cases)
    observed_days    numeric NOT NULL,   -- mix-weighted median days, as observed
    expected_days    numeric NOT NULL,   -- same case mix run at the metro per-type pace
    disparity_ratio  numeric NOT NULL,   -- observed_days / expected_days
    percentile       numeric NOT NULL,   -- rank of the ratio among scored districts
    flagged          boolean NOT NULL,
    PRIMARY KEY (window_year, council_district)
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
    """Create the anomaly_flag + metric_* detail tables if absent."""
    conn.execute(DDL)
