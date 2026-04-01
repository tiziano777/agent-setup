"""Integration tests for rdf_memory module.

Prerequisites: Fuseki running (`make rdf-up`).

These tests interact with a real Fuseki instance. They create and clean up
their own named graphs using unique session UUIDs.
"""

import uuid

import pytest

from src.shared.rdf_memory.config import RDFMemorySettings, admin_policy
from src.shared.rdf_memory.dispatcher import RDFDispatcher
from src.shared.rdf_memory.fuseki_client import FusekiClient
from src.shared.rdf_memory.graph_lifecycle import (
    promote_graph,
    purge_session_graphs,
    resolve_graph_uri,
)

# ── Helpers ──────────────────────────────────────────────────────────

TEST_NS = "http://test.rdf-memory.org"


def _make_settings(**overrides) -> RDFMemorySettings:
    defaults = dict(
        persistent_graphs=["math", "ner", "core"],
        default_persistent_graph="core",
        policy=admin_policy(),
        max_retries=1,
        retry_base_delay=0.1,
    )
    defaults.update(overrides)
    return RDFMemorySettings(**defaults)


def _check_fuseki(settings: RDFMemorySettings) -> bool:
    """Return True if Fuseki is reachable."""
    try:
        client = FusekiClient(settings)
        client.query("SELECT (1 AS ?ok) WHERE {}")
        return True
    except Exception:
        return False


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def settings():
    s = _make_settings()
    if not _check_fuseki(s):
        pytest.skip("Fuseki not running — start with `make rdf-up`")
    return s


@pytest.fixture
def session_id():
    return f"test-{uuid.uuid4().hex[:12]}"


@pytest.fixture
def client(settings):
    c = FusekiClient(settings)
    yield c
    c.close()


@pytest.fixture
def dispatcher(settings):
    return RDFDispatcher(settings=settings)


# ── Test 1: Persistent graph read/write ──────────────────────────────


class TestPersistentGraph:
    """[TEST MODE] Insert triples into persistent:math, query them back."""

    def test_insert_and_select(self, dispatcher, session_id):
        graph = "math"
        # Insert
        insert_sparql = (
            f"INSERT DATA {{ "
            f"<{TEST_NS}/formula/pythagorean> "
            f"<{TEST_NS}/prop/expression> "
            f'"a² + b² = c²" }}'
        )
        result = dispatcher.dispatch(
            sparql=insert_sparql,
            target_lifecycle="persistent",
            session_uuid=session_id,
            persistent_graph=graph,
        )
        assert result["success"] is True, f"INSERT failed: {result}"

        # Select
        select_sparql = (
            f"SELECT ?expr WHERE {{ "
            f"<{TEST_NS}/formula/pythagorean> "
            f"<{TEST_NS}/prop/expression> ?expr }}"
        )
        result = dispatcher.dispatch(
            sparql=select_sparql,
            target_lifecycle="persistent",
            session_uuid=session_id,
            persistent_graph=graph,
        )
        assert result["success"] is True
        bindings = result["data"]["results"]["bindings"]
        assert len(bindings) >= 1
        assert "a² + b² = c²" in bindings[0]["expr"]["value"]

        # Cleanup
        dispatcher.dispatch(
            sparql=f"CLEAR GRAPH <{resolve_graph_uri('persistent', session_id, graph)}>",
            target_lifecycle="persistent",
            session_uuid=session_id,
            persistent_graph=graph,
            force=True,
        )


# ── Test 2: Session lifecycle ────────────────────────────────────────


