#!/usr/bin/env python3
"""Export each dashboard data-story to a self-contained markdown file.

Pulls the LIVE /v1/stories/* endpoints so the numbers in the markdown always match
what the pages render, then writes docs/stories/<slug>.md (+ a README index).

Usage:  python scripts/export_stories.py [--base http://127.0.0.1:8000]
Re-run after `python -m atx_dashboard.cli refresh` to refresh the figures.
"""
from __future__ import annotations

import argparse
import json
import re
import urllib.request
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "docs" / "stories"


# ---- formatters -----------------------------------------------------------
def fmt(n):
    return f"{round(float(n)):,}"

def money(v):
    n = float(v)
    if abs(n) >= 1e9:
        return f"${n/1e9:.2f}B"
    if abs(n) >= 1e6:
        return f"${n/1e6:.1f}M"
    if abs(n) >= 1e3:
        return f"${round(n/1e3)}k"
    return f"${round(n):,}"

def pct(x, d=1):
    return f"{float(x)*100:.{d}f}%"

def title_case(s):
    out = " ".join(w.capitalize() for w in str(s).lower().replace("*", " ").split())
    for t in ("Llc", "Lp", "Inc", "Dba", "Ut", "Aisd", "Coa", "Usa", "Pac"):
        out = out.replace(t, t.upper())
    return out


def get(base, path):
    with urllib.request.urlopen(base + path, timeout=60) as r:
        return json.loads(r.read().decode())


def table(headers, rows):
    out = ["| " + " | ".join(headers) + " |",
           "|" + "|".join("---" for _ in headers) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(c) for c in r) + " |")
    return "\n".join(out)


def footer(d):
    """Standard methodology / sources / limits block from an endpoint payload."""
    parts = ["\n## Methodology\n", d.get("methodology", "")]
    if d.get("caveat"):
        parts += ["\n", d["caveat"]]
    return "\n".join(parts)


# ---- headline-drift lint ---------------------------------------------------
# Every significant number in a story's dek must appear in its rendered body,
# matched at the DEK'S precision (so "$10B" matches a body "$10.04B", "91%"
# matches "90.6%", but 60% vs 56% — the drift class this exists to catch —
# still fails). Bare 4-digit years and single digits are ignored.
_LINT_RE = re.compile(
    r"(?P<money>\$\d[\d,]*(?:\.\d+)?\s?[BMk]?)"
    r"|(?P<ratio>r=\d\.\d+)"
    r"|(?P<pct>\d+(?:\.\d+)?%)"
    r"|(?P<mult>\d+(?:\.\d+)?[×x](?![\w-]))"
    r"|(?P<big>\b\d{1,3}(?:,\d{3})+\b)"
    r"|(?P<plain>\b\d{2,3}(?:\.\d+)?\b(?![×x%,-]))"
)

_MONEY_SCALE = {"B": 1e9, "M": 1e6, "k": 1e3, "": 1.0}


def _lint_tokens(text):
    """[(kind, value_in_suffix_units, decimals, abs_scale, raw)] for every token."""
    out = []
    for m in _LINT_RE.finditer(text):
        kind = m.lastgroup
        raw = m.group().strip()
        t = raw.replace(",", "").replace(" ", "")
        if kind == "money":
            suf = t[-1] if t[-1] in "BMk" else ""
            num = t[1:-1] if suf else t[1:]
        elif kind == "ratio":
            suf, num = "", t[2:]
        elif kind in ("pct", "mult"):
            suf, num = "", t[:-1]
        else:
            suf, num = "", t
        dec = len(num.split(".")[1]) if "." in num else 0
        out.append((kind, float(num), dec, _MONEY_SCALE.get(suf, 1.0), raw))
    return out


def lint_dek(dek, body):
    """Return the dek's numeric tokens that have no match in the body."""
    body_toks = _lint_tokens(body)
    misses = []
    for kind, val, dec, scale, raw in _lint_tokens(dek):
        bkind = kind if kind not in ("big", "plain") else None  # big/plain interchangeable
        hit = any(
            (bk == kind or (bkind is None and bk in ("big", "plain")))
            and round(bv * bs / scale, dec) == round(val, dec)
            for bk, bv, bdec, bs, _ in body_toks
        )
        if not hit:
            misses.append(raw)
    return misses


def _ascii_quotes(s):
    return (s.replace("’", "'").replace("‘", "'")
             .replace("“", '"').replace("”", '"'))


def check_registry_sync(jsx_text, stories):
    """Slugs whose dek text is missing from the frontend registry (quote-normalized)."""
    jsx_norm = _ascii_quotes(jsx_text)
    return [slug for slug, _t, _e, dek, _ep, _r in stories
            if _ascii_quotes(dek) not in jsx_norm]


