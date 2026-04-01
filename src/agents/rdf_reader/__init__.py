"""rdf_reader agent module.

Exposes both the Graph API compiled graph and the Functional API
workflow so that both styles are available from a single import.

Tracing is initialised on import so that every LangChain/LangGraph
operation (LLM calls, node executions, tool invocations) is
automatically captured by Phoenix via OpenTelemetry.
"""

from src.shared.tracing import setup_tracing

# Initialise Phoenix auto-instrumentation *before* graph compilation.
# Idempotent: safe to call multiple times across modules.
setup_tracing()

from src.agents.rdf_reader.agent import graph  # noqa: E402
from src.agents.rdf_reader.pipelines.pipeline import workflow  # noqa: E402

__all__ = ["graph", "workflow"]
