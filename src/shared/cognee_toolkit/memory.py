"""CogneeMemory — high-level wrapper for Cognee's knowledge graph operations.

Wraps Cognee's ``add``, ``cognify``, ``search``, and ``memify`` into a
single class with lazy initialization, async operations, and sync
wrappers for LangGraph node compatibility.

Usage::

    from src.shared.cognee_toolkit import get_cognee_memory

    memory = get_cognee_memory()
    await memory.add("Important fact about the project")
    await memory.cognify()
    results = await memory.search("What do we know?")
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from src.shared.cognee_toolkit.config import CogneeSettings, _check_available, _ensure_configured

logger = logging.getLogger(__name__)


class CogneeMemory:
    """Knowledge graph memory powered by Cognee.

    Provides add/cognify/search/memify with automatic infrastructure
    configuration (LiteLLM proxy, Qdrant, Neo4j) and lazy initialization.

    Args:
        settings: Configuration dataclass.  Uses defaults when *None*.
    """

    def __init__(self, settings: CogneeSettings | None = None) -> None:
        self._settings = settings or CogneeSettings()
        self._initialized = False

    def _ensure_initialized(self) -> None:
        """Lazy setup: calls setup_cognee() on first use."""
        if self._initialized:
            return
        _check_available()
        _ensure_configured()
        self._initialized = True
        logger.info("CogneeMemory initialized")

    # -- Core operations (async) ────────────────────────────────────────

    async def add(
        self,
        data: str | list[str],
        dataset_name: str | None = None,
    ) -> None:
        """Ingest data into Cognee's knowledge base.

        Args:
            data: Text content (string or list of strings) to ingest.
            dataset_name: Dataset to add data to.  Defaults to settings value.
        """
        self._ensure_initialized()
        import cognee

        dataset = dataset_name or self._settings.default_dataset
        if isinstance(data, list):
            for item in data:
                await cognee.add(item, dataset_name=dataset)
        else:
            await cognee.add(data, dataset_name=dataset)

    async def cognify(
        self,
        datasets: str | list[str] | None = None,
    ) -> Any:
        """Build or update the knowledge graph from ingested data.

        Args:
            datasets: Dataset name(s) to process.  Processes all if *None*.
        """
        self._ensure_initialized()
        import cognee

        kwargs: dict[str, Any] = {}
        if datasets is not None:
            if isinstance(datasets, str):
                datasets = [datasets]
            kwargs["datasets"] = datasets

        return await cognee.cognify(**kwargs)

    async def search(
        self,
        query: str,
        search_type: str = "GRAPH_COMPLETION",
        top_k: int | None = None,
        session_id: str | None = None,
        datasets: str | list[str] | None = None,
        only_context: bool = False,
    ) -> list[Any]:
        """Search the knowledge graph.

        Args:
            query: Natural language search query.
            search_type: One of the 14 Cognee search types (string name).
            top_k: Maximum results to return.  Defaults to settings value.
            session_id: Session identifier for conversational continuity.
            datasets: Dataset name(s) to scope the search.
            only_context: If *True*, returns context without LLM completion.
        """
        self._ensure_initialized()
        import cognee

        from src.shared.cognee_toolkit.search import resolve_search_type

        kwargs: dict[str, Any] = {
            "query_text": query,
            "query_type": resolve_search_type(search_type),
            "top_k": top_k or self._settings.top_k,
            "only_context": only_context,
        }
        if session_id is not None:
            kwargs["session_id"] = session_id
        if datasets is not None:
            if isinstance(datasets, str):
                datasets = [datasets]
            kwargs["datasets"] = datasets

        return await cognee.search(**kwargs)

    async def memify(
        self,
        dataset: str | None = None,
        **kwargs: Any,
    ) -> Any:
        """Enrich existing knowledge graph with derived knowledge.

        Args:
            dataset: Dataset to enrich.  Defaults to settings value.
            **kwargs: Forwarded to ``cognee.memify()``.
        """
        self._ensure_initialized()
        import cognee

        return await cognee.memify(
            dataset=dataset or self._settings.default_dataset,
            **kwargs,
        )

    async def add_and_cognify(
        self,
        data: str | list[str],
        dataset_name: str | None = None,
    ) -> Any:
        """Convenience: add data then immediately build the knowledge graph."""
        await self.add(data, dataset_name=dataset_name)
        dataset = dataset_name or self._settings.default_dataset
        return await self.cognify(datasets=dataset)

    # -- Sync wrappers for LangGraph nodes ─────────────────────────────

    def add_sync(self, data: str | list[str], **kwargs: Any) -> None:
        """Synchronous wrapper for :meth:`add`."""
        asyncio.run(self.add(data, **kwargs))

    def cognify_sync(self, **kwargs: Any) -> Any:
        """Synchronous wrapper for :meth:`cognify`."""
        return asyncio.run(self.cognify(**kwargs))

    def search_sync(self, query: str, **kwargs: Any) -> list[Any]:
        """Synchronous wrapper for :meth:`search`."""
        return asyncio.run(self.search(query, **kwargs))

    def add_and_cognify_sync(self, data: str | list[str], **kwargs: Any) -> Any:
        """Synchronous wrapper for :meth:`add_and_cognify`."""
        return asyncio.run(self.add_and_cognify(data, **kwargs))

    # -- Properties ────────────────────────────────────────────────────

    @property
    def settings(self) -> CogneeSettings:
        """Return the current settings."""
        return self._settings