# ---- per-story renderers --------------------------------------------------
def who_owns_austin(d):
    o = d["overall"]
    pub = [r for r in d["top_by_value"] if r["sector"] == "public"][:8]
    priv = [r for r in d["top_by_value"] if r["sector"] == "private"][:10]
    pk = [r for r in d["top_by_parcels"] if r["sector"] == "private"][:10]
    kinds = {k["kind"]: k for k in d["by_kind"]}
    s = []
    s.append("Open the Travis County appraisal roll and you'll find hundreds of thousands of "
             "separate owner names. Link the LLCs, trusts and agencies back together into single "
             f"owners and the picture concentrates fast: **{fmt(o['n_entities'])} resolved owners** "
             f"hold **{fmt(o['n_parcels'])} parcels** worth **{money(o['total_appraised'])}** in "
             "total appraised value (2025 roll).\n")
    s.append("## Three kinds of owner\n")
    s.append("Most parcels belong to individuals, but companies and institutions punch far above "
             "their parcel count in value, and a few hundred government bodies hold a tenth of all "
             "value on 1.4% of parcels.\n")
    s.append(table(["Owner type", "Owners", "Parcels", "% parcels", "% value", "Appraised"],
        [[k.capitalize(), fmt(kinds[k]["n_entities"]), fmt(kinds[k]["n_parcels"]),
          pct(kinds[k]["parcel_share"]), pct(kinds[k]["value_share"]), money(kinds[k]["total_appraised"])]
         for k in ("individual", "institutional", "government") if k in kinds]))
    s.append("\n## The public bodies you'd expect\n")
    s.append(table(["Owner", "Parcels", "Appraised value"],
        [[title_case(r["name"]), fmt(r["n_parcels"]), money(r["total_appraised"])] for r in pub]))
    s.append("\n## The private holders\n")
    tesla = next((r for r in priv if "TESLA" in r["name"].upper()), None)
    if tesla:
        s.append(f"> **{money(tesla['total_appraised'])} across {fmt(tesla['n_parcels'])} parcels** — "
                 "Tesla's Austin footprint is appraised higher than entire neighborhoods.\n")
    s.append(table(["Owner", "Parcels", "Appraised value"],
        [[title_case(r["name"]), fmt(r["n_parcels"]), money(r["total_appraised"])] for r in priv]))
    s.append("\n## Who's accumulating the most parcels\n")
    s.append("Rank by parcel *count* and national production homebuilders appear, holding hundreds "
             "of lots each at low per-parcel value — an inventory of future subdivisions.\n")
    s.append(table(["Owner", "Parcels", "Appraised value"],
        [[title_case(r["name"]), fmt(r["n_parcels"]), money(r["total_appraised"])] for r in pk]))
    return "\n".join(s)


def homestead_cap(d):
    o, c = d["overall"], d["context"]
    top = d["deciles"][-1]
    bot = d["deciles"][0]
    s = []
    s.append("Texas caps how fast a homesteaded property's *taxable* (assessed) value can rise — no "
             "more than 10% a year, even when market value climbs faster. The gap between full "
             "appraised value and the capped value is shielded from taxation.\n")
    s.append(f"> **{money(o['total_shielded'])}** held off the city's {money(c['assessed'])} taxable "
             f"base by the cap, across **{fmt(o['homesteads'])} homesteads** (median shield "
             f"{money(o['median_shield'])}, average {money(o['avg_shield'])}).\n")
    s.append("## Who the cap shields\n")
    s.append("Sort capped homes into ten equal groups by market value and the break climbs steeply "
             f"with value. The most valuable tenth captures **{pct(top['share'])}** of the entire "
             "shield — more than the bottom seven deciles combined.\n")
    s.append(table(["Decile (by market value)", "Homes", "Market range", "Shield", "% of total", "Avg / home"],
        [[d_["dec"], fmt(d_["n"]), f"{money(d_['min_mkt'])}–{money(d_['max_mkt'])}",
          money(d_["shield"]), pct(d_["share"]), money(d_["avg_shield"])] for d_ in d["deciles"]]))
    ratio = top["avg_shield"] / bot["avg_shield"]
    s.append(f"\nPer home, the average top-decile homestead shields **{money(top['avg_shield'])}** — "
             f"about **{ratio:.0f}×** the {money(bot['avg_shield'])} shielded for the average "
             "bottom-decile home.\n")
    s.append("## Almost entirely single-family homes\n")
    s.append(table(["Category", "Homes", "Shield", "Avg / home"],
        [[r["category"], fmt(r["n"]), money(r["shield"]), money(r["avg_shield"])] for r in d["by_category"]]))
    s.append(f"\n*Field validation: `capped_value` equals appraised − assessed for "
             f"{fmt(o['matches_caploss'])} of {fmt(o['homesteads'])} capped homes (99.5%), confirming "
             "it is the cap-loss amount itself.*")
    return "\n".join(s)


def investor_complaints(d):
    a1 = {r["owner_type"]: r for r in d["a1"]}
    ind, inst = a1["individual"], a1["institutional"]
    bl = d["blended"]
    s = []
    s.append("Match Austin code complaints to the properties they're about and to who owns them, and "
             "homes held by companies and investors draw complaints at a higher rate than "
             "owner-occupied ones — once the comparison is made fair.\n")
    s.append("## A gap that looks bigger than it is\n")
    blr = bl["institutional"]["per_1k"] / bl["individual"]["per_1k"]
    s.append(f"Pooling all property types, institution-owned parcels draw **{bl['institutional']['per_1k']:.0f}** "
             f"complaints per 1,000 vs **{bl['individual']['per_1k']:.0f}** for individuals — about "
             f"**{blr:.1f}×**. But that mostly reflects *what* institutions own (apartments, commercial), "
             "which generate more complaints regardless of owner.\n")
    s.append("## Comparing within each property class\n")
    s.append("Dividing each owner type's rate by the all-owner rate *within the same class* (an index "
             "where 1.0 = no different from peers), the gap collapses to ~1.0 in commercial and "
             "multifamily — but not in single-family homes.\n")
    s.append(table(["Property class", "Institution-owned parcels", "Complaints / 1k", "Index vs class norm"],
        [[r["property_class"], fmt(r["parcels"]), f"{r['per_1k']:.0f}", f"{r['index']:.2f}×"]
         for r in sorted(d["by_class"], key=lambda r: -r["parcels"])[:8]]))
    a1r = inst["per_1k"] / ind["per_1k"]
    s.append("\n## Within single-family homes, the gap is real\n")
    s.append(f"> **{inst['per_1k']:.0f} vs {ind['per_1k']:.0f} complaints per 1,000 homes** — investor-owned "
             f"single-family homes draw about **{a1r:.1f}×** the complaints of owner-occupied ones "
             f"(**{inst['index']:.2f}×** the single-family norm).\n")
    s.append("These are **complaints**, not violations or city crackdowns. The most plausible reading "
             "is housing conditions — investor-owned single-family homes are far likelier to be "
             f"rentals. Tellingly, the same homes show **no** assessment gap ({inst['assessment_index']:.2f}× "
             f"the class norm). Cases are windowed from {d['window_start']} and attributed to the "
             "current owner.\n")
    return "\n".join(s)