class TestSessionLifecycle:
    """[TEST MODE] Build a session KB from informational text, then query it."""

    def test_session_kb_build_and_query(self, dispatcher, session_id):
        # Simulate an agent building a session KB from user-provided text.
        # Text: "Dante Alighieri nacque a Firenze nel 1265.
        #         Scrisse la Divina Commedia, completata nel 1320.
        #         L'opera è divisa in Inferno, Purgatorio e Paradiso."
        triples = [
            (
                f"<{TEST_NS}/person/dante>",
                f"<{TEST_NS}/prop/birthPlace>",
                f"<{TEST_NS}/place/firenze>",
            ),
            (
                f"<{TEST_NS}/person/dante>",
                f"<{TEST_NS}/prop/birthYear>",
                '"1265"^^<http://www.w3.org/2001/XMLSchema#integer>',
            ),
            (
                f"<{TEST_NS}/person/dante>",
                f"<{TEST_NS}/prop/wrote>",
                f"<{TEST_NS}/work/divina_commedia>",
            ),
            (
                f"<{TEST_NS}/work/divina_commedia>",
                f"<{TEST_NS}/prop/completionYear>",
                '"1320"^^<http://www.w3.org/2001/XMLSchema#integer>',
            ),
            (
                f"<{TEST_NS}/work/divina_commedia>",
                f"<{TEST_NS}/prop/hasPart>",
                f"<{TEST_NS}/work/inferno>",
            ),
            (
                f"<{TEST_NS}/work/divina_commedia>",
                f"<{TEST_NS}/prop/hasPart>",
                f"<{TEST_NS}/work/purgatorio>",
            ),
            (
                f"<{TEST_NS}/work/divina_commedia>",
                f"<{TEST_NS}/prop/hasPart>",
                f"<{TEST_NS}/work/paradiso>",
            ),
        ]

        # Insert all triples
        triple_str = " . ".join(f"{s} {p} {o}" for s, p, o in triples)
        insert_sparql = f"INSERT DATA {{ {triple_str} }}"
        result = dispatcher.dispatch(
            sparql=insert_sparql,
            target_lifecycle="session",
            session_uuid=session_id,
        )
        assert result["success"] is True

        # Query: "Dove nacque Dante?"
        select_sparql = (
            f"SELECT ?place WHERE {{ <{TEST_NS}/person/dante> <{TEST_NS}/prop/birthPlace> ?place }}"
        )
        result = dispatcher.dispatch(
            sparql=select_sparql,
            target_lifecycle="session",
            session_uuid=session_id,
        )
        assert result["success"] is True
        bindings = result["data"]["results"]["bindings"]
        assert len(bindings) == 1
        assert "firenze" in bindings[0]["place"]["value"]

        # Query: "Quante parti ha la Divina Commedia?"
        count_sparql = (
            f"SELECT (COUNT(?part) AS ?count) WHERE {{ "
            f"<{TEST_NS}/work/divina_commedia> <{TEST_NS}/prop/hasPart> ?part }}"
        )
        result = dispatcher.dispatch(
            sparql=count_sparql,
            target_lifecycle="session",
            session_uuid=session_id,
        )
        assert result["success"] is True
        count = int(result["data"]["results"]["bindings"][0]["count"]["value"])
        assert count == 3

        # Cleanup
        dispatcher.purge_session(session_id)


# ── Test 3: Multi-persistent graph isolation ─────────────────────────


class TestMultiPersistentIsolation:
    """[TEST MODE] Data in persistent:math must NOT appear in persistent:ner."""

    def test_graph_isolation(self, dispatcher, session_id):
        # Insert into persistent:math
        math_insert = (
            f"INSERT DATA {{ <{TEST_NS}/formula/euler> "
            f'<{TEST_NS}/prop/expression> "e^(iπ) + 1 = 0" }}'
        )
        dispatcher.dispatch(
            sparql=math_insert,
            target_lifecycle="persistent",
            session_uuid=session_id,
            persistent_graph="math",
        )

        # Insert into persistent:ner
        ner_insert = f'INSERT DATA {{ <{TEST_NS}/entity/einstein> <{TEST_NS}/prop/type> "Person" }}'
        dispatcher.dispatch(
            sparql=ner_insert,
            target_lifecycle="persistent",
            session_uuid=session_id,
            persistent_graph="ner",
        )

        # Query math — should find Euler
        result = dispatcher.dispatch(
            sparql=f"SELECT ?e WHERE {{ ?e <{TEST_NS}/prop/expression> ?v }}",
            target_lifecycle="persistent",
            session_uuid=session_id,
            persistent_graph="math",
        )
        assert result["success"] is True
        math_bindings = result["data"]["results"]["bindings"]
        assert any("euler" in b["e"]["value"] for b in math_bindings)

        # Query ner — should NOT find Euler
        result = dispatcher.dispatch(
            sparql=f"SELECT ?e WHERE {{ ?e <{TEST_NS}/prop/expression> ?v }}",
            target_lifecycle="persistent",
            session_uuid=session_id,
            persistent_graph="ner",
        )
        assert result["success"] is True
        ner_bindings = result["data"]["results"]["bindings"]
        assert not any("euler" in b.get("e", {}).get("value", "") for b in ner_bindings)

        # Cleanup
        math_uri = resolve_graph_uri("persistent", session_id, "math")
        ner_uri = resolve_graph_uri("persistent", session_id, "ner")
        client = dispatcher._client
        client.update(f"DROP SILENT GRAPH <{math_uri}>")
        client.update(f"DROP SILENT GRAPH <{ner_uri}>")


