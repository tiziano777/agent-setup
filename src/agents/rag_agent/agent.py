"""rag_agent: Graph API definition.

Defines the agent as a 2-node LangGraph StateGraph:

    START -> retrieve -> generate -> END

The retrieve node searches an in-memory hybrid retriever (BM25 + Vector
with RRF fusion) for relevant documents. The generate node calls the LLM
with the retrieved context to produce a grounded answer.

The retriever is injected into build_graph() so that callers (e.g. tests)
can provide a pre-loaded retriever instance.
"""

from __future__ import annotations

from functools import partial

from langgraph.graph import END, START, StateGraph

from src.agents.rag_agent.nodes.generate import generate
from src.agents.rag_agent.nodes.retrieve import retrieve
from src.agents.rag_agent.states.state import AgentState
from src.shared.retrieval import get_retriever
from src.shared.retrieval.pipeline import RetrieverPipeline


def build_graph(retriever: RetrieverPipeline | None = None):
    """Construct a RAG StateGraph with retrieve -> generate flow.

    Args:
        retriever: Optional pre-loaded RetrieverPipeline. If None, creates
                   a fresh (empty) in-memory retriever via get_retriever().
    """
    if retriever is None:
        retriever = get_retriever()

    # Bind the retriever to the retrieve node via partial
    retrieve_with_retriever = partial(retrieve, retriever=retriever)

    builder = StateGraph(AgentState)
    builder.add_node("retrieve", retrieve_with_retriever)
    builder.add_node("generate", generate)
    builder.add_edge(START, "retrieve")
    builder.add_edge("retrieve", "generate")
    builder.add_edge("generate", END)

    return builder.compile()


graph = build_graph()
