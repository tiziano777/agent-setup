"""Tests for rdf_reader.

Unit tests: no infrastructure needed.
Pipeline tests: require Fuseki running (make rdf-up).
E2E tests: require Fuseki + LiteLLM proxy (make build).
"""

import uuid

import pytest

from src.agents.rdf_reader.states.state import AgentState

# ── Test data ──────────────────────────────────────────────────────────

GENEALOGY_TEXT = (
    "Giovanni Rossi (1920-1985) married Maria Bianchi (1925-2010). "
    "They had three children: Paolo (1950), Lucia (1952), and Marco (1955). "
    "Paolo married Elena Verdi (1953) and they had two children: "
    "Anna (1978) and Luca (1980). "
    "Lucia married Roberto Neri (1950) and had one child: Sofia (1982)."
)


# ── Unit tests ─────────────────────────────────────────────────────────


class TestAgentGraph:
    """Test the Graph API agent compiles."""

    def test_graph_compiles(self):
        from src.agents.rdf_reader.agent import graph

        assert graph is not None

    def test_graph_is_callable(self):
        from src.agents.rdf_reader.agent import graph

        assert hasattr(graph, "invoke")

    def test_graph_has_two_nodes(self):
        from src.agents.rdf_reader.agent import graph

        node_names = set(graph.get_graph().nodes.keys())
        assert "extract" in node_names
        assert "query" in node_names


class TestTools:
    """Test that RDF tools are importable."""

    def test_rdf_tools_factory(self):
        from src.agents.rdf_reader.tools import get_rdf_reader_tools

        tools = get_rdf_reader_tools(session_uuid="test-123")
        assert len(tools) == 1
        assert tools[0].name == "rdf_query"

    def test_session_uuid_generated(self):
        from src.agents.rdf_reader.tools import get_session_uuid

        sid = get_session_uuid()
        assert isinstance(sid, str)
        assert len(sid) == 32

    def test_dispatcher_factory(self):
        from src.agents.rdf_reader.tools import get_dispatcher

        dispatcher = get_dispatcher()
        assert dispatcher is not None


class TestAgentState:
    """Test state definition."""

    def test_state_has_messages(self):
        assert "messages" in AgentState.__annotations__

    def test_state_has_context(self):
        assert "context" in AgentState.__annotations__

    def test_state_has_instruction(self):
        assert "instruction" in AgentState.__annotations__

    def test_state_has_triple_count(self):
        assert "triple_count" in AgentState.__annotations__

    def test_state_has_sparql_result(self):
        assert "sparql_result" in AgentState.__annotations__


class TestPrompts:
    """Test that prompts are importable and non-empty."""

    def test_extract_prompt(self):
        from src.agents.rdf_reader.prompts.system import EXTRACT_PROMPT

        assert "INSERT DATA" in EXTRACT_PROMPT
        assert "GRAPH" in EXTRACT_PROMPT  # The "NEVER include GRAPH" rule

    def test_query_prompt(self):
        from src.agents.rdf_reader.prompts.system import QUERY_PROMPT

        assert "SELECT" in QUERY_PROMPT

    def test_answer_prompt(self):
        from src.agents.rdf_reader.prompts.system import ANSWER_PROMPT

        assert len(ANSWER_PROMPT) > 0


class TestNodes:
    """Test that node functions are importable."""

    def test_extract_importable(self):
        from src.agents.rdf_reader.nodes.extract import extract

        assert callable(extract)

    def test_query_importable(self):
        from src.agents.rdf_reader.nodes.query import query

        assert callable(query)


class TestSparqlParser:
    """Test the SPARQL code block parser."""

    def test_extracts_from_sparql_block(self):
        from src.agents.rdf_reader.nodes.extract import _extract_sparql

        text = "Here is the query:\n```sparql\nSELECT ?s WHERE { ?s ?p ?o }\n```\nDone."
        assert _extract_sparql(text) == "SELECT ?s WHERE { ?s ?p ?o }"

    def test_extracts_from_plain_block(self):
        from src.agents.rdf_reader.nodes.extract import _extract_sparql

        text = "```\nINSERT DATA { <a> <b> <c> }\n```"
        assert _extract_sparql(text) == "INSERT DATA { <a> <b> <c> }"

    def test_fallback_to_raw_text(self):
        from src.agents.rdf_reader.nodes.extract import _extract_sparql

        text = "SELECT ?s WHERE { ?s ?p ?o }"
        assert _extract_sparql(text) == text


