"""Configuration for rag_agent.

Agent-specific settings. Inherits LLM defaults from shared config
but can override model, temperature, and other parameters.
"""

from dataclasses import dataclass, field


@dataclass
class AgentSettings:
    """Settings specific to this agent."""

    name: str = "rag_agent"
    description: str = "RAG agent with hybrid retrieval (BM25 + Vector + RRF)"
    model: str = "llm"
    temperature: float = 0.2
    max_tokens: int = 2048
    search_k: int = 3
    tags: list[str] = field(default_factory=lambda: ["rag", "retrieval", "hybrid-search"])


settings = AgentSettings()
