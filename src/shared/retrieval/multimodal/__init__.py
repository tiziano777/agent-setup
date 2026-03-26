"""Multimodal retrieval infrastructure powered by RAG-Anything.

Extends the text-only retrieval module with multimodal document parsing,
knowledge-graph construction, and hybrid vector+graph retrieval.

Quick-start::

    from src.shared.retrieval.multimodal import get_multimodal_retriever

    pipeline = get_multimodal_retriever()
    await pipeline.ingest("report.pdf")
    answer = await pipeline.query("What are the key findings?")
"""

from __future__ import annotations

from src.shared.retrieval.multimodal.config import MultimodalRetrievalSettings
from src.shared.retrieval.multimodal.models import (
    ContentType,
    MultimodalContent,
    MultimodalDocument,
)
from src.shared.retrieval.multimodal.parsers.base import BaseMultimodalParser
from src.shared.retrieval.multimodal.pipeline import MultimodalRetrieverPipeline

__all__ = [
    # data models
    "ContentType",
    "MultimodalContent",
    "MultimodalDocument",
    # ABC
    "BaseMultimodalParser",
    # pipeline
    "MultimodalRetrieverPipeline",
    # config
    "MultimodalRetrievalSettings",
    # factories
    "get_multimodal_retriever",
    "get_multimodal_parser",
]


# ── Factory: Multimodal Retriever ────────────────────────────────────


def get_multimodal_retriever(
    settings: MultimodalRetrievalSettings | None = None,
    **kwargs,
) -> MultimodalRetrieverPipeline:
    """Build a multimodal retrieval pipeline.

    Mirrors the :func:`get_retriever` pattern from the parent package.

    Args:
        settings: Configuration dataclass.  Uses defaults when *None*.
        **kwargs: Forwarded to :class:`MultimodalRetrieverPipeline`.
    """
    if settings is None:
        settings = MultimodalRetrievalSettings()
    return MultimodalRetrieverPipeline(settings=settings, **kwargs)


# ── Factory: Multimodal Parser ───────────────────────────────────────


def get_multimodal_parser(parser: str = "mineru", **kwargs) -> BaseMultimodalParser:
    """Return a multimodal parser instance.

    Supported parsers:
        * ``"mineru"`` – MinerU (default).
        * ``"docling"`` – Docling.
        * ``"paddleocr"`` – PaddleOCR.
        * ``"glmocr"`` – GLM-OCR (cloud or self-hosted).
    """
    if parser == "glmocr":
        from src.shared.retrieval.multimodal.parsers.glmocr import GlmOcrParser

        return GlmOcrParser(**kwargs)

    from src.shared.retrieval.multimodal.parsers.raganything import RAGAnythingParser

    return RAGAnythingParser(parser=parser, **kwargs)
