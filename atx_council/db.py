"""Council analytics storage: connection + DDL for metric_member_funding_activity.

Reads raw_council_matter_sponsors + raw_campaign_contributions read-only; writes
only the metric table here.
"""
from __future__ import annotations

import os
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row

DEFAULT_DSN = "postgresql://atx:atx@localhost:5432/atx_civic"

DDL = """
-- Contribution -> sponsorship (the provable proxy for money->influence; Austin's
-- Legistar does not expose per-member votes). One row per matched council member:
-- matters they SPONSORED vs campaign contributions they RECEIVED. Names matched on
-- last + first-initial across the contribution ("Last, First") and sponsor
-- ("<Title> First Last") formats. SCREENING SIGNAL, not a causal claim.
CREATE TABLE IF NOT EXISTS metric_member_funding_activity (
    member_key          text    PRIMARY KEY,   -- "last|first" canonical key
    canonical_name      text    NOT NULL,
    n_matters_sponsored int     NOT NULL,
    contributions_total numeric NOT NULL,
    n_contributions     int     NOT NULL
);

-- Representation patterns from sponsorship (no votes/district in Austin Legistar):
-- per member, how many matters they LEAD (sponsor sequence 0) vs co-sponsor.
CREATE TABLE IF NOT EXISTS metric_member_sponsorship (
    member_key     text PRIMARY KEY,
    canonical_name text NOT NULL,
    n_lead         int  NOT NULL,   -- matters where this member is the lead sponsor (seq 0)
    n_cosponsor    int  NOT NULL,   -- matters they co-sponsored (seq >= 1)
    n_total        int  NOT NULL
);

-- Co-sponsorship network: how often a pair of members sponsor the same matter
-- (the coalition structure). member_a < member_b (unordered pair, stored once).
CREATE TABLE IF NOT EXISTS metric_cosponsorship (
    member_a       text NOT NULL,
    member_b       text NOT NULL,
    name_a         text NOT NULL,
    name_b         text NOT NULL,
    shared_matters int  NOT NULL,
    PRIMARY KEY (member_a, member_b)
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
    conn.execute(DDL)
