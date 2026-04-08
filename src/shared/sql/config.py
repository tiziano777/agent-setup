"""Configuration for PostgreSQL client.

Provides :class:`SQLSettings` dataclass with connection parameters
and execution settings. All fields read from environment variables
with safe defaults.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ── Guarded import ────────────────────────────────────────────────────

try:
    import sqlalchemy  # noqa: F401
    import psycopg  # noqa: F401

    _AVAILABLE = True
except ImportError:
    _AVAILABLE = False

_INSTALL_HINT = "Install postgres driver: pip install -e '.[sql]'"


def _check_available() -> None:
    if not _AVAILABLE:
        raise ImportError(_INSTALL_HINT)


# ── Settings ──────────────────────────────────────────────────────────


@dataclass
class SQLSettings:
    """PostgreSQL connection and execution configuration."""

    # Connection parameters
    host: str = field(
        default_factory=lambda: os.getenv("SQL_HOST", "localhost"),
    )

    port: int = field(
        default_factory=lambda: int(os.getenv("SQL_PORT", "5432")),
    )

    database: str = field(
        default_factory=lambda: os.getenv("SQL_DATABASE", "agent_db"),
    )

    username: str = field(
        default_factory=lambda: os.getenv("SQL_USERNAME", "postgres"),
    )

    password: str = field(
        default_factory=lambda: os.getenv("SQL_PASSWORD", "postgres"),
    )

    # Connection pool settings
    pool_size: int = field(
        default_factory=lambda: int(os.getenv("SQL_POOL_SIZE", "5")),
    )

    max_overflow: int = field(
        default_factory=lambda: int(os.getenv("SQL_MAX_OVERFLOW", "10")),
    )

    pool_timeout: int = field(
        default_factory=lambda: int(os.getenv("SQL_POOL_TIMEOUT", "30")),
    )

    # Query execution settings
    query_timeout: int = field(
        default_factory=lambda: int(os.getenv("SQL_QUERY_TIMEOUT", "30")),
    )

    # Schema for introspection (default: public)
    schema: str = field(
        default_factory=lambda: os.getenv("SQL_SCHEMA", "public"),
    )

    # Echo SQL statements for debugging
    echo: bool = field(
        default_factory=lambda: os.getenv("SQL_ECHO", "false").lower() == "true",
    )

    @property
    def connection_string(self) -> str:
        """Build PostgreSQL connection string."""
        return (
            f"postgresql+psycopg://{self.username}:{self.password}"
            f"@{self.host}:{self.port}/{self.database}"
        )
