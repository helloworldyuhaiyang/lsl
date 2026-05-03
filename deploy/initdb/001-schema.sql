CREATE SCHEMA IF NOT EXISTS public;

CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
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
    file_size         BIGINT,
    etag              VARCHAR(128),
    storage_provider  VARCHAR(32) NOT NULL,
    upload_status     SMALLINT NOT NULL DEFAULT 0,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_assets_category_entity_created_at
    ON public.assets (category, entity_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_assets_created_at
    ON public.assets (created_at DESC);

CREATE TABLE IF NOT EXISTS public.tasks (
    task_id                 VARCHAR(32) PRIMARY KEY,
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
    created_at              TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_tasks_status_next_poll_at
    ON public.tasks (x_status, next_poll_at);

CREATE INDEX IF NOT EXISTS idx_tasks_created_at
    ON public.tasks (created_at DESC);

CREATE TABLE IF NOT EXISTS public.asr_results (
    task_id           VARCHAR(32) PRIMARY KEY,
    x_provider        VARCHAR(32),
    duration_ms       INTEGER,
    x_full_text       TEXT,
    raw_result_json   TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS public.asr_utterances (
    id               BIGSERIAL PRIMARY KEY,
    task_id          VARCHAR(32) NOT NULL,
    seq              INTEGER NOT NULL,
    x_text           TEXT NOT NULL,
    speaker          VARCHAR(64),
    start_time       INTEGER NOT NULL,
    end_time         INTEGER NOT NULL,
    additions_json   TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_asr_utterances_task_id
    ON public.asr_utterances (task_id, seq);

CREATE UNIQUE INDEX IF NOT EXISTS uq_asr_utterance_task_seq
    ON public.asr_utterances (task_id, seq);

CREATE TABLE IF NOT EXISTS public.sessions (
    session_id        VARCHAR(32) PRIMARY KEY,
    title             VARCHAR(200) NOT NULL,
    f_desc            TEXT,
    f_language        VARCHAR(16),
    f_type            SMALLINT NOT NULL DEFAULT 1,
    asset_object_key  TEXT UNIQUE,
    current_task_id   VARCHAR(32) UNIQUE,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_sessions_created_at
    ON public.sessions (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_sessions_title_lower
    ON public.sessions (lower(title));

CREATE TABLE IF NOT EXISTS public.utterances_revisions (
    revision_id     VARCHAR(32) PRIMARY KEY,
    session_id      VARCHAR(32) NOT NULL UNIQUE,
    task_id         VARCHAR(32) NOT NULL,
    user_prompt     TEXT,
    x_status        SMALLINT NOT NULL DEFAULT 0,
    error_code      VARCHAR(64),
    error_message   TEXT,
    item_count      INTEGER NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_utterances_revisions_session_id
    ON public.utterances_revisions (session_id);

CREATE TABLE IF NOT EXISTS public.utterances_revision_items (
    item_id             VARCHAR(32) PRIMARY KEY,
    revision_id         VARCHAR(32) NOT NULL,
    task_id             VARCHAR(32) NOT NULL,
    source_seq_start    INTEGER NOT NULL,
    source_seq_end      INTEGER NOT NULL,
    source_seq_count    INTEGER NOT NULL,
    source_seqs         TEXT NOT NULL DEFAULT '[]',
    speaker             VARCHAR(64),
    start_time          INTEGER NOT NULL,
    end_time            INTEGER NOT NULL,
    original_text       TEXT NOT NULL,
    suggested_text      TEXT NOT NULL,
    draft_text          TEXT,
    score               SMALLINT NOT NULL,
    issue_tags          TEXT NOT NULL DEFAULT '',
    explanations        TEXT NOT NULL DEFAULT '',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_utterances_revision_items_revision_seq_span
    ON public.utterances_revision_items (revision_id, source_seq_start, source_seq_end);

CREATE INDEX IF NOT EXISTS idx_utterances_revision_items_task_seq_span
    ON public.utterances_revision_items (task_id, source_seq_start, source_seq_end);

CREATE TABLE IF NOT EXISTS public.session_tts_settings (
    session_id              VARCHAR(32) PRIMARY KEY,
    format                  VARCHAR(16) NOT NULL DEFAULT 'mp3',
    emotion_scale           NUMERIC NOT NULL DEFAULT 4.0,
    speech_rate             NUMERIC NOT NULL DEFAULT 0.0,
    loudness_rate           NUMERIC NOT NULL DEFAULT 0.0,
    speaker_mappings_json   TEXT NOT NULL DEFAULT '[]',
    created_at              TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS public.speech_syntheses (
    synthesis_id           VARCHAR(32) PRIMARY KEY,
    session_id             VARCHAR(32) NOT NULL UNIQUE,
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
    created_at             TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at             TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_speech_syntheses_session_created_at
    ON public.speech_syntheses (session_id, created_at);

CREATE TABLE IF NOT EXISTS public.speech_synthesis_items (
    tts_item_id           VARCHAR(32) PRIMARY KEY,
    synthesis_id          VARCHAR(32) NOT NULL,
    source_item_id        VARCHAR(32) NOT NULL,
    source_seq_start      INTEGER NOT NULL,
    source_seq_end        INTEGER NOT NULL,
    source_seqs           TEXT NOT NULL DEFAULT '[]',
    conversation_speaker  VARCHAR(64),
    provider_speaker_id   VARCHAR(128) NOT NULL,
    content               TEXT NOT NULL,
    plain_text            TEXT NOT NULL,
    cue_texts             TEXT NOT NULL DEFAULT '[]',
    content_hash          VARCHAR(64) NOT NULL,
    duration_ms           INTEGER,
    x_status              SMALLINT NOT NULL DEFAULT 0,
    error_code            VARCHAR(64),
    error_message         TEXT,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_speech_synthesis_items_seq_span
    ON public.speech_synthesis_items (synthesis_id, source_seq_start, source_seq_end);

CREATE UNIQUE INDEX IF NOT EXISTS uq_speech_synthesis_items_source_item
    ON public.speech_synthesis_items (synthesis_id, source_item_id);

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