def traffic_deaths(d):
    ys = [y for y in d["years"] if not y["partial"]]
    by = {y["year"]: y for y in ys}
    first, last = ys[0], ys[-1]
    peak_c = max(ys, key=lambda y: y["crashes"])
    peak_d = max(ys, key=lambda y: y["deaths"])
    s = []
    s.append('Austin, like many cities, set a "Vision Zero" goal of eliminating traffic deaths. '
             "Reported crashes have fallen from their 2019 peak — but deaths climbed the other way.\n")
    s.append(f"> Deaths rose from **{first['deaths']}** ({first['year']}) to a high of **{peak_d['deaths']}** "
             f"({peak_d['year']}) and **{last['deaths']}** ({last['year']}), while crashes fell from a "
             f"**{fmt(peak_c['crashes'])}** peak ({peak_c['year']}). The fatal rate roughly doubled "
             f"({first['fatal_per_1k']} → {last['fatal_per_1k']} per 1,000 crashes).\n")
    s.append("## Crashes vs. deaths, by year\n")
    s.append(table(["Year", "Crashes", "Fatal crashes", "Deaths", "Fatal / 1k"],
        [[y["year"], fmt(y["crashes"]), y["fatal_crashes"], y["deaths"], y["fatal_per_1k"]] for y in ys]))
    s.append(f"\n## Over half are pedestrians, cyclists and riders\n")
    vru = last["vru_deaths"]
    s.append(f"Of the {last['deaths']} people killed in {last['year']}, **{vru}** (~{round(100*vru/last['deaths'])}%) "
             f"were vulnerable road users: {last['ped_deaths']} pedestrians, {last['moto_deaths']} "
             f"motorcyclists, {last['bike_deaths']} cyclists.\n")
    s.append(table(["Year", "Total deaths", "Pedestrian", "Motorcycle", "Bicycle"],
        [[y["year"], y["deaths"], y["ped_deaths"], y["moto_deaths"], y["bike_deaths"]] for y in ys[-5:]]))
    return "\n".join(s)


def ballot_money(d):
    s = d["summary"]
    ratio = s["committee_total_m"] / s["candidate_total_m"]
    out = []
    out.append("Campaign-finance filings aren't just about candidates. The committees and PACs that "
               "fight over ballot propositions raise more money overall — and a single donor often "
               "bankrolls a measure almost by itself.\n")
    out.append(f"> Committees & PACs raised **${s['committee_total_m']:.0f}M**, about **{ratio:.1f}×** the "
               f"**${s['candidate_total_m']:.0f}M** raised by all candidates (the state Greg Abbott filing "
               "is excluded).\n")
    out.append("## One donor, one campaign\n")
    out.append("For several of the biggest committees, one donor supplied most — sometimes essentially "
               "all — of the money.\n")
    out.append(table(["Committee", "Raised", "Gifts", "Top donor", "Top donor share"],
        [[c["committee"], money(c["total"]), fmt(c["gifts"]), c["top_donor"], f"{round(c['top_donor_pct'])}%"]
         for c in d["committees"]]))
    out.append("\n## The largest single contributions\n")
    out.append(table(["Donor", "To committee", "Amount", "Date"],
        [[m["donor"], m["committee"], money(m["amount"]), m["date"]] for m in d["mega_gifts"]]))
    return "\n".join(out)


def money_wins(d):
    out = []
    out.append(f"Across **{d['scored']}** ballot fights where the sides' committee funding "
               f"differed, the better-funded side won **{d['won']}** — a coin flip, not a "
               "purchase. Notably, the better-funded side LOST: " + "; ".join(d["losses"]) + ".\n")
    out.append("## Fight by fight\n")
    def m(v):
        return f"${v/1e6:.1f}M" if abs(v) >= 1e6 else f"${round(v/1e3)}k"
    out.append(table(["Election", "Measure", "$ for", "$ against", "Votes for–against", "Outcome", "Money won?"],
        [[f["election_date"], f["measure"], m(f["money_for"]), m(f["money_against"]),
          f"{f['votes_for']:,}–{f['votes_against']:,}", f["outcome"],
          {True: "yes", False: "NO", None: "n/a"}[f["money_won"]]] for f in d["fights"]]))
    return "\n".join(out)


