"""Hyperparams advisor node — proposes configs via LLM."""

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
    for start_c, end_c in [("{", "}"), ("[", "]")]:
        s = text.find(start_c)
        e = text.rfind(end_c)
        if s != -1 and e > s:
            return text[s : e + 1]
    return text


def hyperparams_advisor(state: AutoresearchState) -> dict[str, Any]:
    """LLM proposes next wave of hyperparameter configurations."""
    persona = load_persona("hyperparams-advisor")
    llm = get_llm(temperature=0.7)

    sweep_config = state.get("sweep_config", {})
    waves_parallel = sweep_config.get("strategy", {}).get("waves_parallel", 4)
    trajectory = state.get("trajectory", [])
    importance = state.get("parameter_importance", {})
    similar = state.get("similar_experiments", [])
    blacklist = state.get("blacklist", [])
    search_space = state.get("active_search_space", {})
    wave_number = state.get("wave_number", 0)

    system_prompt = persona.system_prompt
    if persona.protocol:
        system_prompt += f"\n\n## Protocol\n\n{persona.protocol}"

    # Build context
    recent = trajectory[-10:] if len(trajectory) > 10 else trajectory
    context_parts = [
        "## Search space\n",
        json.dumps(search_space, indent=2),
        f"\n\n## Recent experiments ({len(recent)} of {len(trajectory)} total)\n",
        json.dumps(recent, indent=2),
    ]
    if importance:
        context_parts.append(
            f"\n\n## Parameter importance\n{json.dumps(importance, indent=2)}"
        )
    if similar:
        context_parts.append(
            f"\n\n## Similar experiments\n{json.dumps(similar[:3], indent=2)}"
        )
    if blacklist:
        context_parts.append(
            f"\n\n## Blacklisted regions\n{json.dumps(blacklist, indent=2)}"
        )

    user_content = (
        "\n".join(context_parts)
        + f"\n\n## Task\n\nPropose exactly **{waves_parallel}** configs.\n"
        "Respond ONLY with JSON: "
        '`{"proposals": [{"reasoning": "...", "hyperparams": {...}}, ...]}`\n'
        "All values MUST respect search space bounds."
    )

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_content),
    ]

    response = llm.invoke(messages)
    content = response.content if hasattr(response, "content") else str(response)

    # Token tracking
    usage = {}
    if hasattr(response, "response_metadata"):
        meta = response.response_metadata or {}
        token_usage = meta.get("token_usage") or meta.get("usage", {})
        usage = {
            "prompt_tokens": token_usage.get("prompt_tokens", 0),
            "completion_tokens": token_usage.get("completion_tokens", 0),
        }

    # Parse proposals
    wave_configs: list[dict[str, Any]] = []
    try:
        data = json.loads(_extract_json(content))
        if isinstance(data, dict):
            proposals = data.get("proposals", [])
        elif isinstance(data, list):
            proposals = data
        else:
            proposals = []

        for item in proposals:
            if isinstance(item, dict) and "hyperparams" in item:
                wave_configs.append(item["hyperparams"])
    except (json.JSONDecodeError, KeyError):
        pass  # Will be caught by validate_proposals fallback

    # Log decision
    try:
        connector = PostgresConnector()
        AgentDecisionRepository(connector).save(AgentDecision(
            session_id=state["session_id"],
            agent_role="hyperparams_advisor",
            decision_type="propose_configs",
            output_json={"proposals_count": len(wave_configs)},
            reasoning=f"Proposed {len(wave_configs)} configs for wave {wave_number}",
            wave_number=wave_number,
            token_usage=usage,
        ))
    except Exception:
        pass

    return {
        "wave_configs": wave_configs,
        "messages": [
            AIMessage(
                content=f"Advisor proposed {len(wave_configs)} configs "
                f"for wave {wave_number}."
            ),
        ],
    }