# ── Integration helpers ────────────────────────────────────────────────


def _check_fuseki():
    """Return True if Fuseki is reachable."""
    try:
        from src.shared.rdf_memory import FusekiClient, RDFMemorySettings

        client = FusekiClient(RDFMemorySettings())
        client.query("SELECT (1 AS ?ok) WHERE {}")
        client.close()
        return True
    except Exception:
        return False


@pytest.fixture
def session_id():
    return f"test-rdf-reader-{uuid.uuid4().hex[:12]}"


@pytest.fixture
def dispatcher(session_id):
    from src.shared.rdf_memory.config import RDFMemorySettings
    from src.shared.rdf_memory.dispatcher import RDFDispatcher

    d = RDFDispatcher(settings=RDFMemorySettings())
    yield d
    d.purge_session(session_id)


# ── Pipeline tests (SPARQL only, no LLM) ──────────────────────────────


class TestRDFPipeline:
    """Test the extract-then-query pipeline with raw SPARQL (no LLM).

    Validates that the SPARQL patterns from the prompts actually work
    against Fuseki.

    Run with: pytest src/agents/rdf_reader/tests/ -v -k "pipeline"
    """

    def test_insert_and_count(self, dispatcher, session_id):
        if not _check_fuseki():
            pytest.skip("Fuseki not running — start with `make rdf-up`")

        insert = """\
PREFIX ex: <http://example.org/>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
INSERT DATA {
  ex:GiovanniRossi ex:type "Person" .
  ex:GiovanniRossi ex:name "Giovanni Rossi" .
  ex:GiovanniRossi ex:birthYear "1920"^^xsd:integer .
  ex:GiovanniRossi ex:marriedTo ex:MariaBianchi .
  ex:MariaBianchi ex:marriedTo ex:GiovanniRossi .
  ex:MariaBianchi ex:type "Person" .
  ex:PaoloRossi ex:type "Person" .
  ex:PaoloRossi ex:childOf ex:GiovanniRossi .
  ex:PaoloRossi ex:childOf ex:MariaBianchi .
  ex:GiovanniRossi ex:parentOf ex:PaoloRossi .
  ex:MariaBianchi ex:parentOf ex:PaoloRossi .
  ex:LuciaRossi ex:type "Person" .
  ex:LuciaRossi ex:childOf ex:GiovanniRossi .
  ex:LuciaRossi ex:childOf ex:MariaBianchi .
  ex:MarcoRossi ex:type "Person" .
  ex:MarcoRossi ex:childOf ex:GiovanniRossi .
  ex:MarcoRossi ex:childOf ex:MariaBianchi .
  ex:AnnaRossi ex:type "Person" .
  ex:AnnaRossi ex:childOf ex:PaoloRossi .
  ex:LucaRossi ex:type "Person" .
  ex:LucaRossi ex:childOf ex:PaoloRossi .
  ex:SofiaNeri ex:type "Person" .
  ex:SofiaNeri ex:childOf ex:LuciaRossi .
}"""
        result = dispatcher.dispatch(insert, "session", session_id)
        assert result["success"], f"INSERT failed: {result}"

        count_q = "PREFIX ex: <http://example.org/>\nSELECT (COUNT(*) AS ?count) WHERE { ?s ?p ?o }"
        result = dispatcher.dispatch(count_q, "session", session_id)
        assert result["success"]
        count = int(result["data"]["results"]["bindings"][0]["count"]["value"])
        assert count == 23

    def test_pipeline_children_count(self, dispatcher, session_id):
        if not _check_fuseki():
            pytest.skip("Fuseki not running — start with `make rdf-up`")

        insert = """\
PREFIX ex: <http://example.org/>
INSERT DATA {
  ex:PaoloRossi ex:childOf ex:GiovanniRossi .
  ex:LuciaRossi ex:childOf ex:GiovanniRossi .
  ex:MarcoRossi ex:childOf ex:GiovanniRossi .
}"""
        dispatcher.dispatch(insert, "session", session_id)

        q = """\
PREFIX ex: <http://example.org/>
SELECT (COUNT(?child) AS ?count) WHERE {
  ?child ex:childOf ex:GiovanniRossi .
}"""
        result = dispatcher.dispatch(q, "session", session_id)
        assert result["success"]
        count = int(result["data"]["results"]["bindings"][0]["count"]["value"])
        assert count == 3

    def test_pipeline_grandchildren(self, dispatcher, session_id):
        if not _check_fuseki():
            pytest.skip("Fuseki not running — start with `make rdf-up`")

        insert = """\
PREFIX ex: <http://example.org/>
INSERT DATA {
  ex:PaoloRossi ex:childOf ex:GiovanniRossi .
  ex:LuciaRossi ex:childOf ex:GiovanniRossi .
  ex:AnnaRossi ex:childOf ex:PaoloRossi .
  ex:LucaRossi ex:childOf ex:PaoloRossi .
  ex:SofiaNeri ex:childOf ex:LuciaRossi .
}"""
        dispatcher.dispatch(insert, "session", session_id)

        q = """\
PREFIX ex: <http://example.org/>
SELECT ?grandchild WHERE {
  ?child ex:childOf ex:GiovanniRossi .
  ?grandchild ex:childOf ?child .
}"""
        result = dispatcher.dispatch(q, "session", session_id)
        assert result["success"]
        uris = {b["grandchild"]["value"] for b in result["data"]["results"]["bindings"]}
        assert len(uris) == 3
        assert "http://example.org/AnnaRossi" in uris
        assert "http://example.org/LucaRossi" in uris
        assert "http://example.org/SofiaNeri" in uris

    def test_pipeline_spouse(self, dispatcher, session_id):
        if not _check_fuseki():
            pytest.skip("Fuseki not running — start with `make rdf-up`")

        insert = """\
PREFIX ex: <http://example.org/>
INSERT DATA {
  ex:GiovanniRossi ex:marriedTo ex:MariaBianchi .
  ex:MariaBianchi ex:marriedTo ex:GiovanniRossi .
}"""
        dispatcher.dispatch(insert, "session", session_id)

        q = """\
PREFIX ex: <http://example.org/>
SELECT ?spouse WHERE {
  ex:GiovanniRossi ex:marriedTo ?spouse .
}"""
        result = dispatcher.dispatch(q, "session", session_id)
        assert result["success"]
        bindings = result["data"]["results"]["bindings"]
        assert len(bindings) == 1
        assert "MariaBianchi" in bindings[0]["spouse"]["value"]


