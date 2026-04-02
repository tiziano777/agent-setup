"""OpenTelemetry span helpers for RDF Memory operations.

Provides :func:`traced_sparql`, a context manager that emits spans
nested under the parent LangGraph context (via OpenTelemetry contextvars).

All custom attributes use the ``rdf.`` prefix. RDF spans are automatically
linked to their parent node/tool execution through implicit context propagation.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Generator

from opentelemetry import trace

from src.shared.tracing import get_tracer

_tracer: Any = None


def _get_rdf_tracer() -> Any:
    global _tracer
    if _tracer is None:
        _tracer = get_tracer("rdf_memory")
    return _tracer


@contextmanager
def traced_sparql(
    operation: str,
    lifecycle: str,
    run_manager: Any = None,
    **extra_attrs: str,
) -> Generator[Any, None, None]:
    """Emit an OTel span for a SPARQL operation, nested under parent LangGraph context.

    Uses OpenTelemetry's implicit context propagation to nest the RDF span
    as a child of the parent node/tool execution. The run_manager parameter
    provides fallback explicit linkage if contextvars are unavailable.

    Automatically sets:

    - ``rdf.operation`` — SPARQL operation type (SELECT, INSERT, …)
    - ``rdf.target_lifecycle`` — target lifecycle (session, staging, persistent)
    - ``langchain.run_id`` — (if run_manager provided) LangChain execution ID

    Any additional keyword arguments are set as ``rdf.<key>`` attributes.

    Args:
        operation: SPARQL operation type (SELECT, INSERT, DELETE, etc.)
        lifecycle: Target lifecycle (session, staging, persistent)
        run_manager: Optional LangChain RunManager for explicit trace linkage
        **extra_attrs: Additional attributes (set as rdf.<key>)

    Example::

        with traced_sparql("SELECT", "session", query_preview=sparql[:300]) as span:
            result = client.query(sparql)
            bindings = result.get("results", {}).get("bindings", [])
            span.set_attribute("rdf.result_count", len(bindings))
    """
    tracer = _get_rdf_tracer()
    with tracer.start_as_current_span(f"rdf.{operation}") as span:
        # Always set core RDF attributes
        span.set_attribute("rdf.operation", operation)
        span.set_attribute("rdf.target_lifecycle", lifecycle)

        # Fallback: if run_manager provided, inject LangChain trace context explicitly
        if run_manager and hasattr(run_manager, "run_id"):
            span.set_attribute("langchain.run_id", str(run_manager.run_id))

        # Set any additional custom attributes
        for key, value in extra_attrs.items():
            span.set_attribute(f"rdf.{key}", str(value))

        yield span
