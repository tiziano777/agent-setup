"""Sentence-based chunker with overlap."""

from __future__ import annotations

import re

from src.shared.retrieval.chunking.base import BaseChunker


class SentenceChunker(BaseChunker):
    """Split text on sentence boundaries and group into fixed-size chunks.

    Maintains sentence integrity while providing overlap for context
    continuity across chunk boundaries.

    Args:
        max_sentences: Maximum number of sentences per chunk.
        overlap_sentences: Number of trailing sentences repeated in the next chunk.
    """

    _SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")

    def __init__(self, max_sentences: int = 5, overlap_sentences: int = 1) -> None:
        if overlap_sentences >= max_sentences:
            raise ValueError("overlap_sentences must be smaller than max_sentences")
        self._max = max_sentences
        self._overlap = overlap_sentences

    def chunk(self, text: str) -> list[str]:
        sentences = self._SENTENCE_RE.split(text)
        sentences = [s for s in sentences if s.strip()]
        if not sentences:
            return []

        chunks: list[str] = []
        start = 0
        step = self._max - self._overlap

        while start < len(sentences):
            end = min(start + self._max, len(sentences))
            chunks.append(" ".join(sentences[start:end]))
            start += step

        return chunks
