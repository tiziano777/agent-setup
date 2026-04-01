"""Loop operator node — decides next sweep action via LLM."""

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

_VALID_ACTIONS = frozenset({"next_wave", "pause", "stop", "request_diagnostics"})


def _extract_json(text: str) -> str:
    match = re.search(r"```(?:json)?\s*\n(.*?)\n```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    for start_c, end_c in [("{", "}"), ("[", "]")]:
        s = text.find(start_c)
        e = text.rfind(end_c)
        if s != -1 and e > s:
            return text[s : e + 1]
    return text


def loop_operator(state: AutoresearchState) -> dict[str, Any]:
    """LLM decides: next_wave, stop, pause, or request_diagnostics."""
    persona = load_persona("loop-operator")
    llm = get_llm(temperature=0.3)

    sweep_config = state.get("sweep_config", {})
    completed = state.get("experiments_completed", 0)
    remaining = state.get("experiments_remaining", 0)
    wall_time = state.get("wall_time_used_hours", 0.0)
    max_wall = sweep_config.get("budget", {}).get("max_wall_time_hours", 8.0)
    max_exp = sweep_config.get("budget", {}).get("max_experiments", 100)
    crash_patterns = state.get("crash_patterns", [])
    best_metric = state.get("best_metric_value")
    wave_number = state.get("wave_number", 0)

    crash_rate = 0.0
    trajectory = state.get("trajectory", [])
    if trajectory:
        crashed = sum(1 for t in trajectory if t.get("status") == "crashed")
        crash_rate = crashed / len(trajectory)

    system_prompt = persona.system_prompt
    if persona.protocol:
        system_prompt += f"\n\n## Protocol\n\n{persona.protocol}"
    if persona.guardrails:
        system_prompt += f"\n\n## Guardrails\n\n{persona.guardrails}"

    user_content = (
        "## Current sweep state\n\n"
        f"- Experiments: {completed}/{max_exp}\n"
        f"- Wall time: {wall_time:.1f}/{max_wall}h\n"
        f"- Crash rate: {crash_rate:.2f}\n"
        f"- Best metric: {best_metric}\n"
        f"- Wave: {wave_number}\n"
        f"- Crash patterns: {crash_patterns}\n\n"
        "## Decision required\n\n"
        "Respond ONLY with a JSON object:\n"
        '- "action": "next_wave" | "stop" | "pause" | "request_diagnostics"\n'
        '- "reason": human-readable explanation\n'
        f'- "wave_number": {wave_number}\n'
        '- "best_metric": numeric or null\n'
    )

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_content),
    ]

    response = llm.invoke(messages)
    content = response.content if hasattr(response, "content") else str(response)

    # Extract token usage
    usage = {}
    if hasattr(response, "response_metadata"):
        meta = response.response_metadata or {}
        token_usage = meta.get("token_usage") or meta.get("usage", {})
        usage = {
            "prompt_tokens": token_usage.get("prompt_tokens", 0),
            "completion_tokens": token_usage.get("completion_tokens", 0),
        }

    # Parse response
    try:
        data = json.loads(_extract_json(content))
        action = data.get("action", "next_wave")
        reason = data.get("reason", "")
    except (json.JSONDecodeError, KeyError):
        # Default to next_wave on parse failure
        action = "next_wave"
        reason = "Failed to parse LLM response, continuing with next wave."

    if action not in _VALID_ACTIONS:
        action = "next_wave"

    # Budget exhaustion override
    if remaining <= 0:
        action = "stop"
        reason = "Budget exhausted."

    # Log decision
    try:
        connector = PostgresConnector()
        decision_repo = AgentDecisionRepository(connector)
        decision_repo.save(AgentDecision(
            session_id=state["session_id"],
            agent_role="loop_operator",
            decision_type=action,
            output_json={"action": action, "reason": reason},
            reasoning=reason,
            wave_number=wave_number,
            token_usage=usage,
        ))
    except Exception:
        pass  # Non-critical

    return {
        "loop_action": action,
        "loop_reason": reason,
        "wave_number": wave_number + 1 if action == "next_wave" else wave_number,
        "messages": [AIMessage(content=f"Loop operator: {action} — {reason}")],
    }
