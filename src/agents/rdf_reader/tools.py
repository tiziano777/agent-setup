"""RDF query tool for RDF reader agent.

Single @tool wrapper for all SPARQL operations (INSERT, SELECT, etc.).
Handles classification, permissions, and execution via dispatcher.
Automatically traced as langchain.tool::rdf_query in Phoenix.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from langchain_core.callbacks.manager import get_callback_manager
from langchain_core.tools import tool

from src.shared.rdf_memory.dispatcher import RDFDispatcher

logger = logging.getLogger(__name__)

# Single dispatcher instance for all operations
_dispatcher: RDFDispatcher | None = None


def _get_dispatcher() -> RDFDispatcher:
    """Get or create singleton dispatcher."""
    global _dispatcher
    if _dispatcher is None:
        _dispatcher = RDFDispatcher()
    return _dispatcher


def get_dispatcher() -> RDFDispatcher:
    """Get the singleton RDFDispatcher instance."""
    return _get_dispatcher()


def get_session_uuid() -> str:
    """Generate a new session UUID."""
    return uuid.uuid4().hex


def get_rdf_reader_tools(session_uuid: str | None = None) -> list:
    """Get list of RDF reader tools.

    Args:
        session_uuid: Optional session ID. If None, generates a new one.

    Returns:
        List containing the rdf_query tool.
    """
    if session_uuid is None:
        session_uuid = get_session_uuid()

    #  Return the tool (already has session_uuid in its closure if needed)
    return [rdf_query]


@tool
def rdf_query(
    sparql_command: str,
    session_uuid: str,
    target_lifecycle: str = "session",
) -> str:
    """Execute SPARQL command against RDF knowledge graph.

    Accepts any valid SPARQL 1.1 command: SELECT, INSERT, DELETE, etc.
    The dispatcher automatically:
    - Classifies the operation type
    - Enforces access policies
    - Injects the named graph URI
    - Executes the command

    Automatically traced as a LangChain tool call, making RDF operations
    visible in LangGraph execution traces. Tool calls register in Phoenix
    via the LangChain callback system, and RDF operations nest as child spans
    under the tool call.

    Args:
        sparql_command: Valid SPARQL 1.1 query or update.
        session_uuid: Session identifier for graph routing.
        target_lifecycle: Graph lifecycle (session, staging, persistent). Default: session.

    Returns:
        Formatted result string (success/error + data).
    """
    dispatcher = _get_dispatcher()

    # Extract run_manager from LangChain's callback context
    # This links RDF spans to the tool call span in Phoenix
    run_manager = None
    try:
        callback_manager = get_callback_manager()
        if callback_manager:
            run_manager = callback_manager.get_run_manager()
    except Exception:
        # Callback manager may not be available in all contexts - that's fine
        pass

    try:
        result = dispatcher.dispatch(
            sparql=sparql_command,
            target_lifecycle=target_lifecycle,  # type: ignore[arg-type]
            session_uuid=session_uuid,
            run_manager=run_manager,  # ← Pass for explicit trace linkage
        )

        if not result["success"]:
            return f"Error: {result.get('error', 'Unknown error')}"

        # Format based on operation type
        operation = result.get("operation", "UNKNOWN")
        graph = result.get("graph", "unknown")
        data = result.get("data", {})

        if operation == "SELECT":
            bindings = data.get("results", {}).get("bindings", [])
            if not bindings:
                return f"OK [SELECT] on <{graph}>: no results."
            rows = []
            for b in bindings[:50]:  # Cap at 50 rows for context
                row_parts = [f"{k}={v.get('value', '')}" for k, v in b.items()]
                rows.append(" | ".join(row_parts))
            header = f"OK [SELECT] on <{graph}> ({len(bindings)} result(s)):"
            return header + "\n" + "\n".join(rows)

        if operation == "ASK":
            answer = data.get("boolean", False)
            return f"OK [ASK] on <{graph}>: {answer}"

        if operation in ("CONSTRUCT", "DESCRIBE"):
            raw = data.get("results", str(data))
            preview = raw[:2000] if isinstance(raw, str) else json.dumps(raw)[:2000]
            return f"OK [{operation}] on <{graph}>:\n{preview}"

        # Write operations (INSERT, DELETE, DROP, etc.)
        return f"OK [{operation}] on <{graph}>: operation completed successfully."

    except Exception as e:
        logger.exception("rdf_query tool failed")
        return f"Error executing SPARQL: {str(e)[:500]}"

