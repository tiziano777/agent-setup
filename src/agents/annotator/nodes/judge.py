"""LLM judge node — sends batch to LLM and parses structured verdict."""

import json
import logging
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from src.agents.annotator.config import settings
from src.agents.annotator.prompts import load_prompt
from src.agents.annotator.states import AnnotatorState
from src.shared.llm import get_llm

logger = logging.getLogger(__name__)


def _format_batch(batch: list[dict[str, Any]]) -> str:
    """Format K entries into a compact user message for the LLM."""
    items = []
    for entry in batch:
        cand = entry["candidates"][0]
        diag = cand["diagnostics"]
        items.append(json.dumps({
            "_id_hash": entry["metadata"]["_id_hash"],
            "gold": entry["gold_content"][:500],
            "candidate": cand["candidate"]["content"][:500],
            "diagnostics": diag,
        }, ensure_ascii=False))
    return "\n".join(items)


def _parse_response(content: str) -> list[dict[str, Any]]:
    """Parse JSON array from LLM response, with fallback for code blocks."""
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    match = re.search(r"```(?:json)?\s*(.*?)\s*```", content, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    logger.error("Failed to parse LLM response: %s", content[:200])
    return []


def _invoke_with_retry(llm, messages: list, max_retries: int = 3):
    """Invoke LLM with retry on transient errors (404, 429, 500)."""
    import time

    for attempt in range(max_retries):
        try:
            return llm.invoke(messages)
        except Exception as e:
            error_str = str(e)
            is_retriable = any(code in error_str for code in ("404", "429", "500", "503"))
            if not is_retriable or attempt == max_retries - 1:
                raise
            wait = 2 ** attempt
            logger.warning("LLM call failed (attempt %d/%d): %s. Retrying in %ds...",
                           attempt + 1, max_retries, error_str[:100], wait)
            time.sleep(wait)


def judge(state: AnnotatorState) -> dict[str, Any]:
    """Call LLM to judge the current batch of entries."""
    llm = get_llm(
        model=settings.model,
        temperature=settings.temperature,
        max_tokens=settings.max_tokens,
    )

    system_prompt = load_prompt()
    user_content = _format_batch(state["current_batch"])

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_content),
    ]

    response = _invoke_with_retry(llm, messages)
    verdicts = _parse_response(response.content)

    logger.info("Judged %d entries, got %d verdicts", len(state["current_batch"]), len(verdicts))

    return {
        "results": state.get("results", []) + verdicts,
        "messages": [messages[1], response],
        "status": "writing",
    }
