"""Shared type definitions used across agents."""

from typing import Annotated, Any

from langchain_core.messages import AnyMessage
from langgraph.graph import add_messages
from typing_extensions import TypedDict


class BaseAgentState(TypedDict):
    """Base state that all agents can extend.

    Provides the standard 'messages' key with the add_messages reducer.
    Agent-specific states should extend this.
    """

    messages: Annotated[list[AnyMessage], add_messages]


class HandoffPayload(TypedDict):
    """Payload for multi-agent handoffs."""

    target_agent: str
    messages: list[dict[str, Any]]
    metadata: dict[str, Any]
