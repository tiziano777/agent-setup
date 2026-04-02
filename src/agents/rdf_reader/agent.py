from functools import partial

from langgraph.graph import END, START, StateGraph

from src.agents.rdf_reader.nodes.extract import extract
from src.agents.rdf_reader.nodes.query import query
from src.agents.rdf_reader.states.state import AgentState


def build_graph(
    session_uuid: str | None = None,
):
    """Construct the rdf_reader StateGraph.

    Args:
        session_uuid: Optional session ID override. If None, generates
                      a new UUID. Useful for testing with a known ID.
    """
    if session_uuid is None:
        import uuid
        session_uuid = uuid.uuid4().hex

    extract_node = partial(extract, session_uuid=session_uuid)
    query_node = partial(query, session_uuid=session_uuid)

    builder = StateGraph(AgentState)
    builder.add_node("extract", extract_node)
    builder.add_node("query", query_node)
    builder.add_edge(START, "extract")
    builder.add_edge("extract", "query")
    builder.add_edge("query", END)

    return builder.compile()


graph = build_graph()
