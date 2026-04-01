"""Configuration and infrastructure wiring for Cognee.

Provides :class:`CogneeSettings` dataclass and :func:`setup_cognee` to
configure the Cognee runtime to use the project's LiteLLM proxy,
PGVector (default) or LanceDB for vectors, and Neo4j for the graph database.

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
    # "openai" provider passes endpoint as api_base to litellm correctly
    llm_provider: str = "openai"
    llm_model: str = field(
        default_factory=lambda: os.getenv("DEFAULT_MODEL", "llm")
    )
    llm_endpoint: str = field(
        default_factory=lambda: os.getenv("LITELLM_BASE_URL", "http://localhost:4000/v1")
    )
    llm_api_key: str = field(
        default_factory=lambda: os.getenv("OPENAI_API_KEY", "not-needed")
    )

    # -- Vector DB (PGVector default, LanceDB as fallback) --
    vector_db_provider: Literal["lancedb", "pgvector"] = "pgvector"
    vector_db_url: str = field(
        default_factory=lambda: os.getenv("COGNEE_VECTOR_DB_URL", "")
    )
    vector_db_key: str | None = None
    # PGVector connection fields (ignored when provider is lancedb)
    vector_db_host: str = field(
        default_factory=lambda: os.getenv("COGNEE_VECTOR_DB_HOST", "localhost")
    )
    vector_db_port: str = field(
        default_factory=lambda: os.getenv("COGNEE_VECTOR_DB_PORT", "5433")
    )
    vector_db_name: str = field(
        default_factory=lambda: os.getenv("COGNEE_VECTOR_DB_NAME", "vectors")
    )
    vector_db_username: str = field(
        default_factory=lambda: os.getenv("COGNEE_VECTOR_DB_USERNAME", "postgres")
    )
    vector_db_password: str = field(
        default_factory=lambda: os.getenv("COGNEE_VECTOR_DB_PASSWORD", "postgres")
    )

    # -- Embeddings (local fastembed by default, no API needed) --
    embedding_provider: str = field(
        default_factory=lambda: os.getenv("EMBEDDING_PROVIDER", "fastembed")
    )
    embedding_model: str = field(
        default_factory=lambda: os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
    )
    embedding_dimensions: int = 384

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
    - **LLM** → LiteLLM proxy (``openai`` provider with ``openai/`` prefix)
    - **Vector DB** → PGVector (existing PostgreSQL) or LanceDB
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
        "llm_provider": settings.llm_provider,
        "llm_model": model_name,
        "llm_api_key": settings.llm_api_key,
        "llm_endpoint": settings.llm_endpoint,
    })
    # Also set env vars for anything Cognee reads at import time
    os.environ.setdefault("LLM_PROVIDER", settings.llm_provider)
    os.environ.setdefault("LLM_MODEL", model_name)
    os.environ.setdefault("LLM_ENDPOINT", settings.llm_endpoint)
    os.environ.setdefault("LLM_API_KEY", settings.llm_api_key)

    # Vector DB → PGVector (default) or LanceDB
    # Must be set BEFORE system_root_directory() which checks vector_db_provider
    vdb_config: dict = {
        "vector_db_provider": settings.vector_db_provider,
        "vector_dataset_database_handler": settings.vector_db_provider,
        "vector_db_host": settings.vector_db_host,
        "vector_db_port": settings.vector_db_port,
        "vector_db_name": settings.vector_db_name,
        "vector_db_username": settings.vector_db_username,
        "vector_db_password": settings.vector_db_password,
    }
    if settings.vector_db_url:
        vdb_config["vector_db_url"] = settings.vector_db_url
    if settings.vector_db_key:
        vdb_config["vector_db_key"] = settings.vector_db_key
    cognee.config.set_vector_db_config(vdb_config)

    # Set a writable system root (after vector config so lancedb check sees pgvector)
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    cognee_data_dir = os.path.join(project_root, ".cognee_system")
    cognee.config.system_root_directory(cognee_data_dir)

    # Relational DB → PostgreSQL (same instance as PGVector)
    # Cognee's SqlAlchemyAdapter.create_database() runs CREATE EXTENSION vector
    # on the relational engine when vector_db_provider=="pgvector", so the
    # relational DB must also be PostgreSQL to avoid SQLite dialect errors.
    if settings.vector_db_provider == "pgvector":
        cognee.config.set_relational_db_config({
            "db_provider": "postgres",
            "db_host": settings.vector_db_host,
            "db_port": settings.vector_db_port,
            "db_name": settings.vector_db_name,
            "db_username": settings.vector_db_username,
            "db_password": settings.vector_db_password,
        })

    # Embeddings → local fastembed (no API key needed)
    from cognee.infrastructure.databases.vector.embeddings.config import get_embedding_config
    from cognee.infrastructure.databases.vector.embeddings.get_embedding_engine import (
        create_embedding_engine,
    )

    embedding_cfg = get_embedding_config()
    embedding_cfg.embedding_provider = settings.embedding_provider
    embedding_cfg.embedding_model = settings.embedding_model
    embedding_cfg.embedding_dimensions = settings.embedding_dimensions
    # Clear lru_cache so next get_embedding_engine() picks up the new config
    create_embedding_engine.cache_clear()

    # Graph DB → Neo4j
    cognee.config.set_graph_db_config({
        "graph_database_provider": settings.graph_db_provider,
        "graph_database_url": settings.graph_db_url,
        "graph_database_username": settings.graph_db_username,
        "graph_database_password": settings.graph_db_password,
        "graph_dataset_database_handler": settings.graph_db_provider,
    })

    # Disable multi-user access control (requires matching handlers)
    os.environ.setdefault("ENABLE_BACKEND_ACCESS_CONTROL", "false")

    # Skip Cognee's internal LLM connection test (proxy routing handles validation)
    os.environ.setdefault("COGNEE_SKIP_CONNECTION_TEST", "true")

    _CONFIGURED = True
    vdb_detail = settings.vector_db_provider
    if settings.vector_db_provider == "pgvector":
        vdb_detail = (
            f"pgvector@{settings.vector_db_host}:"
            f"{settings.vector_db_port}/{settings.vector_db_name}"
        )
    logger.info(
        "Cognee configured: LLM=%s via %s, VectorDB=%s, GraphDB=%s",
        model_name,
        settings.llm_endpoint,
        vdb_detail,
        settings.graph_db_provider,
    )


def _ensure_configured() -> None:
    """Auto-configure if not yet done."""
    if not _CONFIGURED:
        setup_cognee()
