"""Centralized Phoenix tracing setup.

Bootstraps OpenTelemetry tracing with Arize Phoenix as the collector.
Call :func:`setup_tracing` once at application startup (e.g. in ``serve.py``)
to auto-instrument all LangChain/LangGraph operations.

Environment variables:
    PHOENIX_COLLECTOR_ENDPOINT  Default ``http://localhost:6006``
    PHOENIX_PROJECT_NAME        Default ``agent-setup``
    PHOENIX_TRACING_ENABLED     Default ``true``. Set ``false`` to disable.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

_INITIALISED = False


def setup_tracing(
    project_name: str | None = None,
    endpoint: str | None = None,
    enabled: bool | None = None,
) -> bool:
    """Initialise Phoenix OTEL tracing (idempotent).

    Args:
        project_name: Phoenix project name. Falls back to
            ``PHOENIX_PROJECT_NAME`` env var, then ``"agent-setup"``.
        endpoint: Phoenix collector URL. Falls back to
            ``PHOENIX_COLLECTOR_ENDPOINT`` env var, then ``"http://localhost:6006"``.
        enabled: Whether tracing is active. Falls back to
            ``PHOENIX_TRACING_ENABLED`` env var, then ``True``.

    Returns:
        ``True`` if tracing was successfully initialised, ``False`` otherwise.
    """
    global _INITIALISED  # noqa: PLW0603
    if _INITIALISED:
        return True

    if enabled is None:
        enabled = os.getenv("PHOENIX_TRACING_ENABLED", "true").lower() in ("true", "1", "yes")
    if not enabled:
        logger.info("Phoenix tracing disabled via configuration")
        return False

    if project_name is None:
        project_name = os.getenv("PHOENIX_PROJECT_NAME", "agent-setup")
    if endpoint is None:
        endpoint = os.getenv("PHOENIX_COLLECTOR_ENDPOINT", "http://localhost:6006")

    try:
        from phoenix.otel import register

        register(
            project_name=project_name,
            endpoint=endpoint,
            auto_instrument=True,
            batch=True,
        )
        _INITIALISED = True
        logger.info("Phoenix tracing initialised (project=%s, endpoint=%s)", project_name, endpoint)
        return True
    except Exception:
        logger.warning("Phoenix tracing setup failed — continuing without tracing", exc_info=True)
        return False


def get_tracer(name: str = "agent-setup"):
    """Return an OpenTelemetry tracer for manual span creation.

    Use this in modules that need custom spans (e.g. RAG pipeline).
    Returns a no-op tracer if OTEL is not installed or tracing is disabled.
    """
    try:
        from opentelemetry import trace

        return trace.get_tracer(name)
    except ImportError:
        from contextlib import contextmanager

        class _NoOpSpan:
            def set_attribute(self, key, value):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

        class _NoOpTracer:
            @contextmanager
            def start_as_current_span(self, name, **kwargs):
                yield _NoOpSpan()

        return _NoOpTracer()
