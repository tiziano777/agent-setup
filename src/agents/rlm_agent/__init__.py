"""RLM Agent - Recursive Language Model based problem solver.

Demonstrates RLM integration with full Phoenix OTEL tracing.
Uses recursive problem decomposition to find answers in very long contexts.
"""

from src.agents.rlm_agent.agent import get_agent
from src.agents.rlm_agent.schemas import RLMAgentInput, RLMAgentOutput
from src.agents.rlm_agent.states import RLMAgentState
from src.shared.tracing import setup_tracing

# Enable Phoenix OTEL tracing at module import
setup_tracing()

__all__ = [
    "get_agent",
    "RLMAgentInput",
    "RLMAgentOutput",
    "RLMAgentState",
]
