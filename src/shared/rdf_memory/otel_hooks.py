"""OpenTelemetry span helpers for RDF Memory operations.

Provides :func:`traced_sparql`, a context manager that emits spans
compatible with the existing Phoenix / OTel observability layer.

All custom attributes use the ``rdf.`` prefix.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Generator

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
    **extra_attrs: str,
) -> Generator[Any, None, None]:
    """Emit an OTel span for a SPARQL operation.

    Automatically sets:

    - ``rdf.operation`` — SPARQL operation type (SELECT, INSERT, …)
    - ``rdf.target_lifecycle`` — target lifecycle (session, staging, persistent)

    Any additional keyword arguments are set as ``rdf.<key>`` attributes.

    Example::

        with traced_sparql("SELECT", "session", query_preview=sparql[:300]) as span:
            result = client.query(sparql)
            bindings = result.get("results", {}).get("bindings", [])
            span.set_attribute("rdf.result_count", len(bindings))
    """
    tracer = _get_rdf_tracer()
    with tracer.start_as_current_span(f"rdf.{operation}") as span:
        span.set_attribute("rdf.operation", operation)
        span.set_attribute("rdf.target_lifecycle", lifecycle)
        for key, value in extra_attrs.items():
            span.set_attribute(f"rdf.{key}", str(value))
        yield span
