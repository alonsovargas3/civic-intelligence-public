"""Minimal Socrata SODA client.

Pulls rows incrementally, ordered by a cursor field, and always requests the
Socrata system fields `:id` (stable row identity, used as our primary key) and
`:updated_at` (freshness). Because we lean on system fields, the ingester needs
zero knowledge of any dataset's column schema to work.
"""
import logging

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

log = logging.getLogger("atx.socrata")


def _soql_literal(value) -> str:
    """Quote a value for a SoQL `$where` clause, escaping embedded quotes.

    Cursor/id values originate from Socrata data, but we never trust them into a
    query unescaped — a stray apostrophe would otherwise break the clause (or
    worse). SoQL escapes a single quote by doubling it.
    """
    return "'" + str(value).replace("'", "''") + "'"


class SocrataError(Exception):
    """Raised for HTTP errors from the SODA API."""


class SocrataClient:
    def __init__(self, domain: str, app_token: str | None = None, timeout: int = 60):
        self.domain = domain
        self.timeout = timeout
        self.session = requests.Session()
        if app_token:
            # An app token lifts the (very low) anonymous rate limit. Required
            # in practice for any dataset polled on a schedule.
            self.session.headers["X-App-Token"] = app_token

    def _url(self, dataset_id: str) -> str:
        return f"https://{self.domain}/resource/{dataset_id}.json"

    @retry(
        reraise=True,
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type(SocrataError),
    )
    def _get(self, url: str, params: dict) -> list[dict]:
        resp = self.session.get(url, params=params, timeout=self.timeout)
        # Retry transient / rate-limit responses; surface client errors loudly.
        if resp.status_code in (429, 500, 502, 503, 504):
            raise SocrataError(f"retryable {resp.status_code}: {resp.text[:200]}")
        if resp.status_code >= 400:
            raise SocrataError(
                f"status {resp.status_code}: {resp.text[:300]} (params={params})"
            )
        return resp.json()

    def fetch_incremental(self, dataset_id, cursor_field=":updated_at", since=None, page_size=1000):
        """Yield pages of rows ordered by (cursor_field, :id) ascending.

        Pagination is **keyset** (a.k.a. seek), not `$offset`:

        - Correctness: ordering by cursor_field alone is not a total order — many
          rows commonly share one `:updated_at` (bulk updates). With `$offset`,
          the tie-break order is not stable between HTTP requests, so rows can be
          silently skipped or duplicated across page boundaries. Adding `:id` as a
          unique tiebreaker and seeking past the last `(cursor_field, :id)` seen
          makes paging deterministic — no gaps.
        - Scale: `$offset` forces Socrata to re-scan from the top on every page
          (O(n^2) over a large backfill, and some datasets cap max offset). Seeking
          on an indexed key stays linear.

        `since` applies the starting bound as `cursor_field >= since`, so boundary
        rows are re-pulled across runs; the upsert makes that idempotent.

        NOTE: this requires `cursor_field` to be a sortable column and every row to
        carry `:id` — both hold for the schema-agnostic Socrata model this repo is
        built on (`:id` is also the upsert primary key).
        """
        # `*` returns all data columns; we add the two system fields explicitly.
        # SoQL requires `*` to appear first in the select-list.
        select = "*, :id, :updated_at"
        last_cursor = None
        last_id = None
        while True:
            if last_cursor is None:
                # First page: just the optional starting bound.
                where = f"{cursor_field} >= {_soql_literal(since)}" if since else None
            else:
                # Subsequent pages: seek strictly past the last row of the prior
                # page, breaking cursor-value ties on the unique :id.
                where = (
                    f"({cursor_field} > {_soql_literal(last_cursor)} OR "
                    f"({cursor_field} = {_soql_literal(last_cursor)} AND "
                    f":id > {_soql_literal(last_id)}))"
                )
            params = {
                "$select": select,
                "$order": f"{cursor_field} ASC, :id ASC",
                "$limit": page_size,
            }
            if where:
                params["$where"] = where
            page = self._get(self._url(dataset_id), params)
            if not page:
                break
            yield page
            if len(page) < page_size:
                break
            last = page[-1]
            last_cursor = last.get(cursor_field)
            last_id = last.get(":id")
            if last_cursor is None or last_id is None:
                # Can't build the next seek key without both — stop rather than
                # risk re-requesting the same page forever.
                log.warning(
                    "%s: last row missing %s/:id; stopping pagination early",
                    dataset_id, cursor_field,
                )
                break

    def sample(self, dataset_id, limit=1) -> list[dict]:
        """One row with all fields, for the `discover` command."""
        try:
            return self._get(self._url(dataset_id), {"$select": ":*, *", "$limit": limit})
        except SocrataError:
            # Legacy datasets may reject `:*`; fall back to data columns only.
            return self._get(self._url(dataset_id), {"$limit": limit})
