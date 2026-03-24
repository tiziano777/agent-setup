"""agent1: Graph API definition.

Defines the agent as a LangGraph StateGraph.
Use this when you need explicit node/edge visualization,
conditional routing, or multi-agent composition via subgraphs.
"""

from langgraph.graph import END, START, StateGraph

from src.agents.agent1.nodes.example_node import process
from src.agents.agent1.states.state import AgentState


def build_graph() -> StateGraph:
    """Construct the StateGraph for this agent."""
    builder = StateGraph(AgentState)

    builder.add_node("process", process)

    builder.add_edge(START, "process")
    builder.add_edge("process", END)

    return builder


graph = build_graph().compile()
