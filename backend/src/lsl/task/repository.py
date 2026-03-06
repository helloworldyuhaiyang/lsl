from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg import sql

if TYPE_CHECKING:
    from psycopg_pool import ConnectionPool


class TaskRepository:
    def __init__(self, pool: "ConnectionPool") -> None:
        self._pool = pool

    def create_task(
        self,
        *,
        task_id: str,
        object_key: str,
        audio_url: str,
        language: Optional[str],
        provider: str,
    ) -> None:
        query = sql.SQL("""
            INSERT INTO public.tasks (
                task_id,
                object_key,
                audio_url,
                x_status,
                x_language,
                x_provider
            )
            VALUES (%s, %s, %s, %s, %s, %s)
        """ )
        try:
            with self._pool.connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        query,
                        (task_id, object_key, audio_url, 0, language, provider),
                    )
        except psycopg.Error as exc:  # pragma: no cover
            raise RuntimeError(f"Failed to create task: {exc}") from exc

    def get_task_by_id(self, task_id: str) -> dict[str, Any] | None:
        query = sql.SQL("""
            SELECT
                task_id,
                object_key,
                audio_url,
                x_duration_ms AS duration_ms,
                x_status AS status,
                x_language AS language,
                x_provider AS provider,
                x_provider_request_id AS provider_request_id,
                x_provider_resource_id AS provider_resource_id,
                x_tt_logid,
                x_provider_status_code AS provider_status_code,
                x_provider_message AS provider_message,
                error_code,
                error_message,
                poll_count,
                last_polled_at,
                next_poll_at,
                created_at,
                updated_at
            FROM public.tasks
            WHERE task_id = %s
            LIMIT 1
        """ )
        try:
            with self._pool.connection() as conn:
                with conn.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(query, (task_id,))
                    row = cursor.fetchone()
                    return dict(row) if row else None
        except psycopg.Error as exc:  # pragma: no cover
            raise RuntimeError(f"Failed to query task by id: {exc}") from exc

    def get_task_by_object_key(self, object_key: str) -> dict[str, Any] | None:
        query = sql.SQL("""
            SELECT
                task_id,
                object_key,
                audio_url,
                x_duration_ms AS duration_ms,
                x_status AS status,
                x_language AS language,
                x_provider AS provider,
                x_provider_request_id AS provider_request_id,
                x_provider_resource_id AS provider_resource_id,
                x_tt_logid,
                x_provider_status_code AS provider_status_code,
                x_provider_message AS provider_message,
                error_code,
                error_message,
                poll_count,
                last_polled_at,
                next_poll_at,
                created_at,
                updated_at
            FROM public.tasks
            WHERE object_key = %s
            LIMIT 1
        """ )
        try:
            with self._pool.connection() as conn:
                with conn.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(query, (object_key,))
                    row = cursor.fetchone()
                    return dict(row) if row else None
        except psycopg.Error as exc:  # pragma: no cover
            raise RuntimeError(f"Failed to query task by object_key: {exc}") from exc

    def list_tasks_by_ids(self, *, task_ids: list[str]) -> list[dict[str, Any]]:
        if not task_ids:
            return []

        query = sql.SQL("""
            SELECT
                task_id,
                object_key,
                audio_url,
                x_duration_ms AS duration_ms,
                x_status AS status,
                x_language AS language,
                x_provider AS provider,
                error_code,
                error_message,
                created_at,
                updated_at
            FROM public.tasks
            WHERE task_id::text = ANY(%s)
        """ )
        try:
            with self._pool.connection() as conn:
                with conn.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(query, (task_ids,))
                    rows = cursor.fetchall()
                    return [dict(row) for row in rows]
        except psycopg.Error as exc:  # pragma: no cover
            raise RuntimeError(f"Failed to query tasks by ids: {exc}") from exc

    def list_tasks(
        self,
        *,
        limit: int,
        status: int | None = None,
        category: str | None = None,
        entity_id: str | None = None,
    ) -> list[dict[str, Any]]:
        clauses: list[sql.Composable] = []
        params: list[Any] = []

        if status is not None:
            clauses.append(sql.SQL("x_status = %s"))
            params.append(status)
        if category:
            clauses.append(sql.SQL("split_part(object_key, '/', 1) = %s"))
            params.append(category)
        if entity_id:
            clauses.append(sql.SQL("split_part(object_key, '/', 2) = %s"))
            params.append(entity_id)

        where_clause: sql.Composable = sql.SQL("")
        if clauses:
            where_clause = sql.SQL("WHERE ") + sql.SQL(" AND ").join(clauses)

        # build composable SQL with optional where clause
        base_sql = sql.SQL("""
            SELECT
                task_id,
                object_key,
                audio_url,
                x_duration_ms AS duration_ms,
                x_status AS status,
                x_language AS language,
                x_provider AS provider,
                error_code,
                error_message,
                created_at,
                updated_at
            FROM public.tasks
            {where_sql}
            ORDER BY created_at DESC
            LIMIT %s
        """ )
        query_sql = base_sql.format(where_sql=where_clause)
        params.append(limit)

        try:
            with self._pool.connection() as conn:
                with conn.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(query_sql, tuple(params))
                    rows = cursor.fetchall()
                    return [dict(row) for row in rows]
        except psycopg.Error as exc:  # pragma: no cover
            raise RuntimeError(f"Failed to list tasks: {exc}") from exc

    def mark_submitted(
        self,
        *,
        task_id: str,
        provider_request_id: str,
        provider_resource_id: str | None,
        x_tt_logid: str | None,
        next_poll_at: datetime,
    ) -> None:
        update_sql = sql.SQL("""
            UPDATE public.tasks
            SET
                x_status = 1,
                x_provider_request_id = %s,
                x_provider_resource_id = %s,
                x_tt_logid = %s,
                x_duration_ms = NULL,
                x_provider_status_code = NULL,
                x_provider_message = NULL,
                error_code = NULL,
                error_message = NULL,
                poll_count = 0,
                last_polled_at = NULL,
                next_poll_at = %s
            WHERE task_id = %s
        """ )
        try:
            with self._pool.connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        update_sql,
                        (
                            provider_request_id,
                            provider_resource_id,
                            x_tt_logid,
                            next_poll_at,
                            task_id,
                        ),
                    )
        except psycopg.Error as exc:  # pragma: no cover
            raise RuntimeError(f"Failed to mark task as submitted: {exc}") from exc

    def mark_processing(
        self,
        *,
        task_id: str,
        provider_status_code: str | None,
        provider_message: str | None,
        x_tt_logid: str | None,
        next_poll_at: datetime,
    ) -> None:
        update_sql = sql.SQL("""
            UPDATE public.tasks
            SET
                x_status = 1,
                x_provider_status_code = %s,
                x_provider_message = %s,
                x_tt_logid = COALESCE(%s, x_tt_logid),
                poll_count = poll_count + 1,
                last_polled_at = NOW(),
                next_poll_at = %s
            WHERE task_id = %s
        """ )
        try:
            with self._pool.connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        update_sql,
                        (
                            provider_status_code,
                            provider_message,
                            x_tt_logid,
                            next_poll_at,
                            task_id,
                        ),
                    )
        except psycopg.Error as exc:  # pragma: no cover
            raise RuntimeError(f"Failed to mark task as processing: {exc}") from exc

    def mark_failed(
        self,
        *,
        task_id: str,
        error_code: str | None,
        error_message: str | None,
        provider_status_code: str | None,
        provider_message: str | None,
        x_tt_logid: str | None,
    ) -> None:
        update_sql = sql.SQL("""
            UPDATE public.tasks
            SET
                x_status = 4,
                error_code = %s,
                error_message = %s,
                x_provider_status_code = %s,
                x_provider_message = %s,
                x_tt_logid = COALESCE(%s, x_tt_logid),
                x_duration_ms = NULL,
                last_polled_at = NOW(),
                next_poll_at = NULL
            WHERE task_id = %s
        """ )
        try:
            with self._pool.connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        update_sql,
                        (
                            error_code,
                            error_message,
                            provider_status_code,
                            provider_message,
                            x_tt_logid,
                            task_id,
                        ),
                    )
        except psycopg.Error as exc:  # pragma: no cover
            raise RuntimeError(f"Failed to mark task as failed: {exc}") from exc

    def reset_for_retry(self, *, task_id: str) -> None:
        query = sql.SQL("""
            UPDATE public.tasks
            SET
                x_status = 0,
                x_provider_request_id = NULL,
                x_provider_resource_id = NULL,
                x_provider_status_code = NULL,
                x_provider_message = NULL,
                x_duration_ms = NULL,
                error_code = NULL,
                error_message = NULL,
                poll_count = 0,
                last_polled_at = NULL,
                next_poll_at = NULL
            WHERE task_id = %s
        """ )
        try:
            with self._pool.connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query, (task_id,))
        except psycopg.Error as exc:  # pragma: no cover
            raise RuntimeError(f"Failed to reset task for retry: {exc}") from exc

    def mark_completed_with_result(
        self,
        *,
        task_id: str,
        provider: str,
        duration_ms: int | None,
        full_text: str | None,
        raw_result_json: dict[str, Any],
        utterances: list[dict[str, Any]],
        provider_status_code: str | None,
        provider_message: str | None,
        x_tt_logid: str | None,
    ) -> None:
        upsert_result_sql = sql.SQL("""
            INSERT INTO public.asr_results (
                task_id,
                x_provider,
                duration_ms,
                x_full_text,
                raw_result_json
            )
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (task_id) DO UPDATE SET
                x_provider = EXCLUDED.x_provider,
                duration_ms = EXCLUDED.duration_ms,
                x_full_text = EXCLUDED.x_full_text,
                raw_result_json = EXCLUDED.raw_result_json
        """ )
        delete_utterances_sql = sql.SQL("DELETE FROM public.asr_utterances WHERE task_id = %s")
        insert_utterance_sql = sql.SQL("""
            INSERT INTO public.asr_utterances (
                task_id,
                seq,
                x_text,
                speaker,
                start_time,
                end_time,
                additions_json
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """ )
        update_task_sql = sql.SQL("""
            UPDATE public.tasks
            SET
                x_status = 3,
                x_duration_ms = %s,
                x_provider_status_code = %s,
                x_provider_message = %s,
                x_tt_logid = COALESCE(%s, x_tt_logid),
                error_code = NULL,
                error_message = NULL,
                last_polled_at = NOW(),
                next_poll_at = NULL
            WHERE task_id = %s
        """ )
        try:
            with self._pool.connection() as conn:
                with conn.transaction():
                    with conn.cursor() as cursor:
                        cursor.execute(
                            upsert_result_sql,
                            (
                                task_id,
                                provider,
                                duration_ms,
                                full_text,
                                Jsonb(raw_result_json),
                            ),
                        )
                        cursor.execute(delete_utterances_sql, (task_id,))
                        for item in utterances:
                            cursor.execute(
                                insert_utterance_sql,
                                (
                                    task_id,
                                    item["seq"],
                                    item["text"],
                                    item.get("speaker"),
                                    item["start_time"],
                                    item["end_time"],
                                    Jsonb(item.get("additions", {})),
                                ),
                            )
                        cursor.execute(
                            update_task_sql,
                            (
                                duration_ms,
                                provider_status_code,
                                provider_message,
                                x_tt_logid,
                                task_id,
                            ),
                        )
        except psycopg.Error as exc:  # pragma: no cover
            raise RuntimeError(f"Failed to persist ASR result: {exc}") from exc

    def get_transcript(self, *, task_id: str) -> dict[str, Any] | None:
        result_sql = sql.SQL("""
            SELECT
                duration_ms,
                x_full_text AS full_text,
                raw_result_json
            FROM public.asr_results
            WHERE task_id = %s
            LIMIT 1
        """ )
        utterance_sql = sql.SQL("""
            SELECT
                seq,
                x_text AS text,
                speaker,
                start_time,
                end_time,
                additions_json
            FROM public.asr_utterances
            WHERE task_id = %s
            ORDER BY seq ASC
        """ )
        try:
            with self._pool.connection() as conn:
                with conn.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(result_sql, (task_id,))
                    row = cursor.fetchone()
                    if row is None:
                        return None
                    result = dict(row)
                    cursor.execute(utterance_sql, (task_id,))
                    utterances = cursor.fetchall()
                    result["utterances"] = [dict(item) for item in utterances]
                    return result
        except psycopg.Error as exc:  # pragma: no cover
            raise RuntimeError(f"Failed to fetch transcript: {exc}") from exc
