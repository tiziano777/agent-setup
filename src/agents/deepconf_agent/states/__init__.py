"""Agent state definition for deepconf_agent."""

from typing import Annotated, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph import add_messages


class DeepConfAgentState(TypedDict):
    """State for deepconf single-node agent."""

    question: str
    messages: Annotated[list[AnyMessage], add_messages]
    reasoning_output: dict  # DeepConfOutput as dict
    final_answer: str
