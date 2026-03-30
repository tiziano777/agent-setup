"""Configuration for knowledge_agent.

Agent-specific settings. Uses low temperature for factual, grounded
responses from the knowledge graph.
"""

from dataclasses import dataclass, field


@dataclass
class AgentSettings:
    """Settings specific to this agent."""

    name: str = "knowledge_agent"
    description: str = "Knowledge graph agent with Cognee ECL (Extract-Cognify-Load) and sandbox"
    model: str = "llm"
    temperature: float = 0.2
    max_tokens: int = 2048
    tags: list[str] = field(default_factory=lambda: ["knowledge-graph", "cognee", "sandbox"])


settings = AgentSettings()
