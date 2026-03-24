"""Qdrant vector store implementation."""

from __future__ import annotations

import uuid
from typing import Any

from src.shared.retrieval.vectorstores.base import BaseVectorStore, Document, SearchResult


class QdrantVectorStore(BaseVectorStore):
    """Vector store backed by Qdrant.

    Supports three connection modes:

    * **In-memory** – ``url=":memory:"`` (no persistence, good for tests).
    * **Local file** – ``url="./qdrant_data"`` (embedded, no server).
    * **Remote server** – ``url="http://localhost:6333"`` (default).

    Args:
        url: Qdrant server URL or special path for embedded mode.
        api_key: Optional API key for Qdrant Cloud.
        collection_name: Default collection name.
        distance: Distance metric (``"cosine"``, ``"euclid"``, ``"dot"``).
    """

    def __init__(
        self,
        url: str = "http://localhost:6333",
        api_key: str | None = None,
        collection_name: str = "default",
        distance: str = "cosine",
    ) -> None:
        self._url = url
        self._api_key = api_key
        self._collection_name = collection_name
        self._distance = distance
        self._client = None  # lazy

    # -- lazy client -------------------------------------------------------

    def _get_client(self):
        if self._client is not None:
            return self._client
        from qdrant_client import QdrantClient

        if self._url == ":memory:":
            self._client = QdrantClient(location=":memory:")
        elif self._url.startswith("http"):
            self._client = QdrantClient(url=self._url, api_key=self._api_key)
        else:
            # Treat as local file path for embedded mode.
            self._client = QdrantClient(path=self._url)
        return self._client

    # -- distance mapping --------------------------------------------------

    @staticmethod
    def _qdrant_distance(name: str):
        from qdrant_client.models import Distance

        mapping = {
            "cosine": Distance.COSINE,
            "euclid": Distance.EUCLID,
            "dot": Distance.DOT,
        }
        result = mapping.get(name)
        if result is None:
            raise ValueError(f"Unknown distance metric: {name!r}. Choose from {list(mapping)}")
        return result

    # -- BaseVectorStore interface -----------------------------------------

    def ensure_collection(self, name: str, dims: int) -> None:
        from qdrant_client.models import VectorParams

        client = self._get_client()
        self._collection_name = name
        collections = [c.name for c in client.get_collections().collections]
        if name not in collections:
            client.create_collection(
                collection_name=name,
                vectors_config=VectorParams(
                    size=dims,
                    distance=self._qdrant_distance(self._distance),
                ),
            )

    def upsert(self, documents: list[Document]) -> None:
        from qdrant_client.models import PointStruct

        client = self._get_client()
        points = []
        for doc in documents:
            if doc.embedding is None:
                raise ValueError(f"Document {doc.id!r} has no embedding set")
            points.append(
                PointStruct(
                    id=doc.id,
                    vector=doc.embedding,
                    payload={"content": doc.content, **doc.metadata},
                )
            )
        client.upsert(collection_name=self._collection_name, points=points)

    def search(
        self,
        query_vector: list[float],
        k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        client = self._get_client()

        query_filter = None
        if filters:
            from qdrant_client.models import Filter, FieldCondition, MatchValue

            conditions = [
                FieldCondition(key=key, match=MatchValue(value=val))
                for key, val in filters.items()
            ]
            query_filter = Filter(must=conditions)

        hits = client.search(
            collection_name=self._collection_name,
            query_vector=query_vector,
            limit=k,
            query_filter=query_filter,
        )

        results: list[SearchResult] = []
        for hit in hits:
            payload = hit.payload or {}
            content = payload.pop("content", "")
            doc = Document(
                id=str(hit.id),
                content=content,
                metadata=payload,
            )
            results.append(SearchResult(document=doc, score=hit.score))
        return results

    def delete(self, ids: list[str]) -> None:
        from qdrant_client.models import PointIdsList

        client = self._get_client()
        client.delete(
            collection_name=self._collection_name,
            points_selector=PointIdsList(points=ids),
        )