# ── Test 4: Promotion (move + copy) ─────────────────────────────────


class TestPromotion:
    """[TEST MODE] session → persistent:core promotion with move and copy."""

    def test_promote_move(self, client, session_id):
        session_uri = resolve_graph_uri("session", session_id)
        core_uri = resolve_graph_uri("persistent", session_id, "core")

        # Insert into session
        client.update(
            f"INSERT DATA {{ GRAPH <{session_uri}> {{ "
            f'<{TEST_NS}/fact/x> <{TEST_NS}/prop/val> "42" }} }}'
        )

        # Promote (move)
        ok = promote_graph(
            client,
            from_lifecycle="session",
            to_lifecycle="persistent",
            session_uuid=session_id,
            mode="move",
            to_persistent_graph="core",
        )
        assert ok is True

        # Verify in persistent
        res = client.query(
            f"SELECT ?v WHERE {{ GRAPH <{core_uri}> {{ "
            f"<{TEST_NS}/fact/x> <{TEST_NS}/prop/val> ?v }} }}"
        )
        assert len(res["results"]["bindings"]) == 1
        assert res["results"]["bindings"][0]["v"]["value"] == "42"

        # Verify NOT in session (move empties source)
        res = client.query(
            f"SELECT ?v WHERE {{ GRAPH <{session_uri}> {{ "
            f"<{TEST_NS}/fact/x> <{TEST_NS}/prop/val> ?v }} }}"
        )
        assert len(res["results"]["bindings"]) == 0

        # Cleanup
        client.update(f"DROP SILENT GRAPH <{core_uri}>")

    def test_promote_copy(self, client, session_id):
        session_uri = resolve_graph_uri("session", session_id)
        core_uri = resolve_graph_uri("persistent", session_id, "core")

        # Insert into session
        client.update(
            f"INSERT DATA {{ GRAPH <{session_uri}> {{ "
            f'<{TEST_NS}/fact/y> <{TEST_NS}/prop/val> "99" }} }}'
        )

        # Promote (copy)
        ok = promote_graph(
            client,
            from_lifecycle="session",
            to_lifecycle="persistent",
            session_uuid=session_id,
            mode="copy",
            to_persistent_graph="core",
        )
        assert ok is True

        # Verify in persistent
        res = client.query(
            f"SELECT ?v WHERE {{ GRAPH <{core_uri}> {{ "
            f"<{TEST_NS}/fact/y> <{TEST_NS}/prop/val> ?v }} }}"
        )
        assert len(res["results"]["bindings"]) == 1

        # Verify STILL in session (copy keeps source)
        res = client.query(
            f"SELECT ?v WHERE {{ GRAPH <{session_uri}> {{ "
            f"<{TEST_NS}/fact/y> <{TEST_NS}/prop/val> ?v }} }}"
        )
        assert len(res["results"]["bindings"]) == 1

        # Cleanup
        client.update(f"DROP SILENT GRAPH <{core_uri}>")
        client.update(f"DROP SILENT GRAPH <{session_uri}>")


# ── Test 5: Purge session ────────────────────────────────────────────


class TestPurgeSession:
    """[TEST MODE] Purge drops both session and staging graphs."""

    def test_purge(self, client, session_id):
        session_uri = resolve_graph_uri("session", session_id)
        staging_uri = resolve_graph_uri("staging", session_id)

        # Insert into both
        client.update(f"INSERT DATA {{ GRAPH <{session_uri}> {{ <s1> <p> <o> }} }}")
        client.update(f"INSERT DATA {{ GRAPH <{staging_uri}> {{ <s2> <p> <o> }} }}")

        # Verify non-empty
        r1 = client.query(f"ASK {{ GRAPH <{session_uri}> {{ ?s ?p ?o }} }}")
        r2 = client.query(f"ASK {{ GRAPH <{staging_uri}> {{ ?s ?p ?o }} }}")
        assert r1.get("boolean") is True
        assert r2.get("boolean") is True

        # Purge
        ok = purge_session_graphs(client, session_id)
        assert ok is True

        # Verify empty
        r1 = client.query(f"ASK {{ GRAPH <{session_uri}> {{ ?s ?p ?o }} }}")
        r2 = client.query(f"ASK {{ GRAPH <{staging_uri}> {{ ?s ?p ?o }} }}")
        assert r1.get("boolean") is False
        assert r2.get("boolean") is False
