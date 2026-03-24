"""Abstract base class for embedding providers."""

from abc import ABC, abstractmethod


class BaseEmbedding(ABC):
    """Interface that all embedding implementations must satisfy."""

    @abstractmethod
    def embed(self, text: str) -> list[float]:
        """Embed a single piece of text and return a float vector."""

    @abstractmethod
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts at once. Implementations should optimize for batch."""

    @property
    @abstractmethod
    def dimensions(self) -> int:
        """Return the dimensionality of the produced vectors."""
