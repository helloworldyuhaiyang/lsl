-- SQLite migration: add incremental AI script preview storage.
-- This script is for local SQLite databases only and should be run once.

ALTER TABLE script_generations
    ADD COLUMN preview_items_json TEXT NOT NULL DEFAULT '[]';
