"""Pure normalization helpers for entity resolution (no DB, no deps)."""
import re

# Name patterns. Order matters: government is checked before institutional.
# Keep alternatives multi-character: bare short tokens (CO, LP, THI, VAN) are
# common in person names, so adding them would mis-tag individuals (see
# test_name_kind_does_not_overmatch_short_tokens).
_GOV = re.compile(
    r"\b(CITY OF|COUNTY|STATE OF|UNITED STATES|[A-Z ]+ ISD\b|INDEPENDENT SCHOOL|"
    r"PUBLIC SCHOOLS?|UNIVERSITY|AUTHORITY|DISTRICT)\b"
)
_INST = re.compile(
    r"\b(LLC|INC|LTD|LLP|CORP|COMPANY|TRUST|HOA|"
    r"HOMEOWNERS|PARTNERS|PARTNERSHIP|HOLDINGS|PROPERTIES|HOMES|ASSOCIATION|"
    r"FOUNDATION|CHURCH|BANK|HEALTHCARE|HEALTH|HOSPITAL|MEDICAL|CLINIC|"
    r"INVESTMENTS?|MANAGEMENT|ENTERPRISES?|VENTURES?|REALTY|DEVELOPMENT|"
    r"GROUP|CAPITAL)\b"
)
_JUNK_ADDR = re.compile(r"^\s*(REVOCABLE TRUST|LIVING TRUST|FAMILY TRUST)\s*$", re.I)


def addr_key(mail_addr: dict) -> str:
    """Normalized mailing-address key = 'lower(trim(line1))|trim(zip)'.

    Returns '' when line1 is blank (no usable address to link on).
    """
    line1 = (mail_addr or {}).get("line1") or ""
    line1 = " ".join(line1.split()).lower()
    if not line1:
        return ""
    zip_ = ((mail_addr or {}).get("zip") or "").strip()
    return f"{line1}|{zip_}"


def is_junk_addr(line1: str) -> bool:
    """True for non-addresses we must not link on (blank, bare trust labels)."""
    if not line1 or not line1.strip():
        return True
    return bool(_JUNK_ADDR.match(line1))


def name_kind(name: str) -> str:
    """Classify an owner name: government | institutional | individual."""
    n = (name or "").upper()
    if _GOV.search(n):
        return "government"
    if _INST.search(n):
        return "institutional"
    return "individual"
