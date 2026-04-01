"""rdf_reader: Graph API definition.

Defines the agent as a 2-node LangGraph StateGraph:

    START -> extract -> query -> END

The extract node reads complex text and inserts RDF triples into a
Fuseki session graph via SPARQL INSERT DATA. The query node translates
the user's question into a SPARQL SELECT, executes it, and formats a
natural-language answer.

Both nodes use the same RDFDispatcher (the single CLI-like interface)
— the operation (INSERT, SELECT, COUNT) depends on the node's task.
"""

from __future__ import annotations

import uuid
from functools import partial

from langgraph.graph import END, START, StateGraph

from src.agents.rdf_reader.nodes.extract import extract
from src.agents.rdf_reader.nodes.query import query
from src.agents.rdf_reader.states.state import AgentState
from src.shared.rdf_memory.dispatcher import RDFDispatcher


def build_graph(
    dispatcher: RDFDispatcher | None = None,
    session_uuid: str | None = None,
):
    """Construct the rdf_reader StateGraph.

    Args:
        dispatcher: Optional pre-built RDFDispatcher. If None, creates
                    a fresh one with default settings.
        session_uuid: Optional session ID override. If None, generates
                      a new UUID. Useful for testing with a known ID.
    """
    if dispatcher is None:
        dispatcher = RDFDispatcher()
    if session_uuid is None:
        session_uuid = uuid.uuid4().hex

    extract_node = partial(extract, dispatcher=dispatcher, session_uuid=session_uuid)
    query_node = partial(query, dispatcher=dispatcher, session_uuid=session_uuid)

    builder = StateGraph(AgentState)
    builder.add_node("extract", extract_node)
    builder.add_node("query", query_node)
    builder.add_edge(START, "extract")
    builder.add_edge("extract", "query")
    builder.add_edge("query", END)

    return builder.compile()


graph = build_graph()
