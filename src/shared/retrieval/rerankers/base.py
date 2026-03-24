"""Abstract base class for rerankers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.shared.retrieval.vectorstores.base import Document


class BaseReranker(ABC):
    """Interface that all reranker implementations must satisfy."""

    @abstractmethod
    def rerank(self, query: str, documents: list[Document], k: int) -> list[Document]:
        """Return the top *k* documents reordered by relevance to *query*."""
