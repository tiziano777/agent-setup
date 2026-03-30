"""Configuration for code_runner.

Agent-specific settings. Inherits LLM defaults from shared config
but can override model, temperature, and other parameters.
"""

from dataclasses import dataclass, field


@dataclass
class AgentSettings:
    """Settings specific to this agent."""

    name: str = "code_runner"
    description: str = "Python code execution agent with Docker sandbox"
    model: str = "llm"
    temperature: float = 0.2
    max_tokens: int = 2048
    tags: list[str] = field(default_factory=lambda: ["coding", "sandbox", "python"])


settings = AgentSettings()
