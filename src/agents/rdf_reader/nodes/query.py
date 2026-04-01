"""Query node for rdf_reader.

Reads the instruction from state, asks the LLM to generate a SPARQL
SELECT query, executes it via the dispatcher, then formats a
natural-language answer from the results.
"""

from __future__ import annotations

import logging
import re

from langchain_core.messages import AIMessage

from src.agents.rdf_reader.config import settings
from src.agents.rdf_reader.prompts.system import ANSWER_PROMPT, QUERY_PROMPT
from src.agents.rdf_reader.states.state import AgentState
from src.shared.llm import get_llm
from src.shared.rdf_memory.dispatcher import RDFDispatcher

logger = logging.getLogger(__name__)

_SPARQL_BLOCK_RE = re.compile(r"```(?:sparql)?\s*\n?(.*?)```", re.DOTALL)


def _extract_sparql(text: str) -> str:
    """Parse SPARQL from a code block in LLM output."""
    match = _SPARQL_BLOCK_RE.search(text)
    if match:
        return match.group(1).strip()
    return text.strip()


def _format_bindings(bindings: list[dict]) -> str:
    """Format SPARQL result bindings into a readable string."""
    if not bindings:
        return "No results found."
    rows: list[str] = []
    for b in bindings[:50]:
        parts = [f"{k}={v.get('value', '')}" for k, v in b.items()]
        rows.append(" | ".join(parts))
    return "\n".join(rows)


def query(state: AgentState, *, dispatcher: RDFDispatcher, session_uuid: str) -> dict:
    """Query the session KB and return a precise answer.

    The dispatcher is injected via functools.partial in build_graph().
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

    result = dispatcher.dispatch(
        sparql=sparql,
        target_lifecycle="session",
        session_uuid=session_uuid,
    )

    if not result["success"]:
        error_msg = result.get("error", "Unknown error")
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
        result = dispatcher.dispatch(
            sparql=sparql,
            target_lifecycle="session",
            session_uuid=session_uuid,
        )
        if not result["success"]:
            return {
                "sparql_result": "",
                "messages": [AIMessage(content=f"Query failed: {result.get('error')}")],
            }

    raw_bindings = result["data"].get("results", {}).get("bindings", [])
    formatted_results = _format_bindings(raw_bindings)

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
