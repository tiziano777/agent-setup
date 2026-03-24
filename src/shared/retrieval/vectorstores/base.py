"""Abstract base class for vector stores and shared data models."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class Document:
    """A document that can be stored in a vector store."""

    id: str
    content: str
    embedding: list[float] | None = None
    metadata: dict = field(default_factory=dict)


@dataclass
class SearchResult:
    """A single result returned from a vector store search."""

    document: Document
    score: float


class BaseVectorStore(ABC):
    """Interface that all vector store implementations must satisfy."""

    @abstractmethod
    def ensure_collection(self, name: str, dims: int) -> None:
        """Create or verify a collection/table exists with the given dimensionality."""

    @abstractmethod
    def upsert(self, documents: list[Document]) -> None:
        """Insert or update documents. Each document must have an embedding set."""

    @abstractmethod
    def search(
        self,
        query_vector: list[float],
        k: int = 5,
        filters: dict | None = None,
    ) -> list[SearchResult]:
        """Return the k most similar documents to the query vector."""

    @abstractmethod
    def delete(self, ids: list[str]) -> None:
        """Delete documents by their IDs."""
