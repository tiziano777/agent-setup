"""Abstract base class for text chunking strategies."""

from abc import ABC, abstractmethod


class BaseChunker(ABC):
    """Interface that all chunking implementations must satisfy."""

    @abstractmethod
    def chunk(self, text: str) -> list[str]:
        """Split *text* into a list of chunk strings."""
