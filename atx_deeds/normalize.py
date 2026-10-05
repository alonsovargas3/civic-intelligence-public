"""Pure normalization helpers for deed records (no DB, no deps)."""
import re

# Collapse internal whitespace, drop noise punctuation that varies between sources
# ('*' separators, periods in abbreviations), but KEEP '&' and '-' which are
# meaningful in legal descriptions ("LOTS 5-7 & 8").
_NOISE = re.compile(r"[*.,]")


def legal_key(legal_desc) -> str:
    """Normalized legal-description key for matching: upper, collapse whitespace,
    drop noise punctuation. Returns '' for blank/None."""
    if not legal_desc:
        return ""
    s = _NOISE.sub(" ", str(legal_desc).upper())
    return " ".join(s.split())


def normalize_party(name) -> str:
    """Normalize a grantor/grantee name: upper, drop commas/periods, collapse spaces.
    Returns '' for blank/None."""
    if not name:
        return ""
    s = str(name).upper().replace(",", " ").replace(".", "")
    return " ".join(s.split())
