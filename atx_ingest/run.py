"""Ingestion orchestration: one pass = pull every enabled source from its cursor."""
import logging
from datetime import datetime

from . import db
from .config import Settings, Source
from .legistar import LegistarClient
from .socrata import SocrataClient

log = logging.getLogger("atx.run")


def _parse_ts(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _fmt_counts(inserted: int, updated: int) -> str:
    """Render insert/update counts without conflating them (cd2).

    The `>=` cursor boundary re-pulls already-stored rows, which surface as
    updates — not new ingests. Reporting `inserted + updated` as one "ingested N"
    figure overstates what actually landed, so every report site uses this.
    """
    return f"{inserted} new, {updated} updated"


def _due(seconds_since_last_run: float | None, min_interval_seconds: int) -> bool:
    """Whether a source is due to poll this pass.

    Due if it has no throttle (min_interval_seconds <= 0), has never run
    (seconds_since_last_run is None), or enough time has elapsed since its last run.
    """
    if min_interval_seconds <= 0 or seconds_since_last_run is None:
        return True
    return seconds_since_last_run >= min_interval_seconds


def _make_client(src: Source, settings: Settings):
    """Pick the ingest client for a source by its declared kind."""
    if src.kind == "legistar":
        return LegistarClient(settings.legistar_base, settings.legistar_client)
    if src.kind == "socrata":
        return SocrataClient(settings.socrata_domain, settings.app_token)
    # Fail loudly rather than silently treating a typo'd kind as Socrata.
    raise ValueError(f"unknown source kind {src.kind!r} for {src.dataset_id}")


def ingest_source(client, conn, src: Source) -> tuple[int, int]:
    """Pull a source from its cursor; return (inserted, updated) counts.

    `inserted` is genuinely-new rows; `updated` is boundary re-pulls of rows we
    already had (idempotent). They're kept separate so callers don't report the
    `>=` re-pull as fresh ingestion (cd2).
    """
    db.ensure_source_table(conn, src.table)
    cursor = db.get_cursor(conn, src.dataset_id) or src.backfill_since
    log.info("ingesting %s (%s) since cursor=%s", src.name, src.dataset_id, cursor)

    inserted = 0
    updated = 0
    max_cursor = cursor
    for page in client.fetch_incremental(
        src.dataset_id, src.cursor_field, since=cursor, page_size=src.page_size
    ):
        rows = []
        for r in page:
            cval = r.get(src.cursor_field)
            # fetch_incremental yields rows ordered by cursor_field ASC, so the
            # last non-null value seen across the pass is the new high-water mark.
            # No value comparison needed (which also sidesteps the trap of
            # comparing non-timestamp cursors lexicographically).
            if cval is not None:
                max_cursor = str(cval)
            # Generalized over both clients: Socrata defaults primary_key=":id"
            # and cursor_field=":updated_at", so this is behavior-identical there;
            # Legistar uses e.g. EventId / EventLastModifiedUtc. The PK is coerced
            # to str for the text socrata_id column (Legistar ids are ints).
            sid = r.get(src.primary_key)
            rows.append((str(sid) if sid is not None else None, _parse_ts(cval), r))
        ins, upd = db.upsert_rows(conn, src.table, rows)
        inserted += ins
        updated += upd
        if (ins + upd) < len(rows):
            log.warning(
                "%s: %d/%d rows lacked %s (legacy dataset?) — set primary_key/cursor_field",
                src.table, len(rows) - (ins + upd), len(rows), src.primary_key,
            )
        log.info("  %s: +%d new, %d updated (pass %s)",
                 src.table, ins, upd, _fmt_counts(inserted, updated))

    # Record only newly-inserted rows in the lifetime counter; the `>=` boundary
    # re-pull means `updated` counts include rows we re-saw, which would inflate
    # a lifetime "rows ingested" figure on every poll.
    db.set_cursor(conn, src.dataset_id, max_cursor, inserted)
    log.info("done %s: %s, cursor=%s", src.name, _fmt_counts(inserted, updated), max_cursor)
    return (inserted, updated)


def run_once(settings: Settings) -> tuple[int, int]:
    """Run one pass over all enabled+due sources; return (inserted, updated)."""
    grand_inserted = 0
    grand_updated = 0
    for src in settings.sources:
        if not src.enabled:
            continue
        # A fresh connection per source (not one shared connection for the whole
        # pass). This is a resilience precaution, not a fix for an observed bug:
        # a single shared connection handles a full ~5M-row pass fine. But since
        # the db now runs with restart: unless-stopped, a DB restart mid-pass
        # would kill a shared connection and poison every later source; a
        # per-source connection contains that to the one source that hit it and
        # makes the error isolation below actually hold. Cost is ~5 connects/pass.
        try:
            with db.connect(settings.database_url) as conn:
                db.bootstrap(conn)  # idempotent (CREATE TABLE IF NOT EXISTS)
                since = db.seconds_since_last_run(conn, src.dataset_id)
                if not _due(since, src.min_interval_seconds):
                    log.info(
                        "skipping %s: ran %.0fs ago (min interval %ds)",
                        src.dataset_id, since, src.min_interval_seconds,
                    )
                    continue
                client = _make_client(src, settings)
                ins, upd = ingest_source(client, conn, src)
                grand_inserted += ins
                grand_updated += upd
        except Exception as exc:  # one bad source shouldn't stop the pass
            log.error("source %s failed: %s", src.dataset_id, exc)
    return (grand_inserted, grand_updated)
