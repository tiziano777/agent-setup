"""Abstract base class for multimodal document parsers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from src.shared.retrieval.multimodal.models import MultimodalContent


class BaseMultimodalParser(ABC):
    """Interface that all multimodal parser implementations must satisfy.

    Unlike :class:`BaseChunker` which operates on text strings, multimodal
    parsers operate on file paths and return structured
    :class:`MultimodalContent` elements preserving images, tables, and
    equations alongside text.
    """

    @abstractmethod
    async def parse(
        self,
        file_path: str | Path,
        output_dir: str | Path | None = None,
        **kwargs,
    ) -> list[MultimodalContent]:
        """Parse a single file into structured multimodal content elements."""

    @abstractmethod
    async def parse_batch(
        self,
        folder_path: str | Path,
        output_dir: str | Path | None = None,
        file_extensions: list[str] | None = None,
        recursive: bool = True,
        max_workers: int = 4,
        **kwargs,
    ) -> dict[str, list[MultimodalContent]]:
        """Parse all matching files in a folder.

        Returns:
            Mapping of ``{file_path: content_list}`` for each successfully
            parsed file.
        """

    @property
    @abstractmethod
    def supported_extensions(self) -> list[str]:
        """File extensions this parser can handle."""
