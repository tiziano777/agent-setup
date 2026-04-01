"""Crash diagnostician node — analyzes failed experiments."""

from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from src.agents.autoresearch.prompts.personas import load_persona
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


def crash_diagnostician(state: AutoresearchState) -> dict[str, Any]:
    """Analyze crashed experiments and update blacklist / crash patterns."""
    persona = load_persona("crash-diagnostician")
    llm = get_llm(temperature=0.2)

    trajectory = state.get("trajectory", [])
    crashed = [t for t in trajectory if t.get("status") == "crashed"]

    if not crashed:
        return {
            "messages": [AIMessage(content="No crashed experiments to diagnose.")],
        }

    system_prompt = persona.system_prompt
    if persona.protocol:
        system_prompt += f"\n\n## Protocol\n\n{persona.protocol}"

    user_content = (
        f"## Crashed experiments ({len(crashed)})\n\n"
        f"{json.dumps(crashed[-5:], indent=2)}\n\n"
        "Analyze and respond with JSON:\n"
        '- "classifications": array of {run_id, failure_type, root_cause}\n'
        '- "blacklist": array of HP region dicts to avoid\n'
        '- "recommendations": array of strings\n'
    )

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_content),
    ]

    response = llm.invoke(messages)
    content = response.content if hasattr(response, "content") else str(response)

    blacklist = state.get("blacklist", [])
    patterns = state.get("crash_patterns", [])

    try:
        data = json.loads(_extract_json(content))
        new_blacklist = data.get("blacklist", [])
        blacklist = blacklist + new_blacklist
        recs = data.get("recommendations", [])
        patterns = patterns + recs
    except (json.JSONDecodeError, KeyError):
        patterns.append(f"Diagnosed {len(crashed)} crashes (parse failed).")

    return {
        "blacklist": blacklist,
        "crash_patterns": patterns,
        "messages": [
            AIMessage(
                content=f"Diagnostician: analyzed {len(crashed)} crashes, "
                f"{len(blacklist)} blacklisted regions."
            ),
        ],
    }
