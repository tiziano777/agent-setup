"""RLM Agent: Graph API definition.

Defines the agent as a single-node StateGraph that executes RLM completion
on long contexts to find answers to queries. Uses recursive problem
decomposition to handle 50k+ line contexts.

For the Functional API see pipelines/pipeline.py.
"""

from langgraph.graph import StateGraph

from src.agents.rlm_agent.nodes.search import search_node
from src.agents.rlm_agent.states import RLMAgentState


def build_graph() -> StateGraph:
    """Construct the RLM search agent StateGraph.

    Single-node pipeline:
    Input → search_node (RLM completion) → Output

    Returns:
        Compiled StateGraph ready for invocation.
    """
    graph_builder = StateGraph(RLMAgentState)

    # Add single node for RLM execution
    graph_builder.add_node("search", search_node)

    # Set entry and exit
    graph_builder.set_entry_point("search")
    graph_builder.set_finish_point("search")

    return graph_builder.compile()


# Compile at module level for caching
graph = build_graph()
