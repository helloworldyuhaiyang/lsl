from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

import psycopg
from psycopg.rows import dict_row

if TYPE_CHECKING:
    from psycopg_pool import ConnectionPool


class AssetRepository:
    def __init__(self, pool: "ConnectionPool") -> None:
        self._pool = pool

    def upsert_completed_upload(
        self,
        *,
        object_key: str,
        category: str,
        entity_id: str,
        filename: Optional[str],
        content_type: Optional[str],
        file_size: Optional[int],
        etag: Optional[str],
        storage_provider: str,
        upload_status: int,
    ) -> None:
        sql = """
            INSERT INTO public.assets (
                object_key,
                category,
                entity_id,
                filename,
                content_type,
                file_size,
                etag,
                storage_provider,
                upload_status
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (object_key) DO UPDATE SET
                category = EXCLUDED.category,
                entity_id = EXCLUDED.entity_id,
                filename = COALESCE(EXCLUDED.filename, public.assets.filename),
                content_type = COALESCE(EXCLUDED.content_type, public.assets.content_type),
                file_size = COALESCE(EXCLUDED.file_size, public.assets.file_size),
                etag = COALESCE(EXCLUDED.etag, public.assets.etag),
                storage_provider = EXCLUDED.storage_provider,
                upload_status = EXCLUDED.upload_status
        """

        try:
            with self._pool.connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        sql,
                        (
                            object_key,
                            category,
                            entity_id,
                            filename,
                            content_type,
                            file_size,
                            etag,
                            storage_provider,
                            upload_status,
                        ),
                    )
        except psycopg.Error as exc:  # pragma: no cover
            raise RuntimeError(f"Failed to persist asset record: {exc}") from exc

    def list_assets(
        self,
        *,
        limit: int,
        category: Optional[str] = None,
        entity_id: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []

        if category:
            clauses.append("category = %s")
            params.append(category)
        if entity_id:
            clauses.append("entity_id = %s")
            params.append(entity_id)

        where_sql = ""
        if clauses:
            where_sql = "WHERE " + " AND ".join(clauses)

        sql = f"""
            SELECT
                object_key,
                category,
                entity_id,
                filename,
                content_type,
                file_size,
                etag,
                upload_status,
                created_at
            FROM public.assets
            {where_sql}
            ORDER BY created_at DESC
            LIMIT %s
        """
        params.append(limit)

        try:
            with self._pool.connection() as conn:
                with conn.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(sql, tuple(params))
                    rows = cursor.fetchall()
                    return [dict(row) for row in rows]
        except psycopg.Error as exc:  # pragma: no cover
            raise RuntimeError(f"Failed to list asset records: {exc}") from exc
