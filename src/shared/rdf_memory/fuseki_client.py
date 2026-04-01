"""Low-level Fuseki SPARQL client.

Pure I/O layer — no business logic.  Uses :mod:`SPARQLWrapper` for query
operations (SELECT / ASK / CONSTRUCT / DESCRIBE) and :mod:`httpx` for
SPARQL Update (INSERT / DELETE / DROP / MOVE / …) and Graph Store Protocol.

Every call is retried with exponential back-off + jitter.
"""

from __future__ import annotations

import logging
import random
import time
from typing import Any, Callable

import httpx
from SPARQLWrapper import JSON, N3, SPARQLWrapper

from src.shared.rdf_memory.config import RDFMemorySettings

logger = logging.getLogger(__name__)

# ── Exceptions ───────────────────────────────────────────────────────


class FusekiError(Exception):
    """Base exception for Fuseki client errors."""


class FusekiConnectionError(FusekiError):
    """Fuseki is unreachable."""


class FusekiQueryError(FusekiError):
    """SPARQL query / update rejected by Fuseki."""


# ── Format mapping ───────────────────────────────────────────────────

_ACCEPT_HEADERS: dict[str, str] = {
    "turtle": "text/turtle",
    "json-ld": "application/ld+json",
    "n-triples": "application/n-triples",
}

# ── Client ───────────────────────────────────────────────────────────


class FusekiClient:
    """Thin wrapper around Fuseki's SPARQL and Graph Store Protocol endpoints."""

    def __init__(self, settings: RDFMemorySettings) -> None:
        base = settings.fuseki_url.rstrip("/")
        ds = settings.dataset
        self._query_endpoint = f"{base}/{ds}/sparql"
        self._update_endpoint = f"{base}/{ds}/update"
        self._gsp_endpoint = f"{base}/{ds}/data"
        self._settings = settings
        self._http = httpx.Client(
            auth=(settings.admin_user, settings.admin_password),
            timeout=30.0,
        )

    # ── Query (read) ─────────────────────────────────────────────────

    def query(self, sparql: str, return_format: str = "json") -> dict:
        """Execute a read query (SELECT / ASK / CONSTRUCT / DESCRIBE).

        Returns the parsed JSON result dict for SELECT/ASK, or raw string
        for CONSTRUCT/DESCRIBE wrapped in ``{"results": <str>}``.
        """

        def _do() -> dict:
            sw = SPARQLWrapper(self._query_endpoint)
            sw.setQuery(sparql)
            if return_format == "json":
                sw.setReturnFormat(JSON)
                return sw.query().convert()  # type: ignore[return-value]
            else:
                sw.setReturnFormat(N3)
                raw = sw.query().convert()
                return {"results": raw.decode() if isinstance(raw, bytes) else str(raw)}

        return self._retry(_do, "query")

    # ── Update (write) ───────────────────────────────────────────────

    def update(self, sparql: str) -> bool:
        """Execute a SPARQL Update (INSERT / DELETE / DROP / MOVE / …).

        Returns *True* on success.  Raises :class:`FusekiQueryError` on
        4xx/5xx responses.
        """

        def _do() -> bool:
            resp = self._http.post(
                self._update_endpoint,
                content=sparql.encode("utf-8"),
                headers={"Content-Type": "application/sparql-update"},
            )
            if resp.status_code >= 400:
                raise FusekiQueryError(f"Update failed ({resp.status_code}): {resp.text[:500]}")
            return True

        return self._retry(_do, "update")

    # ── Graph Store Protocol ─────────────────────────────────────────

    def get_graph(self, graph_uri: str, fmt: str = "turtle") -> str:
        """Fetch a named graph via the Graph Store Protocol.

        Returns the serialised graph as a string in the requested format.
        """
        accept = _ACCEPT_HEADERS.get(fmt, "text/turtle")

        def _do() -> str:
            resp = self._http.get(
                self._gsp_endpoint,
                params={"graph": graph_uri},
                headers={"Accept": accept},
            )
            if resp.status_code == 404:
                return ""
            if resp.status_code >= 400:
                raise FusekiQueryError(f"GSP GET failed ({resp.status_code}): {resp.text[:500]}")
            return resp.text

        return self._retry(_do, "get_graph")

    # ── Retry logic ──────────────────────────────────────────────────

    def _retry(self, fn: Callable[[], Any], operation: str) -> Any:
        """Execute *fn* with exponential back-off and jitter."""
        last_exc: Exception | None = None
        for attempt in range(self._settings.max_retries + 1):
            try:
                return fn()
            except (httpx.ConnectError, httpx.TimeoutException, ConnectionError) as exc:
                last_exc = exc
                if attempt < self._settings.max_retries:
                    delay = self._settings.retry_base_delay * (2**attempt) + random.uniform(0, 0.1)
                    logger.warning(
                        "Fuseki %s attempt %d failed (%s), retrying in %.2fs",
                        operation,
                        attempt + 1,
                        exc,
                        delay,
                    )
                    time.sleep(delay)
            except FusekiError:
                raise
            except Exception as exc:
                raise FusekiConnectionError(f"Unexpected error during {operation}: {exc}") from exc

        raise FusekiConnectionError(
            f"Fuseki {operation} failed after {self._settings.max_retries + 1} attempts"
        ) from last_exc

    # ── Cleanup ──────────────────────────────────────────────────────

    def close(self) -> None:
        """Close the underlying httpx client."""
        self._http.close()
