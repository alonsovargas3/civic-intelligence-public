"""Pure deed -> parcel matcher (no DB).

Conservative, like entity resolution: an exact normalized-legal match is `strong`;
a (subdivision, first-lot, block) partial match is `review`; anything else is
unmatched (kept in raw_deeds, absent from deed_parcel). No fuzzy free-text matching.
Legal descriptions are already normalized via normalize.legal_key before they reach here.
"""
import re

# Parse "LOT <n>[-<m>] [BLK <b>] <SUBDIVISION...>" from a normalized legal_key.
# Real examples: "LOT 1 BLK A OAKWOOD", "LOT 19-22 BLK 18 SOUTH HEIGHTS",
#                "LOT 1-4 TEMPLER LOTS" (no block).
_LOT = re.compile(r"\bLOTS?\s+([0-9]+)(?:-[0-9]+)?")
_BLK = re.compile(r"\bBLK\s+(\S+)")
# Noise clauses that follow the subdivision name in messy legal descriptions.
# Strip everything from these keywords onward to get the bare subdivision name.
_NOISE = re.compile(r"\b(LESS|EXCEPT|AND|BEING|ALSO|AKA|A/K/A|UNIT|STE|SUITE|APT)\b.*$")


def _parse(legal: str):
    """Return (subdivision, first_lot, block) or None if not parseable.

    first_lot = the first lot number (range '19-22' -> '19'); block from BLK token
    (None if absent); subdivision = the tail after the lot/block tokens.
    """
    if not legal:
        return None
    lot_m = _LOT.search(legal)
    if not lot_m:
        return None
    first_lot = lot_m.group(1)
    blk_m = _BLK.search(legal)
    block = blk_m.group(1) if blk_m else None
    # subdivision = everything after the last of the lot/block matches,
    # with trailing noise clauses (LESS, EXCEPT, ...) stripped.
    cut = max(lot_m.end(), blk_m.end() if blk_m else 0)
    subdivision = legal[cut:].strip()
    subdivision = _NOISE.sub("", subdivision).strip()
    if not subdivision:
        return None
    return (subdivision, first_lot, block)


def build_parcel_index(rows) -> dict:
    """Build a match index from parcel rows = iterable of (account_id, legal_key).

    Returns {"exact": {legal: account_id}, "partial": {(subdiv, lot, block): account_id}}.
    On collisions the first row wins (deterministic given sorted input from db layer).
    """
    exact = {}
    partial = {}
    for account_id, legal in rows:
        if not legal:
            continue
        exact.setdefault(legal, account_id)
        parsed = _parse(legal)
        if parsed:
            partial.setdefault(parsed, account_id)
    return {"exact": exact, "partial": partial}


def match_to_parcel(deed: dict, index: dict):
    """Match a deed to a parcel. Returns (account_id|None, confidence|None, method).

    method is one of: legal_exact, subdiv_lot_block, unmatched.
    """
    legal = deed.get("legal_desc") or ""
    if not legal:
        return (None, None, "unmatched")
    acct = index["exact"].get(legal)
    if acct is not None:
        return (acct, "strong", "legal_exact")
    parsed = _parse(legal)
    if parsed is not None:
        acct = index["partial"].get(parsed)
        if acct is not None:
            return (acct, "review", "subdiv_lot_block")
    return (None, None, "unmatched")
