"""Unit tests for FusekiClient with mocked HTTP."""

from unittest.mock import MagicMock, patch

import pytest

from src.shared.rdf_memory.config import RDFMemorySettings
from src.shared.rdf_memory.fuseki_client import (
    FusekiClient,
    FusekiConnectionError,
    FusekiQueryError,
)


@pytest.fixture
def settings():
    return RDFMemorySettings(
        fuseki_url="http://localhost:3030",
        dataset="test",
        max_retries=2,
        retry_base_delay=0.01,
    )


@pytest.fixture
def client(settings):
    return FusekiClient(settings)


class TestEndpoints:
    """Verify endpoint URL construction."""

    def test_query_endpoint(self, client):
        assert client._query_endpoint == "http://localhost:3030/test/sparql"

    def test_update_endpoint(self, client):
        assert client._update_endpoint == "http://localhost:3030/test/update"

    def test_gsp_endpoint(self, client):
        assert client._gsp_endpoint == "http://localhost:3030/test/data"


class TestQuery:
    """Verify SPARQLWrapper-based query calls."""

    @patch("src.shared.rdf_memory.fuseki_client.SPARQLWrapper")
    def test_select_query(self, mock_sw_cls, client):
        mock_sw = MagicMock()
        mock_sw_cls.return_value = mock_sw
        mock_result = MagicMock()
        mock_result.convert.return_value = {"results": {"bindings": [{"x": {"value": "42"}}]}}
        mock_sw.query.return_value = mock_result

        result = client.query("SELECT ?x WHERE { ?x ?y ?z }")
        assert "results" in result
        mock_sw.setQuery.assert_called_once()

    @patch("src.shared.rdf_memory.fuseki_client.SPARQLWrapper")
    def test_construct_query_n3_format(self, mock_sw_cls, client):
        mock_sw = MagicMock()
        mock_sw_cls.return_value = mock_sw
        mock_result = MagicMock()
        mock_result.convert.return_value = b"<s> <p> <o> ."
        mock_sw.query.return_value = mock_result

        result = client.query("CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o }", "n3")
        assert "results" in result


class TestUpdate:
    """Verify httpx-based update calls."""

    def test_update_success(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        client._http = MagicMock()
        client._http.post.return_value = mock_resp

        assert client.update("INSERT DATA { <s> <p> <o> }") is True

    def test_update_failure_raises(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.text = "Parse error"
        client._http = MagicMock()
        client._http.post.return_value = mock_resp

        with pytest.raises(FusekiQueryError, match="Parse error"):
            client.update("INVALID SPARQL")


class TestRetry:
    """Verify exponential backoff retry logic."""

    def test_retries_on_connection_error(self, settings):
        import httpx

        client = FusekiClient(settings)
        call_count = 0

        def failing_fn():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise httpx.ConnectError("refused")
            return "ok"

        result = client._retry(failing_fn, "test")
        assert result == "ok"
        assert call_count == 3

    def test_max_retries_exceeded(self, settings):
        import httpx

        client = FusekiClient(settings)

        def always_fail():
            raise httpx.ConnectError("refused")

        with pytest.raises(FusekiConnectionError, match="failed after"):
            client._retry(always_fail, "test")

    def test_fuseki_error_not_retried(self, settings):
        client = FusekiClient(settings)
        call_count = 0

        def raises_query_error():
            nonlocal call_count
            call_count += 1
            raise FusekiQueryError("bad query")

        with pytest.raises(FusekiQueryError):
            client._retry(raises_query_error, "test")
        assert call_count == 1


class TestGetGraph:
    """Verify Graph Store Protocol GET."""

    def test_get_graph_success(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "<s> <p> <o> ."
        client._http = MagicMock()
        client._http.get.return_value = mock_resp

        result = client.get_graph("urn:graph:test", fmt="turtle")
        assert "<s> <p> <o>" in result

    def test_get_graph_404_returns_empty(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        client._http = MagicMock()
        client._http.get.return_value = mock_resp

        result = client.get_graph("urn:graph:missing")
        assert result == ""