def home_builders(d):
    peak = max(d["years"], key=lambda y: y["permits"])
    first, last = d["years"][0], d["years"][-1]
    out = []
    out.append("Austin's permit file is enormous, but most rows aren't new buildings — every new house "
               "also generates separate electrical, plumbing and mechanical permits. Counting only the "
               "**building permit for new residential work** (the general contractor's permit) leaves "
               f"about **{fmt(d['total_since_2010'])} new-home permits since 2010**.\n")
    out.append("## A boom that tripled, then cooled\n")
    out.append(f"Permitting climbed from {fmt(first['permits'])} in {first['year']} to a peak of "
               f"**{fmt(peak['permits'])}** in {peak['year']}, then fell with rising interest rates to "
               f"{fmt(last['permits'])} in {last['year']}.\n")
    out.append(table(["Year", "New-home permits"], [[y["year"], fmt(y["permits"])] for y in d["years"]]))
    out.append("\n## A handful of national builders dominate\n")
    out.append(f"The ten most active builders account for **{pct(d['top10_share'],0)}** of every new-home "
               "permit that names a builder.\n")
    out.append(table(["Builder", "New-home permits"],
        [[title_case(b["builder"]), fmt(b["permits"])] for b in d["builders"]]))
    return "\n".join(out)


def service_equity(d):
    rs = sorted(d["districts"], key=lambda r: r["council_district"])
    obs = [r["observed_days"] for r in rs]
    rat = [r["disparity_ratio"] for r in rs]
    out = []
    out.append("It's a fair question: do some neighborhoods wait longer for 311 service? Austin logs "
               "millions of requests with the council district attached, so we can check. **We publish "
               "this non-finding on purpose** — a research tool earns trust by reporting what it "
               "*doesn't* find as plainly as what it does.\n")
    out.append(f"> Raw median days-to-close ranges **{min(obs):.1f}–{max(obs):.1f}** across districts. "
               f"But adjust for each district's request mix and all ten land in **{min(rat):.2f}×–{max(rat):.2f}×** "
               f"of expected — **{d['n_flagged']} of {len(rs)}** flagged (threshold {d['threshold']}×).\n")
    out.append("## Why the raw gap misleads\n")
    out.append("Districts ask for different things — a downed limb closes in a day, a code case in "
               "months. Using indirect standardization, we compute the days-to-close each district "
               "would be *expected* to show if its ~290 request types were each handled at the "
               "citywide pace, and compare to observed.\n")
    out.append("## Every district lands near 1.0\n")
    out.append(table(["District", "Closed cases", "Observed days", "Expected days", "Ratio", "Flagged"],
        [[f"D{r['council_district']}", fmt(r["n_closed"]), f"{r['observed_days']:.1f}",
          f"{r['expected_days']:.1f}", f"{r['disparity_ratio']:.2f}×", "yes" if r["flagged"] else "no"]
         for r in rs]))
    return "\n".join(out)


def city_dollars(d):
    t = d["totals"]
    debt_share = t["debt_b"] / t["total_b"]
    latest = d["by_year"][-1]
    out = []
    out.append("The City of Austin publishes every check and electronic payment it sends back to 2008 — "
               f"a public ledger of **{money(t['total_b']*1e9)}**. Add it up by where it went and the "
               "biggest flows are debt and a short list of big construction and engineering firms.\n")
    out.append(f"> **{money(t['debt_b']*1e9)}** (~{pct(debt_share,0)} of all spending) is debt service — "
               f"the single largest category. Annual spending reached {money(latest['amount_b']*1e9)} in "
               f"{latest['year']}.\n")
    out.append("## Top departments\n")
    out.append(table(["Department", "Total"],
        [[r["dept"], money(r["amount_b"]*1e9)] for r in d["by_department"]]))
    out.append("\n## Largest non-debt-service vendors\n")
    out.append(table(["Vendor (legal payee)", "Total paid"],
        [[v["vendor"], money(v["amount_m"]*1e6)] for v in d["top_vendors_operating"]]))
    return "\n".join(out)


def local_money(d):
    cand, comm = d["candidate"], d["committee"]
    factor = comm["oos_share"] / cand["oos_share"]
    out = []
    out.append("A common worry is that outside cash floods local politics. Split Austin's campaign money "
               "into candidate races and ballot committees and the answer differs sharply.\n")
    out.append(f"> Candidate races: **{pct(cand['oos_share'])}** out of state (of {money(cand['total'])}). "
               f"Ballot committees: **{pct(comm['oos_share'])}** (of {money(comm['total'])}) — about "
               f"**{factor:.0f}×** the candidate rate.\n")
    out.append("## Funded close to home — candidates\n")
    out.append(table(["Donor location", "Total"],
        [["In Texas", money(cand["texas"])], ["Out of state", money(cand["out_of_state"])],
         ["Unknown", money(cand["unknown"])]]))
    out.append("\nTop out-of-state origins of candidate money:\n")
    out.append(table(["Donor city", "Gifts", "Total"],
        [[o["place"].rstrip(", "), fmt(o["gifts"]), money(o["total"])] for o in d["top_oos_origins"]]))
    out.append("\n## A different map — committees\n")
    out.append(table(["Donor location", "Total"],
        [["In Texas", money(comm["texas"])], ["Out of state", money(comm["out_of_state"])],
         ["Unknown", money(comm["unknown"])]]))
    out.append("\nNational corporations and advocacy groups fund Austin ballot fights from afar — see "
               "*Who funds Austin's ballot fights* for the company-by-company breakdown.")
    return "\n".join(out)


