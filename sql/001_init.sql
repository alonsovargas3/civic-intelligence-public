-- Optional: the app bootstraps these automatically (atx_ingest.db).
-- Kept here for reference / manual setup.
CREATE TABLE IF NOT EXISTS ingestion_state (
    dataset_id    text PRIMARY KEY,
    last_cursor   text,
    last_run_at   timestamptz,
    rows_ingested bigint DEFAULT 0
);
-- raw_<table> tables are created per source by ensure_source_table().
