"""Unit tests for the RDF Dispatcher — classification, injection, policy."""

from unittest.mock import MagicMock, patch

import pytest

from src.shared.rdf_memory.config import (
    LifecyclePolicy,
    PolicyConfig,
    RDFMemorySettings,
    admin_policy,
    default_policy,
)
from src.shared.rdf_memory.dispatcher import RDFDispatcher


@pytest.fixture
def admin_settings():
    return RDFMemorySettings(
        persistent_graphs=["math", "ner", "core"],
        policy=admin_policy(),
    )


@pytest.fixture
def default_settings():
    return RDFMemorySettings(
        persistent_graphs=["math", "ner", "core"],
        policy=default_policy(),
    )


class TestQueryClassification:
    """Verify that all SPARQL operation types are classified correctly."""

    @pytest.mark.parametrize(
        "sparql, expected",
        [
            ("SELECT ?s WHERE { ?s ?p ?o }", "SELECT"),
            ("  select ?s where { ?s ?p ?o }", "SELECT"),
            ("ASK { <s> <p> <o> }", "ASK"),
            ("CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o }", "CONSTRUCT"),
            ("DESCRIBE <http://example.org/>", "DESCRIBE"),
            ("INSERT DATA { <s> <p> <o> }", "INSERT"),
            ("INSERT { ?s ?p ?o } WHERE { ?s ?p ?o }", "INSERT"),
            ("DELETE DATA { <s> <p> <o> }", "DELETE"),
            ("DELETE { ?s ?p ?o } WHERE { ?s ?p ?o }", "DELETE"),
            ("DROP GRAPH <urn:test>", "DROP"),
            ("CLEAR GRAPH <urn:test>", "CLEAR"),
            ("MOVE GRAPH <a> TO GRAPH <b>", "MOVE"),
            ("COPY GRAPH <a> TO GRAPH <b>", "COPY"),
            ("LOAD <file.rdf>", "LOAD"),
            # With PREFIX
            ("PREFIX ex: <http://ex.org/> SELECT ?s WHERE { ?s ex:p ?o }", "SELECT"),
            (
                "PREFIX ex: <http://ex.org/>\nPREFIX rdf: <http://w3.org/rdf#>\n"
                "INSERT DATA { ex:s ex:p ex:o }",
                "INSERT",
            ),
        ],
    )
    def test_classify(self, sparql, expected):
        assert RDFDispatcher._classify(sparql) == expected

    def test_classify_unknown(self):
        assert RDFDispatcher._classify("GIBBERISH") is None


class TestGraphInjection:
    """Verify GRAPH clause wrapping for various query types."""

    def test_select_injection(self):
        sparql = "SELECT ?s ?p ?o WHERE { ?s ?p ?o }"
        result = RDFDispatcher._inject_graph(sparql, "urn:graph:session:abc", "SELECT")
        assert "GRAPH <urn:graph:session:abc>" in result
        assert "WHERE" in result

    def test_insert_data_injection(self):
        sparql = "INSERT DATA { <s> <p> <o> }"
        result = RDFDispatcher._inject_graph(sparql, "urn:graph:session:abc", "INSERT")
        assert "GRAPH <urn:graph:session:abc>" in result

    def test_skip_if_graph_present(self):
        sparql = "SELECT ?s WHERE { GRAPH <urn:custom> { ?s ?p ?o } }"
        result = RDFDispatcher._inject_graph(sparql, "urn:graph:session:abc", "SELECT")
        assert result == sparql

    def test_construct_injection(self):
        sparql = "CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o }"
        result = RDFDispatcher._inject_graph(sparql, "urn:graph:persistent:math", "CONSTRUCT")
        assert "GRAPH <urn:graph:persistent:math>" in result

    def test_ask_injection(self):
        sparql = "ASK WHERE { <s> <p> <o> }"
        result = RDFDispatcher._inject_graph(sparql, "urn:graph:session:abc", "ASK")
        assert "GRAPH <urn:graph:session:abc>" in result


