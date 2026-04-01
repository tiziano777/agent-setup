"""RDF Memory — Semantic Dispatcher Tool for LangGraph agents.

Structured RDF memory with lifecycle-differentiated named graphs
(session / staging / persistent) backed by Apache Jena Fuseki.

Quick start::

    from src.shared.rdf_memory import get_rdf_tools, RDFMemorySettings

    tools = get_rdf_tools(session_uuid="my-session-123")
    # tools = [rdf_query] — ready for create_react_agent()

Dependencies: ``pip install -e '.[rdf]'``

All imports below are **lazy** — ``ImportError`` is raised only when a
function is actually called, so importing this package is always safe.
"""

from src.shared.rdf_memory.config import (
    LifecyclePolicy,
    PolicyConfig,
    RDFMemorySettings,
    admin_policy,
    default_policy,
    read_write_policy,
)

__all__ = [
    # Config & Policy
    "RDFMemorySettings",
    "PolicyConfig",
    "LifecyclePolicy",
    "default_policy",
    "read_write_policy",
    "admin_policy",
    "setup_rdf_memory",
    # Client
    "FusekiClient",
    # Dispatcher
    "RDFDispatcher",
    # Lifecycle
    "promote_graph",
    "export_graph",
    "purge_session_graphs",
    "resolve_graph_uri",
    # Tool
    "get_rdf_tools",
]


# ── Lazy re-exports ──────────────────────────────────────────────────


def setup_rdf_memory(settings=None):
    """Configure the RDF Memory module (idempotent)."""
    from src.shared.rdf_memory.config import setup_rdf_memory as _fn

    return _fn(settings=settings)


def FusekiClient(settings=None):  # type: ignore[misc]
    """Create a :class:`~fuseki_client.FusekiClient` instance."""
    from src.shared.rdf_memory.fuseki_client import FusekiClient as _cls

    return _cls(settings=settings or RDFMemorySettings())


def RDFDispatcher(settings=None):  # type: ignore[misc]
    """Create an :class:`~dispatcher.RDFDispatcher` instance."""
    from src.shared.rdf_memory.dispatcher import RDFDispatcher as _cls

    return _cls(settings=settings)


def get_rdf_tools(settings=None, session_uuid=""):
    """Return ``[rdf_query]`` tool for LangGraph agents."""
    from src.shared.rdf_memory.langchain_tool import get_rdf_tools as _factory

    return _factory(settings=settings, session_uuid=session_uuid)


def promote_graph(
    client=None, from_lifecycle="session", to_lifecycle="persistent", session_uuid="", **kwargs
):
    """Promote triples between lifecycle tiers."""
    from src.shared.rdf_memory.graph_lifecycle import promote_graph as _fn

    return _fn(client, from_lifecycle, to_lifecycle, session_uuid, **kwargs)


def export_graph(client=None, lifecycle="session", session_uuid="", **kwargs):
    """Export a named graph in turtle / json-ld / n-triples."""
    from src.shared.rdf_memory.graph_lifecycle import export_graph as _fn

    return _fn(client, lifecycle, session_uuid, **kwargs)


def purge_session_graphs(client=None, session_uuid=""):
    """Drop session + staging graphs for a given session."""
    from src.shared.rdf_memory.graph_lifecycle import purge_session_graphs as _fn

    return _fn(client, session_uuid)


def resolve_graph_uri(lifecycle="session", session_uuid="", persistent_graph=None):
    """Resolve the named-graph URI for a lifecycle."""
    from src.shared.rdf_memory.graph_lifecycle import resolve_graph_uri as _fn

    return _fn(lifecycle, session_uuid, persistent_graph)
