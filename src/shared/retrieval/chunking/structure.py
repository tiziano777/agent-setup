"""Structure-based chunker (splits on headings)."""

from __future__ import annotations

import re

from src.shared.retrieval.chunking.base import BaseChunker


class StructureChunker(BaseChunker):
    """Split text on structural boundaries such as Markdown headings.

    Works best with well-formatted documents that use heading hierarchy.

    Args:
        pattern: Regex pattern used to split the document.
            Defaults to splitting on Markdown ``##`` headings.
    """

    DEFAULT_PATTERN = r"\n## "

    def __init__(self, pattern: str = DEFAULT_PATTERN) -> None:
        self._pattern = pattern

    def chunk(self, text: str) -> list[str]:
        parts = re.split(self._pattern, text)
        return [p.strip() for p in parts if p.strip()]
