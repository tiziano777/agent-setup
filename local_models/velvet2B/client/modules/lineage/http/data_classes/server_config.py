"""Server connection configuration loaded from .lineage/server.yml."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

_DEFAULT_TIMEOUT: int = 30
_DEFAULT_RETRIES: int = 3
_CONFIG_FILENAME: str = "server.yml"


class ServerConfig(BaseModel):
    """Connection configuration for the lineage server.

    Loaded from .lineage/server.yml in the project root.
    """

    url: str = "http://localhost:8000"
    protocol: Literal["http", "grpc"] = "http"
    timeout: int = Field(default=_DEFAULT_TIMEOUT, ge=1)
    retries: int = Field(default=_DEFAULT_RETRIES, ge=0)
    blocking: bool = True


class ServerConfigError(Exception):
    """Raised when .lineage/server.yml is missing or invalid."""


def load_server_config(project_root: Path) -> ServerConfig:
    """Load server config from .lineage/server.yml.

    Args:
        project_root: Path to the project root containing .lineage/.

    Returns:
        ServerConfig instance.

    Raises:
        ServerConfigError: If the file is missing or malformed.
    """
    config_path = project_root / ".lineage" / _CONFIG_FILENAME

    if not config_path.exists():
        raise ServerConfigError(
            f"Server config not found at '{config_path}'. "
            f"Create .lineage/server.yml with at minimum: url: <server_url>"
        )

    try:
        with open(config_path) as f:
            data = yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        raise ServerConfigError(f"Invalid YAML in '{config_path}': {e}") from e

    try:
        return ServerConfig.model_validate(data)
    except Exception as e:
        raise ServerConfigError(
            f"Invalid server config in '{config_path}': {e}"
        ) from e
