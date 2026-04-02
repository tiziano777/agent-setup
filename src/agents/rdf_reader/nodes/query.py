"""Query node for rdf_reader.

Reads the instruction from state, asks the LLM to generate a SPARQL
SELECT query, executes it via the rdf_query tool, then formats a
natural-language answer from the results.
"""

from __future__ import annotations

import logging
import re

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig

from src.agents.rdf_reader.config import settings
from src.agents.rdf_reader.prompts.system import ANSWER_PROMPT, QUERY_PROMPT
from src.agents.rdf_reader.states.state import AgentState
from src.agents.rdf_reader.tools import rdf_query
from src.shared.llm import get_llm

logger = logging.getLogger(__name__)

_SPARQL_BLOCK_RE = re.compile(r"```(?:sparql)?\s*\n?(.*?)```", re.DOTALL)


def _extract_sparql(text: str) -> str:
    """Parse SPARQL from a code block in LLM output."""
    match = _SPARQL_BLOCK_RE.search(text)
    if match:
        return match.group(1).strip()
    return text.strip()


def _extract_results_from_tool_output(result_text: str) -> str:
    """Extract results section from rdf_query tool output.

    Tool output format: "OK [SELECT] on <...> (N result(s)):\n<results>"
    Returns just the results part (after the header).
    """
    if not result_text.startswith("OK"):
        return ""

    # Find the first newline - everything after is results
    newline_idx = result_text.find("\n")
    if newline_idx == -1:
        # No results (single line like "OK [SELECT] on <...>: no results.")
        if "no results" in result_text.lower():
            return "No results found."
        return result_text

    return result_text[newline_idx + 1:].rstrip()


def _is_success(result_text: str) -> bool:
    """Check if result_text indicates success."""
    return result_text.startswith("OK ")


def query(
    state: AgentState,
    *,
    session_uuid: str,
    config: RunnableConfig | None = None,
) -> dict:
    """Query the session KB and return a precise answer.

    Uses the rdf_query tool for all SPARQL operations, which ensures
    automatic tracing in the LangGraph execution trace.

    Args:
        state: Current agent state.
        session_uuid: Session identifier for RDF graph routing.
        config: LangChain RunnableConfig with execution context (propagates
                run_manager to tool for unified trace linkage).
    """
    instruction = state["instruction"]
    llm = get_llm(temperature=settings.temperature)

    sparql_response = llm.invoke(
        [
            {"role": "system", "content": QUERY_PROMPT},
            {"role": "user", "content": instruction},
        ]
    )

    sparql = _extract_sparql(sparql_response.content)

    result_text = rdf_query.invoke(
        {"sparql_command": sparql, "session_uuid": session_uuid},
        config=config,  # ← Pass config for trace linkage
    )

    if not _is_success(result_text):
        error_msg = result_text
        logger.warning("SELECT failed: %s. Retrying with LLM feedback.", error_msg)
        retry_response = llm.invoke(
            [
                {"role": "system", "content": QUERY_PROMPT},
                {"role": "user", "content": instruction},
                {"role": "assistant", "content": sparql_response.content},
                {
                    "role": "user",
                    "content": f"The SPARQL above failed with: {error_msg}\n"
                    "Please fix the query and output corrected SPARQL.",
                },
            ]
        )
        sparql = _extract_sparql(retry_response.content)
        result_text = rdf_query.invoke(
            {"sparql_command": sparql, "session_uuid": session_uuid},
            config=config,
        )
        if not _is_success(result_text):
            return {
                "sparql_result": "",
                "messages": [AIMessage(content=f"Query failed: {result_text}")],
            }

    formatted_results = _extract_results_from_tool_output(result_text)

    answer_response = llm.invoke(
        [
            {"role": "system", "content": ANSWER_PROMPT},
            {
                "role": "user",
                "content": f"Question: {instruction}\n\nSPARQL Results:\n{formatted_results}",
            },
        ]
    )

    return {
        "sparql_result": formatted_results,
        "messages": [AIMessage(content=answer_response.content)],
    }

