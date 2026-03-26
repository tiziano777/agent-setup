"""PostgreSQL + pgvector vector store implementation."""

from __future__ import annotations

import json
import os
from typing import Any

from src.shared.retrieval.vectorstores.base import BaseVectorStore, Document, SearchResult


class PgVectorStore(BaseVectorStore):
    """Vector store backed by PostgreSQL with the pgvector extension.

    Auto-creates the ``vector`` extension and a table per collection.
    Supports HNSW and IVFFlat index types.

    Args:
        connection_uri: PostgreSQL connection string.
        index_type: Index type to create (``"hnsw"`` or ``"ivfflat"``).
            Set to ``None`` to skip index creation (flat scan).
        schema: PostgreSQL schema to create tables in.  Defaults to
            ``PGVECTOR_SCHEMA`` env var, or ``"public"`` if unset.
    """

    def __init__(
        self,
        connection_uri: str = "postgresql://postgres:postgres@localhost:5433/vectors",
        index_type: str | None = "hnsw",
        schema: str | None = None,
    ) -> None:
        self._uri = connection_uri
        self._index_type = index_type
        self._schema = schema or os.getenv("PGVECTOR_SCHEMA", "public")
        self._pool = None  # lazy
        self._table: str = "documents"

    # -- lazy connection pool ----------------------------------------------

    def _get_pool(self):
        if self._pool is not None:
            return self._pool
        from psycopg_pool import ConnectionPool

        self._pool = ConnectionPool(conninfo=self._uri, min_size=1, max_size=5)
        return self._pool

    # -- helpers -----------------------------------------------------------

    def _execute(self, sql: str, params: tuple = ()) -> list[tuple]:
        pool = self._get_pool()
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                if cur.description is not None:
                    return cur.fetchall()
                return []

    def _vector_literal(self, vec: list[float]) -> str:
        """Format a float list as a pgvector literal ``'[1,2,3]'``."""
        return "[" + ",".join(str(v) for v in vec) + "]"

    # -- BaseVectorStore interface -----------------------------------------

    def ensure_collection(self, name: str, dims: int) -> None:
        qualified = f"{self._schema}.{name}" if self._schema != "public" else name
        self._table = qualified
        pool = self._get_pool()
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
                if self._schema != "public":
                    cur.execute(f"CREATE SCHEMA IF NOT EXISTS {self._schema}")
                cur.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS {qualified} (
                        id TEXT PRIMARY KEY,
                        content TEXT NOT NULL,
                        embedding vector({dims}),
                        metadata JSONB DEFAULT '{{}}'::jsonb
                    )
                    """
                )
                if self._index_type == "hnsw":
                    cur.execute(
                        f"""
                        CREATE INDEX IF NOT EXISTS idx_{name}_hnsw
                        ON {qualified}
                        USING hnsw (embedding vector_cosine_ops)
                        """
                    )
                elif self._index_type == "ivfflat":
                    cur.execute(
                        f"""
                        CREATE INDEX IF NOT EXISTS idx_{name}_ivfflat
                        ON {qualified}
                        USING ivfflat (embedding vector_cosine_ops)
                        WITH (lists = 100)
                        """
                    )

    def upsert(self, documents: list[Document]) -> None:
        pool = self._get_pool()
        with pool.connection() as conn:
            with conn.cursor() as cur:
                for doc in documents:
                    if doc.embedding is None:
                        raise ValueError(f"Document {doc.id!r} has no embedding set")
                    cur.execute(
                        f"""
                        INSERT INTO {self._table} (id, content, embedding, metadata)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (id) DO UPDATE SET
                            content = EXCLUDED.content,
                            embedding = EXCLUDED.embedding,
                            metadata = EXCLUDED.metadata
                        """,
                        (
                            doc.id,
                            doc.content,
                            self._vector_literal(doc.embedding),
                            json.dumps(doc.metadata),
                        ),
                    )

    def search(
        self,
        query_vector: list[float],
        k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        where_clause = ""
        params: list[Any] = [self._vector_literal(query_vector), k]

        if filters:
            conditions = []
            for key, val in filters.items():
                params.append(json.dumps(val))
                conditions.append(f"metadata->>'{key}' = %s")
            where_clause = "WHERE " + " AND ".join(conditions)

        rows = self._execute(
            f"""
            SELECT id, content, metadata,
                   embedding <=> %s AS distance
            FROM {self._table}
            {where_clause}
            ORDER BY distance
            LIMIT %s
            """,
            tuple(params),
        )

        results: list[SearchResult] = []
        for row in rows:
            doc_id, content, meta, distance = row
            if isinstance(meta, str):
                meta = json.loads(meta)
            doc = Document(id=doc_id, content=content, metadata=meta or {})
            # Convert cosine distance to similarity score.
            results.append(SearchResult(document=doc, score=1.0 - distance))
        return results

    def delete(self, ids: list[str]) -> None:
        if not ids:
            return
        placeholders = ",".join(["%s"] * len(ids))
        self._execute(
            f"DELETE FROM {self._table} WHERE id IN ({placeholders})",
            tuple(ids),
        )
