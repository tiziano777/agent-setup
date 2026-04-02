"""RDF Dispatcher — business layer for the rdf_memory module.

Classifies incoming SPARQL, enforces lifecycle policies, injects the
correct named-graph URI, emits OTel spans, and delegates execution to
:class:`~src.shared.rdf_memory.fuseki_client.FusekiClient`.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Literal

from src.shared.rdf_memory.config import RDFMemorySettings
from src.shared.rdf_memory.fuseki_client import FusekiClient
from src.shared.rdf_memory.graph_lifecycle import (
    export_graph,
    promote_graph,
    purge_session_graphs,
    resolve_graph_uri,
)
from src.shared.rdf_memory.otel_hooks import traced_sparql

logger = logging.getLogger(__name__)

# ── SPARQL operation classification ──────────────────────────────────

# Prefixes are stripped before matching so the regex only needs to
# match the first keyword of the actual query body.
_PREFIX_RE = re.compile(r"(?:PREFIX\s+\S+:\s*<[^>]*>\s*)+", re.IGNORECASE)

_OPERATION_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("SELECT", re.compile(r"^\s*SELECT\b", re.IGNORECASE)),
    ("ASK", re.compile(r"^\s*ASK\b", re.IGNORECASE)),
    ("CONSTRUCT", re.compile(r"^\s*CONSTRUCT\b", re.IGNORECASE)),
    ("DESCRIBE", re.compile(r"^\s*DESCRIBE\b", re.IGNORECASE)),
    ("INSERT", re.compile(r"^\s*INSERT\b", re.IGNORECASE)),
    ("DELETE", re.compile(r"^\s*DELETE\b", re.IGNORECASE)),
    ("DROP", re.compile(r"^\s*DROP\b", re.IGNORECASE)),
    ("CLEAR", re.compile(r"^\s*CLEAR\b", re.IGNORECASE)),
    ("MOVE", re.compile(r"^\s*MOVE\b", re.IGNORECASE)),
    ("COPY", re.compile(r"^\s*COPY\b", re.IGNORECASE)),
    ("LOAD", re.compile(r"^\s*LOAD\b", re.IGNORECASE)),
    ("ADD", re.compile(r"^\s*ADD\b", re.IGNORECASE)),
]

_READ_OPS = frozenset({"SELECT", "ASK", "CONSTRUCT", "DESCRIBE"})

# ── Graph injection patterns ─────────────────────────────────────────

_WHERE_BRACE = re.compile(r"(WHERE\s*)\{", re.IGNORECASE)
_DATA_BRACE = re.compile(r"(DATA\s*)\{", re.IGNORECASE)
_GRAPH_PRESENT = re.compile(r"\bGRAPH\s*<", re.IGNORECASE)


# ── Dispatcher ───────────────────────────────────────────────────────


class RDFDispatcher:
    """Central dispatch layer: classify → policy-check → inject graph → execute."""

    def __init__(self, settings: RDFMemorySettings | None = None) -> None:
        self._settings = settings or RDFMemorySettings()
        self._client = FusekiClient(self._settings)

    # ── Main entry point ─────────────────────────────────────────────

    def dispatch(
        self,
        sparql: str,
        target_lifecycle: Literal["session", "staging", "persistent"],
        session_uuid: str,
        persistent_graph: str | None = None,
        force: bool = False,
        run_manager: Any = None,
    ) -> dict[str, Any]:
        """Classify, validate, inject named graph, execute, and return results.

        Args:
            persistent_graph: Required when *target_lifecycle* is ``"persistent"``.
                Falls back to ``settings.default_persistent_graph`` when *None*.
            run_manager: Optional LangChain RunManager for explicit trace linkage
                (fallback to OpenTelemetry contextvars if not provided).

        Returns:
            ``{"success": bool, "operation": str, "data": ..., "graph": str}``
            On failure: ``{"success": False, "error": str, "operation": str, "graph": str}``
        """
        # 1. Classify
        operation = self._classify(sparql)
        if operation is None:
            return {
                "success": False,
                "error": f"Unable to classify SPARQL operation: {sparql[:200]}",
                "operation": "UNKNOWN",
                "graph": "",
            }

        # 2. Resolve persistent graph name
        if target_lifecycle == "persistent":
            persistent_graph = persistent_graph or self._settings.default_persistent_graph
            if persistent_graph not in self._settings.persistent_graphs:
                return {
                    "success": False,
                    "error": (
                        f"Unknown persistent graph '{persistent_graph}'. "
                        f"Available: {self._settings.persistent_graphs}"
                    ),
                    "operation": operation,
                    "graph": "",
                }

        # 3. Policy check
        policy_error = self._check_policy(operation, target_lifecycle, force)
        if policy_error:
            return {
                "success": False,
                "error": policy_error,
                "operation": operation,
                "graph": "",
            }

        # 4. Resolve named graph URI
        graph_uri = resolve_graph_uri(target_lifecycle, session_uuid, persistent_graph)

        # 5. Inject GRAPH clause
        injected = self._inject_graph(sparql, graph_uri, operation)

        # 6. Execute with OTel span
        with traced_sparql(
            operation,
            target_lifecycle,
            run_manager=run_manager,
            query_preview=sparql[:300],
            session_graph=graph_uri,
        ) as span:
            try:
                if operation in _READ_OPS:
                    data = self._client.query(injected)
                else:
                    data = self._client.update(injected)
                span.set_attribute("rdf.success", "true")
            except Exception as exc:
                span.set_attribute("rdf.success", "false")
                span.set_attribute("rdf.error", str(exc)[:300])
                logger.exception("Dispatch failed for %s on <%s>", operation, graph_uri)
                return {
                    "success": False,
                    "error": str(exc),
                    "operation": operation,
                    "graph": graph_uri,
                }

        return {
            "success": True,
            "operation": operation,
            "data": data,
            "graph": graph_uri,
        }

    # ── Convenience wrappers ─────────────────────────────────────────

    def promote(
        self,
        from_lifecycle: Literal["session", "staging", "persistent"],
        to_lifecycle: Literal["session", "staging", "persistent"],
        session_uuid: str,
        mode: Literal["move", "copy"] = "move",
        from_persistent_graph: str | None = None,
        to_persistent_graph: str | None = None,
    ) -> bool:
        return promote_graph(
            self._client,
            from_lifecycle,
            to_lifecycle,
            session_uuid,
            mode=mode,
            from_persistent_graph=from_persistent_graph,
            to_persistent_graph=to_persistent_graph,
        )

    def purge_session(self, session_uuid: str) -> bool:
        return purge_session_graphs(self._client, session_uuid)

    def export(
        self,
        lifecycle: Literal["session", "staging", "persistent"],
        session_uuid: str,
        persistent_graph: str | None = None,
        fmt: Literal["turtle", "json-ld", "n-triples"] = "turtle",
    ) -> str:
        return export_graph(
            self._client,
            lifecycle,
            session_uuid,
            persistent_graph,
            fmt,
        )

    # ── Internal helpers ─────────────────────────────────────────────

    @staticmethod
    def _classify(sparql: str) -> str | None:
        """Detect the SPARQL operation type by matching the first keyword."""
        body = _PREFIX_RE.sub("", sparql).strip()
        for op_name, pattern in _OPERATION_PATTERNS:
            if pattern.match(body):
                return op_name
        return None

    def _check_policy(
        self,
        operation: str,
        lifecycle: Literal["session", "staging", "persistent"],
        force: bool,
    ) -> str | None:
        """Return an error message if the operation is not allowed, else *None*."""
        lp = getattr(self._settings.policy, lifecycle)

        if operation not in lp.allowed_operations:
            return (
                f"Operation {operation} is not allowed on lifecycle '{lifecycle}'. "
                f"Allowed: {lp.allowed_operations}"
            )

        if operation in lp.requires_flag and not force:
            return (
                f"Operation {operation} on '{lifecycle}' requires explicit "
                f"confirmation (force=True)"
            )

        return None

    @staticmethod
    def _inject_graph(sparql: str, graph_uri: str, operation: str) -> str:
        """Wrap the query body with a ``GRAPH <uri>`` clause.

        Skips injection if the query already contains an explicit ``GRAPH <`` clause.
        """
        if _GRAPH_PRESENT.search(sparql):
            return sparql

        graph_clause = f"GRAPH <{graph_uri}> {{"

        # INSERT DATA { ... } / DELETE DATA { ... }
        if _DATA_BRACE.search(sparql):
            return _DATA_BRACE.sub(rf"\g<1>{{ {graph_clause} ", sparql, count=1) + " }"

        # SELECT / ASK / CONSTRUCT ... WHERE { ... }
        if _WHERE_BRACE.search(sparql):
            return _WHERE_BRACE.sub(rf"\g<1>{{ {graph_clause} ", sparql, count=1) + " }"

        return sparql
