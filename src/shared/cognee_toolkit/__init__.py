"""Cognee knowledge graph memory toolkit.

Provides knowledge graph-based memory for LangGraph agents, backed by
the project's LiteLLM proxy, Qdrant vector store, and Neo4j graph database.

Quick start::

    from src.shared.cognee_toolkit import get_cognee_memory, get_cognee_tools

    # As a Python class
    memory = get_cognee_memory()
    await memory.add("Important fact")
    await memory.cognify()
    results = await memory.search("What do we know?")

    # As LangGraph tools
    tools = get_cognee_tools(session_id="user_123")
    agent = create_react_agent(get_llm(), tools)

Dependencies:
    Requires ``pip install -e '.[cognee]'``.  All imports are lazy --
    ``ImportError`` is raised only when a function is actually called.
"""

from src.shared.cognee_toolkit.config import CogneeSettings, setup_cognee
from src.shared.cognee_toolkit.memory import CogneeMemory
from src.shared.cognee_toolkit.search import (
    CODE_TYPES,
    CONVERSATIONAL_TYPES,
    FAST_TYPES,
    CogneeSearchType,
)

__all__ = [
    # Config
    "CogneeSettings",
    "setup_cognee",
    # Memory
    "CogneeMemory",
    "get_cognee_memory",
    # Tools
    "get_cognee_tools",
    "get_cognee_memory_tools",
    # Search
    "CogneeSearchType",
    "CONVERSATIONAL_TYPES",
    "FAST_TYPES",
    "CODE_TYPES",
    "search_with_fallback",
    "multi_search",
]


# ── Factory: CogneeMemory ────────────────────────────────────────────


def get_cognee_memory(settings: CogneeSettings | None = None) -> CogneeMemory:
    """Build a :class:`CogneeMemory` instance with default or custom settings."""
    return CogneeMemory(settings=settings)


# ── Lazy re-exports for tools ────────────────────────────────────────


def get_cognee_tools(settings=None, session_id=None):
    """Return ``[cognee_add, cognee_search, cognee_cognify]`` tools."""
    from src.shared.cognee_toolkit.tools import get_cognee_tools as _factory

    return _factory(settings=settings, session_id=session_id)


def get_cognee_memory_tools(settings=None, session_id=None):
    """Return ``(add_tool, search_tool)`` pair for conversational memory."""
    from src.shared.cognee_toolkit.tools import get_cognee_memory_tools as _factory

    return _factory(settings=settings, session_id=session_id)


# ── Lazy re-exports for search utilities ─────────────────────────────


def search_with_fallback(query, **kwargs):
    """Search with automatic fallback if primary type returns no results."""
    from src.shared.cognee_toolkit.search import search_with_fallback as _fn

    return _fn(query, **kwargs)


def multi_search(query, **kwargs):
    """Run multiple search types concurrently, return results keyed by type."""
    from src.shared.cognee_toolkit.search import multi_search as _fn

    return _fn(query, **kwargs)