def who_pays(d):
    big, small = d["buckets"][-1], d["buckets"][0]
    out = []
    out.append(f"Austin's filings hold about **{fmt(d['total_gifts'])} contributions** totaling "
               f"**{money(d['total_dollars'])}**. Most are small. Most of the money isn't.\n")
    out.append(f"> The largest **1%** of gifts supply **{pct(d['top1pct_share'],0)}** of every dollar "
               f"(top 10% = {pct(d['top10pct_share'],0)}). {fmt(big['gifts'])} gifts of $25k+ supplied "
               f"{money(big['total'])}; {fmt(small['gifts'])} gifts under $50 supplied just "
               f"{money(small['total'])}.\n")
    out.append("## Share of gifts vs. share of dollars, by size\n")
    out.append(table(["Contribution size", "Gifts", "% of gifts", "Dollars", "% of dollars"],
        [[b["bucket"], fmt(b["gifts"]), pct(b["gifts"]/d["total_gifts"]),
          money(b["total"]), pct(b["total"]/d["total_dollars"])] for b in d["buckets"]]))
    out.append("\n## By donor type\n")
    out.append(table(["Donor type", "Gifts", "Total", "Avg gift"],
        [[t["dtype"].capitalize(), fmt(t["gifts"]), money(t["total"]), money(t["total"]/t["gifts"])]
         for t in d["by_type"]]))
    return "\n".join(out)


def money_influence(d):
    v, o = d["votes"], d["overlap"]
    cv = {r["vote"]: r["n"] for r in d["contract_votes"]}
    yes, no = cv.get("Yes", 0), cv.get("No", 0)
    don_share = o["donated_total"] / o["contract_total"] if o["contract_total"] else 0
    out = []
    out.append("Throughout this project we treated the money→influence question as out of reach — "
               "Austin's Legistar API exposes no per-member votes. But the city publishes the roll "
               f"call as a separate open dataset: **{fmt(v['all_votes'])} member-votes** since "
               f"{v['min_yr']}. Paired with award-level contracts, the whole chain is finally "
               "traceable: contribution → council member → their vote → the contract.\n")
    out.append("## The council vote is a near-unanimous rubber stamp\n")
    out.append(f"Across every recorded contract authorization since {v['min_yr']}, **{fmt(yes)} votes "
               f"were Yes and just {fmt(no)} were No**. Overall, **{v['pct_yes']}%** of all "
               f"{fmt(v['all_votes'])} council votes are Yes. There is essentially no dissent for a "
               "donation to 'buy.'\n")
    out.append("## Tiny dollars — and the timing runs backwards\n")
    out.append(f"Of the {fmt(d['contracts_total']['n'])} contracts on file ({money(d['contracts_total']['amt'])}), "
               f"**{o['firms']}** went to firms that are also donors — holding **{money(o['contract_total'])}** "
               f"in contracts while donating **{money(o['donated_total'])}** (~{pct(don_share,2)} of contract "
               f"value). **{o['gift_after']} of {o['firms']}** made their first contribution in or after the "
               "award year — you can't buy a contract you've already won.\n")
    out.append(table(["Firm", "City contracts", "Donated"],
        [[f["vendor"], money(f["contract_amt"]), money(f["donated"])] for f in d["matched_firms"]]))
    out.append(f"\n## The conflict mechanism is used\n")
    out.append(f"The votes also show **{sum(r['n'] for r in d['recusals'])} recusals** across "
               f"{len(d['recusals'])} members — formally stepping out of a vote rather than casting it.\n")
    out.append(table(["Member", "Recusals"], [[r["member"], r["n"]] for r in d["recusals"]]))
    out.append("\n## The honest conclusion\n")
    out.append("The donor–contractor overlap is small, the dollars trivial next to the contracts, most "
               "donations postdate the award, and the vote is a near-unanimous formality with a working "
               "recusal safeguard. **No detectable pay-to-play** at any decision point the public data "
               "exposes. If influence operates, it does so upstream — in procurement scoring and "
               "agenda-setting that no open dataset records.")
    return "\n".join(out)


def district_divide(d):
    rs = d["districts"]
    poor, rich = rs[0], rs[-1]
    out = []
    out.append("Austin elects its council by district, and the districts are not alike. In District "
               f"{poor['d']}, **{poor['pct_under35k']:.0f}%** of households earn under $35,000; in "
               f"District {rich['d']} it's **{rich['pct_under35k']:.0f}%**. The racial map is just as "
               "divided.\n")
    out.append(table(["District", "Under $35k", "Over $150k", "Hispanic", "White", "Black", "Asian", "Crime/1k", "311 ratio"],
        [[f"D{r['d']}", f"{r['pct_under35k']:.1f}%", f"{r['pct_over150k']:.1f}%", f"{r['hispanic']:.0f}%",
          f"{r['white']:.0f}%", f"{r['black']:.0f}%", f"{r['asian']:.0f}%", f"{r['crime_per_1k']:.0f}",
          f"{r['resp_ratio']:.2f}×"] for r in rs]))
    out.append(f"\n## Crime reports follow the income line (r={d['corr_crime_income']:.2f})\n")
    out.append("Reported crime tracks the divide almost in lockstep — the poorest districts report two "
               "to three times the rate of the wealthiest. But these are *reported incidents*, which "
               "fold in differences in reporting and policing, not a clean measure of crime itself.\n")
    out.append(f"## But the city's 311 response doesn't (r={d['corr_response_income']:.2f})\n")
    out.append("Once you adjust for what each district asks for, the 311 response ratio is flat across "
               "the income gradient — essentially no relationship. The poorest district is served as "
               "fast as its requests predict; so is the richest. **The divide is real; the 311 double "
               "standard isn't.**")
    return "\n".join(out)


