"""Connector protocol and factory for server communication.

Defines the abstract interface that all transport connectors must implement.
Concrete implementations (HTTP, gRPC) are in Phase 6.3.
"""

from __future__ import annotations

from typing import Protocol

from ..data_classes.server_config import ServerConfig
from ..data_classes.http_config import (
    CheckpointRequest,
    CheckpointResponse,
    HealthResponse,
    PostRequest,
    PostResponse,
    PreRequest,
    PreResponse,
)



class Connector(Protocol):
    """Abstract protocol for lineage server communication.

    All connectors must implement these methods to handle
    PRE/POST lifecycle communication with the lineage server.
    """

    def health(self) -> HealthResponse:
        """Check server health/connectivity.

        Returns:
            HealthResponse from the server.

        Raises:
            ConnectionError: If server is unreachable.
        """
        ...

    def send_pre(self, request: PreRequest) -> PreResponse:
        """Send PRE-execution payload to server.

        Args:
            request: PreRequest with experiment config + codebase snapshot.

        Returns:
            PreResponse with experiment_id, strategy, etc.

        Raises:
            ConnectionError: If server is unreachable.
            ServerError: If server returns an error response.
        """
        ...

    def send_post(self, request: PostRequest) -> PostResponse:
        """Send POST-execution payload to server.

        Args:
            request: PostRequest with final status.

        Returns:
            PostResponse acknowledgement.

        Raises:
            ConnectionError: If server is unreachable.
            ServerError: If server returns an error response.
        """
        ...

    def send_checkpoint(self, request: CheckpointRequest) -> CheckpointResponse:
        """Send checkpoint creation payload to server.

        Args:
            request: CheckpointRequest with checkpoint data.

        Returns:
            CheckpointResponse with assigned checkpoint_id.

        Raises:
            ConnectionError: If server is unreachable.
            ServerError: If server returns an error response.
        """
        ...

    def close(self) -> None:
        """Release any held resources (connections, sessions)."""
        ...

class ServerError(Exception):
    """Raised when the server returns an error response."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Server error {status_code}: {detail}")


class ConnectorFactory:
    """Factory for creating connector instances based on protocol config."""

    _registry: dict[str, type] = {}

    @classmethod
    def register(cls, protocol: str, connector_cls: type) -> None:
        """Register a connector class for a protocol name.

        Args:
            protocol: Protocol identifier (e.g., "http", "grpc").
            connector_cls: Class implementing the Connector protocol.
        """
        cls._registry[protocol] = connector_cls

    @classmethod
    def create(cls, config: ServerConfig) -> Connector:
        """Create a connector instance from server config.

        Args:
            config: ServerConfig with protocol and connection params.

        Returns:
            Connector instance.

        Raises:
            ValueError: If protocol is not registered.
        """
        connector_cls = cls._registry.get(config.protocol)
        if connector_cls is None:
            available = list(cls._registry.keys()) or ["none registered"]
            raise ValueError(
                f"Unknown protocol '{config.protocol}'. "
                f"Available: {', '.join(available)}. "
                f"Ensure the connector module is imported."
            )
        return connector_cls(config)
