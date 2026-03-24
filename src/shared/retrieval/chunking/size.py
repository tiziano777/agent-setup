"""Size-based chunker with character overlap."""

from __future__ import annotations

from src.shared.retrieval.chunking.base import BaseChunker


class SizeChunker(BaseChunker):
    """Split text into fixed-size character chunks with optional overlap.

    This is the most reliable strategy and works with any document type.

    Args:
        chunk_size: Maximum number of characters per chunk.
        chunk_overlap: Number of trailing characters to repeat in the next chunk.
    """

    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50) -> None:
        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap

    def chunk(self, text: str) -> list[str]:
        chunks: list[str] = []
        start = 0
        while start < len(text):
            end = min(start + self._chunk_size, len(text))
            chunks.append(text[start:end])
            if end >= len(text):
                break
            start = end - self._chunk_overlap
        return chunks
