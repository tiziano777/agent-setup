"""RLM Agent graph definition."""

from langgraph.graph import StateGraph

from src.agents.rlm_agent.nodes.search import search_node
from src.agents.rlm_agent.schemas import RLMAgentInput, RLMAgentOutput
from src.agents.rlm_agent.states import RLMAgentState


def create_agent() -> StateGraph:
    """Create RLM-based search agent graph.

    Single-node pipeline:
    Input → search_node (RLM completion) → Output

    Returns:
        Compiled StateGraph ready for invocation.
    """
    graph = StateGraph(RLMAgentState)

    # Add single node for RLM execution
    graph.add_node("search", search_node)

    # Set entry and exit
    graph.set_entry_point("search")
    graph.set_finish_point("search")

    return graph.compile()


# Compile at module level for caching
_agent = create_agent()


def get_agent() -> StateGraph:
    """Get compiled RLM Agent."""
    return _agent
