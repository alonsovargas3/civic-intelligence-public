"""Deed acquisition sources. A DeedSource yields normalized deed dicts; the loader
is source-agnostic so bulk adapters (TexasFile / Clerk-bulk, bead 1lj) plug in later.

Normalized deed dict shape:
    {instrument_num, recorded_date, doc_type, grantors: [str], grantees: [str],
     legal_desc, raw: <original record>}
"""
import json
from typing import Iterable, Protocol

from .normalize import legal_key, normalize_party


class DeedSource(Protocol):
    def iter_deeds(self) -> Iterable[dict]:
        ...


def _normalize_record(rec: dict) -> dict:
    """Map a raw source record to the normalized deed dict."""
    return {
        "instrument_num": str(rec.get("instrument_num") or "").strip(),
        "recorded_date": rec.get("recorded_date"),
        "doc_type": rec.get("doc_type"),
        "grantors": [normalize_party(g) for g in (rec.get("grantors") or [])],
        "grantees": [normalize_party(g) for g in (rec.get("grantees") or [])],
        "legal_desc": legal_key(rec.get("legal_desc")),
        "raw": rec,
    }


class SampleSource:
    """Reads deeds from a local JSON-lines file (one JSON object per line).

    Used to build/test the loader before a bulk acquisition route is chosen.
    """
    name = "sample"

    def __init__(self, path: str):
        self.path = path

    def iter_deeds(self) -> Iterable[dict]:
        with open(self.path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                yield _normalize_record(json.loads(line))