class TestPolicyEnforcement:
    """Verify that the dispatcher enforces the policy correctly."""

    @patch("src.shared.rdf_memory.dispatcher.FusekiClient")
    def test_default_policy_blocks_insert_on_persistent(self, mock_client, default_settings):
        d = RDFDispatcher(settings=default_settings)
        d._client = MagicMock()

        result = d.dispatch(
            sparql="INSERT DATA { <s> <p> <o> }",
            target_lifecycle="persistent",
            session_uuid="test-uuid",
            persistent_graph="math",
        )
        assert result["success"] is False
        assert "not allowed" in result["error"]

    @patch("src.shared.rdf_memory.dispatcher.FusekiClient")
    def test_default_policy_allows_select_on_persistent(self, mock_client, default_settings):
        d = RDFDispatcher(settings=default_settings)
        mock_fuseki = MagicMock()
        mock_fuseki.query.return_value = {"results": {"bindings": []}}
        d._client = mock_fuseki

        result = d.dispatch(
            sparql="SELECT ?s WHERE { ?s ?p ?o }",
            target_lifecycle="persistent",
            session_uuid="test-uuid",
            persistent_graph="math",
        )
        assert result["success"] is True

    @patch("src.shared.rdf_memory.dispatcher.FusekiClient")
    def test_default_policy_allows_insert_on_session(self, mock_client, default_settings):
        d = RDFDispatcher(settings=default_settings)
        mock_fuseki = MagicMock()
        mock_fuseki.update.return_value = True
        d._client = mock_fuseki

        result = d.dispatch(
            sparql="INSERT DATA { <s> <p> <o> }",
            target_lifecycle="session",
            session_uuid="test-uuid",
        )
        assert result["success"] is True

    @patch("src.shared.rdf_memory.dispatcher.FusekiClient")
    def test_requires_flag_blocks_without_force(self, mock_client):
        settings = RDFMemorySettings(
            persistent_graphs=["core"],
            policy=PolicyConfig(
                session=LifecyclePolicy(allowed_operations=["SELECT"]),
                staging=LifecyclePolicy(allowed_operations=["SELECT"]),
                persistent=LifecyclePolicy(
                    allowed_operations=["SELECT", "DELETE"],
                    requires_flag=["DELETE"],
                ),
            ),
        )
        d = RDFDispatcher(settings=settings)
        d._client = MagicMock()

        result = d.dispatch(
            sparql="DELETE DATA { <s> <p> <o> }",
            target_lifecycle="persistent",
            session_uuid="uuid",
            persistent_graph="core",
        )
        assert result["success"] is False
        assert "force=True" in result["error"]

    @patch("src.shared.rdf_memory.dispatcher.FusekiClient")
    def test_requires_flag_passes_with_force(self, mock_client):
        settings = RDFMemorySettings(
            persistent_graphs=["core"],
            policy=PolicyConfig(
                session=LifecyclePolicy(allowed_operations=["SELECT"]),
                staging=LifecyclePolicy(allowed_operations=["SELECT"]),
                persistent=LifecyclePolicy(
                    allowed_operations=["SELECT", "DELETE"],
                    requires_flag=["DELETE"],
                ),
            ),
        )
        d = RDFDispatcher(settings=settings)
        mock_fuseki = MagicMock()
        mock_fuseki.update.return_value = True
        d._client = mock_fuseki

        result = d.dispatch(
            sparql="DELETE DATA { <s> <p> <o> }",
            target_lifecycle="persistent",
            session_uuid="uuid",
            persistent_graph="core",
            force=True,
        )
        assert result["success"] is True


class TestPersistentGraphValidation:
    """Verify that unknown persistent graphs are rejected."""

    @patch("src.shared.rdf_memory.dispatcher.FusekiClient")
    def test_unknown_graph_rejected(self, mock_client, default_settings):
        d = RDFDispatcher(settings=default_settings)
        d._client = MagicMock()

        result = d.dispatch(
            sparql="SELECT ?s WHERE { ?s ?p ?o }",
            target_lifecycle="persistent",
            session_uuid="uuid",
            persistent_graph="nonexistent",
        )
        assert result["success"] is False
        assert "Unknown persistent graph" in result["error"]

    @patch("src.shared.rdf_memory.dispatcher.FusekiClient")
    def test_default_graph_used_when_none(self, mock_client):
        settings = RDFMemorySettings(
            persistent_graphs=["core"],
            default_persistent_graph="core",
            policy=admin_policy(),
        )
        d = RDFDispatcher(settings=settings)
        mock_fuseki = MagicMock()
        mock_fuseki.query.return_value = {"results": {"bindings": []}}
        d._client = mock_fuseki

        result = d.dispatch(
            sparql="SELECT ?s WHERE { ?s ?p ?o }",
            target_lifecycle="persistent",
            session_uuid="uuid",
            persistent_graph=None,
        )
        assert result["success"] is True
        assert "persistent:core" in result["graph"]


class TestDispatchFlow:
    """Verify the full dispatch → classify → inject → execute flow."""

    @patch("src.shared.rdf_memory.dispatcher.FusekiClient")
    def test_select_flow(self, mock_client, admin_settings):
        d = RDFDispatcher(settings=admin_settings)
        mock_fuseki = MagicMock()
        mock_fuseki.query.return_value = {
            "results": {"bindings": [{"s": {"value": "http://test.org/dante"}}]}
        }
        d._client = mock_fuseki

        result = d.dispatch(
            sparql="SELECT ?s WHERE { ?s ?p ?o }",
            target_lifecycle="persistent",
            session_uuid="uuid",
            persistent_graph="math",
        )

        assert result["success"] is True
        assert result["operation"] == "SELECT"
        assert "persistent:math" in result["graph"]
        mock_fuseki.query.assert_called_once()

    @patch("src.shared.rdf_memory.dispatcher.FusekiClient")
    def test_insert_flow(self, mock_client, admin_settings):
        d = RDFDispatcher(settings=admin_settings)
        mock_fuseki = MagicMock()
        mock_fuseki.update.return_value = True
        d._client = mock_fuseki

        result = d.dispatch(
            sparql=(
                "INSERT DATA { <http://test.org/dante>"
                " <http://test.org/wrote> <http://test.org/commedia> }"
            ),
            target_lifecycle="session",
            session_uuid="sess-123",
        )

        assert result["success"] is True
        assert result["operation"] == "INSERT"
        assert "session:sess-123" in result["graph"]
        mock_fuseki.update.assert_called_once()

    @patch("src.shared.rdf_memory.dispatcher.FusekiClient")
    def test_unknown_operation_fails(self, mock_client, admin_settings):
        d = RDFDispatcher(settings=admin_settings)
        d._client = MagicMock()

        result = d.dispatch(
            sparql="GIBBERISH QUERY",
            target_lifecycle="session",
            session_uuid="uuid",
        )
        assert result["success"] is False
        assert result["operation"] == "UNKNOWN"
