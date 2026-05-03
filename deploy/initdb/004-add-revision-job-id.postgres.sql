-- PostgreSQL migration: attach revisions to the generic job module.
-- Safe to run more than once.

ALTER TABLE public.revision_revisions
    ADD COLUMN IF NOT EXISTS job_id VARCHAR(32);
