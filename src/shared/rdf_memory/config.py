"""Configuration and policy system for RDF Memory.

Provides :class:`RDFMemorySettings` with Fuseki connection params,
:class:`PolicyConfig` / :class:`LifecyclePolicy` for per-agent access control,
and preset factories (:func:`default_policy`, :func:`read_write_policy`,
:func:`admin_policy`).

Usage::

    from src.shared.rdf_memory.config import RDFMemorySettings, setup_rdf_memory

    setup_rdf_memory()  # auto-configures from env vars
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Literal

logger = logging.getLogger(__name__)

# ── Guarded imports ──────────────────────────────────────────────────

try:
    import rdflib  # noqa: F401
    from SPARQLWrapper import SPARQLWrapper  # noqa: F401

    _AVAILABLE = True
except ImportError:
    _AVAILABLE = False

_INSTALL_HINT = "Install RDF dependencies: pip install -e '.[rdf]'"


def _check_available() -> None:
    if not _AVAILABLE:
        raise ImportError(_INSTALL_HINT)


# ── Policy ───────────────────────────────────────────────────────────

SPARQL_READ_OPS = frozenset({"SELECT", "ASK", "CONSTRUCT", "DESCRIBE"})
SPARQL_WRITE_OPS = frozenset({"INSERT", "DELETE", "LOAD"})
SPARQL_ADMIN_OPS = frozenset({"DROP", "CLEAR", "MOVE", "COPY", "ADD"})
SPARQL_ALL_OPS = SPARQL_READ_OPS | SPARQL_WRITE_OPS | SPARQL_ADMIN_OPS


@dataclass
class LifecyclePolicy:
    """Access permissions for a single lifecycle (session / staging / persistent)."""

    allowed_operations: list[str] = field(default_factory=lambda: list(SPARQL_READ_OPS))
    visible: bool = True
    llm_accessible: bool = True
    requires_flag: list[str] = field(default_factory=list)


@dataclass
class PolicyConfig:
    """Complete permission configuration for all three lifecycles."""

    session: LifecyclePolicy = field(default_factory=LifecyclePolicy)
    staging: LifecyclePolicy = field(default_factory=LifecyclePolicy)
    persistent: LifecyclePolicy = field(default_factory=LifecyclePolicy)


def default_policy() -> PolicyConfig:
    """LLM reads/writes session, reads persistent (read-only). Staging code-only."""
    return PolicyConfig(
        session=LifecyclePolicy(
            allowed_operations=[
                "SELECT",
                "ASK",
                "CONSTRUCT",
                "DESCRIBE",
                "INSERT",
                "DELETE",
                "CLEAR",
            ],
            visible=True,
            llm_accessible=True,
            requires_flag=[],
        ),
        staging=LifecyclePolicy(
            allowed_operations=[
                "SELECT",
                "ASK",
                "CONSTRUCT",
                "DESCRIBE",
                "INSERT",
                "DELETE",
                "CLEAR",
                "MOVE",
                "COPY",
            ],
            visible=False,
            llm_accessible=False,
            requires_flag=[],
        ),
        persistent=LifecyclePolicy(
            allowed_operations=["SELECT", "ASK", "CONSTRUCT", "DESCRIBE"],
            visible=True,
            llm_accessible=True,
            requires_flag=["DELETE", "DROP", "CLEAR"],
        ),
    )


def read_write_policy() -> PolicyConfig:
    """LLM reads/writes session + persistent. Staging visible read-only."""
    return PolicyConfig(
        session=LifecyclePolicy(
            allowed_operations=[
                "SELECT",
                "ASK",
                "CONSTRUCT",
                "DESCRIBE",
                "INSERT",
                "DELETE",
                "CLEAR",
            ],
            visible=True,
            llm_accessible=True,
            requires_flag=[],
        ),
        staging=LifecyclePolicy(
            allowed_operations=["SELECT", "ASK", "CONSTRUCT", "DESCRIBE"],
            visible=True,
            llm_accessible=False,
            requires_flag=[],
        ),
        persistent=LifecyclePolicy(
            allowed_operations=[
                "SELECT",
                "ASK",
                "CONSTRUCT",
                "DESCRIBE",
                "INSERT",
                "DELETE",
            ],
            visible=True,
            llm_accessible=True,
            requires_flag=["DELETE", "DROP", "CLEAR"],
        ),
    )


def admin_policy() -> PolicyConfig:
    """Full access to all lifecycles. For testing / admin only."""
    all_ops = list(SPARQL_ALL_OPS)
    return PolicyConfig(
        session=LifecyclePolicy(
            allowed_operations=all_ops,
            visible=True,
            llm_accessible=True,
        ),
        staging=LifecyclePolicy(
            allowed_operations=all_ops,
            visible=True,
            llm_accessible=True,
        ),
        persistent=LifecyclePolicy(
            allowed_operations=all_ops,
            visible=True,
            llm_accessible=True,
        ),
    )


# ── Settings ─────────────────────────────────────────────────────────


@dataclass
class RDFMemorySettings:
    """Central configuration for the RDF Memory module.

    Reads defaults from environment variables where appropriate.
    """

    # -- Fuseki connection --
    fuseki_url: str = field(
        default_factory=lambda: os.getenv("FUSEKI_URL", "http://localhost:3030"),
    )
    dataset: str = field(
        default_factory=lambda: os.getenv("FUSEKI_DATASET", "knowledge"),
    )
    admin_user: str = field(
        default_factory=lambda: os.getenv("FUSEKI_ADMIN_USER", "admin"),
    )
    admin_password: str = field(
        default_factory=lambda: os.getenv("FUSEKI_ADMIN_PASSWORD", "admin"),
    )

    # -- Retry --
    max_retries: int = 3
    retry_base_delay: float = 0.5

    # -- Defaults --
    default_lifecycle: Literal["session", "staging", "persistent"] = "session"
    default_persistent_graph: str = field(
        default_factory=lambda: os.getenv("FUSEKI_DEFAULT_GRAPH", "core"),
    )
    default_format: Literal["turtle", "json-ld", "n-triples"] = "turtle"

    # -- Persistent graphs registry --
    persistent_graphs: list[str] = field(
        default_factory=lambda: os.getenv("FUSEKI_PERSISTENT_GRAPHS", "core").split(","),
    )

    # -- SHACL (optional) --
    shacl_enabled: bool = False
    shacl_shapes_path: str | None = None

    # -- Policy --
    policy: PolicyConfig = field(default_factory=default_policy)


# ── Setup ────────────────────────────────────────────────────────────

_CONFIGURED = False
_settings: RDFMemorySettings | None = None


def setup_rdf_memory(settings: RDFMemorySettings | None = None) -> None:
    """Configure the RDF Memory module (idempotent).

    Args:
        settings: Configuration dataclass.  Uses defaults when *None*.
    """
    global _CONFIGURED, _settings
    _check_available()

    if settings is None:
        settings = RDFMemorySettings()

    _settings = settings
    _CONFIGURED = True
    logger.info(
        "RDF Memory configured: Fuseki=%s/%s, persistent_graphs=%s, policy=%s/%s/%s",
        settings.fuseki_url,
        settings.dataset,
        settings.persistent_graphs,
        "session:visible" if settings.policy.session.visible else "session:hidden",
        "staging:visible" if settings.policy.staging.visible else "staging:hidden",
        "persistent:visible" if settings.policy.persistent.visible else "persistent:hidden",
    )


def _ensure_configured() -> RDFMemorySettings:
    """Auto-configure if not yet done. Returns the active settings."""
    global _settings
    if not _CONFIGURED:
        setup_rdf_memory()
    assert _settings is not None
    return _settings
