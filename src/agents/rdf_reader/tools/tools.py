"""Tools for rdf_reader.

Provides the RDFDispatcher for direct use by graph nodes and the
rdf_query LangChain tool for optional ReAct usage. Both share the
same session UUID so all SPARQL operations target the same session graph.

Session graphs are ephemeral and cleaned up via atexit.
"""

import atexit
import uuid

from src.shared.rdf_memory import (
    FusekiClient,
    RDFMemorySettings,
    get_rdf_tools,
    purge_session_graphs,
)
from src.shared.rdf_memory.dispatcher import RDFDispatcher

_SESSION_UUID = uuid.uuid4().hex


def get_rdf_reader_tools(session_uuid: str | None = None) -> list:
    """Build the tool set: [rdf_query] scoped to a session graph."""
    sid = session_uuid or _SESSION_UUID
    return get_rdf_tools(session_uuid=sid)


def get_dispatcher(settings: RDFMemorySettings | None = None) -> RDFDispatcher:
    """Create an RDFDispatcher for direct node usage."""
    return RDFDispatcher(settings=settings)


def get_session_uuid() -> str:
    """Return the current module-level session UUID."""
    return _SESSION_UUID


def _cleanup():
    try:
        settings = RDFMemorySettings()
        client = FusekiClient(settings)
        purge_session_graphs(client, _SESSION_UUID)
        client.close()
    except Exception:
        pass


atexit.register(_cleanup)
