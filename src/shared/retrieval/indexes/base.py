"""Protocol (structural typing) for in-memory search indexes.

Mirrors the SearchIndex protocol from the Anthropic course so that
BM25Index and VectorIndex can be used interchangeably in the pipeline.
"""

from __future__ import annotations

from typing import Any, Protocol


class BaseIndex(Protocol):
    """Structural interface for search indexes."""

    def add_document(self, document: dict[str, Any]) -> None: ...

    def add_documents(self, documents: list[dict[str, Any]]) -> None: ...

    def search(self, query: Any, k: int = 5) -> list[tuple[dict[str, Any], float]]: ...