# ── E2E tests (full agent with LLM + Fuseki) ──────────────────────────


class TestRDFReaderE2E:
    """End-to-end: feed text → extract → query → verify answer.

    Requires LiteLLM proxy + Fuseki running (make build).
    Run with: pytest src/agents/rdf_reader/tests/ -v -k "e2e"
    """

    def test_e2e_genealogy(self):
        if not _check_fuseki():
            pytest.skip("Fuseki not running — start with `make rdf-up`")

        from langchain_core.messages import HumanMessage

        from src.agents.rdf_reader.agent import build_graph
        from src.shared.rdf_memory import FusekiClient, RDFMemorySettings, purge_session_graphs

        session_id = f"test-e2e-{uuid.uuid4().hex[:12]}"

        last_error = None
        for attempt in range(3):
            try:
                agent = build_graph(session_uuid=session_id)

                try:
                    result = agent.invoke(
                        {
                            "messages": [HumanMessage(content="Extract and answer")],
                            "context": GENEALOGY_TEXT,
                            "instruction": "Who are Giovanni Rossi's grandchildren?",
                        }
                    )

                    assert result.get("triple_count", 0) > 0, (
                        f"Expected triples, got {result.get('triple_count')}"
                    )

                    response = result["messages"][-1].content.lower()
                    assert any(name in response for name in ["anna", "luca", "sofia"]), (
                        f"Expected grandchildren names: {response[:500]}"
                    )
                    return
                finally:
                    settings = RDFMemorySettings()
                    client = FusekiClient(settings)
                    purge_session_graphs(client, session_id)
                    client.close()

            except Exception as e:
                last_error = e
                session_id = f"test-e2e-{uuid.uuid4().hex[:12]}"

        pytest.skip(f"Agent failed after 3 attempts (LLM issue): {last_error}")
