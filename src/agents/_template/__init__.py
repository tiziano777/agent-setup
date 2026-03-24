"""__AGENT_NAME__ agent module.

Exposes both the Graph API compiled graph and the Functional API
workflow so that both styles are available from a single import.
"""

from src.agents.__AGENT_NAME__.agent import graph
from src.agents.__AGENT_NAME__.pipelines.pipeline import workflow

__all__ = ["graph", "workflow"]
