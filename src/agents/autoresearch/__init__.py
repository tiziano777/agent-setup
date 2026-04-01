"""AutoResearch — AutoEvolve-inspired hyperparameter optimization agent.

Three pipeline variants (agent/random/grid) for evidence-based hyperparameter
search with trajectory awareness, knowledge accumulation, and sandbox execution.
"""

from src.shared.tracing import setup_tracing

setup_tracing()

from src.agents.autoresearch.agent import graph, workflow  # noqa: E402

__all__ = ["graph", "workflow"]
