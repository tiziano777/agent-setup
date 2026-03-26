"""Search type enum and utilities for Cognee queries.

Provides :class:`CogneeSearchType` (importable without the ``cognee``
package) and helper functions for fallback and multi-type searches.

Usage::

    from src.shared.cognee_toolkit.search import CogneeSearchType

    results = await memory.search("query", search_type=CogneeSearchType.CHUNKS)
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.shared.cognee_toolkit.memory import CogneeMemory

logger = logging.getLogger(__name__)


# ── Search type enum (avoids importing cognee at module level) ────────


class CogneeSearchType(str, Enum):
    """All 14 Cognee search types."""

    SUMMARIES = "SUMMARIES"
    CHUNKS = "CHUNKS"
    RAG_COMPLETION = "RAG_COMPLETION"
    TRIPLET_COMPLETION = "TRIPLET_COMPLETION"
    GRAPH_COMPLETION = "GRAPH_COMPLETION"
    GRAPH_SUMMARY_COMPLETION = "GRAPH_SUMMARY_COMPLETION"
    CYPHER = "CYPHER"
    NATURAL_LANGUAGE = "NATURAL_LANGUAGE"
    GRAPH_COMPLETION_COT = "GRAPH_COMPLETION_COT"
    GRAPH_COMPLETION_CONTEXT_EXTENSION = "GRAPH_COMPLETION_CONTEXT_EXTENSION"
    FEELING_LUCKY = "FEELING_LUCKY"
    TEMPORAL = "TEMPORAL"
    CODING_RULES = "CODING_RULES"
    CHUNKS_LEXICAL = "CHUNKS_LEXICAL"


# Curated presets for common use cases
CONVERSATIONAL_TYPES: list[str] = [
    CogneeSearchType.GRAPH_COMPLETION.value,
    CogneeSearchType.RAG_COMPLETION.value,
    CogneeSearchType.TRIPLET_COMPLETION.value,
]

FAST_TYPES: list[str] = [
    CogneeSearchType.CHUNKS.value,
    CogneeSearchType.CHUNKS_LEXICAL.value,
    CogneeSearchType.SUMMARIES.value,
]

CODE_TYPES: list[str] = [
    CogneeSearchType.CODING_RULES.value,
    CogneeSearchType.CHUNKS.value,
]


# ── Bridge: string → cognee.SearchType ────────────────────────────────


def resolve_search_type(search_type: str | CogneeSearchType) -> Any:
    """Convert a string or :class:`CogneeSearchType` to ``cognee.SearchType``.

    Lazily imports ``cognee`` so this module stays lightweight.
    """
    from cognee.modules.search.types import SearchType

    name = search_type.value if isinstance(search_type, CogneeSearchType) else search_type
    return SearchType[name]


# ── Search utilities ──────────────────────────────────────────────────


async def search_with_fallback(
    query: str,
    primary_type: str = "GRAPH_COMPLETION",
    fallback_type: str = "CHUNKS",
    memory: CogneeMemory | None = None,
    **kwargs: Any,
) -> list[Any]:
    """Search with automatic fallback if the primary type returns no results.

    Args:
        query: Natural language search query.
        primary_type: Primary search type to try first.
        fallback_type: Fallback search type if primary returns empty.
        memory: :class:`CogneeMemory` instance.  Creates one if *None*.
        **kwargs: Forwarded to :meth:`CogneeMemory.search`.
    """
    if memory is None:
        from src.shared.cognee_toolkit.memory import CogneeMemory

        memory = CogneeMemory()

    results = await memory.search(query, search_type=primary_type, **kwargs)

    if not results:
        logger.info(
            "No results for %s search, falling back to %s", primary_type, fallback_type
        )
        results = await memory.search(query, search_type=fallback_type, **kwargs)

    return results


async def multi_search(
    query: str,
    search_types: list[str] | None = None,
    memory: CogneeMemory | None = None,
    **kwargs: Any,
) -> dict[str, list[Any]]:
    """Run multiple search types concurrently and return results keyed by type.

    Args:
        query: Natural language search query.
        search_types: Search types to run.  Defaults to GRAPH_COMPLETION + CHUNKS.
        memory: :class:`CogneeMemory` instance.  Creates one if *None*.
        **kwargs: Forwarded to :meth:`CogneeMemory.search`.
    """
    if memory is None:
        from src.shared.cognee_toolkit.memory import CogneeMemory

        memory = CogneeMemory()

    if search_types is None:
        search_types = [CogneeSearchType.GRAPH_COMPLETION.value, CogneeSearchType.CHUNKS.value]

    tasks = {
        st: memory.search(query, search_type=st, **kwargs) for st in search_types
    }

    results: dict[str, list[Any]] = {}
    for st, coro in tasks.items():
        results[st] = await coro

    return results
