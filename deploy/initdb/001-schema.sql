CREATE SCHEMA IF NOT EXISTS public;

CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TABLE IF NOT EXISTS public.assets (
    id                BIGSERIAL PRIMARY KEY,
    object_key        TEXT NOT NULL UNIQUE,
    category          VARCHAR(64) NOT NULL,
    entity_id         VARCHAR(128) NOT NULL,
    filename          VARCHAR(255),
    content_type      VARCHAR(128),
    file_size         BIGINT CHECK (file_size IS NULL OR file_size >= 0),
    etag              VARCHAR(128),
    storage_provider  VARCHAR(32) NOT NULL,
    upload_status     SMALLINT NOT NULL DEFAULT 0,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_assets_storage_provider
        CHECK (storage_provider IN ('oss', 's3', 'gcs', 'fake')),
    CONSTRAINT ck_assets_upload_status
        CHECK (upload_status IN (0, 1, 2, 3, 4))
);

CREATE INDEX IF NOT EXISTS idx_assets_category_entity_created_at
    ON public.assets (category, entity_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_assets_created_at
    ON public.assets (created_at DESC);

CREATE TABLE IF NOT EXISTS public.tasks (
    task_id                 UUID PRIMARY KEY,
    object_key              TEXT NOT NULL UNIQUE,
    audio_url               TEXT NOT NULL,
    x_duration_ms           INTEGER,
    x_status                SMALLINT NOT NULL DEFAULT 0,
    x_language              VARCHAR(16),
    x_provider              VARCHAR(32),
    x_provider_request_id   VARCHAR(128),
    x_provider_resource_id  VARCHAR(128),
    x_tt_logid              VARCHAR(255),
    x_provider_status_code  VARCHAR(32),
    x_provider_message      TEXT,
    error_code              VARCHAR(64),
    error_message           TEXT,
    poll_count              INTEGER NOT NULL DEFAULT 0,
    last_polled_at          TIMESTAMPTZ,
    next_poll_at            TIMESTAMPTZ,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_tasks_status
        CHECK (x_status IN (0, 1, 2, 3, 4))
);

CREATE INDEX IF NOT EXISTS idx_tasks_status_next_poll_at
    ON public.tasks (x_status, next_poll_at);

CREATE INDEX IF NOT EXISTS idx_tasks_created_at
    ON public.tasks (created_at DESC);

CREATE TABLE IF NOT EXISTS public.asr_results (
    task_id           UUID PRIMARY KEY REFERENCES public.tasks(task_id) ON DELETE CASCADE,
    x_provider        VARCHAR(32),
    duration_ms       INTEGER,
    x_full_text       TEXT,
    raw_result_json   JSONB,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.asr_utterances (
    id               BIGSERIAL PRIMARY KEY,
    task_id          UUID NOT NULL REFERENCES public.tasks(task_id) ON DELETE CASCADE,
    seq              INTEGER NOT NULL,
    x_text           TEXT NOT NULL,
    speaker          VARCHAR(64),
    start_time       INTEGER NOT NULL,
    end_time         INTEGER NOT NULL,
    additions_json   JSONB,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_asr_utterance_task_seq UNIQUE (task_id, seq)
);

CREATE INDEX IF NOT EXISTS idx_asr_utterances_task_id
    ON public.asr_utterances (task_id, seq);

CREATE TABLE IF NOT EXISTS public.sessions (
    session_id        UUID PRIMARY KEY,
    title             VARCHAR(200) NOT NULL,
    f_desc            TEXT,
    f_language        VARCHAR(16),
    f_type            SMALLINT NOT NULL DEFAULT 1,
    asset_object_key  TEXT UNIQUE,
    current_task_id   UUID UNIQUE,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_sessions_title_non_empty
        CHECK (length(btrim(title)) > 0),
    CONSTRAINT ck_sessions_type
        CHECK (f_type IN (1, 2)),
    CONSTRAINT fk_sessions_asset_object_key
        FOREIGN KEY (asset_object_key)
        REFERENCES public.assets(object_key)
        ON DELETE SET NULL,
    CONSTRAINT fk_sessions_current_task_id
        FOREIGN KEY (current_task_id)
        REFERENCES public.tasks(task_id)
        ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_sessions_created_at
    ON public.sessions (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_sessions_title_lower
    ON public.sessions (lower(title));

CREATE TABLE IF NOT EXISTS public.utterances_revisions (
    revision_id     UUID PRIMARY KEY,
    session_id      UUID NOT NULL UNIQUE REFERENCES public.sessions(session_id) ON DELETE CASCADE,
    task_id         UUID NOT NULL REFERENCES public.tasks(task_id) ON DELETE CASCADE,
    user_prompt     TEXT,
    x_status        SMALLINT NOT NULL DEFAULT 0,
    error_code      VARCHAR(64),
    error_message   TEXT,
    item_count      INTEGER NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_utterances_revisions_status
        CHECK (x_status IN (0, 1, 2, 3)),
    CONSTRAINT ck_utterances_revisions_item_count
        CHECK (item_count >= 0)
);

CREATE INDEX IF NOT EXISTS idx_utterances_revisions_session_id
    ON public.utterances_revisions (session_id);

CREATE TABLE IF NOT EXISTS public.utterances_revision_items (
    item_id             UUID PRIMARY KEY,
    revision_id         UUID NOT NULL REFERENCES public.utterances_revisions(revision_id) ON DELETE CASCADE,
    task_id             UUID NOT NULL REFERENCES public.tasks(task_id) ON DELETE CASCADE,
    source_seq_start    INTEGER NOT NULL,
    source_seq_end      INTEGER NOT NULL,
    source_seq_count    INTEGER NOT NULL,
    source_seqs         JSONB NOT NULL DEFAULT '[]'::jsonb,
    speaker             VARCHAR(64),
    start_time          INTEGER NOT NULL,
    end_time            INTEGER NOT NULL,
    original_text       TEXT NOT NULL,
    suggested_text      TEXT NOT NULL,
    draft_text          TEXT,
    score               SMALLINT NOT NULL,
    issue_tags          TEXT NOT NULL DEFAULT '',
    explanations        TEXT NOT NULL DEFAULT '',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_utterances_revision_items_seq_span
        CHECK (source_seq_end >= source_seq_start),
    CONSTRAINT ck_utterances_revision_items_seq_count
        CHECK (source_seq_count > 0),
    CONSTRAINT ck_utterances_revision_items_time_span
        CHECK (end_time >= start_time)
);

CREATE INDEX IF NOT EXISTS idx_utterances_revision_items_revision_seq_span
    ON public.utterances_revision_items (revision_id, source_seq_start, source_seq_end);

CREATE INDEX IF NOT EXISTS idx_utterances_revision_items_task_seq_span
    ON public.utterances_revision_items (task_id, source_seq_start, source_seq_end);

CREATE TABLE IF NOT EXISTS public.session_tts_settings (
    session_id              UUID PRIMARY KEY REFERENCES public.sessions(session_id) ON DELETE CASCADE,
    format                  VARCHAR(16) NOT NULL DEFAULT 'mp3',
    emotion_scale           NUMERIC(4, 2) NOT NULL DEFAULT 1.0,
    speech_rate             NUMERIC(4, 2) NOT NULL DEFAULT 1.0,
    loudness_rate           NUMERIC(4, 2) NOT NULL DEFAULT 1.0,
    speaker_mappings_json   JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.speech_syntheses (
    synthesis_id           UUID PRIMARY KEY,
    session_id             UUID NOT NULL UNIQUE REFERENCES public.sessions(session_id) ON DELETE CASCADE,
    x_provider             VARCHAR(32) NOT NULL,
    full_content_hash      VARCHAR(64) NOT NULL,
    full_asset_object_key  TEXT,
    full_duration_ms       INTEGER,
    item_count             INTEGER NOT NULL DEFAULT 0,
    completed_item_count   INTEGER NOT NULL DEFAULT 0,
    failed_item_count      INTEGER NOT NULL DEFAULT 0,
    x_status               SMALLINT NOT NULL DEFAULT 0,
    error_code             VARCHAR(64),
    error_message          TEXT,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_speech_syntheses_status
        CHECK (x_status IN (0, 1, 2, 3, 4)),
    CONSTRAINT ck_speech_syntheses_item_count
        CHECK (item_count >= 0 AND completed_item_count >= 0 AND failed_item_count >= 0)
);

CREATE INDEX IF NOT EXISTS idx_speech_syntheses_session_created_at
    ON public.speech_syntheses (session_id, created_at);

CREATE TABLE IF NOT EXISTS public.speech_synthesis_items (
    tts_item_id           UUID PRIMARY KEY,
    synthesis_id          UUID NOT NULL REFERENCES public.speech_syntheses(synthesis_id) ON DELETE CASCADE,
    source_item_id        UUID NOT NULL,
    source_seq_start      INTEGER NOT NULL,
    source_seq_end        INTEGER NOT NULL,
    source_seqs           JSONB NOT NULL DEFAULT '[]'::jsonb,
    conversation_speaker  VARCHAR(64),
    provider_speaker_id   VARCHAR(128) NOT NULL,
    content               TEXT NOT NULL,
    plain_text            TEXT NOT NULL,
    cue_texts             JSONB NOT NULL DEFAULT '[]'::jsonb,
    content_hash          VARCHAR(64) NOT NULL,
    duration_ms           INTEGER,
    x_status              SMALLINT NOT NULL DEFAULT 0,
    error_code            VARCHAR(64),
    error_message         TEXT,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_speech_synthesis_items_source_item
        UNIQUE (synthesis_id, source_item_id),
    CONSTRAINT ck_speech_synthesis_items_status
        CHECK (x_status IN (0, 1, 2, 3, 4)),
    CONSTRAINT ck_speech_synthesis_items_seq_span
        CHECK (source_seq_end >= source_seq_start)
);

CREATE INDEX IF NOT EXISTS idx_speech_synthesis_items_seq_span
    ON public.speech_synthesis_items (synthesis_id, source_seq_start, source_seq_end);

DROP TRIGGER IF EXISTS trg_assets_set_updated_at ON public.assets;
DROP TRIGGER IF EXISTS trg_tasks_set_updated_at ON public.tasks;
DROP TRIGGER IF EXISTS trg_sessions_set_updated_at ON public.sessions;
DROP TRIGGER IF EXISTS trg_utterances_revisions_set_updated_at ON public.utterances_revisions;
DROP TRIGGER IF EXISTS trg_utterances_revision_items_set_updated_at ON public.utterances_revision_items;
DROP TRIGGER IF EXISTS trg_session_tts_settings_set_updated_at ON public.session_tts_settings;
DROP TRIGGER IF EXISTS trg_speech_syntheses_set_updated_at ON public.speech_syntheses;
DROP TRIGGER IF EXISTS trg_speech_synthesis_items_set_updated_at ON public.speech_synthesis_items;

CREATE TRIGGER trg_assets_set_updated_at
BEFORE UPDATE ON public.assets
FOR EACH ROW
EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_tasks_set_updated_at
BEFORE UPDATE ON public.tasks
FOR EACH ROW
EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_sessions_set_updated_at
BEFORE UPDATE ON public.sessions
FOR EACH ROW
EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_utterances_revisions_set_updated_at
BEFORE UPDATE ON public.utterances_revisions
FOR EACH ROW
EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_utterances_revision_items_set_updated_at
BEFORE UPDATE ON public.utterances_revision_items
FOR EACH ROW
EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_session_tts_settings_set_updated_at
BEFORE UPDATE ON public.session_tts_settings
FOR EACH ROW
EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_speech_syntheses_set_updated_at
BEFORE UPDATE ON public.speech_syntheses
FOR EACH ROW
EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_speech_synthesis_items_set_updated_at
BEFORE UPDATE ON public.speech_synthesis_items
FOR EACH ROW
EXECUTE FUNCTION public.set_updated_at();

