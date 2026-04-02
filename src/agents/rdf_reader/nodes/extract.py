"""Extract node for rdf_reader.

Reads the context text from state, asks the LLM to generate SPARQL
INSERT DATA statements, executes them via the rdf_query tool, and verifies
the triple count.
"""

from __future__ import annotations

import logging
import re

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig

from src.agents.rdf_reader.config import settings
from src.agents.rdf_reader.prompts.system import EXTRACT_PROMPT
from src.agents.rdf_reader.states.state import AgentState
from src.agents.rdf_reader.tools import rdf_query
from src.shared.llm import get_llm

logger = logging.getLogger(__name__)

_SPARQL_BLOCK_RE = re.compile(r"```(?:sparql)?\s*\n?(.*?)```", re.DOTALL)
_COUNT_RE = re.compile(r"count=(\d+)")


def _extract_sparql(text: str) -> str:
    """Parse SPARQL from a code block in LLM output."""
    match = _SPARQL_BLOCK_RE.search(text)
    if match:
        return match.group(1).strip()
    return text.strip()


def _parse_triple_count(result_text: str) -> int:
    """Extract triple count from rdf_query result string."""
    match = _COUNT_RE.search(result_text)
    if match:
        return int(match.group(1))
    return 0


def _is_success(result_text: str) -> bool:
    """Check if result_text indicates success."""
    return result_text.startswith("OK ")


def extract(
    state: AgentState,
    *,
    session_uuid: str,
    config: RunnableConfig | None = None,
) -> dict:
    """Read context text and extract RDF triples into the session graph.

    Uses the rdf_query tool for all SPARQL operations, which ensures
    automatic tracing in the LangGraph execution trace.

    Args:
        state: Current agent state.
        session_uuid: Session identifier for RDF graph routing.
        config: LangChain RunnableConfig with execution context (propagates
                run_manager to tool for unified trace linkage).
    """
    context = state["context"]
    llm = get_llm(temperature=settings.temperature, max_tokens=settings.max_tokens)

    response = llm.invoke(
        [
            {"role": "system", "content": EXTRACT_PROMPT},
            {"role": "user", "content": context},
        ]
    )

    sparql = _extract_sparql(response.content)

    result_text = rdf_query.invoke(
        {"sparql_command": sparql, "session_uuid": session_uuid},
        config=config,  # ← Pass config for trace linkage
    )

    if not _is_success(result_text):
        error_msg = result_text
        logger.warning("INSERT failed: %s. Retrying with LLM feedback.", error_msg)
        retry_response = llm.invoke(
            [
                {"role": "system", "content": EXTRACT_PROMPT},
                {"role": "user", "content": context},
                {"role": "assistant", "content": response.content},
                {
                    "role": "user",
                    "content": f"The SPARQL above failed with: {error_msg}\n"
                    "Please fix the query and output corrected SPARQL.",
                },
            ]
        )
        sparql = _extract_sparql(retry_response.content)
        result_text = rdf_query.invoke({"sparql_command": sparql, "session_uuid": session_uuid}, config=config)
        if not _is_success(result_text):
            return {
                "triple_count": 0,
                "messages": [AIMessage(content=f"Triple extraction failed: {result_text}")],
            }

    count_query = (
        "PREFIX ex: <http://example.org/>\n"
        "SELECT (COUNT(*) AS ?count) WHERE { ?s ?p ?o }"
    )
    count_result_text = rdf_query.invoke({
        "sparql_command": count_query,
        "session_uuid": session_uuid
    }, config=config)

    triple_count = _parse_triple_count(count_result_text)

    return {
        "triple_count": triple_count,
        "messages": [
            AIMessage(content=f"Extracted {triple_count} RDF triples into session graph.")
        ],
    }

