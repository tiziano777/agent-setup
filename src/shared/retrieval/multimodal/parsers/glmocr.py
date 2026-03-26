"""GLM-OCR backed multimodal parser.

Uses GLM-OCR (``glmocr``) to extract structured multimodal content from
images and PDFs via the GLM-4.1V vision-language model.
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Any

from src.shared.retrieval.multimodal.models import ContentType, MultimodalContent
from src.shared.retrieval.multimodal.parsers.base import BaseMultimodalParser

logger = logging.getLogger(__name__)

_SUPPORTED_EXTENSIONS = [
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".bmp",
    ".tiff",
    ".tif",
    ".gif",
    ".webp",
]

_LABEL_TO_CONTENT_TYPE: dict[str, ContentType] = {
    "text": ContentType.TEXT,
    "table": ContentType.TABLE,
    "formula": ContentType.EQUATION,
    "image": ContentType.IMAGE,
}


class GlmOcrParser(BaseMultimodalParser):
    """Multimodal parser backed by GLM-OCR.

    Lazy-imports ``glmocr`` so the file can be imported even when the
    package is not installed.  Supports both MaaS (cloud) and self-hosted
    deployment modes.
    """

    def __init__(
        self,
        mode: str = "maas",
        api_key: str | None = None,
        selfhosted_host: str = "localhost",
        selfhosted_port: int = 8080,
    ) -> None:
        self._mode = mode
        self._api_key = api_key or os.getenv("GLMOCR_API_KEY") or os.getenv("ZHIPU_API_KEY")
        self._selfhosted_host = selfhosted_host
        self._selfhosted_port = selfhosted_port

    def _build_parser_kwargs(self) -> dict[str, Any]:
        """Build constructor kwargs for ``GlmOcr`` based on mode."""
        if self._mode == "selfhosted":
            return {
                "mode": "selfhosted",
                "ocr_api_host": self._selfhosted_host,
                "ocr_api_port": self._selfhosted_port,
            }
        kwargs: dict[str, Any] = {}
        if self._api_key:
            kwargs["api_key"] = self._api_key
        return kwargs

    # ── ABC implementation ──────────────────────────────────────────────

    async def parse(
        self,
        file_path: str | Path,
        output_dir: str | Path | None = None,
        **kwargs: Any,
    ) -> list[MultimodalContent]:
        """Parse a single file via GLM-OCR.

        The *output_dir* parameter is accepted for API compatibility but
        is not used — GLM-OCR does not write intermediate files.
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        if file_path.suffix.lower() not in _SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"Unsupported file type {file_path.suffix!r} for GLM-OCR. "
                f"Supported: {_SUPPORTED_EXTENSIONS}"
            )

        result = await asyncio.to_thread(self._parse_sync, file_path)
        return self._convert_pipeline_result(result)

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

        sem = asyncio.Semaphore(max_workers)
        results: dict[str, list[MultimodalContent]] = {}

        async def _parse_one(fp: Path) -> None:
            async with sem:
                try:
                    content = await self.parse(fp, output_dir=output_dir, **kwargs)
                    results[str(fp)] = content
                except Exception:
                    logger.exception("Failed to parse %s", fp)

        await asyncio.gather(*[_parse_one(f) for f in files])
        return results

    @property
    def supported_extensions(self) -> list[str]:
        return list(_SUPPORTED_EXTENSIONS)

    # ── Internal helpers ────────────────────────────────────────────────

    def _parse_sync(self, file_path: Path) -> Any:
        """Synchronous parse wrapped by :func:`asyncio.to_thread`."""
        from glmocr import GlmOcr

        if self._mode != "selfhosted" and not self._api_key:
            raise RuntimeError(
                "GLM-OCR MaaS mode requires an API key. "
                "Set GLMOCR_API_KEY or ZHIPU_API_KEY in .env, "
                "or pass api_key= to the constructor."
            )

        parser_kwargs = self._build_parser_kwargs()
        with GlmOcr(**parser_kwargs) as parser:
            return parser.parse(str(file_path))

    @staticmethod
    def _convert_pipeline_result(result: Any) -> list[MultimodalContent]:
        """Map GLM-OCR ``PipelineResult`` to typed :class:`MultimodalContent` list."""
        contents: list[MultimodalContent] = []

        for page_idx, page_regions in enumerate(result.json_result):
            for region in page_regions:
                label = region.get("label", "text")
                raw_content = region.get("content", "")
                content_type = _LABEL_TO_CONTENT_TYPE.get(label, ContentType.GENERIC)

                if content_type is ContentType.TEXT:
                    contents.append(
                        MultimodalContent(
                            content_type=ContentType.TEXT,
                            page_idx=page_idx,
                            text=raw_content,
                        )
                    )
                elif content_type is ContentType.TABLE:
                    contents.append(
                        MultimodalContent(
                            content_type=ContentType.TABLE,
                            page_idx=page_idx,
                            table_body=raw_content,
                        )
                    )
                elif content_type is ContentType.EQUATION:
                    contents.append(
                        MultimodalContent(
                            content_type=ContentType.EQUATION,
                            page_idx=page_idx,
                            latex=raw_content,
                        )
                    )
                elif content_type is ContentType.IMAGE:
                    contents.append(
                        MultimodalContent(
                            content_type=ContentType.IMAGE,
                            page_idx=page_idx,
                            img_path=None,
                            image_caption=raw_content,
                        )
                    )
                else:
                    contents.append(
                        MultimodalContent(
                            content_type=ContentType.GENERIC,
                            page_idx=page_idx,
                            content=raw_content,
                        )
                    )

        return contents
