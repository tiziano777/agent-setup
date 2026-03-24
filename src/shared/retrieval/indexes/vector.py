"""In-memory dense vector index.

Adapted from the Anthropic course implementation
(anthropic_course/rag/VectorDB/VectorIndex.py) and conforms to the
:class:`BaseIndex` protocol.
"""

from __future__ import annotations

import math
from typing import Any, Callable


class VectorIndex:
    """In-memory brute-force vector search.

    Useful for development and testing without an external database.

    Args:
        distance_metric: ``"cosine"`` or ``"euclidean"``.
        embedding_fn: Callable that maps a string to a float vector.
    """

    def __init__(
        self,
        distance_metric: str = "cosine",
        embedding_fn: Callable[[str], list[float]] | None = None,
    ) -> None:
        if distance_metric not in ("cosine", "euclidean"):
            raise ValueError("distance_metric must be 'cosine' or 'euclidean'")
        self._metric = distance_metric
        self._embedding_fn = embedding_fn
        self.vectors: list[list[float]] = []
        self.documents: list[dict[str, Any]] = []
        self._dim: int | None = None

    # -- distance helpers --------------------------------------------------

    @staticmethod
    def _dot(a: list[float], b: list[float]) -> float:
        return sum(x * y for x, y in zip(a, b))

    @staticmethod
    def _mag(v: list[float]) -> float:
        return math.sqrt(sum(x * x for x in v))

    def _cosine_dist(self, a: list[float], b: list[float]) -> float:
        ma, mb = self._mag(a), self._mag(b)
        if ma == 0 or mb == 0:
            return 1.0
        sim = max(-1.0, min(1.0, self._dot(a, b) / (ma * mb)))
        return 1.0 - sim

    @staticmethod
    def _euclidean_dist(a: list[float], b: list[float]) -> float:
        return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))

    # -- BaseIndex protocol ------------------------------------------------

    def add_document(self, document: dict[str, Any]) -> None:
        if self._embedding_fn is None:
            raise ValueError("embedding_fn required for add_document")
        content = document.get("content", "")
        if not isinstance(content, str):
            raise TypeError("Document 'content' must be a string.")
        vec = self._embedding_fn(content)
        self._store(vec, document)

    def add_documents(self, documents: list[dict[str, Any]]) -> None:
        for doc in documents:
            self.add_document(doc)

    def search(
        self, query: Any, k: int = 5
    ) -> list[tuple[dict[str, Any], float]]:
        if not self.vectors:
            return []

        if isinstance(query, str):
            if self._embedding_fn is None:
                raise ValueError("embedding_fn required for string queries")
            qvec = self._embedding_fn(query)
        elif isinstance(query, list):
            qvec = query
        else:
            raise TypeError("Query must be a string or list of floats.")

        dist_fn = self._cosine_dist if self._metric == "cosine" else self._euclidean_dist
        scored = [(dist_fn(qvec, v), self.documents[i]) for i, v in enumerate(self.vectors)]
        scored.sort(key=lambda x: x[0])
        return [(doc, dist) for dist, doc in scored[:k]]

    # -- internal ----------------------------------------------------------

    def _store(self, vector: list[float], document: dict[str, Any]) -> None:
        if self._dim is None:
            self._dim = len(vector)
        elif len(vector) != self._dim:
            raise ValueError(
                f"Dimension mismatch: expected {self._dim}, got {len(vector)}"
            )
        self.vectors.append(list(vector))
        self.documents.append(document)

    def __len__(self) -> int:
        return len(self.vectors)
