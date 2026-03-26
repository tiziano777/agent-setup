"""RAG-Anything backed multimodal parser.

Uses RAG-Anything's underlying document parser (MinerU, Docling, or
PaddleOCR) to extract structured multimodal content from files.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from src.shared.retrieval.multimodal.models import ContentType, MultimodalContent
from src.shared.retrieval.multimodal.parsers.base import BaseMultimodalParser

logger = logging.getLogger(__name__)

_SUPPORTED_EXTENSIONS = [
    ".pdf",
    ".doc",
    ".docx",
    ".ppt",
    ".pptx",
    ".xls",
    ".xlsx",
    ".png",
    ".jpg",
    ".jpeg",
    ".bmp",
    ".tiff",
    ".tif",
    ".gif",
    ".webp",
    ".txt",
    ".md",
]


class RAGAnythingParser(BaseMultimodalParser):
    """Multimodal parser backed by RAG-Anything's document parsers.

    Lazy-imports ``raganything`` so the file can be imported even when the
    package is not installed.
    """

    def __init__(
        self,
        parser: str = "mineru",
        parse_method: str = "auto",
        enable_image_processing: bool = True,
        enable_table_processing: bool = True,
        enable_equation_processing: bool = True,
    ) -> None:
        self._parser_type = parser
        self._parse_method = parse_method
        self._enable_image = enable_image_processing
        self._enable_table = enable_table_processing
        self._enable_equation = enable_equation_processing
        self._parser_instance: Any = None

    def _get_parser(self) -> Any:
        """Lazy-import and cache the RAG-Anything Parser."""
        if self._parser_instance is None:
            from raganything import Parser

            self._parser_instance = Parser(parser_type=self._parser_type)
        return self._parser_instance

    async def parse(
        self,
        file_path: str | Path,
        output_dir: str | Path | None = None,
        **kwargs: Any,
    ) -> list[MultimodalContent]:
        """Parse a single file via RAG-Anything's parser.

        Returns a list of :class:`MultimodalContent` preserving the document
        structure (text blocks, images, tables, equations).
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        out = Path(output_dir) if output_dir else file_path.parent / "parsed_output"

        parser = self._get_parser()
        raw_content: list[dict[str, Any]] = await asyncio.to_thread(
            parser.parse,
            str(file_path),
            str(out),
            self._parse_method,
        )

        return self._convert_content_list(raw_content)

    async def parse_batch(
        self,
        folder_path: str | Path,
        output_dir: str | Path | None = None,
        file_extensions: list[str] | None = None,
        recursive: bool = True,
        max_workers: int = 4,
        **kwargs: Any,
    ) -> dict[str, list[MultimodalContent]]:
        """Parse all matching files in *folder_path* with concurrency control."""
        folder = Path(folder_path)
        if not folder.is_dir():
            raise NotADirectoryError(f"Not a directory: {folder}")

        exts = set(file_extensions or _SUPPORTED_EXTENSIONS)
        if recursive:
            files = [f for f in folder.rglob("*") if f.suffix.lower() in exts]
        else:
            files = [f for f in folder.iterdir() if f.is_file() and f.suffix.lower() in exts]

        out = Path(output_dir) if output_dir else folder / "parsed_output"

        sem = asyncio.Semaphore(max_workers)
        results: dict[str, list[MultimodalContent]] = {}

        async def _parse_one(fp: Path) -> None:
            async with sem:
                try:
                    content = await self.parse(fp, output_dir=out, **kwargs)
                    results[str(fp)] = content
                except Exception:
                    logger.exception("Failed to parse %s", fp)

        await asyncio.gather(*[_parse_one(f) for f in files])
        return results

    @property
    def supported_extensions(self) -> list[str]:
        return list(_SUPPORTED_EXTENSIONS)

    @staticmethod
    def _convert_content_list(raw_items: list[dict[str, Any]]) -> list[MultimodalContent]:
        """Map RAG-Anything's raw dicts to typed :class:`MultimodalContent`."""
        result: list[MultimodalContent] = []
        for item in raw_items:
            item_type = item.get("type", "text")
            page_idx = item.get("page_idx", 0)

            if item_type == "image":
                result.append(
                    MultimodalContent(
                        content_type=ContentType.IMAGE,
                        page_idx=page_idx,
                        img_path=Path(item["img_path"]) if item.get("img_path") else None,
                        image_caption=item.get("image_caption"),
                        image_footnote=item.get("image_footnote"),
                    )
                )
            elif item_type == "table":
                result.append(
                    MultimodalContent(
                        content_type=ContentType.TABLE,
                        page_idx=page_idx,
                        table_body=item.get("table_body", ""),
                        table_caption=item.get("table_caption"),
                        table_footnote=item.get("table_footnote"),
                    )
                )
            elif item_type == "equation":
                result.append(
                    MultimodalContent(
                        content_type=ContentType.EQUATION,
                        page_idx=page_idx,
                        latex=item.get("latex", ""),
                        text=item.get("text"),
                    )
                )
            elif item_type == "text":
                result.append(
                    MultimodalContent(
                        content_type=ContentType.TEXT,
                        page_idx=page_idx,
                        text=item.get("text", ""),
                    )
                )
            else:
                result.append(
                    MultimodalContent(
                        content_type=ContentType.GENERIC,
                        page_idx=page_idx,
                        content=item.get("content", item.get("text", "")),
                    )
                )
        return result