def council_dissent(d):
    s = d["summary"]
    top = d["dissent_by_member"][0]
    out = []
    out.append(f"Austin's council governs by consensus. Of {fmt(s['items'])} agenda items since "
               f"2023, just **{fmt(s['contested'])} ({s['pct_contested']}%)** drew even a single No "
               f"vote — the council agrees on **{s['pct_agree']}%** of everything it votes on.\n")
    out.append("## Who dissents, per vote cast\n")
    out.append("Ranking by No-votes *per 100 votes cast* (so tenure doesn't distort the picture), "
               f"dissent is still concentrated: **{top['member']}** (D{top['district']}) said No on "
               f"**{top['no_rate_per_100']}%** of votes cast — but that is the ceiling, not the norm.\n")
    out.append(table(["Council member", "District", "No rate / 100 votes", "No votes", "Votes cast", "Serving?"],
        [[r["member"], f"D{r['district']}", f"{r['no_rate_per_100']}%", r["no_votes"], fmt(r["votes_cast"]),
          "yes" if r["current"] else f"through {r['last_vote_label']}"] for r in d["dissent_by_member"]]))
    out.append("\n## What they split on\n")
    out.append(table(["Item type", '"No" votes'],
        [[r["topic"], r["no_votes"]] for r in d["topics"]]))
    out.append("\nZoning and rezoning cases draw the most dissent of any single category — the "
               "site-by-site fights over how Austin grows.\n")
    out.append("## No stable opposition coalition\n")
    pair = d["coalitions"][0]
    out.append(f"The dissenters mostly don't vote as a bloc. The pair that most often votes No "
               f"together — {pair['member_a']} and {pair['member_b']} — did so only "
               f"**{pair['co_dissents']}** times. Co-dissent is rare and shifts by issue.")
    return "\n".join(out)


def short_term_rentals(d):
    central = sum(r["n"] for r in d["by_district"] if r["district"] in (9, 3, 1))
    out = []
    out.append(f"The friendly image of a short-term rental — a host renting their spare room — is the "
               f"minority. **{d['pct_non_owner']}%** of Austin's {fmt(d['total'])} *licensed* STRs are "
               "NOT owner-occupied: whole houses and multifamily units run as investment properties.\n")
    out.append("## Licensed STRs by type\n")
    out.append(table(["Type", "Count"], [[t["type"], fmt(t["n"])] for t in d["by_type"]]))
    out.append("\n## Where they cluster\n")
    out.append(f"STRs concentrate downtown and in East Austin — Districts 9, 3 and 1 alone hold "
               f"**{fmt(central)}** (~{round(100*central/d['total'])}%) of the licensed total.\n")
    out.append(table(["District", "STRs"], [[f"District {r['district']}", fmt(r["n"])] for r in d["by_district"]]))
    out.append("\n*Licensed STRs only — Austin has a documented gap between licensed and operating "
               "rentals, so these are a floor.*")
    return "\n".join(out)


def str_gap(d):
    lc = d["license_classes"]
    ratio_city = d["in_district"] / d["licensed_n"]
    out = []
    out.append(f"Inside Airbnb's {d['snapshot_date']} snapshot lists **{fmt(d['total'])}** Austin "
               f"short-term rentals on Airbnb alone, **{fmt(d['active'])}** of them reviewed in the "
               f"last 12 months. The city registry holds **{fmt(d['licensed_n'])}** licenses of any "
               f"type — {d['active']/d['licensed_n']:.1f}× fewer than the active listings, and "
               f"restricting to the {fmt(d['in_district'])} listings inside the 10 council districts "
               f"(the licensing jurisdiction) the gap is still **{ratio_city:.1f}×**.\n")
    claims, verified, missing = lc["claims_number"], lc["verified"], lc["missing"]
    out.append("## Most listings still show no license number\n")
    out.append(f"In this snapshot **{fmt(claims)}** of {fmt(d['active'])} active listings "
               f"({round(100 * claims / d['active'])}%) display a license number and **{fmt(verified)}** "
               f"({round(100 * verified / d['active'])}%) match a case number in the city registry — up "
               f"from zero in the 2025 snapshot, as Airbnb began surfacing a license field. The "
               f"remaining **{fmt(missing)}** ({round(100 * missing / d['active'])}%) show none; a blank "
               "field isn't proof of non-compliance, but enforcement can't rely on the listing side "
               "alone.\n")
    out.append("## Operating vs licensed, by district\n")
    out.append(table(["District", "Active Airbnb listings", "Licensed STRs"],
        [[f"D{r['district']}", fmt(r["active_n"]), fmt(r["licensed_n"])] for r in d["by_district"]]))
    out.append(f"\n*{fmt(d['unlocated'])} active listings geolocate outside all 10 districts — the "
               "export covers the metro area, wider than city jurisdiction.*\n")
    out.append("## Top ZIPs\n")
    out.append(table(["ZIP", "Active Airbnb listings", "Licensed STRs"],
        [[r["zip"], fmt(r["active_n"]), fmt(r["licensed_n"])] for r in d["by_zip"]]))
    out.append("\n## Mostly multi-listing hosts\n")
    h = d["hosts"]
    out.append(table(["Host size", "Listings"],
        [["Host has 2+ listings", fmt(h["multi2"])], ["Host has 5+ listings", fmt(h["multi5"])],
         ["Host has 10+ listings", fmt(h["multi10"])]]))
    return "\n".join(out)


