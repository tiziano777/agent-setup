"""HTTP connector for lineage server communication.

Uses httpx for synchronous HTTP requests with proper timeout handling.
Auto-registers with ConnectorFactory on import.
"""

from __future__ import annotations

import logging

import httpx

from .data_classes.server_config import ServerConfig
from .base.connector import ConnectorFactory, ServerError
from .data_classes.http_config import (
    CheckpointRequest,
    CheckpointResponse,
    HealthResponse,
    PostRequest,
    PostResponse,
    PreRequest,
    PreResponse,
)

logger = logging.getLogger(__name__)


class HttpConnector:
    """HTTP connector implementing the Connector protocol.

    Communicates with the lineage server via REST endpoints:
        - GET  /health       → HealthResponse
        - POST /api/v1/pre   → PreResponse
        - POST /api/v1/post  → PostResponse
    """

    def __init__(self, config: ServerConfig):
        self._config = config
        self._base_url = config.url.rstrip("/")
        self._client = httpx.Client(
            base_url=self._base_url,
            timeout=httpx.Timeout(config.timeout),
        )

    def health(self) -> HealthResponse:
        """Check server health."""
        try:
            resp = self._client.get("/health")
            resp.raise_for_status()
            return HealthResponse.model_validate(resp.json())
        except httpx.ConnectError as e:
            raise ConnectionError(f"Cannot reach server at {self._base_url}: {e}") from e
        except httpx.TimeoutException as e:
            raise ConnectionError(f"Server timeout at {self._base_url}: {e}") from e

    def send_pre(self, request: PreRequest) -> PreResponse:
        """Send PRE-execution payload to server."""
        try:
            resp = self._client.post(
                "/api/v1/pre",
                content=request.model_dump_json(),
                headers={"Content-Type": "application/json"},
            )
        except httpx.ConnectError as e:
            raise ConnectionError(
                f"Cannot reach server at {self._base_url}/api/v1/pre: {e}"
            ) from e
        except httpx.TimeoutException as e:
            raise ConnectionError(
                f"Server timeout at {self._base_url}/api/v1/pre: {e}"
            ) from e

        if resp.status_code >= 400:
            detail = resp.text
            try:
                detail = resp.json().get("detail", resp.text)
            except Exception:
                pass
            raise ServerError(resp.status_code, str(detail))

        return PreResponse.model_validate(resp.json())

    def send_post(self, request: PostRequest) -> PostResponse:
        """Send POST-execution payload to server."""
        try:
            resp = self._client.post(
                "/api/v1/post",
                content=request.model_dump_json(),
                headers={"Content-Type": "application/json"},
            )
        except httpx.ConnectError as e:
            raise ConnectionError(
                f"Cannot reach server at {self._base_url}/api/v1/post: {e}"
            ) from e
        except httpx.TimeoutException as e:
            raise ConnectionError(
                f"Server timeout at {self._base_url}/api/v1/post: {e}"
            ) from e

        if resp.status_code >= 400:
            detail = resp.text
            try:
                detail = resp.json().get("detail", resp.text)
            except Exception:
                pass
            raise ServerError(resp.status_code, str(detail))

        return PostResponse.model_validate(resp.json())

    def send_checkpoint(self, request: CheckpointRequest) -> CheckpointResponse:
        """Send checkpoint creation payload to server."""
        try:
            resp = self._client.post(
                "/api/v1/checkpoint",
                content=request.model_dump_json(),
                headers={"Content-Type": "application/json"},
            )
        except httpx.ConnectError as e:
            raise ConnectionError(
                f"Cannot reach server at {self._base_url}/api/v1/checkpoint: {e}"
            ) from e
        except httpx.TimeoutException as e:
            raise ConnectionError(
                f"Server timeout at {self._base_url}/api/v1/checkpoint: {e}"
            ) from e

        if resp.status_code >= 400:
            detail = resp.text
            try:
                detail = resp.json().get("detail", resp.text)
            except Exception:
                pass
            raise ServerError(resp.status_code, str(detail))

        return CheckpointResponse.model_validate(resp.json())

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()


# Auto-register on import
ConnectorFactory.register("http", HttpConnector)
