"""State definition for knowledge_agent.

Defines the TypedDict that flows through the graph.
The `messages` key uses LangGraph's built-in `add_messages` reducer
so that message lists accumulate correctly across nodes.
"""

from typing import Annotated

from langchain_core.messages import AnyMessage
from langgraph.graph import add_messages
from typing_extensions import TypedDict


class AgentState(TypedDict):
    """Core state shared across all nodes in this agent's graph."""

    messages: Annotated[list[AnyMessage], add_messages]
    # Add agent-specific state keys below:
    # context: str
    # iteration_count: int
