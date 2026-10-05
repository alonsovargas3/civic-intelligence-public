"""Minimal Legistar Web API client (OData v3).

Mirrors SocrataClient.fetch_incremental's generator contract — yields pages of
raw dict rows ordered by (cursor_field, primary_key) — so run.py can drive it
identically. Each Legistar entity carries its own *LastModifiedUtc freshness
field (the cursor) and an integer id (the upsert key). Tokenless.

Verified client slug for Austin is 'austintexas' (NOT 'austin').
"""
import logging

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

log = logging.getLogger("atx.legistar")


def _odata_dt(value) -> str:
    """OData v3 datetime literal: datetime'...'. Values come from *LastModifiedUtc
    fields (trusted-ish) but we escape single quotes defensively, same as SoQL."""
    return "datetime'" + str(value).replace("'", "''") + "'"


class LegistarError(Exception):
    """Raised for HTTP errors from the Legistar Web API."""


class LegistarClient:
    PAGE_CAP = 1000  # Legistar caps $top at 1000 (verified)

    # entity dataset_id -> (endpoint suffix, integer primary key field)
    _ENTITIES = {
        "Events": ("Events", "EventId"),
        "Matters": ("Matters", "MatterId"),
        "Persons": ("Persons", "PersonId"),
        "Bodies": ("Bodies", "BodyId"),
    }

    def __init__(self, base: str, client: str, timeout: int = 60):
        self.base = base.rstrip("/")     # e.g. https://webapi.legistar.com/v1
        self.client = client             # e.g. austintexas
        self.timeout = timeout
        self.session = requests.Session()

    @retry(
        reraise=True,
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type(LegistarError),
    )
    def _get(self, url: str, params: dict) -> list[dict]:
        try:
            resp = self.session.get(url, params=params, timeout=self.timeout)
        except requests.exceptions.RequestException as exc:
            # transient connection drop / timeout — common over a long per-matter
            # drill (~20k sequential requests); make it retryable, not fatal.
            raise LegistarError(f"connection error: {exc}") from exc
        if resp.status_code in (429, 500, 502, 503, 504):
            raise LegistarError(f"retryable {resp.status_code}: {resp.text[:200]}")
        if resp.status_code >= 400:
            raise LegistarError(
                f"status {resp.status_code}: {resp.text[:300]} (params={params})"
            )
        return resp.json()

    def fetch_incremental(self, dataset_id, cursor_field, since=None, page_size=1000):
        """Yield pages of rows ordered by (cursor_field, primary_key) ascending.

        dataset_id is the Legistar entity name ("Events", "Matters", "Persons",
        "Bodies") or the special "EventItems" (per-event drill-down). Same
        contract as SocrataClient.fetch_incremental so run.py is client-agnostic.
        """
        if dataset_id == "EventItems":
            yield from self._fetch_event_items(since, page_size)
            return
        if dataset_id == "MatterSponsors":
            yield from self._fetch_matter_sponsors(since, page_size)
            return
        endpoint, pk = self._ENTITIES[dataset_id]
        yield from self._fetch_entity(endpoint, pk, cursor_field, since, page_size)

    def _fetch_entity(self, endpoint, pk, cursor_field, since, page_size):
        url = f"{self.base}/{self.client}/{endpoint}"
        limit = min(page_size, self.PAGE_CAP)
        last_cursor = None
        last_id = None
        while True:
            if last_cursor is None:
                flt = f"{cursor_field} ge {_odata_dt(since)}" if since else None
            else:
                # Keyset seek past the last (cursor, id) of the prior page; ties on
                # cursor_field broken by the unique integer pk (no quotes on int).
                flt = (
                    f"({cursor_field} gt {_odata_dt(last_cursor)} or "
                    f"({cursor_field} eq {_odata_dt(last_cursor)} and {pk} gt {last_id}))"
                )
            params = {"$orderby": f"{cursor_field},{pk}", "$top": limit}
            if flt:
                params["$filter"] = flt
            page = self._get(url, params)
            if not page:
                break
            yield page
            if len(page) < limit:
                break
            last = page[-1]
            last_cursor = last.get(cursor_field)
            last_id = last.get(pk)
            if last_cursor is None or last_id is None:
                log.warning(
                    "%s: last row missing %s/%s; stopping pagination early",
                    endpoint, cursor_field, pk,
                )
                break

    def _fetch_event_items(self, since, page_size):
        """Per-event drill-down for EventItems (no global list endpoint).

        Iterate events ordered by EventLastModifiedUtc (keyset, filtered `ge since`
        so only changed/new meetings are re-drilled in steady state), and for each
        event GET its EventItems. Each item is stamped with `_event_last_modified`
        (the parent event's freshness) so run.py advances the cursor on the parent
        and stores it as the item's updated_at — matching the design.
        """
        event_url = f"{self.base}/{self.client}/Events"
        limit = min(page_size, self.PAGE_CAP)
        last_cursor = None
        last_id = None
        while True:
            if last_cursor is None:
                flt = f"EventLastModifiedUtc ge {_odata_dt(since)}" if since else None
            else:
                flt = (
                    f"(EventLastModifiedUtc gt {_odata_dt(last_cursor)} or "
                    f"(EventLastModifiedUtc eq {_odata_dt(last_cursor)} "
                    f"and EventId gt {last_id}))"
                )
            params = {"$orderby": "EventLastModifiedUtc,EventId", "$top": limit}
            if flt:
                params["$filter"] = flt
            events = self._get(event_url, params)
            if not events:
                break
            for ev in events:
                eid = ev.get("EventId")
                elm = ev.get("EventLastModifiedUtc")
                try:
                    items = self._get(f"{event_url}/{eid}/EventItems", {})
                except LegistarError as exc:
                    log.warning("EventItems for event %s failed: %s; skipping", eid, exc)
                    continue
                stamped = []
                for it in items:
                    it = dict(it)
                    it["_event_last_modified"] = elm
                    stamped.append(it)
                if stamped:
                    yield stamped
            if len(events) < limit:
                break
            last = events[-1]
            last_cursor = last.get("EventLastModifiedUtc")
            last_id = last.get("EventId")
            if last_cursor is None or last_id is None:
                log.warning("EventItems: last event missing lastmod/id; stopping early")
                break

    def _fetch_matter_sponsors(self, since, page_size):
        """Per-matter drill-down for sponsors (no global Sponsors list endpoint).

        Iterate Matters ordered by MatterLastModifiedUtc (keyset, filtered `ge since`
        so only changed/new matters are re-drilled in steady state), and for each
        matter GET its Sponsors. Each sponsor row is stamped with
        `_matter_last_modified` (the parent matter's freshness) so run.py advances
        the cursor on the parent — exactly mirroring the EventItems drill.
        """
        matter_url = f"{self.base}/{self.client}/Matters"
        limit = min(page_size, self.PAGE_CAP)
        last_cursor = None
        last_id = None
        while True:
            if last_cursor is None:
                flt = f"MatterLastModifiedUtc ge {_odata_dt(since)}" if since else None
            else:
                flt = (
                    f"(MatterLastModifiedUtc gt {_odata_dt(last_cursor)} or "
                    f"(MatterLastModifiedUtc eq {_odata_dt(last_cursor)} "
                    f"and MatterId gt {last_id}))"
                )
            params = {"$orderby": "MatterLastModifiedUtc,MatterId", "$top": limit}
            if flt:
                params["$filter"] = flt
            matters = self._get(matter_url, params)
            if not matters:
                break
            for m in matters:
                mid = m.get("MatterId")
                mlm = m.get("MatterLastModifiedUtc")
                try:
                    sponsors = self._get(f"{matter_url}/{mid}/Sponsors", {})
                except LegistarError as exc:
                    log.warning("Sponsors for matter %s failed: %s; skipping", mid, exc)
                    continue
                stamped = []
                for s in sponsors:
                    s = dict(s)
                    s["_matter_last_modified"] = mlm
                    stamped.append(s)
                if stamped:
                    yield stamped
            if len(matters) < limit:
                break
            last = matters[-1]
            last_cursor = last.get("MatterLastModifiedUtc")
            last_id = last.get("MatterId")
            if last_cursor is None or last_id is None:
                log.warning("MatterSponsors: last matter missing lastmod/id; stopping early")
                break
