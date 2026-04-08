"""deepconf_agent module.

Single-node ReAct-style agent for deep reasoning via DeepConf (facebookresearch/deepconf).

Tracing is initialised on import so that every LangChain/LangGraph operation
(LLM calls, node executions) is automatically captured by Phoenix via OpenTelemetry.
"""

from src.shared.tracing import setup_tracing

# Initialise Phoenix auto-instrumentation *before* graph compilation.
# Idempotent: safe to call multiple times across modules.
setup_tracing()

from src.agents.deepconf_agent.agent import graph  # noqa: E402

__all__ = ["graph"]
