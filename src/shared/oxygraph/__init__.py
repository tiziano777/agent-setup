"""Oxigraph triple store toolkit.

Provides SPARQL query execution and graph management for LangGraph agents,
backed by an Oxigraph server with HTTP SPARQL endpoint.

Quick start::

    from src.shared.oxygraph import get_oxigraph_tools, OxigraphClient

    # Direct Python usage
    client = OxigraphClient()
    result = client.query("SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 10")

    # As LangGraph tools
    tools = get_oxigraph_tools()
    agent = create_react_agent(get_llm(), tools)
"""

from src.shared.oxygraph.config import OxigraphSettings

__all__ = [
    "OxigraphSettings",
    "OxigraphClient",
    "get_oxigraph_tools",
]


def OxigraphClient(settings: OxigraphSettings | None = None):
    """Create an :class:`~src.shared.oxygraph.client.OxigraphClient` instance."""
    from src.shared.oxygraph.client import OxigraphClient as _cls

    return _cls(settings=settings)


def get_oxigraph_tools(settings: OxigraphSettings | None = None) -> list:
    """Return ``[execute_sparql, manage_graph]`` tools for LangGraph agents."""
    from src.shared.oxygraph.tools import get_oxigraph_tools as _factory

    return _factory(settings=settings)
