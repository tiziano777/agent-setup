"""Configuration and infrastructure wiring for Cognee.

Provides :class:`CogneeSettings` dataclass and :func:`setup_cognee` to
configure the Cognee runtime to use the project's LiteLLM proxy,
existing Qdrant/PgVector vector stores, and Neo4j graph database.

All Cognee LLM calls are routed through the LiteLLM proxy — never
directly to a provider.

Usage::

    from src.shared.cognee_toolkit.config import setup_cognee

    setup_cognee()  # auto-configures from env vars
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Literal

logger = logging.getLogger(__name__)

# ── Guarded import ────────────────────────────────────────────────────

try:
    import cognee  # noqa: F401

    _AVAILABLE = True
except ImportError:
    _AVAILABLE = False

_INSTALL_HINT = "Install cognee: pip install -e '.[cognee]'"


def _check_available() -> None:
    if not _AVAILABLE:
        raise ImportError(_INSTALL_HINT)


# ── Settings ──────────────────────────────────────────────────────────


@dataclass
class CogneeSettings:
    """Central configuration for the Cognee integration.

    Reads defaults from environment variables where appropriate.
    """

    # -- LLM (routes through LiteLLM proxy) --
    llm_provider: str = "custom"
    llm_model: str = field(
        default_factory=lambda: os.getenv("DEFAULT_MODEL", "llm")
    )
    llm_endpoint: str = field(
        default_factory=lambda: os.getenv("LITELLM_BASE_URL", "http://localhost:4000/v1")
    )
    llm_api_key: str = field(
        default_factory=lambda: os.getenv("OPENAI_API_KEY", "not-needed")
    )

    # -- Vector DB (reuse existing infrastructure) --
    vector_db_provider: Literal["qdrant", "pgvector", "lancedb"] = "qdrant"
    vector_db_url: str = field(
        default_factory=lambda: os.getenv("QDRANT_URL", "http://localhost:6333")
    )
    vector_db_key: str | None = None

    # -- Graph DB (Neo4j) --
    graph_db_provider: Literal["neo4j", "kuzu", "falkordb", "networkx"] = "neo4j"
    graph_db_url: str = field(
        default_factory=lambda: os.getenv("NEO4J_URL", "bolt://localhost:7687")
    )
    graph_db_username: str = field(
        default_factory=lambda: os.getenv("NEO4J_USERNAME", "neo4j")
    )
    graph_db_password: str = field(
        default_factory=lambda: os.getenv("NEO4J_PASSWORD", "password")
    )

    # -- Processing defaults --
    default_dataset: str = "main_dataset"
    default_search_type: str = "GRAPH_COMPLETION"
    top_k: int = 10


# ── Setup ─────────────────────────────────────────────────────────────

_CONFIGURED = False


def setup_cognee(settings: CogneeSettings | None = None) -> None:
    """Configure Cognee to use the project's infrastructure (idempotent).

    Wires:
    - **LLM** → LiteLLM proxy (``custom`` provider with ``openai/`` prefix)
    - **Vector DB** → existing Qdrant or PgVector
    - **Graph DB** → Neo4j

    Args:
        settings: Configuration dataclass.  Uses defaults when *None*.
    """
    global _CONFIGURED
    _check_available()

    import cognee

    if settings is None:
        settings = CogneeSettings()

    # LLM → LiteLLM proxy
    model_name = f"openai/{settings.llm_model}"
    cognee.config.set_llm_config({
        "provider": settings.llm_provider,
        "model": model_name,
        "api_key": settings.llm_api_key,
        "endpoint": settings.llm_endpoint,
    })
    # Also set env vars for anything Cognee reads at import time
    os.environ.setdefault("LLM_PROVIDER", settings.llm_provider)
    os.environ.setdefault("LLM_MODEL", model_name)
    os.environ.setdefault("LLM_ENDPOINT", settings.llm_endpoint)
    os.environ.setdefault("LLM_API_KEY", settings.llm_api_key)

    # Vector DB → existing infrastructure
    vdb_config: dict = {
        "vector_db_provider": settings.vector_db_provider,
        "vector_db_url": settings.vector_db_url,
    }
    if settings.vector_db_key:
        vdb_config["vector_db_key"] = settings.vector_db_key
    cognee.config.set_vector_db_config(vdb_config)

    # Graph DB → Neo4j
    cognee.config.set_graph_db_config({
        "provider": settings.graph_db_provider,
        "url": settings.graph_db_url,
        "username": settings.graph_db_username,
        "password": settings.graph_db_password,
    })

    _CONFIGURED = True
    logger.info(
        "Cognee configured: LLM=%s via %s, VectorDB=%s, GraphDB=%s",
        model_name,
        settings.llm_endpoint,
        settings.vector_db_provider,
        settings.graph_db_provider,
    )


def _ensure_configured() -> None:
    """Auto-configure if not yet done."""
    if not _CONFIGURED:
        setup_cognee()
