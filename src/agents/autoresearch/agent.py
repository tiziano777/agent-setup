"""AutoResearch agent — pipeline selector and graph builder.

Provides ``build_graph()`` which returns the appropriate LangGraph pipeline
based on the strategy type (agent, random, or grid).
"""

from __future__ import annotations

from typing import Any

from src.agents.autoresearch.config.settings import settings
from src.agents.autoresearch.pipelines.agent_pipeline import build_agent_pipeline
from src.agents.autoresearch.pipelines.grid_pipeline import build_grid_pipeline
from src.agents.autoresearch.pipelines.random_pipeline import build_random_pipeline


def build_graph(strategy: str | None = None) -> Any:
    """Build and compile the appropriate pipeline.

    Args:
        strategy: One of 'agent', 'random', 'grid'.
            Defaults to ``AutoresearchSettings.default_strategy``.
    """
    strategy = strategy or settings.default_strategy

    if strategy == "random":
        return build_random_pipeline()
    elif strategy == "grid":
        return build_grid_pipeline()
    else:
        return build_agent_pipeline()


# Default graph uses the configured strategy
graph = build_graph()

# Functional API workflow (alias for compatibility with registry)
workflow = graph
