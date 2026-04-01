"""PostgreSQL connection pool for the autoresearch schema.

Follows the psycopg3 + ConnectionPool pattern from
``src.shared.retrieval.vectorstores.pgvector.PgVectorStore``.
"""

from __future__ import annotations

import os
from pathlib import Path


class PostgresConnector:
    """Manages a lazy psycopg3 connection pool for the autoresearch schema."""

    def __init__(
        self,
        connection_uri: str | None = None,
        schema: str = "autoresearch",
    ) -> None:
        self._uri = connection_uri or os.getenv(
            "PGVECTOR_URI",
            "postgresql://postgres:postgres@localhost:5433/vectors",
        )
        self._schema = schema
        self._pool = None  # lazy

    def _get_pool(self):
        if self._pool is not None:
            return self._pool
        from psycopg_pool import ConnectionPool

        self._pool = ConnectionPool(conninfo=self._uri, min_size=1, max_size=5)
        return self._pool

    def execute(self, sql: str, params: tuple = ()) -> list[tuple]:
        """Execute SQL and return rows (if any)."""
        pool = self._get_pool()
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                if cur.description is not None:
                    return cur.fetchall()
                return []

    def execute_returning(
        self, sql: str, params: tuple = ()
    ) -> tuple[list[tuple], list[str]]:
        """Execute SQL and return ``(rows, column_names)``."""
        pool = self._get_pool()
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                columns = [desc[0] for desc in cur.description] if cur.description else []
                rows = cur.fetchall() if cur.description else []
                return rows, columns

    def apply_schema(self) -> None:
        """Ensure the autoresearch schema and all tables exist."""
        schema_path = Path(__file__).parent / "schema.sql"
        sql = schema_path.read_text()
        pool = self._get_pool()
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)

    def close(self) -> None:
        """Shut down the connection pool."""
        if self._pool is not None:
            self._pool.close()
            self._pool = None
