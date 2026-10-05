"""Dashboard storage: connection + DDL for the metric_* summary tables.

Reads the shared Postgres read-only for aggregation; the only tables this package
WRITES are the metric_*/district_boundary tables defined here.
"""
from __future__ import annotations

import logging
import os
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row

log = logging.getLogger("atx.dashboard.db")

DEFAULT_DSN = "postgresql://atx:atx@localhost:5432/atx_civic"

DDL = """
CREATE TABLE IF NOT EXISTS metric_incidents_by_district (
    dataset          text     NOT NULL,
    council_district smallint NOT NULL,
    period_month     date     NOT NULL,
    incident_count   integer  NOT NULL,
    PRIMARY KEY (dataset, council_district, period_month)
);

CREATE TABLE IF NOT EXISTS metric_district_breakdown (
    dataset          text     NOT NULL,
    council_district smallint NOT NULL,
    period           text     NOT NULL,
    dimension        text     NOT NULL,
    label            text     NOT NULL,
    value            integer  NOT NULL,
    PRIMARY KEY (dataset, council_district, period, dimension, label)
);

CREATE TABLE IF NOT EXISTS metric_311_response (
    council_district smallint NOT NULL,
    period           text     NOT NULL,
    median_days      numeric,
    closed_count     integer  NOT NULL,
    open_count       integer  NOT NULL,
    PRIMARY KEY (council_district, period)
);

CREATE TABLE IF NOT EXISTS district_boundary (
    council_district smallint PRIMARY KEY,
    geom             jsonb    NOT NULL
);

CREATE TABLE IF NOT EXISTS zip_boundary (
    zip  text  PRIMARY KEY,
    geom jsonb NOT NULL
);

CREATE TABLE IF NOT EXISTS recent_incidents (
    dataset          text      NOT NULL,
    council_district smallint,
    ts               timestamp NOT NULL,
    lat              float8,
    lon              float8,
    payload          jsonb     NOT NULL
);

-- self-heal: a pre-existing recent_incidents (created before lat/lon existed) leaves the
-- CREATE TABLE above a no-op, so the columns must be added explicitly before the geo index
-- below can reference them.
ALTER TABLE recent_incidents ADD COLUMN IF NOT EXISTS lat float8;
ALTER TABLE recent_incidents ADD COLUMN IF NOT EXISTS lon float8;

CREATE INDEX IF NOT EXISTS recent_incidents_lookup
    ON recent_incidents (dataset, council_district, ts DESC);

CREATE INDEX IF NOT EXISTS recent_incidents_geo
    ON recent_incidents (lat, lon);
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
    """Create the metric_*/district_boundary tables if absent."""
    conn.execute(DDL)
