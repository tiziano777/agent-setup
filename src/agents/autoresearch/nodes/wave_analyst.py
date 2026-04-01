"""Wave analyst node — post-wave LLM analysis with early stop detection."""

from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from src.agents.autoresearch.db.connector import PostgresConnector
from src.agents.autoresearch.db.repositories import AgentDecisionRepository
from src.agents.autoresearch.prompts.personas import load_persona
from src.agents.autoresearch.schemas.entities import AgentDecision
from src.agents.autoresearch.states.state import AutoresearchState
from src.shared.llm import get_llm


def _extract_json(text: str) -> str:
    match = re.search(r"```(?:json)?\s*\n(.*?)\n```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    for s, e in [("{", "}"), ("[", "]")]:
        si = text.find(s)
        ei = text.rfind(e)
        if si != -1 and ei > si:
            return text[si : ei + 1]
    return text


def wave_analyst(state: AutoresearchState) -> dict[str, Any]:
    """Analyze wave results via LLM. Returns early stop signal and insights."""
    persona = load_persona("report-analyst")
    llm = get_llm(temperature=0.3)

    sweep_config = state.get("sweep_config", {})
    completed = state.get("experiments_completed", 0)
    max_exp = sweep_config.get("budget", {}).get("max_experiments", 100)
    wall_time = state.get("wall_time_used_hours", 0.0)
    max_wall = sweep_config.get("budget", {}).get("max_wall_time_hours", 8.0)
    wave_results = state.get("wave_results", [])
    wave_number = state.get("wave_number", 0)

    system_prompt = persona.system_prompt
    if persona.protocol:
        system_prompt += f"\n\n## Protocol\n\n{persona.protocol}"
    system_prompt += (
        "\n\n## Additional context\n\n"
        "You are analyzing results after a wave of experiments. "
        "Respond concisely with structured JSON."
    )

    user_content = (
        f"## Wave {wave_number} results\n\n"
        f"{json.dumps(wave_results, indent=2)}\n\n"
        f"Budget: {completed}/{max_exp} experiments\n"
        f"Wall time: {wall_time:.1f}/{max_wall}h\n\n"
        "Respond ONLY with JSON:\n"
        '- "should_continue": boolean\n'
        '- "early_stop_reason": string or null\n'
        '- "insights": array of 1-3 strings\n'
        '- "search_space_adjustments": object or null\n'
    )

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_content),
    ]

    response = llm.invoke(messages)
    content = response.content if hasattr(response, "content") else str(response)

    # Parse
    should_continue = True
    insights: list[str] = []
    try:
        data = json.loads(_extract_json(content))
        should_continue = data.get("should_continue", True)
        insights = data.get("insights", [])
    except (json.JSONDecodeError, KeyError):
        insights = ["Failed to parse analyst response."]

    # Token tracking
    usage = {}
    if hasattr(response, "response_metadata"):
        meta = response.response_metadata or {}
        tu = meta.get("token_usage") or meta.get("usage", {})
        usage = {
            "prompt_tokens": tu.get("prompt_tokens", 0),
            "completion_tokens": tu.get("completion_tokens", 0),
        }

    # Log decision
    try:
        connector = PostgresConnector()
        AgentDecisionRepository(connector).save(AgentDecision(
            session_id=state["session_id"],
            agent_role="wave_analyst",
            decision_type="post_wave_analysis",
            output_json={"should_continue": should_continue, "insights": insights},
            reasoning="; ".join(insights) if insights else "",
            wave_number=wave_number,
            token_usage=usage,
        ))
    except Exception:
        pass

    return {
        "should_continue": should_continue,
        "messages": [
            AIMessage(
                content=f"Wave analyst: continue={should_continue}. "
                + ("; ".join(insights[:2]) if insights else "No insights.")
            ),
        ],
    }
