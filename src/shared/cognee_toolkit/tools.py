"""LangGraph-compatible tools for Cognee knowledge graph memory.

Factory functions that return ``@tool``-decorated functions ready to
attach to any LangGraph agent's tool list.

Usage::

    from src.shared.cognee_toolkit import get_cognee_tools

    tools = get_cognee_tools(session_id="user_123")
    agent = create_react_agent(get_llm(), tools)
"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import tool

from src.shared.cognee_toolkit.config import CogneeSettings
from src.shared.cognee_toolkit.memory import CogneeMemory


def get_cognee_tools(
    settings: CogneeSettings | None = None,
    session_id: str | None = None,
) -> list:
    """Return a list of LangGraph-compatible Cognee tools.

    Returns ``[cognee_add, cognee_search, cognee_cognify]``.
    Each tool captures *settings* and *session_id* in its closure.

    Args:
        settings: Configuration dataclass.  Uses defaults when *None*.
        session_id: Session identifier for conversational continuity.
    """
    memory = CogneeMemory(settings=settings)

    @tool
    async def cognee_add(data: str) -> str:
        """Store information in the knowledge graph memory.

        Use this tool to remember facts, documents, or any text data.
        The data will be processed into entities, relationships, and
        summaries in the knowledge graph.

        Args:
            data: Text content to store in the knowledge graph.
        """
        await memory.add_and_cognify(data)
        return f"Stored and processed: {data[:100]}..."

    @tool
    async def cognee_search(query: str) -> str:
        """Search the knowledge graph memory for relevant information.

        Use this tool to recall previously stored information.
        Returns relevant knowledge from the graph database.

        Args:
            query: Natural language search query.
        """
        results = await memory.search(query, session_id=session_id)
        if not results:
            return "No relevant information found in the knowledge graph."
        return "\n\n".join(str(r) for r in results)

    @tool
    async def cognee_cognify(dataset_name: str = "main_dataset") -> str:
        """Build or update the knowledge graph from stored data.

        Call this after adding multiple pieces of data to process
        them all into entities, relationships, and summaries at once.
        This is more efficient than processing after each add.

        Args:
            dataset_name: Name of the dataset to process.
        """
        await memory.cognify(datasets=dataset_name)
        return f"Knowledge graph updated for dataset: {dataset_name}"

    return [cognee_add, cognee_search, cognee_cognify]


def get_cognee_memory_tools(
    settings: CogneeSettings | None = None,
    session_id: str | None = None,
) -> tuple[Any, Any]:
    """Return ``(add_tool, search_tool)`` — minimal pair for conversational memory.

    The add tool automatically triggers knowledge graph construction
    after ingestion. This mirrors the ``cognee-integration-langgraph``
    pattern but routes all calls through the project's LiteLLM proxy.

    Args:
        settings: Configuration dataclass.  Uses defaults when *None*.
        session_id: Session identifier for conversational continuity.
    """
    tools = get_cognee_tools(settings=settings, session_id=session_id)
    return tools[0], tools[1]  # cognee_add, cognee_search
