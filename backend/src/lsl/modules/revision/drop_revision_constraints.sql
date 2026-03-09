BEGIN;

-- utterances_revisions
ALTER TABLE public.utterances_revisions
    DROP CONSTRAINT IF EXISTS fk_utterances_revisions_session_id,
    DROP CONSTRAINT IF EXISTS utterances_revisions_session_id_fkey,
    DROP CONSTRAINT IF EXISTS fk_utterances_revisions_task_id,
    DROP CONSTRAINT IF EXISTS utterances_revisions_task_id_fkey,
    DROP CONSTRAINT IF EXISTS ck_utterances_revisions_status,
    DROP CONSTRAINT IF EXISTS utterances_revisions_session_id_key;

DROP INDEX IF EXISTS public.idx_utterances_revisions_session_id;

CREATE INDEX IF NOT EXISTS idx_utterances_revisions_session_id
    ON public.utterances_revisions (session_id);

-- utterances_revision_items
ALTER TABLE public.utterances_revision_items
    DROP CONSTRAINT IF EXISTS fk_utterances_revision_items_revision_id,
    DROP CONSTRAINT IF EXISTS utterances_revision_items_revision_id_fkey,
    DROP CONSTRAINT IF EXISTS fk_utterances_revision_items_task_id,
    DROP CONSTRAINT IF EXISTS utterances_revision_items_task_id_fkey,
    DROP CONSTRAINT IF EXISTS uq_utterances_revision_items_revision_seq,
    DROP CONSTRAINT IF EXISTS utterances_revision_items_revision_id_utterance_seq_key,
    DROP CONSTRAINT IF EXISTS ck_utterances_revision_items_score;

COMMIT;
