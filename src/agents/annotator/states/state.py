"""Annotator agent state definition."""

from typing import Annotated, Any

from langchain_core.messages import AnyMessage
from langgraph.graph import add_messages
from typing_extensions import TypedDict


class AnnotatorState(TypedDict):
    """State for the LLM-as-judge annotator graph.

    Tracks batch processing progress through a JSONL file.
    """

    messages: Annotated[list[AnyMessage], add_messages]

    all_entries: list[dict[str, Any]]
    current_batch: list[dict[str, Any]]
    batch_index: int
    results: list[dict[str, Any]]

    status: str
    total_entries: int
    processed_count: int
