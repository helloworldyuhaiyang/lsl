# Translation Module

Shared translation domain for transcript and revision text.

## Responsibilities

- Store translation batches in `translation_translations`.
- Store per-source-line translation state in `translation_items`.
- Generate translations through async `translation_generation` jobs.
- Reuse the same API from Session Detail, Revise, and Listening pages.

## API

- `POST /translations` creates or refreshes a translation batch.
- `POST /translations/items/translate` synchronously translates one source item.
- `GET /translations?source_type={type}&source_entity_id={id}` returns the current batch.

Supported `source_type` values:

- `transcript`: source items come from transcript utterances.
- `revision`: source items come from `draft_text`, falling back to `suggested_text`.

## State Rules

- Parent `generating` means an active job is still producing item translations.
- Parent `partial` means no active job is running and some items still need attention.
- Item `stale` means source text changed after the last completed translation.
- A read refresh may update source hashes, but it must not turn an active job into `partial`.
- Batch regeneration should be started with `force=true` after the caller has saved the latest source text.
- Single-item refresh should use the synchronous item endpoint instead of creating a job.

## Boundaries

- API routes only map HTTP parameters and errors.
- `service.py` owns orchestration and job decisions.
- `repo.py` owns persistence and aggregate status calculation.
- Provider-specific LLM code stays in `provider.py`.
