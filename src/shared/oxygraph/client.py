"""HTTP client for Oxigraph SPARQL endpoint."""

from __future__ import annotations

import logging
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen

from src.shared.oxygraph.config import OxigraphSettings

logger = logging.getLogger(__name__)


class OxigraphConnectionError(Exception):
    """Raised when Oxigraph is unreachable."""


class OxigraphQueryError(Exception):
    """Raised when a SPARQL query fails."""


class OxigraphClient:
    """HTTP client for Oxigraph SPARQL operations."""

    def __init__(self, settings: OxigraphSettings | None = None) -> None:
        self.settings = settings or OxigraphSettings()
        self._base_url = self.settings.base_url.rstrip("/")

    def query(self, sparql: str, graph: str | None = None) -> dict[str, Any]:
        """Execute a SPARQL SELECT/ASK/CONSTRUCT query.

        Returns parsed JSON results for SELECT/ASK, raw text for CONSTRUCT.
        """
        url = f"{self._base_url}/query"
        params = {"query": sparql}
        if graph or self.settings.default_graph:
            params["default-graph-uri"] = graph or self.settings.default_graph

        return self._request(
            url,
            method="POST",
            data=urlencode(params).encode("utf-8"),
            content_type="application/x-www-form-urlencoded",
            accept="application/sparql-results+json",
        )

    def update(self, sparql: str) -> dict[str, Any]:
        """Execute a SPARQL UPDATE (INSERT/DELETE) operation."""
        url = f"{self._base_url}/update"
        data = urlencode({"update": sparql}).encode("utf-8")

        return self._request(
            url,
            method="POST",
            data=data,
            content_type="application/x-www-form-urlencoded",
            accept="*/*",
        )

    def load_triples(self, turtle_data: str, graph: str | None = None) -> dict[str, Any]:
        """Load Turtle triples via SPARQL UPDATE INSERT DATA."""
        graph_uri = graph or self.settings.default_graph
        # If the Turtle document contains prefix/base declarations (common in files),
        # sending it inside a SPARQL `INSERT DATA { ... }` will fail because prefixes
        # are not allowed inside the DATA block. Use the RDF `POST /data` endpoint
        # with content-type `text/turtle` which accepts full Turtle documents.
        doc = turtle_data.lstrip()
        has_prefix = doc.startswith("@") or "@prefix" in doc or doc.upper().startswith("PREFIX")

        if has_prefix:
            url = f"{self._base_url}/data"
            if graph_uri:
                url = f"{url}?graph={quote(graph_uri, safe='')}"
            try:
                return self._request(
                    url,
                    method="POST",
                    data=turtle_data.encode("utf-8"),
                    content_type="text/turtle",
                    accept="*/*",
                )
            except OxigraphQueryError as e:
                msg = str(e)
                # Some Oxigraph builds (or proxied servers) don't support /data.
                # Fall back to parsing the Turtle and inserting expanded N-Triples
                # via SPARQL `INSERT DATA` if rdflib is available.
                if "POST /data is not supported" in msg or "404" in msg:
                    try:
                        from rdflib import Graph  # type: ignore

                        g = Graph()
                        g.parse(data=turtle_data, format="turtle")
                        nt = g.serialize(format="nt")
                        # Build SPARQL INSERT DATA with expanded triples (N-Triples)
                        triples_block = nt.strip()
                        if graph_uri:
                            sparql = f"INSERT DATA {{ GRAPH <{graph_uri}> {{ {triples_block} }} }}"
                        else:
                            sparql = f"INSERT DATA {{ {triples_block} }}"
                        return self.update(sparql)
                    except ModuleNotFoundError:
                        raise RuntimeError(
                            "Oxigraph /data unsupported and 'rdflib' not installed. "
                            "Install optional dependency 'agent-setup[rdf]' or enable /data on the server."
                        )
                raise

        # Fallback: inline triples only (no prefix declarations) can be inserted via SPARQL.
        if graph_uri:
            sparql = f"INSERT DATA {{ GRAPH <{graph_uri}> {{ {turtle_data} }} }}"
        else:
            sparql = f"INSERT DATA {{ {turtle_data} }}"
        return self.update(sparql)

    def health_check(self) -> bool:
        """Check if Oxigraph is reachable."""
        try:
            self.query("ASK {}")
            return True
        except (OxigraphConnectionError, OxigraphQueryError):
            return False

    def _request(
        self,
        url: str,
        method: str,
        data: bytes | None = None,
        content_type: str = "application/x-www-form-urlencoded",
        accept: str = "application/sparql-results+json",
    ) -> dict[str, Any]:
        """Make an HTTP request with retry logic."""
        import json

        req = Request(url, data=data, method=method)
        req.add_header("Content-Type", content_type)
        req.add_header("Accept", accept)

        last_error: Exception | None = None
        for attempt in range(self.settings.max_retries + 1):
            t0 = time.monotonic()
            try:
                with urlopen(req, timeout=self.settings.timeout) as resp:
                    elapsed = time.monotonic() - t0
                    body = resp.read().decode("utf-8")
                    logger.debug(
                        "Oxigraph %s %s -> %d (%.3fs)",
                        method,
                        url,
                        resp.status,
                        elapsed,
                    )
                    if "json" in accept and body.strip():
                        return {"status": resp.status, "data": json.loads(body), "elapsed": elapsed}
                    return {"status": resp.status, "data": body, "elapsed": elapsed}
            except HTTPError as e:
                elapsed = time.monotonic() - t0
                body = e.read().decode("utf-8") if e.fp else ""
                logger.warning(
                    "Oxigraph HTTP %d on attempt %d: %s", e.code, attempt + 1, body[:200]
                )
                last_error = OxigraphQueryError(f"HTTP {e.code}: {body[:500]}")
            except (URLError, TimeoutError, OSError) as e:
                elapsed = time.monotonic() - t0
                logger.warning(
                    "Oxigraph connection error on attempt %d (%.3fs): %s",
                    attempt + 1,
                    elapsed,
                    e,
                )
                last_error = OxigraphConnectionError(str(e))

            if attempt < self.settings.max_retries:
                time.sleep(0.5 * (attempt + 1))

        raise last_error  # type: ignore[misc]
