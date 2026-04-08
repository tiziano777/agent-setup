"""RLM Agent state definitions."""

from typing import Annotated

from langchain_core.messages import AnyMessage
from langgraph.graph import add_messages
from typing_extensions import TypedDict


class RLMAgentState(TypedDict):
    """State for RLM-based search agent.

    Tracks the entire execution flow with full message history for
    observability in Phoenix.
    """

    # Input
    prompt: str  # Task prompt (e.g., "Find the SECRET_NUMBER in the text")
    context: str  # Long context text to search through

    # RLM execution
    rlm_response: str | None  # Final model response
    rlm_metadata: dict | None  # Execution trajectory from RLM
    rlm_status: str  # "pending" | "success" | "error"

    # Message history (for LangChain integration)
    messages: Annotated[list[AnyMessage], add_messages]
