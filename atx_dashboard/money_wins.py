"""Money-wins: shared computation for the story endpoint and the findings script."""
from __future__ import annotations


def fight_summary(rows: list[dict], money: dict) -> list[dict]:
    """Aggregate crosswalk rows + per-(committee, election) money into one dict per fight.

    money: {(committee_recipient_name, election_date): float}
    A committee backing multiple same-day measures contributes its full total to each
    (stated caveat — filings don't split spending per measure).
    """
    fights: dict[tuple, dict] = {}
    for r in rows:
        key = (r["election_date"], r["measure"])
        f = fights.setdefault(key, {
            "election_date": r["election_date"], "measure": r["measure"],
            "money_for": 0.0, "money_against": 0.0,
            "votes_for": r["votes_for"], "votes_against": r["votes_against"],
            "outcome": r["outcome"],
        })
        amt = float(money.get((r["committee_recipient_name"], r["election_date"]), 0.0))
        f["money_for" if r["side"] == "for" else "money_against"] += amt
    out = []
    for f in fights.values():
        f["winner"] = "for" if f["outcome"] == "passed" else "against"
        if f["money_for"] > f["money_against"]:
            f["better_funded"] = "for"
        elif f["money_against"] > f["money_for"]:
            f["better_funded"] = "against"
        else:
            f["better_funded"] = None
        f["money_won"] = (f["better_funded"] == f["winner"]) if f["better_funded"] else None
        out.append(f)
    return sorted(out, key=lambda f: f["election_date"])


MONEY_SQL = """
SELECT coalesce(sum(amount), 0)::float8 AS total
FROM mv_campaign_contributions
WHERE recipient = %s
  AND contribution_date ~ '^\\d{4}-\\d{2}-\\d{2}'
  AND left(contribution_date, 10)::date >  %s::date - interval '24 months'
  AND left(contribution_date, 10)::date <= %s::date
"""


def compute_fights(conn) -> dict:
    """Fights + windowed money + tally from ref_ballot_measures. Pure data — no prose."""
    rows = conn.execute(
        "SELECT election_date::text AS election_date, measure, committee_recipient_name, "
        "       side, votes_for, votes_against, outcome "
        "FROM ref_ballot_measures ORDER BY election_date, measure, committee_recipient_name"
    ).fetchall()
    money = {}
    for r in rows:
        key = (r["committee_recipient_name"], r["election_date"])
        if key not in money:
            money[key] = conn.execute(MONEY_SQL, (key[0], key[1], key[1])).fetchone()["total"]
    fights = fight_summary(rows, money)
    scored = [f for f in fights if f["money_won"] is not None]
    return {
        "fights": fights,
        "scored": len(scored),
        "won": sum(1 for f in scored if f["money_won"]),
        "losses": [f"{f['measure']} ({f['election_date']})" for f in scored if not f["money_won"]],
    }
