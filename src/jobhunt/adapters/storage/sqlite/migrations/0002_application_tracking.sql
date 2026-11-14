-- JT-2: application tracking.
-- Tracking fields live on jobs (one set per job). Notes get their own table
-- because there can be many per job, each with its own date.
-- Runs once per database (recorded in schema_version); never edit this file.

ALTER TABLE jobs ADD COLUMN status TEXT NOT NULL DEFAULT 'new';
ALTER TABLE jobs ADD COLUMN applied_at TEXT;
ALTER TABLE jobs ADD COLUMN tracking_url TEXT;
ALTER TABLE jobs ADD COLUMN contact TEXT;

CREATE TABLE job_notes (
    id          INTEGER PRIMARY KEY,   -- insertion order = note order
    job_id      TEXT NOT NULL REFERENCES jobs (id),
    created_at  TEXT NOT NULL,         -- ISO 8601 with UTC offset
    body        TEXT NOT NULL
);

CREATE INDEX idx_job_notes_job_id ON job_notes (job_id);
