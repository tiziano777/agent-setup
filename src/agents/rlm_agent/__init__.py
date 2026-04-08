"""RLM Agent module.

Recursive Language Model based problem solver that uses RLM integration
with full Phoenix OTEL tracing. Uses recursive problem decomposition to
find answers in very long contexts (50k+ lines supported).

Exposes both the Graph API compiled graph and the Functional API workflow.
Tracing is initialised on import so that every LangChain/LangGraph operation
is automatically captured by Phoenix via OpenTelemetry.
"""

from src.shared.tracing import setup_tracing

# Initialise Phoenix auto-instrumentation *before* graph compilation.
# Idempotent: safe to call multiple times across modules.
setup_tracing()

from src.agents.rlm_agent.agent import graph  # noqa: E402
from src.agents.rlm_agent.schemas import RLMAgentInput, RLMAgentOutput  # noqa: E402
from src.agents.rlm_agent.states import RLMAgentState  # noqa: E402

__all__ = [
    "graph",
    "RLMAgentInput",
    "RLMAgentOutput",
    "RLMAgentState",
]
