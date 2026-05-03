-- SQLite migration: attach revisions to the generic job module.
-- This script is for local SQLite databases only and should be run once.

ALTER TABLE revision_revisions
    ADD COLUMN job_id VARCHAR(32);
