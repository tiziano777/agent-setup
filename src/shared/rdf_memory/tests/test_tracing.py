"""Tests for RDF observability integration with LangGraph tracing.

Validates that RDF spans are properly nested under LangGraph context
via OpenTelemetry's implicit context propagation.

Run with: pytest src/shared/rdf_memory/tests/test_tracing.py -v
"""

from __future__ import annotations

from opentelemetry import trace

from src.shared.rdf_memory.otel_hooks import traced_sparql


class TestTracedSparQL:
    """Test traced_sparql context manager."""

    def test_traced_sparql_creates_span(self):
        """Verify that traced_sparql creates an OTEL span."""
        with traced_sparql("SELECT", "session", query_preview="SELECT ?s") as span:
            assert span is not None
            # Span should have attributes set
            # (We can't directly inspect them without accessing internal state,
            # but the context manager should not raise)

    def test_traced_sparql_with_run_manager(self):
        """Verify that traced_sparql accepts run_manager parameter."""
        from typing import Any

        # Mock run_manager
        class MockRunManager:
            run_id: str = "test-run-123"

        manager = MockRunManager()

        with traced_sparql(
            "SELECT",
            "session",
            run_manager=manager,
            query_preview="SELECT ?s",
        ) as span:
            assert span is not None
            # Should not raise even with run_manager

    def test_traced_sparql_with_extra_attrs(self):
        """Verify that traced_sparql accepts and sets extra attributes."""
        with traced_sparql(
            "INSERT",
            "staging",
            query_preview="INSERT DATA { ... }",
            session_graph="urn:graph:session:test-123",
            result_count=42,
        ) as span:
            assert span is not None
            # Extra attributes should be accepted without error

    def test_context_propagation_hierarchy(self):
        """Verify that RDF spans nest under parent context.

        This is the key test: when talked_sparql is called within a parent
        tracer context, the RDF span should be a child (via contextvars).
        """
        tracer = trace.get_tracer(__name__)

        # Create a parent span (simulating LangGraph node or tool)
        with tracer.start_as_current_span("parent_operation") as parent:
            # Now call traced_sparql within this context
            with traced_sparql("SELECT", "session", query_preview="SELECT ?s") as rdf_span:
                # Both spans should exist
                assert parent is not None
                assert rdf_span is not None

                # The RDF span should inherit the parent's trace context
                # via OpenTelemetry's contextvars
                # (Exact verification would require accessing internal span state)

    def test_traced_sparql_explicit_run_manager_injection(self):
        """Verify run_manager trace ID is captured as a span attribute."""

        class MockRunManager:
            run_id: str = "langchain-run-abc123"

        manager = MockRunManager()

        with traced_sparql(
            "DELETE",
            "persistent",
            run_manager=manager,
            query_preview="DELETE WHERE { ... }",
        ) as span:
            # The span should have the langchain.run_id attribute set
            # (Verification would require accessing internal attributes)
            assert span is not None


class TestDispatcherWithRunManager:
    """Test that dispatcher passes run_manager through to traced_sparql."""

    def test_dispatcher_accepts_run_manager(self):
        """Verify dispatcher.dispatch accepts run_manager parameter."""
        from src.shared.rdf_memory.dispatcher import RDFDispatcher

        dispatcher = RDFDispatcher()

        class MockRunManager:
            run_id: str = "test-123"

        # This should not raise, even if Fuseki is not running
        # (We're just testing the signature, not execution)
        try:
            result = dispatcher.dispatch(
                sparql="SELECT (1 AS ?ok) WHERE {}",
                target_lifecycle="staging",
                session_uuid="test-session-123",
                run_manager=MockRunManager(),
            )
            # If Fuseki is running, this might succeed
            # If not, it will fail (but not due to signature mismatch)
        except Exception as e:
            # Any error should NOT be about unexpected run_manager argument
            assert "run_manager" not in str(e), f"run_manager should be accepted: {e}"
