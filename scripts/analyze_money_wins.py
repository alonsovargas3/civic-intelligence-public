#!/usr/bin/env python3
"""Does money win Austin ballot fights? Committee money vs official results.

Usage:  python scripts/analyze_money_wins.py      # writes docs/money-wins-findings.md

Reads data/ballot_crosswalk.csv (hand-curated, source-cited; see Task 5 of the plan),
recreates ref_ballot_measures from it, joins committee totals from
mv_campaign_contributions windowed to the 24 months before each election, and writes
the findings doc. Pure helpers below are unit-tested offline.
"""
from __future__ import annotations

import csv
import io
import logging
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # runnable as scripts/foo.py

log = logging.getLogger("atx.scripts.money_wins")

CROSSWALK = "data/ballot_crosswalk.csv"
OUT = "docs/money-wins-findings.md"

REQUIRED = ("election_date", "measure", "committee_recipient_name", "side",
            "votes_for", "votes_against", "outcome", "source_url")


def parse_crosswalk(text: str) -> list[dict]:
    """Parse + validate the crosswalk CSV. Fails loudly on any bad row."""
    reader = csv.DictReader(io.StringIO(text))
    missing = [c for c in REQUIRED if c not in (reader.fieldnames or [])]
    if missing:
        raise ValueError(f"crosswalk missing columns: {missing}")
    rows = []
    for i, row in enumerate(reader, start=2):     # 1-based; header is line 1
        if row["side"] not in ("for", "against"):
            raise ValueError(f"line {i}: side must be for/against, got {row['side']!r}")
        if row["outcome"] not in ("passed", "failed"):
            raise ValueError(f"line {i}: outcome must be passed/failed, got {row['outcome']!r}")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", row["election_date"]):
            raise ValueError(f"line {i}: election_date must be YYYY-MM-DD")
        if not (row["source_url"] or "").startswith("http"):
            raise ValueError(f"line {i}: source_url is required (official canvass or equivalent)")
        try:
            row["votes_for"] = int(row["votes_for"])
            row["votes_against"] = int(row["votes_against"])
        except ValueError as e:
            raise ValueError(f"line {i}: votes_for/votes_against must be integers") from e
        rows.append(row)
    if not rows:
        raise ValueError("crosswalk is empty")
    return rows


# --- analysis main (DB-touching; not unit-tested, per repo convention) -----

REF_DDL = """
DROP TABLE IF EXISTS ref_ballot_measures;
CREATE TABLE ref_ballot_measures (
    election_date            date NOT NULL,
    measure                  text NOT NULL,
    committee_recipient_name text NOT NULL,
    side          text NOT NULL CHECK (side IN ('for','against')),
    votes_for     int  NOT NULL,
    votes_against int  NOT NULL,
    outcome       text NOT NULL CHECK (outcome IN ('passed','failed')),
    source_url    text NOT NULL,
    notes         text,
    PRIMARY KEY (election_date, measure, committee_recipient_name)
)
"""


def _validate_recipients(conn, rows) -> None:
    """Every crosswalk committee must exist in the filings — fail loudly with near-misses."""
    for name in sorted({r["committee_recipient_name"] for r in rows}):
        hit = conn.execute(
            "SELECT 1 FROM mv_campaign_contributions WHERE recipient = %s LIMIT 1",
            (name,)).fetchone()
        if not hit:
            near = conn.execute(
                "SELECT DISTINCT recipient FROM mv_campaign_contributions "
                "WHERE recipient ILIKE '%%' || %s || '%%' LIMIT 5",
                (name.split()[0],)).fetchall()
            raise SystemExit(
                f"crosswalk committee {name!r} not found in mv_campaign_contributions; "
                f"near-misses: {[r['recipient'] for r in near]}")


def _money(v: float) -> str:
    return f"${v/1e6:.1f}M" if abs(v) >= 1e6 else f"${round(v/1e3)}k"


def run(conn) -> str:
    from atx_dashboard.money_wins import compute_fights
    from atx_dashboard.str_gap import md_table   # shared table formatter

    with open(CROSSWALK, encoding="utf-8") as f:
        rows = parse_crosswalk(f.read())
    _validate_recipients(conn, rows)

    conn.execute(REF_DDL)
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO ref_ballot_measures VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            [(r["election_date"], r["measure"], r["committee_recipient_name"], r["side"],
              r["votes_for"], r["votes_against"], r["outcome"], r["source_url"],
              r.get("notes") or None) for r in rows])

    data = compute_fights(conn)
    fights, scored, won, losses = data["fights"], data["scored"], data["won"], data["losses"]

    fight_rows = [[f["election_date"], f["measure"], _money(f["money_for"]),
                   _money(f["money_against"]),
                   f"{f['votes_for']:,}–{f['votes_against']:,}", f["outcome"],
                   {True: "yes", False: "NO", None: "n/a"}[f["money_won"]]]
                  for f in fights]
    # precomputed local — quoted md_table args inside f-string expressions are a
    # SyntaxError below Python 3.12
    fights_tbl = md_table(
        ["Election", "Measure", "$ for", "$ against", "Votes for–against", "Outcome",
         "Better-funded side won?"], fight_rows)
    losses_line = ("Notably, the better-funded side LOST: " + "; ".join(losses) + ".") \
        if losses else "The better-funded side won every scored fight."

    return f"""# Does money win Austin ballot fights? — findings

*Generated by `scripts/analyze_money_wins.py` from a hand-curated, source-cited crosswalk
(`data/ballot_crosswalk.csv`, one official source per row) joined to the campaign-finance
filings. Research, not advocacy.*

## The headline

Across **{scored}** ballot fights where the sides' committee funding differed, the
better-funded side won **{won}** — **{won}/{scored}**. {losses_line}

## Fight by fight

{fights_tbl}

## Methodology

Fights and sides come from a hand-curated crosswalk: one row per (committee, measure), the
committee name exactly as filed, the side it took, official FOR/AGAINST vote counts and the
outcome, each row citing its source (Travis County canvass or equivalent). Committee money
is summed from mv_campaign_contributions windowed to the 24 months before election day, so
ongoing PACs don't drag unrelated years into one fight.

## Caveats

- Side attribution is editorial, documented and sourced per crosswalk row.
- Committee money ≠ all campaign spending — no independent-expenditure or in-kind data.
- A committee backing multiple same-day measures counts its full total toward each.
- The 24-month window approximates cycle money; stated, not exact.
- Small n ({len(fights)} fights) — a tally, not a statistical claim.

## Sources

- data/ballot_crosswalk.csv (source URL per row).
- Austin campaign-finance filings (mv_campaign_contributions, municipal filers).
"""


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    from atx_dashboard import db   # deferred: keeps pure helpers import-safe offline
    with db.connect() as conn:
        report = run(conn)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(report)
    log.info("wrote %s", OUT)


if __name__ == "__main__":
    main()
