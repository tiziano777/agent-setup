"""Extract node for rdf_reader.

Reads the context text from state, asks the LLM to generate SPARQL
INSERT DATA statements, executes them via the dispatcher, and verifies
the triple count.
"""

from __future__ import annotations

import logging
import re

from langchain_core.messages import AIMessage

from src.agents.rdf_reader.config import settings
from src.agents.rdf_reader.prompts.system import EXTRACT_PROMPT
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


def extract(state: AgentState, *, dispatcher: RDFDispatcher, session_uuid: str) -> dict:
    """Read context text and extract RDF triples into the session graph.

    The dispatcher is injected via functools.partial in build_graph().
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

    result = dispatcher.dispatch(
        sparql=sparql,
        target_lifecycle="session",
        session_uuid=session_uuid,
    )

    if not result["success"]:
        error_msg = result.get("error", "Unknown error")
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
        result = dispatcher.dispatch(
            sparql=sparql,
            target_lifecycle="session",
            session_uuid=session_uuid,
        )
        if not result["success"]:
            return {
                "triple_count": 0,
                "messages": [AIMessage(content=f"Triple extraction failed: {result.get('error')}")],
            }

    count_result = dispatcher.dispatch(
        sparql="PREFIX ex: <http://example.org/>\nSELECT (COUNT(*) AS ?count) WHERE { ?s ?p ?o }",
        target_lifecycle="session",
        session_uuid=session_uuid,
    )

    triple_count = 0
    if count_result["success"]:
        bindings = count_result["data"].get("results", {}).get("bindings", [])
        if bindings:
            triple_count = int(bindings[0]["count"]["value"])

    return {
        "triple_count": triple_count,
        "messages": [
            AIMessage(content=f"Extracted {triple_count} RDF triples into session graph.")
        ],
    }