def who_lobbies(d):
    s = d["scale"]
    out = []
    out.append(f"Austin's **{fmt(s['lobbyists'])} registered lobbyists** work for some "
               f"**{fmt(s['clients'])} distinct clients** — and one industry swamps the rest. "
               f"**{round(d['re_dev_share']*100)}%** of clients are real estate, development, land or "
               "construction; technology is a rounding error by comparison.\n")
    out.append("## Lobbying clients by industry\n")
    out.append(table(["Industry", "Clients"], [[x["sector"], fmt(x["clients"])] for x in d["sectors"]]))
    out.append("\n## Modest fees, and almost no gifts\n")
    out.append("Most engagements report under $10,000 or no compensation; only a few dozen reach "
               "$50,000+.\n")
    out.append(table(["Compensation band", "Filings"], [[b["band"], fmt(b["n"])] for b in d["comp_bands"]]))
    out.append(f"\n> **{money(d['official_spend']['total'])}** is the entire amount Austin's registered "
               "lobbyists report spending on officials — food, gifts, entertainment and travel — across "
               "every filing on record. There is no lavish wining-and-dining in the disclosures.\n")
    out.append("## The takeaway\n")
    out.append("Beside the rest of the money trail — donations don't track contracts, council votes are "
               "near-unanimous, lobbyists barely spend on officials — organized influence in Austin isn't "
               "gifts or quiet payments. It's a development industry that registers, hires lobbyists, and "
               "works the land-use process in the open.")
    return "\n".join(out)


def animal_shelter(d):
    out = []
    out.append(f"\"No-kill\" doesn't mean no animal is ever euthanized — it's a benchmark: at least "
               f"90% of shelter animals leaving alive. Austin clears it. Of {fmt(d['total'])} outcomes "
               f"in the past year, **{pct(d['live_release_rate'])}** were live (adopted, sent to rescue, "
               f"or returned to an owner) against **{fmt(d['euthanized'])}** euthanized.\n")
    out.append("## What happens to animals at the shelter\n")
    out.append(table(["Outcome", "Count"], [[o["grp"], fmt(o["n"])] for o in d["outcomes"]]))
    out.append("\n## By animal type\n")
    out.append(table(["Type", "Count"], [[t["type"], fmt(t["n"])] for t in d["by_type"]]))
    out.append(f"\n*Recent rolling window ({d['window']['mn']} – {d['window']['mx']}); {fmt(d['intakes'])} intakes.*")
    return "\n".join(out)


def food_inspections(d):
    good = next((b for b in d["distribution"] if b["band"] == "90–100"), {"n": 0})
    under = next((b for b in d["distribution"] if b["band"] == "Under 70"), {"n": 0})
    out = []
    out.append(f"Austin's food inspectors grade each visit 0–100. The picture is reassuring: the "
               f"average is **{d['avg_score']}**, more than two-thirds of inspections land at 90+, and "
               f"only **{fmt(under['n'])}** of {fmt(d['total'])} fall below 70.\n")
    out.append("## Inspection scores, by band\n")
    out.append(table(["Score band", "Inspections"], [[b["band"], fmt(b["n"])] for b in d["distribution"]]))
    out.append("\n## The repeat low-scorers\n")
    out.append("A handful of establishments score low again and again — public health records the city "
               "publishes for residents (some already flagged ineligible-for-renewal or out-of-business).\n")
    out.append(table(["Establishment", "Low inspections", "Worst score"],
        [[r["name"], r["low_inspections"], r["worst"]] for r in d["repeat_low"]]))
    out.append("\n*A score is a point-in-time snapshot; inspections drive fixes and scores change between visits.*")
    return "\n".join(out)


