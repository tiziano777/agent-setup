"""Retrieve node for rag_agent.

Extracts the user's query from the last message, searches the retriever
for relevant documents, and stores the concatenated context + source IDs
in the state.
"""

from src.agents.rag_agent.states.state import AgentState
from src.shared.retrieval.pipeline import RetrieverPipeline


def retrieve(state: AgentState, *, retriever: RetrieverPipeline) -> dict:
    """Search the retriever and return context + sources.

    The retriever is injected via closure in build_graph() so that
    tests can provide a pre-loaded in-memory retriever instance.
    """
    query = state["messages"][-1].content
    results = retriever.search(query, k=3)

    context = "\n\n".join(doc["content"] for doc in results)
    sources = [doc["id"] for doc in results]

    return {"context": context, "sources": sources}
