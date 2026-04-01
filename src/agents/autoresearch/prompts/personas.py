"""Persona loader for agent prompt definitions.

Loads agent persona ``.md`` files with YAML frontmatter from the
``agent/agents/`` directory and produces ``AgentPersona`` dataclasses.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

_AGENTS_DIR = Path(__file__).resolve().parent.parent / "personas" / "agents"


@dataclass
class AgentPersona:
    """Structured representation of an agent loaded from its .md file."""

    name: str
    role: str
    model_hint: str
    tools: list[str] = field(default_factory=list)
    triggers: list[str] = field(default_factory=list)
    system_prompt: str = ""
    protocol: str = ""
    examples: str = ""
    guardrails: str = ""
    full_document: str = ""


def load_persona(agent_name: str) -> AgentPersona:
    """Load a single persona by name (e.g. ``'loop-operator'``)."""
    md_path = _AGENTS_DIR / f"{agent_name}.md"
    if not md_path.exists():
        raise FileNotFoundError(f"Agent persona file not found: {md_path}")
    return _parse_agent_md(md_path)


def load_all_personas() -> dict[str, AgentPersona]:
    """Load all agent personas from the agents directory."""
    personas: dict[str, AgentPersona] = {}
    for md_file in sorted(_AGENTS_DIR.glob("*.md")):
        persona = _parse_agent_md(md_file)
        personas[persona.name] = persona
    return personas


def _parse_agent_md(path: Path) -> AgentPersona:
    text = path.read_text(encoding="utf-8")
    frontmatter, body = _split_frontmatter(text)
    sections = _extract_sections(body)
    return AgentPersona(
        name=frontmatter.get("name", path.stem),
        role=frontmatter.get("role", ""),
        model_hint=frontmatter.get("model", "sonnet"),
        tools=frontmatter.get("tools", []),
        triggers=frontmatter.get("triggers", []),
        system_prompt=sections.get("system prompt", ""),
        protocol=sections.get("protocol", ""),
        examples=sections.get("examples", ""),
        guardrails=sections.get("guardrails", ""),
        full_document=text,
    )


def _split_frontmatter(text: str) -> tuple[dict, str]:
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)", text, re.DOTALL)
    if not match:
        return {}, text
    fm_text, body = match.group(1), match.group(2)
    try:
        fm = yaml.safe_load(fm_text) or {}
    except yaml.YAMLError:
        fm = {}
    return fm, body


def _extract_sections(body: str) -> dict[str, str]:
    parts = re.split(r"^## (.+)$", body, flags=re.MULTILINE)
    sections: dict[str, str] = {}
    for i in range(1, len(parts) - 1, 2):
        header = parts[i].strip().lower()
        content = parts[i + 1].strip()
        sections[header] = content
    return sections
