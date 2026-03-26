"""Multimodal retrieval pipeline wrapping RAG-Anything.

This is the primary class agents interact with.  It provides document
ingestion (parsing + indexing), text queries, and multimodal queries —
all routed through the LiteLLM proxy via the adapter layer.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Literal

from src.shared.retrieval.multimodal.config import MultimodalRetrievalSettings
from src.shared.retrieval.multimodal.models import MultimodalContent

logger = logging.getLogger(__name__)


class MultimodalRetrieverPipeline:
    """Orchestrates multimodal document ingestion and knowledge-graph retrieval.

    Wraps :class:`RAGAnything` with lazy initialization, adapter wiring, and
    synchronous convenience wrappers for LangGraph node compatibility.

    Args:
        settings: Configuration for the pipeline.  Uses defaults when *None*.
        rag_instance: Pre-built ``RAGAnything`` instance for advanced usage.
            When provided, adapters and config are not created automatically.
    """

    def __init__(
        self,
        settings: MultimodalRetrievalSettings | None = None,
        rag_instance: Any = None,
    ) -> None:
        self._settings = settings or MultimodalRetrievalSettings()
        self._rag = rag_instance
        self._initialized = rag_instance is not None

    # -- Lazy initialization -----------------------------------------------

    def _ensure_initialized(self) -> None:
        """Construct ``RAGAnything`` on first use (lazy-imports)."""
        if self._initialized:
            return

        from raganything import RAGAnything, RAGAnythingConfig

        from src.shared.retrieval.multimodal.adapters import (
            create_embedding_func,
            create_llm_model_func,
            create_vision_model_func,
        )

        s = self._settings

        config = RAGAnythingConfig(
            working_dir=s.working_dir,
            parser=s.parser,
            parse_method=s.parse_method,
            enable_image_processing=s.enable_image_processing,
            enable_table_processing=s.enable_table_processing,
            enable_equation_processing=s.enable_equation_processing,
        )

        llm_func = create_llm_model_func(
            model=s.llm_model,
            temperature=s.llm_temperature,
            max_tokens=s.llm_max_tokens,
        )

        vision_func = None
        if s.vision_model:
            vision_func = create_vision_model_func(
                model=s.vision_model,
                temperature=s.llm_temperature,
                max_tokens=s.llm_max_tokens,
            )

        embedding_func = create_embedding_func(
            embedding_provider=s.embedding_provider,
            embedding_model=s.embedding_model,
            embedding_dims=s.embedding_dims,
            max_token_size=s.embedding_max_tokens,
        )

        self._rag = RAGAnything(
            config=config,
            llm_model_func=llm_func,
            vision_model_func=vision_func,
            embedding_func=embedding_func,
        )
        self._initialized = True
        logger.info("MultimodalRetrieverPipeline initialized (working_dir=%s)", s.working_dir)

    # -- Document Ingestion (async) ----------------------------------------

    async def ingest(
        self,
        file_path: str | Path,
        output_dir: str | Path | None = None,
        **kwargs: Any,
    ) -> None:
        """Parse and index a single document.

        Delegates to ``RAGAnything.process_document_complete``.
        """
        self._ensure_initialized()
        fp = str(file_path)
        out = str(output_dir) if output_dir else None
        await self._rag.process_document_complete(
            file_path=fp,
            output_dir=out,
            **kwargs,
        )

    async def ingest_folder(
        self,
        folder_path: str | Path,
        output_dir: str | Path | None = None,
        file_extensions: list[str] | None = None,
        recursive: bool = True,
        max_workers: int | None = None,
        **kwargs: Any,
    ) -> None:
        """Parse and index all documents in a folder."""
        self._ensure_initialized()
        await self._rag.process_folder_complete(
            folder_path=str(folder_path),
            output_dir=str(output_dir) if output_dir else None,
            file_extensions=file_extensions or self._settings.file_extensions,
            recursive=recursive,
            max_workers=max_workers or self._settings.max_workers,
            **kwargs,
        )

    async def ingest_content_list(
        self,
        content_list: list[MultimodalContent] | list[dict[str, Any]],
        file_path: str = "manual_input",
        doc_id: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Insert pre-parsed content directly (bypasses document parsing).

        Accepts either :class:`MultimodalContent` objects or raw dicts.
        """
        self._ensure_initialized()

        raw: list[dict[str, Any]] = []
        for item in content_list:
            if isinstance(item, MultimodalContent):
                raw.append(item.to_raganything_dict())
            else:
                raw.append(item)

        await self._rag.insert_content_list(
            content_list=raw,
            file_path=file_path,
            doc_id=doc_id,
            **kwargs,
        )

    # -- Query (async) -----------------------------------------------------

    async def query(
        self,
        question: str,
        mode: Literal["hybrid", "local", "global", "naive"] | None = None,
        vlm_enhanced: bool | None = None,
    ) -> str:
        """Query the multimodal knowledge base.

        Args:
            question: The question to answer.
            mode: Retrieval mode.  Defaults to settings value.
            vlm_enhanced: Whether to use VLM-enhanced retrieval.

        Returns:
            The generated answer string.
        """
        self._ensure_initialized()
        return await self._rag.aquery(
            question,
            mode=mode or self._settings.default_query_mode,
            vlm_enhanced=vlm_enhanced if vlm_enhanced is not None else self._settings.vlm_enhanced,
        )

    async def query_with_multimodal(
        self,
        question: str,
        multimodal_content: list[dict[str, Any]],
        mode: Literal["hybrid", "local", "global", "naive"] | None = None,
    ) -> str:
        """Query with additional multimodal context (images, tables, equations).

        Args:
            question: The question to answer.
            multimodal_content: List of content dicts (see RAG-Anything docs).
            mode: Retrieval mode.

        Returns:
            The generated answer string.
        """
        self._ensure_initialized()
        return await self._rag.aquery_with_multimodal(
            question,
            multimodal_content=multimodal_content,
            mode=mode or self._settings.default_query_mode,
        )

    # -- Sync wrappers for LangGraph nodes ---------------------------------

    def query_sync(
        self,
        question: str,
        mode: Literal["hybrid", "local", "global", "naive"] | None = None,
        vlm_enhanced: bool | None = None,
    ) -> str:
        """Synchronous wrapper for :meth:`query`.

        Use in LangGraph node functions that run in a synchronous context.
        """
        return asyncio.run(self.query(question, mode=mode, vlm_enhanced=vlm_enhanced))

    def ingest_sync(self, file_path: str | Path, **kwargs: Any) -> None:
        """Synchronous wrapper for :meth:`ingest`."""
        asyncio.run(self.ingest(file_path, **kwargs))

    # -- Properties --------------------------------------------------------

    @property
    def rag(self) -> Any:
        """Direct access to the underlying ``RAGAnything`` instance."""
        self._ensure_initialized()
        return self._rag

    @property
    def settings(self) -> MultimodalRetrievalSettings:
        """Return the current settings."""
        return self._settings
