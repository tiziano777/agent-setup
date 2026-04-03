"""LangGraph-compatible tools for Oxigraph SPARQL operations."""

from __future__ import annotations

from langchain_core.tools import tool

from src.shared.oxygraph.client import OxigraphClient as _OxigraphClient
from src.shared.oxygraph.config import OxigraphSettings


def get_oxigraph_tools(settings: OxigraphSettings | None = None) -> list:
    """Return SPARQL tools for LangGraph agents."""
    client = _OxigraphClient(settings=settings)

    @tool
    def execute_sparql(query: str, graph: str = "") -> str:
        """Execute a SPARQL query (SELECT/ASK/CONSTRUCT) or update (INSERT/DELETE) on Oxigraph.

        For read queries (SELECT, ASK, CONSTRUCT, DESCRIBE): uses the query endpoint.
        For write queries (INSERT, DELETE, LOAD, CLEAR, DROP): uses the update endpoint.

        Args:
            query: SPARQL query or update string.
            graph: Optional named graph URI.
        """
        import json

        query_stripped = query.strip().upper()
        is_update = any(
            query_stripped.startswith(kw)
            for kw in ("INSERT", "DELETE", "LOAD", "CLEAR", "DROP", "CREATE", "COPY", "MOVE", "ADD")
        )

        if is_update:
            result = client.update(query)
        else:
            result = client.query(query, graph=graph or None)

        data = result.get("data", "")
        if isinstance(data, dict):
            return json.dumps(data, indent=2, ensure_ascii=False)
        return str(data) if data else "(no output)"

    @tool
    def load_turtle(turtle_data: str, graph: str = "") -> str:
        """Load Turtle-formatted RDF triples into Oxigraph.

        Args:
            turtle_data: RDF triples in Turtle format.
            graph: Optional named graph URI for the triples.
        """
        result = client.load_triples(turtle_data, graph=graph or None)
        status = result.get("status", "unknown")
        return f"Triples loaded successfully (HTTP {status})"

    return [execute_sparql, load_turtle]
