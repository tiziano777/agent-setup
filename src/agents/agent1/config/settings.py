"""Configuration for agent1.

Agent-specific settings. Inherits LLM defaults from shared config
but can override model, temperature, and other parameters.
"""

from dataclasses import dataclass, field


@dataclass
class AgentSettings:
    """Settings specific to this agent."""

    name: str = "agent1"
    description: str = "Description of agent1"
    model: str = "llm"
    temperature: float = 0.7
    max_tokens: int = 2048
    tags: list[str] = field(default_factory=list)


settings = AgentSettings()
