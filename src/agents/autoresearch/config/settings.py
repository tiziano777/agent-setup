"""Agent-level settings for the autoresearch agent."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class AutoresearchSettings:
    """Configuration for the autoresearch agent (environment-driven defaults)."""

    name: str = "autoresearch"
    description: str = "AutoEvolve-inspired hyperparameter optimization"
    model: str = field(
        default_factory=lambda: os.getenv("DEFAULT_MODEL", "llm")
    )
    temperature: float = 0.7
    max_tokens: int = 4096
    max_total_tokens: int = 500_000
    db_uri: str = field(
        default_factory=lambda: os.getenv(
            "PGVECTOR_URI",
            "postgresql://postgres:postgres@localhost:5433/vectors",
        )
    )
    db_schema: str = "autoresearch"
    default_strategy: str = "agent"
    tags: list[str] = field(
        default_factory=lambda: [
            "hyperparameter-optimization",
            "autoevolve",
            "multi-agent",
        ]
    )


settings = AutoresearchSettings()
