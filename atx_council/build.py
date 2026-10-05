"""Contribution -> sponsorship analysis (the provable money->influence proxy).

Austin's Legistar API does not expose per-member votes, so we link campaign
contributions to council members and to the matters those members SPONSOR. The
sponsor roster (raw_council_matter_sponsors) defines the member universe; campaign
contributions (raw_campaign_contributions) are matched in by name (last +
first-initial, across the "Last, First" and "<Title> First Last" formats).
Full rebuild. SCREENING SIGNAL — descriptive, never a causal claim.
"""
from __future__ import annotations

import logging

from .normalize import normalize_member_name, same_member

log = logging.getLogger("atx.council.build")


def _display_name(last: str, first: str) -> str:
    return f"{first.title()} {last.title()}"


def build_member_activity(conn, prefix: str = "") -> dict:
    """Rebuild metric_member_funding_activity. Returns a summary."""
    # 1. roster + sponsorship counts: distinct matters per normalized member
    roster: dict[tuple, dict] = {}   # (last, first) -> {matters:set, name:str}
    for r in conn.execute(
        f"SELECT payload->>'MatterSponsorName' AS name, "
        f"payload->>'MatterSponsorMatterId' AS mid "
        f"FROM {prefix}raw_council_matter_sponsors "
        # person sponsors only — exclude committee/body sponsors (NameId null)
        f"WHERE nullif(payload->>'MatterSponsorNameId','') IS NOT NULL"
    ).fetchall():
        key = normalize_member_name(r["name"])
        if key is None:
            continue
        entry = roster.setdefault(key, {"matters": set(), "name": _display_name(*key)})
        if r["mid"]:
            entry["matters"].add(r["mid"])

    # 2. contributions matched to roster members (last + first-initial)
    funds = {key: {"total": 0.0, "n": 0} for key in roster}
    ambiguous = 0
    for r in conn.execute(
        f"SELECT payload->>'recipient' AS recip, "
        f"payload->>'contribution_amount' AS amt "
        f"FROM {prefix}raw_campaign_contributions"
    ).fetchall():
        rkey = normalize_member_name(r["recip"])
        if rkey is None:
            continue
        matches = [k for k in roster if same_member(rkey, k)]
        if len(matches) != 1:
            ambiguous += len(matches) > 1          # skip ambiguous (>1 roster match)
            continue
        try:
            amt = float(r["amt"]) if r["amt"] not in (None, "") else 0.0
        except (TypeError, ValueError):
            amt = 0.0
        funds[matches[0]]["total"] += amt
        funds[matches[0]]["n"] += 1

    conn.execute(f"TRUNCATE {prefix}metric_member_funding_activity")
    for key, entry in roster.items():
        f = funds[key]
        conn.execute(
            f"""INSERT INTO {prefix}metric_member_funding_activity
                (member_key, canonical_name, n_matters_sponsored,
                 contributions_total, n_contributions)
                VALUES (%s,%s,%s,%s,%s)""",
            (f"{key[0]}|{key[1]}", entry["name"], len(entry["matters"]),
             round(f["total"], 2), f["n"]),
        )

    summary = {"members": len(roster),
               "members_with_contributions": sum(1 for f in funds.values() if f["n"]),
               "ambiguous_recipients_skipped": ambiguous}
    log.info("member activity build: %s", summary)
    return summary
