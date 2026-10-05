"""Pure council-member name normalization (no DB, stdlib only).

Matches names across the three formats we hold:
  - campaign contributions: "Last, First Middle"          (e.g. "Adler, Stephen")
  - Legistar matter sponsors: "<Title> First Last"        (e.g. "Council Member Ryan Alter")
  - quoted nicknames / suffixes in either                 (e.g. 'Casar, Gregorio E. "Greg"')

normalize_member_name -> (last, first) lowercased, or None for non-person names
(PACs/orgs have neither a comma nor a council title, so they're rejected).
same_member matches on last name + first INITIAL — loose enough to bridge
Steve/Stephen and Greg/Gregorio (which aren't prefixes of each other), tight
enough to keep distinct people apart (e.g. Alison Alter vs Ryan Alter). It's a
screening match, not identity resolution.
"""
from __future__ import annotations

import re
import unicodedata

_TITLE = re.compile(r"^\s*(mayor pro tem|mayor|council member|councilmember|council)\s+", re.I)
_NICK = re.compile(r"[\"']{1,2}[^\"']*[\"']{1,2}")   # "Greg", ''Chito''
_SUFFIX = {"jr", "sr", "ii", "iii", "iv", "phd", "md"}


def _clean(tok: str) -> str:
    # fold diacritics (josé -> jose, Velásquez -> velasquez) so the same person's
    # name matches across the contribution + sponsor sources
    tok = "".join(ch for ch in unicodedata.normalize("NFKD", tok)
                  if not unicodedata.combining(ch))
    return re.sub(r"[^\w]", "", tok, flags=re.UNICODE).lower()


def normalize_member_name(raw):
    """Return (last, first) for a person name, else None."""
    if not raw:
        return None
    s = _NICK.sub(" ", str(raw)).strip()
    if "," in s:
        last, _, rest = s.partition(",")
        toks = [t for t in rest.split() if t]
        first = toks[0] if toks else ""
        last_tok = last.strip()
    else:
        m = _TITLE.match(s)
        if not m:
            return None                      # no comma + no title -> not a member
        toks = [t for t in s[m.end():].split() if t and _clean(t) not in _SUFFIX]
        if len(toks) < 2:
            return None
        first, last_tok = toks[0], toks[-1]
    last, first = _clean(last_tok), _clean(first)
    if not last or not first:
        return None
    return (last, first)


def same_member(a, b) -> bool:
    """True if two normalized (last, first) names plausibly refer to one person:
    same last name and same first initial."""
    if not a or not b:
        return False
    return a[0] == b[0] and a[1][:1] == b[1][:1]
