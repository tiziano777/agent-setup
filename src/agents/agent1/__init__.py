"""agent1 agent module.

Exposes both the Graph API compiled graph and the Functional API
workflow so that both styles are available from a single import.
"""

from src.agents.agent1.agent import graph
from src.agents.agent1.pipelines.pipeline import workflow

__all__ = ["graph", "workflow"]
