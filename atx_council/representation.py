"""Representation patterns from council sponsorship.

Austin's Legistar exposes no per-member votes and no member->district mapping, so
representation is read from SPONSORSHIP (raw_council_matter_sponsors):
  - per member: matters LED (sponsor sequence 0) vs co-sponsored (seq >= 1)
  - the co-sponsorship NETWORK: how often each pair of members sponsor the same
    matter (coalition structure; ~96% of matters are co-sponsored)

Person sponsors only (committee/body sponsors excluded). Full rebuild. Descriptive.
"""
from __future__ import annotations

import logging
from itertools import combinations

from .normalize import normalize_member_name

log = logging.getLogger("atx.council.representation")


def _display(last: str, first: str) -> str:
    return f"{first.title()} {last.title()}"


def build_representation(conn, prefix: str = "") -> dict:
    """Rebuild metric_member_sponsorship + metric_cosponsorship. Returns a summary."""
    # matter -> list of (member_key, name, sequence), person sponsors only
    matters: dict[str, list] = {}
    for r in conn.execute(
        f"SELECT payload->>'MatterSponsorMatterId' AS mid, "
        f"payload->>'MatterSponsorName' AS name, "
        f"payload->>'MatterSponsorSequence' AS seq "
        f"FROM {prefix}raw_council_matter_sponsors "
        f"WHERE nullif(payload->>'MatterSponsorNameId','') IS NOT NULL"
    ).fetchall():
        key = normalize_member_name(r["name"])
        if key is None or not r["mid"]:
            continue
        try:
            seq = int(r["seq"]) if r["seq"] not in (None, "") else 99
        except (TypeError, ValueError):
            seq = 99
        matters.setdefault(r["mid"], []).append((key, _display(*key), seq))

    lead: dict = {}        # member_key -> {"name", "lead", "co", "matters": set}
    pairs: dict = {}       # (a, b) sorted -> {"n", "na", "nb"}
    for mid, sponsors in matters.items():
        # de-dup a member appearing twice on one matter; keep their best (lowest) seq
        best: dict = {}
        for key, name, seq in sponsors:
            if key not in best or seq < best[key][1]:
                best[key] = (name, seq)
        for key, (name, seq) in best.items():
            e = lead.setdefault(key, {"name": name, "lead": 0, "co": 0, "matters": set()})
            e["matters"].add(mid)
            if seq == 0:
                e["lead"] += 1
            else:
                e["co"] += 1
        members = sorted(best)
        for a, b in combinations(members, 2):
            p = pairs.setdefault((a, b), {"n": 0, "na": best[a][0], "nb": best[b][0]})
            p["n"] += 1

    conn.execute(f"TRUNCATE {prefix}metric_member_sponsorship")
    conn.execute(f"TRUNCATE {prefix}metric_cosponsorship")
    for key, e in lead.items():
        conn.execute(
            f"""INSERT INTO {prefix}metric_member_sponsorship
                (member_key, canonical_name, n_lead, n_cosponsor, n_total)
                VALUES (%s,%s,%s,%s,%s)""",
            (f"{key[0]}|{key[1]}", e["name"], e["lead"], e["co"], len(e["matters"])),
        )
    for (a, b), p in pairs.items():
        conn.execute(
            f"""INSERT INTO {prefix}metric_cosponsorship
                (member_a, member_b, name_a, name_b, shared_matters)
                VALUES (%s,%s,%s,%s,%s)""",
            (f"{a[0]}|{a[1]}", f"{b[0]}|{b[1]}", p["na"], p["nb"], p["n"]),
        )

    summary = {"members": len(lead), "pairs": len(pairs), "matters": len(matters)}
    log.info("representation build: %s", summary)
    return summary
