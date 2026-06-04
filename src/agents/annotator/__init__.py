"""Annotator agent — LLM-as-judge for DPO negative quality annotation.

Exposes the compiled graph for the annotator.
Phoenix tracing is initialised on import.
"""

from src.shared.tracing import setup_tracing

setup_tracing()

from src.agents.annotator.agent import graph  # noqa: E402

__all__ = ["graph"]
