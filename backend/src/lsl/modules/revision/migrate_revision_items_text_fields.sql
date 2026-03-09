BEGIN;

ALTER TABLE public.utterances_revision_items
    RENAME COLUMN issue_tags_json TO issue_tags;

ALTER TABLE public.utterances_revision_items
    ALTER COLUMN issue_tags DROP DEFAULT,
    ALTER COLUMN issue_tags TYPE TEXT
    USING (
        CASE
            WHEN issue_tags IS NULL OR issue_tags = '[]'::jsonb THEN ''
            ELSE array_to_string(
                ARRAY(SELECT jsonb_array_elements_text(issue_tags)),
                ', '
            )
        END
    ),
    ALTER COLUMN issue_tags SET DEFAULT '',
    ALTER COLUMN issue_tags SET NOT NULL;

ALTER TABLE public.utterances_revision_items
    RENAME COLUMN explanations_json TO explanations;

ALTER TABLE public.utterances_revision_items
    ALTER COLUMN explanations DROP DEFAULT,
    ALTER COLUMN explanations TYPE TEXT
    USING (
        CASE
            WHEN explanations IS NULL OR explanations = '[]'::jsonb THEN ''
            ELSE array_to_string(
                ARRAY(SELECT jsonb_array_elements_text(explanations)),
                ' '
            )
        END
    ),
    ALTER COLUMN explanations SET DEFAULT '',
    ALTER COLUMN explanations SET NOT NULL;

COMMIT;
