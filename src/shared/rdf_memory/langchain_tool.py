"""LangGraph tool wrapper for the RDF Dispatcher.

Exposes a single ``rdf_query`` tool whose description is dynamically
generated from the active :class:`PolicyConfig` and the list of
registered persistent graphs.

Tool invocations are automatically traced as child spans of LangGraph
execution via OpenTelemetry's implicit context propagation. Each SPARQL
operation (SELECT, INSERT, etc.) will appear as a nested ``rdf.<OPERATION>``
span in the Phoenix trace hierarchy.

Only file in the module that imports from ``langchain_core``.
"""

from __future__ import annotations

import json
import logging

from langchain_core.tools import tool

from src.shared.rdf_memory.config import RDFMemorySettings
from src.shared.rdf_memory.dispatcher import RDFDispatcher

logger = logging.getLogger(__name__)


def get_rdf_tools(
    settings: RDFMemorySettings | None = None,
    session_uuid: str = "",
) -> list:
    """Return ``[rdf_query]`` — a single tool ready for ``create_react_agent()``.

    The *session_uuid* is captured in the closure and injected transparently;
    the LLM never needs to provide it.
    """
    dispatcher = RDFDispatcher(settings=settings)
    effective = dispatcher._settings

    # Build the list of targets visible and accessible to the LLM
    accessible_targets: list[str] = []
    policy = effective.policy

    if policy.session.visible and policy.session.llm_accessible:
        accessible_targets.append("session")

    if policy.persistent.visible and policy.persistent.llm_accessible:
        for graph_name in effective.persistent_graphs:
            accessible_targets.append(f"persistent:{graph_name}")

    if policy.staging.visible and policy.staging.llm_accessible:
        accessible_targets.append("staging")

    # Resolve the default target
    default_target = effective.default_lifecycle
    if default_target == "persistent":
        default_target = f"persistent:{effective.default_persistent_graph}"
    if default_target not in accessible_targets:
        default_target = accessible_targets[0] if accessible_targets else "session"

    targets_desc = ", ".join(f'"{t}"' for t in accessible_targets)

    # ── Tool definition ──────────────────────────────────────────────

    @tool
    def rdf_query(sparql_query: str, target: str = default_target) -> str:
        """Execute a SPARQL query against the RDF knowledge graph.

        Use this tool to store, retrieve, or manage structured knowledge
        as RDF triples.  Write standard SPARQL 1.1 queries — the system
        automatically routes to the correct named graph.

        **Targets**

        - ``"session"``: Your working memory (read/write, cleared when the session ends).
        - ``"persistent:<name>"``: Long-term validated knowledge
          (e.g. ``"persistent:math"``).  Read-only by default.

        Available targets: <<TARGETS>>

        Args:
            sparql_query: Valid SPARQL 1.1 (SELECT, ASK, CONSTRUCT,
                INSERT DATA, DELETE DATA, …).
            target: Named-graph target.  Default: ``"<<DEFAULT>>"``
        """
        if target not in accessible_targets:
            return f"Error: target '{target}' is not available. Use one of: {targets_desc}"

        # Parse target → lifecycle + optional graph name
        if target.startswith("persistent:"):
            lifecycle = "persistent"
            graph_name: str | None = target.split(":", 1)[1]
        else:
            lifecycle = target  # "session" or "staging"
            graph_name = None

        result = dispatcher.dispatch(
            sparql=sparql_query,
            target_lifecycle=lifecycle,  # type: ignore[arg-type]
            session_uuid=session_uuid,
            persistent_graph=graph_name,
        )

        if not result["success"]:
            return f"Error: {result.get('error', 'Unknown error')}"

        return _format_result(result)

    # Patch the docstring with the actual target list
    rdf_query.description = rdf_query.description.replace("<<TARGETS>>", targets_desc).replace(
        "<<DEFAULT>>", default_target
    )

    return [rdf_query]


# ── Result formatting ────────────────────────────────────────────────


def _format_result(result: dict) -> str:
    """Format a dispatcher result dict into a human/LLM-readable string."""
    op = result["operation"]
    graph = result["graph"]
    data = result["data"]

    if op == "SELECT":
        bindings = data.get("results", {}).get("bindings", [])
        if not bindings:
            return f"OK [{op}] on <{graph}>: no results."
        rows: list[str] = []
        for b in bindings[:50]:  # cap at 50 rows for context-length safety
            row_parts = [f"{k}={v.get('value', '')}" for k, v in b.items()]
            rows.append(" | ".join(row_parts))
        header = f"OK [{op}] on <{graph}> ({len(bindings)} result(s)):"
        return header + "\n" + "\n".join(rows)

    if op == "ASK":
        answer = data.get("boolean", data)
        return f"OK [{op}] on <{graph}>: {answer}"

    if op in ("CONSTRUCT", "DESCRIBE"):
        raw = data.get("results", str(data))
        preview = raw[:2000] if isinstance(raw, str) else json.dumps(raw)[:2000]
        return f"OK [{op}] on <{graph}>:\n{preview}"

    # Write operations (INSERT, DELETE, …)
    return f"OK [{op}] on <{graph}>: operation completed successfully."
