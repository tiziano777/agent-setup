"""Lineage Client SDK — Public API."""

from .http.client import LineageClient, LineageClientError, ExecutionContext
from .http.data_classes.server_config import ServerConfig, ServerConfigError
from .http.base.connector import Connector, ConnectorFactory, ServerError
from .http.data_classes.http_config import (
    CheckpointRequest, CheckpointResponse,
    PostRequest, PostResponse,
    PreRequest, PreResponse,
    HealthResponse,
)
from .utils.snapshot import FileTooLargeError, capture_codebase, content_hash
from .tracker import lineage_tracker, LineageCheckpointCallback

# Auto-register built-in connectors
from .http import http_connector as _http_connector  # noqa: F401

__all__ = [
    "LineageClient",
    "LineageClientError",
    "ExecutionContext",
    "LineageCheckpointCallback",
    "ServerConfig",
    "ServerConfigError",
    "Connector",
    "ConnectorFactory",
    "ServerError",
    "PreRequest",
    "PreResponse",
    "PostRequest",
    "PostResponse",
    "CheckpointRequest",
    "CheckpointResponse",
    "HealthResponse",
    "FileTooLargeError",
    "capture_codebase",
    "content_hash",
    "lineage_tracker",
]