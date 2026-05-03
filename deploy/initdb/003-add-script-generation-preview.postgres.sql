-- PostgreSQL migration: add incremental AI script preview storage.
-- Safe to run more than once.

ALTER TABLE public.script_generations
    ADD COLUMN IF NOT EXISTS preview_items_json TEXT NOT NULL DEFAULT '[]';
