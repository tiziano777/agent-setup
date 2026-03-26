"""Pre-built LangGraph node factories for Cognee knowledge graph integration.

Each factory returns a node function compatible with LangGraph's
``StateGraph.add_node()``.  Nodes follow the project pattern:
receive state (TypedDict), return a partial state update dict.

Usage::

    from src.shared.cognee_toolkit import create_cognee_enriched_llm_node

    builder = StateGraph(AgentState)
    builder.add_node("process", create_cognee_enriched_llm_node())
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from src.shared.cognee_toolkit.config import CogneeSettings
from src.shared.cognee_toolkit.memory import CogneeMemory

logger = logging.getLogger(__name__)


def create_cognee_add_node(
    settings: CogneeSettings | None = None,
    state_key: str = "cognee_input",
) -> Callable[[dict], dict]:
    """Create a node that adds data from state to Cognee's knowledge graph.

    Reads text from ``state[state_key]`` and ingests it via
    :meth:`CogneeMemory.add_and_cognify`.

    Args:
        settings: Configuration dataclass.  Uses defaults when *None*.
        state_key: State key to read input data from.

    Usage::

        builder.add_node("cognee_add", create_cognee_add_node())
    """
    memory = CogneeMemory(settings=settings)

    def cognee_add_node(state: dict) -> dict:
        data = state.get(state_key, "")
        if data:
            memory.add_and_cognify_sync(data)
            logger.info("Cognee add node: ingested %d chars", len(str(data)))
        return {}

    return cognee_add_node


def create_cognee_search_node(
    settings: CogneeSettings | None = None,
    query_key: str = "messages",
    result_key: str = "cognee_context",
    search_type: str = "GRAPH_COMPLETION",
    session_id: str | None = None,
    top_k: int | None = None,
) -> Callable[[dict], dict]:
    """Create a node that searches Cognee and stores results in state.

    By default, extracts the query from the last message's content
    and stores results in ``state["cognee_context"]``.

    Args:
        settings: Configuration dataclass.  Uses defaults when *None*.
        query_key: State key to read the query from.
            If ``"messages"``, uses the last message content.
        result_key: State key to write search results to.
        search_type: Cognee search type name.
        session_id: Session identifier for conversational continuity.
        top_k: Maximum results to return.

    Usage::

        builder.add_node("cognee_search", create_cognee_search_node())
    """
    memory = CogneeMemory(settings=settings)

    def cognee_search_node(state: dict) -> dict:
        if query_key == "messages":
            messages = state.get("messages", [])
            if not messages:
                return {result_key: []}
            last = messages[-1]
            query = last.content if hasattr(last, "content") else str(last)
        else:
            query = state.get(query_key, "")

        if not query:
            return {result_key: []}

        kwargs: dict[str, Any] = {"search_type": search_type}
        if session_id is not None:
            kwargs["session_id"] = session_id
        if top_k is not None:
            kwargs["top_k"] = top_k

        results = memory.search_sync(query, **kwargs)
        logger.info("Cognee search node: %d results for '%s...'", len(results), query[:50])
        return {result_key: results}

    return cognee_search_node


def create_cognee_cognify_node(
    settings: CogneeSettings | None = None,
    datasets: str | list[str] | None = None,
) -> Callable[[dict], dict]:
    """Create a node that triggers knowledge graph construction.

    Args:
        settings: Configuration dataclass.  Uses defaults when *None*.
        datasets: Dataset name(s) to process.  Processes all if *None*.

    Usage::

        builder.add_node("cognee_cognify", create_cognee_cognify_node())
    """
    memory = CogneeMemory(settings=settings)

    def cognee_cognify_node(state: dict) -> dict:
        memory.cognify_sync(datasets=datasets)
        logger.info("Cognee cognify node: knowledge graph updated")
        return {}

    return cognee_cognify_node


def create_cognee_enriched_llm_node(
    settings: CogneeSettings | None = None,
    search_type: str = "GRAPH_COMPLETION",
    session_id: str | None = None,
    top_k: int | None = None,
    system_prompt: str | None = None,
) -> Callable[[dict], dict]:
    """Create a node that searches Cognee for context, then calls the LLM.

    This is the ``RAG-over-knowledge-graph`` pattern:

    1. Extracts the user query from ``state["messages"]``
    2. Searches Cognee's knowledge graph for relevant context
    3. Injects the context into the system prompt
    4. Calls ``get_llm()`` with the enriched prompt
    5. Returns the LLM response in ``state["messages"]``

    Args:
        settings: Configuration dataclass.  Uses defaults when *None*.
        search_type: Cognee search type name.
        session_id: Session identifier for conversational continuity.
        top_k: Maximum context results to retrieve.
        system_prompt: Base system prompt.  Context is appended to it.

    Usage::

        builder.add_node("process", create_cognee_enriched_llm_node(
            search_type="GRAPH_COMPLETION",
            session_id="researcher",
        ))
    """
    memory = CogneeMemory(settings=settings)

    _base_prompt = system_prompt or (
        "You are a helpful assistant with access to a knowledge graph. "
        "Use the provided context to answer the user's question accurately."
    )

    def cognee_enriched_llm_node(state: dict) -> dict:
        from src.shared.llm import get_llm

        messages = state.get("messages", [])
        if not messages:
            return {"messages": []}

        last = messages[-1]
        query = last.content if hasattr(last, "content") else str(last)

        # Search knowledge graph for context
        kwargs: dict[str, Any] = {"search_type": search_type}
        if session_id is not None:
            kwargs["session_id"] = session_id
        if top_k is not None:
            kwargs["top_k"] = top_k

        context_results = memory.search_sync(query, **kwargs)

        # Build enriched prompt
        if context_results:
            context_text = "\n\n".join(str(r) for r in context_results)
            enriched_prompt = (
                f"{_base_prompt}\n\n"
                f"## Knowledge Graph Context\n\n{context_text}"
            )
        else:
            enriched_prompt = _base_prompt

        # Call LLM
        llm = get_llm()
        full_messages = [{"role": "system", "content": enriched_prompt}] + list(messages)
        response = llm.invoke(full_messages)

        logger.info(
            "Cognee enriched LLM node: %d context results, query='%s...'",
            len(context_results),
            query[:50],
        )
        return {"messages": [response]}

    return cognee_enriched_llm_node
