"""Retrieval pipeline with multi-index search and Reciprocal Rank Fusion.

Adapted from the Anthropic course Retriever
(anthropic_course/rag/retriver/MultipleIndex.py).
"""

from __future__ import annotations

import random
import string
from typing import Any

from src.shared.retrieval.rerankers.base import BaseReranker
from src.shared.retrieval.vectorstores.base import Document


class RetrieverPipeline:
    """Orchestrates search across multiple indexes and fuses results.

    Workflow:
        1. Query each index for ``k * fan_out`` candidates.
        2. Merge results with **Reciprocal Rank Fusion** (RRF).
        3. Optionally rerank the top results with a :class:`BaseReranker`.
        4. Return the final top-*k* documents.

    Args:
        indexes: One or more objects satisfying the :class:`BaseIndex` protocol.
        reranker: Optional reranker applied after RRF fusion.
        k_rrf: RRF smoothing constant (higher = less weight on top ranks).
        fan_out: Multiplier for per-index retrieval (``k * fan_out`` per index).
    """

    def __init__(
        self,
        indexes: list[Any],
        reranker: BaseReranker | None = None,
        k_rrf: int = 60,
        fan_out: int = 5,
    ) -> None:
        if not indexes:
            raise ValueError("At least one index must be provided")
        self._indexes = list(indexes)
        self._reranker = reranker
        self._k_rrf = k_rrf
        self._fan_out = fan_out

    # -- document management -----------------------------------------------

    def add_document(self, document: dict[str, Any]) -> None:
        """Add a single document to all indexes."""
        if "id" not in document:
            document["id"] = _random_id()
        for index in self._indexes:
            index.add_document(document)

    def add_documents(self, documents: list[dict[str, Any]]) -> None:
        """Add multiple documents to all indexes."""
        for doc in documents:
            if "id" not in doc:
                doc["id"] = _random_id()
        for index in self._indexes:
            index.add_documents(documents)

    # -- search ------------------------------------------------------------

    def search(self, query: str, k: int = 5) -> list[dict[str, Any]]:
        """Search all indexes, fuse with RRF, optionally rerank, return top-*k*.

        Returns:
            A list of document dicts ordered by decreasing relevance.
        """
        per_index_k = k * self._fan_out

        # Collect ranked results from every index.
        all_results: list[list[tuple[dict[str, Any], float]]] = [
            index.search(query, k=per_index_k) for index in self._indexes
        ]

        # --- Reciprocal Rank Fusion ---
        doc_ranks: dict[str, dict[str, Any]] = {}

        for idx, results in enumerate(all_results):
            for rank, (doc, _score) in enumerate(results):
                doc_id = doc.get("id") or str(id(doc))
                if doc_id not in doc_ranks:
                    doc_ranks[doc_id] = {
                        "doc": doc,
                        "ranks": [float("inf")] * len(self._indexes),
                    }
                doc_ranks[doc_id]["ranks"][idx] = rank + 1

        def rrf_score(ranks: list[float]) -> float:
            return sum(1.0 / (self._k_rrf + r) for r in ranks if r != float("inf"))

        scored: list[tuple[dict[str, Any], float]] = [
            (entry["doc"], rrf_score(entry["ranks"]))
            for entry in doc_ranks.values()
        ]
        scored = [(d, s) for d, s in scored if s > 0]
        scored.sort(key=lambda x: x[1], reverse=True)

        top_docs = [doc for doc, _ in scored[:k]]

        # --- Optional reranking ---
        if self._reranker is not None and top_docs:
            documents = [
                Document(
                    id=doc.get("id", _random_id()),
                    content=doc.get("content", ""),
                    metadata={k: v for k, v in doc.items() if k not in ("id", "content")},
                )
                for doc in top_docs
            ]
            reranked = self._reranker.rerank(query, documents, k)
            top_docs = [
                {"id": d.id, "content": d.content, **d.metadata}
                for d in reranked
            ]

        return top_docs


def _random_id(length: int = 8) -> str:
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))
