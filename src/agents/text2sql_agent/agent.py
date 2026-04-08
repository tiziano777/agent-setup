"""Main ReAct agent graph for text2sql.

Implements a multi-node StateGraph with:
1. Catalog extraction (deterministic)
2. Table selection (LLM)
3. Graph expansion (deterministic)
4. Context building (deterministic)
5. SQL generation (LLM)
6. Query execution + feedback loop (deterministic + LLM)
"""

from __future__ import annotations

import logging

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph

from src.shared.tracing import setup_tracing
from src.agents.text2sql_agent.states import Text2SQLState
from src.agents.text2sql_agent.nodes import (
    catalog_extraction_node,
    table_selection_node,
    graph_expansion_node,
    context_builder_node,
    sql_generator_node,
    query_executor_node,
    feedback_loop_node,
)

logger = logging.getLogger(__name__)

# Auto-instrument with Phoenix tracing
setup_tracing()


def _should_retry(state: Text2SQLState) -> str:
    """Routing logic: if query failed, go to feedback loop; otherwise end."""
    status = state.get("status", "")
    if status == "feedback":
        return "feedback"
    return "end"


def create_text2sql_graph() -> StateGraph:
    """Create and return the text2sql agent graph."""
    graph = StateGraph(Text2SQLState)

    # Add nodes
    graph.add_node("catalog", catalog_extraction_node)
    graph.add_node("selection", table_selection_node)
    graph.add_node("expansion", graph_expansion_node)
    graph.add_node("context", context_builder_node)
    graph.add_node("generation", sql_generator_node)
    graph.add_node("execution", query_executor_node)
    graph.add_node("feedback", feedback_loop_node)

    # Add edges (linear flow with conditional)
    graph.add_edge("catalog", "selection")
    graph.add_edge("selection", "expansion")
    graph.add_edge("expansion", "context")
    graph.add_edge("context", "generation")
    graph.add_edge("generation", "execution")

    # Conditional: execution -> feedback or end
    graph.add_conditional_edges(
        "execution",
        _should_retry,
        {
            "feedback": "feedback",
            "end": END,
        },
    )

    # Conditional from feedback: try again (loop) or end
    graph.add_conditional_edges(
        "feedback",
        _should_retry,
        {
            "feedback": "feedback",
            "end": END,
        },
    )

    # Set entry point
    graph.set_entry_point("catalog")

    return graph.compile()


# Compile the graph
graph = create_text2sql_graph()

__all__ = ["graph"]
