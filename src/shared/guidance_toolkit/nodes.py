"""Pre-built LangGraph node factories for guidance structured generation.

Each factory returns a node function compatible with LangGraph's
``StateGraph.add_node()``.  Nodes follow the project pattern:
receive state (TypedDict), return a partial state update dict.

Usage::

    from src.shared.guidance_toolkit import create_guidance_structured_node
    from pydantic import BaseModel

    class Analysis(BaseModel):
        sentiment: str
        confidence: float
        summary: str

    builder = StateGraph(AgentState)
    builder.add_node("analyze", create_guidance_structured_node(Analysis))
"""

from __future__ import annotations

import logging
from typing import Callable

from src.shared.guidance_toolkit.config import GuidanceSettings

logger = logging.getLogger(__name__)


def create_guidance_structured_node(
    schema: type,
    *,
    settings: GuidanceSettings | None = None,
    query_key: str = "messages",
    result_key: str = "guidance_output",
    system_prompt: str | None = None,
    temperature: float | None = None,
) -> Callable[[dict], dict]:
    """Create a node that generates structured JSON from the last message.

    Reads the user query from state (default: last message content),
    generates JSON constrained to the Pydantic schema, and stores
    the parsed dict in ``state[result_key]``.

    Args:
        schema: Pydantic BaseModel class defining the output structure.
        settings: Configuration dataclass.  Uses defaults when *None*.
        query_key: State key to read the query from.
            If ``"messages"``, uses the last message content.
        result_key: State key to write the structured output to.
        system_prompt: Optional system prompt for the generation.
        temperature: Sampling temperature override.

    Usage::

        builder.add_node("extract", create_guidance_structured_node(Person))
    """

    def guidance_structured_node(state: dict) -> dict:
        from src.shared.guidance_toolkit.programs import structured_json

        if query_key == "messages":
            messages = state.get("messages", [])
            if not messages:
                return {result_key: {}}
            last = messages[-1]
            query = last.content if hasattr(last, "content") else str(last)
        else:
            query = state.get(query_key, "")

        if not query:
            return {result_key: {}}

        result = structured_json(
            schema,
            query,
            system_prompt=system_prompt,
            temperature=temperature,
        )

        logger.info(
            "Guidance structured node: generated %d fields for '%s...'",
            len(result),
            query[:50],
        )
        return {result_key: result}

    return guidance_structured_node


def create_guidance_select_node(
    options: list[str],
    *,
    settings: GuidanceSettings | None = None,
    query_key: str = "messages",
    result_key: str = "guidance_selection",
    system_prompt: str | None = None,
    temperature: float | None = None,
) -> Callable[[dict], dict]:
    """Create a node that selects one option from a fixed list.

    Reads the user query from state (default: last message content),
    forces selection from the provided options using guidance's
    ``select()`` primitive, and stores the choice in ``state[result_key]``.

    Args:
        options: List of allowed string values.
        settings: Configuration dataclass.  Uses defaults when *None*.
        query_key: State key to read the query from.
            If ``"messages"``, uses the last message content.
        result_key: State key to write the selection to.
        system_prompt: Optional system prompt for the selection.
        temperature: Sampling temperature override.

    Usage::

        builder.add_node("classify", create_guidance_select_node(
            ["positive", "negative", "neutral"],
            system_prompt="Classify the sentiment of the user message.",
        ))
    """

    def guidance_select_node(state: dict) -> dict:
        from src.shared.guidance_toolkit.programs import constrained_select

        if query_key == "messages":
            messages = state.get("messages", [])
            if not messages:
                return {result_key: ""}
            last = messages[-1]
            query = last.content if hasattr(last, "content") else str(last)
        else:
            query = state.get(query_key, "")

        if not query:
            return {result_key: ""}

        result = constrained_select(
            options,
            query,
            system_prompt=system_prompt,
            temperature=temperature,
        )

        logger.info(
            "Guidance select node: selected '%s' for '%s...'",
            result,
            query[:50],
        )
        return {result_key: result}

    return guidance_select_node
