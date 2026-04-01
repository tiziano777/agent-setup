"""Named-graph lifecycle management.

Provides functions for promoting triples between lifecycle tiers
(session → staging → persistent), exporting graphs in various RDF
serialisation formats, purging session data, and resolving named-graph URIs.

All graph-level operations use SPARQL MOVE / COPY / DROP — never
direct triple manipulation in Python.
"""

from __future__ import annotations

import logging
from typing import Literal

from src.shared.rdf_memory.fuseki_client import FusekiClient

logger = logging.getLogger(__name__)

# ── Graph URI resolution ─────────────────────────────────────────────


def resolve_graph_uri(
    lifecycle: Literal["session", "staging", "persistent"],
    session_uuid: str,
    persistent_graph: str | None = None,
) -> str:
    """Return the named-graph URI for a lifecycle + identifier.

    - session    → ``<urn:graph:session:{session_uuid}>``
    - staging    → ``<urn:graph:staging:{session_uuid}>``
    - persistent → ``<urn:graph:persistent:{persistent_graph}>``
    """
    if lifecycle == "session":
        return f"urn:graph:session:{session_uuid}"
    if lifecycle == "staging":
        return f"urn:graph:staging:{session_uuid}"
    if lifecycle == "persistent":
        if not persistent_graph:
            raise ValueError("persistent_graph is required for lifecycle 'persistent'")
        return f"urn:graph:persistent:{persistent_graph}"
    raise ValueError(f"Unknown lifecycle: {lifecycle}")


# ── Promotion ────────────────────────────────────────────────────────


def promote_graph(
    client: FusekiClient,
    from_lifecycle: Literal["session", "staging", "persistent"],
    to_lifecycle: Literal["session", "staging", "persistent"],
    session_uuid: str,
    mode: Literal["move", "copy"] = "move",
    from_persistent_graph: str | None = None,
    to_persistent_graph: str | None = None,
    shacl_shapes_path: str | None = None,
) -> bool:
    """Promote triples between lifecycle tiers via SPARQL MOVE or COPY GRAPH.

    Args:
        mode: ``"move"`` empties the source graph; ``"copy"`` keeps it intact.
        shacl_shapes_path: Optional filesystem path to a SHACL shapes file.
            When provided, the source graph is validated before promotion.
            If validation fails the promotion is aborted and *False* is returned.

    Returns:
        *True* on success, *False* on SHACL validation failure.
    """
    src_uri = resolve_graph_uri(from_lifecycle, session_uuid, from_persistent_graph)
    dst_uri = resolve_graph_uri(to_lifecycle, session_uuid, to_persistent_graph)

    # Optional SHACL validation
    if shacl_shapes_path:
        if not _validate_shacl(client, src_uri, shacl_shapes_path):
            logger.warning(
                "SHACL validation failed for <%s>; promotion aborted",
                src_uri,
            )
            return False

    verb = "MOVE" if mode == "move" else "COPY"
    sparql = f"{verb} GRAPH <{src_uri}> TO GRAPH <{dst_uri}>"
    client.update(sparql)
    logger.info("Promoted <%s> → <%s> (%s)", src_uri, dst_uri, verb)
    return True


# ── Export ───────────────────────────────────────────────────────────


def export_graph(
    client: FusekiClient,
    lifecycle: Literal["session", "staging", "persistent"],
    session_uuid: str,
    persistent_graph: str | None = None,
    fmt: Literal["turtle", "json-ld", "n-triples"] = "turtle",
) -> str:
    """Dump a named graph via the Graph Store Protocol.

    Returns the serialised graph as a string.
    """
    graph_uri = resolve_graph_uri(lifecycle, session_uuid, persistent_graph)
    return client.get_graph(graph_uri, fmt=fmt)


# ── Purge ────────────────────────────────────────────────────────────


def purge_session_graphs(
    client: FusekiClient,
    session_uuid: str,
) -> bool:
    """Drop both session and staging graphs for a given session.

    Uses ``DROP SILENT GRAPH`` so it succeeds even if the graph does not exist.
    """
    for lifecycle in ("session", "staging"):
        uri = resolve_graph_uri(lifecycle, session_uuid)  # type: ignore[arg-type]
        client.update(f"DROP SILENT GRAPH <{uri}>")
        logger.info("Purged <%s>", uri)
    return True


# ── SHACL validation (optional) ─────────────────────────────────────

try:
    from pyshacl import validate as _shacl_validate

    _SHACL_AVAILABLE = True
except ImportError:
    _SHACL_AVAILABLE = False

_SHACL_INSTALL_HINT = "Install pySHACL: pip install -e '.[rdf-shacl]'"


def _validate_shacl(client: FusekiClient, graph_uri: str, shapes_path: str) -> bool:
    """Validate a graph against SHACL shapes.

    Fetches the graph in Turtle format, then runs pySHACL locally.
    """
    if not _SHACL_AVAILABLE:
        raise ImportError(_SHACL_INSTALL_HINT)

    import rdflib

    data_ttl = client.get_graph(graph_uri, fmt="turtle")
    if not data_ttl.strip():
        logger.warning("Graph <%s> is empty — SHACL validation skipped", graph_uri)
        return True

    data_graph = rdflib.Graph()
    data_graph.parse(data=data_ttl, format="turtle")

    shapes_graph = rdflib.Graph()
    shapes_graph.parse(shapes_path)

    conforms, _, results_text = _shacl_validate(
        data_graph,
        shacl_graph=shapes_graph,
    )
    if not conforms:
        logger.warning("SHACL validation failed:\n%s", results_text)
    return conforms
