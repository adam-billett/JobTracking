-- Initial schema for JT-1: the jobs table.
-- Numbered migration, never edited once committed (per ARCHITECTURE.md §5);
-- later schema changes land as 0002_*.sql, 0003_*.sql, and so on.

CREATE TABLE IF NOT EXISTS jobs (
    id           TEXT PRIMARY KEY,   -- hash of source + external_id
    source       TEXT NOT NULL,
    external_id  TEXT NOT NULL,
    company      TEXT NOT NULL,
    title        TEXT NOT NULL,
    url          TEXT NOT NULL,
    location     TEXT,               -- nullable: not every posting has one
    posted_at    TEXT                -- ISO 8601 string, nullable
);