# ---- story registry (slug, title, eyebrow, dek, endpoint, renderer) -------
STORIES = [
    ("animal-shelter", "Austin's no-kill shelter, by the numbers", "City services · Animals",
     "About 91% of animals that came through Austin Animal Center in the past year left alive — clearing the 90% no-kill bar.",
     "/v1/stories/animal-shelter", animal_shelter),
    ("food-inspections", "How clean is Austin's kitchen?", "City services · Food safety",
     "The average food-inspection score is 91 and most kitchens score well — but a small set of establishments keep failing.",
     "/v1/stories/food-inspections", food_inspections),
    ("who-owns-austin", "Who Owns Austin", "Property · Ownership",
     "Behind 364,903 owners on the tax roll, a handful of public bodies and private companies hold an outsized share of $453B in property.",
     "/v1/stories/who-owns-austin", who_owns_austin),
    ("homestead-cap", "The homestead cap shields $10 billion", "Property · Taxes",
     "The 10% homestead cap keeps ~$10B of value off the tax rolls — and nearly half of that break flows to the most expensive 10% of homes.",
     "/v1/stories/homestead-cap", homestead_cap),
    ("short-term-rentals", "Austin's short-term rentals are mostly not someone's home", "Housing · Rentals",
     "Nearly two-thirds of licensed STRs aren't owner-occupied — investor-run units clustered in the urban core and East Austin.",
     "/v1/stories/short-term-rentals", short_term_rentals),
    ("str-gap", "The STR licensing gap", "Housing · Rentals",
     "Austin has 2.5× more active Airbnb listings than STR licenses — and most listings still show no license number.",
     "/v1/stories/str-gap", str_gap),
    ("investor-single-family", "Investor-owned homes draw more complaints", "Property · Code",
     "Within single-family housing, investor-owned homes draw about 1.7× the code complaints of owner-occupied ones — after controlling for property mix.",
     "/v1/stories/investor-complaints", investor_complaints),
    ("traffic-deaths", "Fewer crashes, more deaths", "Safety · Vision Zero",
     "Crashes fell from their 2019 peak, but Austin traffic deaths roughly doubled — and over half the dead are pedestrians, cyclists and riders.",
     "/v1/stories/traffic-deaths", traffic_deaths),
    ("district-divide", "Two Austins, one service standard", "Equity · Districts",
     "The 10 council districts split sharply by income and race; crime reports track that divide (r=0.89) but 311 response does not (r=0.13).",
     "/v1/stories/district-divide", district_divide),
    ("who-lobbies", "Who lobbies City Hall? Overwhelmingly, developers.", "Influence · Lobbying",
     "Nearly three-quarters of Austin's 2,630 lobbying clients are real estate & development — and lobbyists report just ~$27k spent on officials across all years.",
     "/v1/stories/who-lobbies", who_lobbies),
    ("council-dissent", "What Austin City Council actually fights about", "Governance · Council",
     "The council agrees on 95.3% of everything it votes on; the contested 4.7% is zoning and contracts — and even the top dissenter said No on just 4.6% of their votes.",
     "/v1/stories/council-dissent", council_dissent),
    ("money-influence", "Does campaign money buy influence at City Hall?", "Money · Influence",
     "With council votes finally traceable, the full chain is visible — contribution → member → vote → contract. The result: no pay-to-play at any decision point the data exposes.",
     "/v1/stories/money-influence", money_influence),
    ("ballot-money", "Who funds Austin's ballot fights", "Money · Elections",
     "Ballot-measure committees out-raise candidates 2-to-1 — and a single company often funds a campaign almost by itself.",
     "/v1/stories/ballot-money", ballot_money),
    ("money-wins", "Does money win Austin elections?", "Money · Elections",
     "The better-funded side won just 4 of Austin's last 8 contested ballot fights — Uber's $2.2M and a $6.1M police-staffing campaign both lost.",
     "/v1/stories/money-wins", money_wins),
    ("home-builders", "Who's building Austin's homes", "Growth · Housing",
     "Counted properly — one permit per house, not per electrician — a short list of national production builders pulls more than a third of all new-home permits.",
     "/v1/stories/home-builders", home_builders),
    ("service-equity", "Does the city answer some neighborhoods slower?", "Civic services · 311",
     "We checked 311 response times by district. Once you adjust for what each district asks for, the gaps vanish — a null result, published on purpose.",
     "/v1/stories/service-equity", service_equity),
    ("local-money", "Local races, local money — except the ballot fights", "Money · Elections",
     "Only ~4% of money to Austin council candidates comes from out of state — but a quarter of ballot-committee money does.",
     "/v1/stories/local-money", local_money),
    ("who-pays", "Who pays for Austin politics", "Money · Elections",
     "Most contributions are small; most of the money isn't. The largest 1% of gifts supply 56% of every campaign dollar.",
     "/v1/stories/who-pays", who_pays),
    ("where-city-dollars-go", "Where your city dollars actually go", "Money · Spending",
     "The city has written $37B in checks since 2008 — most of it to debt-service banks and a short list of big construction and engineering firms.",
     "/v1/stories/city-dollars", city_dollars),
]

DISCLAIMER = ("> *Research, not advocacy. Every figure is produced by a query against Austin's open-data "
              "warehouse and carries its methodology and limits. Screening signals, not accusations — "
              "readers draw their own conclusions.*")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8000")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    # Build header without count; will add count after loop
    index = ["# Austin Civic Intelligence — Data Stories\n",
             DISCLAIMER, "\n"]

    jsx_path = Path(__file__).resolve().parent.parent / "frontend" / "src" / "stories" / "index.jsx"
    failures = check_registry_sync(jsx_path.read_text(encoding="utf-8"), STORIES)
    failures = [f"registry-sync: dek for '{s}' differs between export_stories.py and index.jsx"
                for s in failures]

    written = 0  # Count successfully written stories
    for slug, title, eyebrow, dek, endpoint, render in STORIES:
        try:
            d = get(args.base, endpoint)
            body = render(d)
            foot = footer(d)
        except Exception as e:
            failures.append(f"render-error: '{slug}': {type(e).__name__}: {e}")
            continue
        misses = lint_dek(dek, body + foot)   # deks may cite numbers explained in the footer
        if misses:
            failures.append(f"dek-drift: '{slug}' dek numbers not in body: {misses}")
            continue                      # do not write a drifted story
        md = [f"# {title}\n", f"*{eyebrow}*\n", f"**{dek}**\n", DISCLAIMER, "\n", body,
              foot,
              "\n## Sources & provenance\n",
              f"- Live endpoint: `{endpoint}`",
              "- Source datasets are listed in `config/sources.yaml`.",
              "- Figures current as of the latest `atx_dashboard.cli refresh`.\n"]
        (OUT / f"{slug}.md").write_text("\n".join(md))
        index.append(f"| [{title}]({slug}.md) | {eyebrow} |")
        written += 1
        print(f"wrote docs/stories/{slug}.md")

    # Insert count and table headers after building all entries
    index.insert(3, f"{written} sourced narrative reads built by crossing Austin's "
                    "public datasets. Generated from the live read-API; re-run "
                    "`python scripts/export_stories.py` after a data refresh.\n")
    index.insert(4, "| Story | Topic |")
    index.insert(5, "|---|---|")

    (OUT / "README.md").write_text("\n".join(index) + "\n")
    if failures:
        print("\nLINT FAILURES:")
        for f in failures:
            print(f"  - {f}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
