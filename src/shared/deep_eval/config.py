"""DeepEval configuration and environment wiring.

Routes all DeepEval LLM calls through the project's LiteLLM proxy and
provides infrastructure connection settings for vector databases.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ── Guarded import ────────────────────────────────────────────────────

try:
    from deepeval.models import LiteLLMModel  # noqa: F401

    _AVAILABLE = True
except ImportError:
    _AVAILABLE = False

_INSTALL_HINT = "Install deepeval: pip install -e '.[deepeval]'"


def _check_available() -> None:
    if not _AVAILABLE:
        raise ImportError(_INSTALL_HINT)


# ── Settings dataclass ────────────────────────────────────────────────


@dataclass
class DeepEvalSettings:
    """Configuration for the DeepEval evaluation toolkit.

    All fields read from environment variables with sensible defaults.
    """

    # LLM
    litellm_base_url: str = field(
        default_factory=lambda: os.getenv("LITELLM_BASE_URL", "http://localhost:4000/v1"),
    )
    default_model: str = field(
        default_factory=lambda: os.getenv("DEFAULT_MODEL", "llm"),
    )
    temperature: float = 0.0

    # Vector databases
    qdrant_url: str = field(
        default_factory=lambda: os.getenv("QDRANT_URL", "http://localhost:6333"),
    )
    pgvector_uri: str = field(
        default_factory=lambda: os.getenv(
            "PGVECTOR_URI", "postgresql://postgres:postgres@localhost:5433/vectors"
        ),
    )
    pgvector_schema: str = field(
        default_factory=lambda: os.getenv("PGVECTOR_SCHEMA_DEEPEVAL", "deepeval"),
    )

    # Graph database (Cognee)
    neo4j_url: str = field(
        default_factory=lambda: os.getenv("NEO4J_URL", "bolt://localhost:7687"),
    )
    neo4j_username: str = field(
        default_factory=lambda: os.getenv("NEO4J_USERNAME", "neo4j"),
    )
    neo4j_password: str = field(
        default_factory=lambda: os.getenv("NEO4J_PASSWORD", "password"),
    )


# ── Idempotent configuration ─────────────────────────────────────────

_CONFIGURED = False
_SETTINGS: DeepEvalSettings | None = None


def configure_deepeval(settings: DeepEvalSettings | None = None) -> DeepEvalSettings:
    """Configure DeepEval to route LLM calls through the LiteLLM proxy.

    Idempotent — safe to call multiple times.  Returns the active settings.

    Args:
        settings: Custom settings.  Defaults to a new ``DeepEvalSettings()``
                  which reads from environment variables.
    """
    global _CONFIGURED, _SETTINGS
    _check_available()

    if settings is None:
        settings = DeepEvalSettings()

    _SETTINGS = settings
    _CONFIGURED = True
    logger.info(
        "DeepEval configured: model=%s via %s",
        settings.default_model,
        settings.litellm_base_url,
    )
    return settings


def _ensure_configured() -> DeepEvalSettings:
    """Auto-configure if not yet done.  Returns the active settings."""
    global _SETTINGS
    if not _CONFIGURED:
        configure_deepeval()
    assert _SETTINGS is not None
    return _SETTINGS


def get_settings() -> DeepEvalSettings:
    """Return the active settings, configuring if necessary."""
    return _ensure_configured()
