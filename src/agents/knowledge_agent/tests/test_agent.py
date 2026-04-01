"""Tests for knowledge_agent.

Integration tests use Cognee (Neo4j + PGVector + LLM proxy).
All test data is cleaned up via `cognee.prune` in teardown.

Prerequisites: `make build` (LiteLLM proxy + Neo4j + PostgreSQL running).

IMPORTANT: Cognee uses async Neo4j driver internally. Multiple calls to
asyncio.run() create separate event loops, causing "Future attached to a
different loop" errors. Solution: (1) each test runs all async ops in a
single asyncio.run(), and (2) a fixture clears Cognee's lru_cached
singletons between tests so each gets a fresh Neo4j driver.
"""

import asyncio
import json

import pytest

from src.agents.knowledge_agent.states.state import AgentState

# ---------------------------------------------------------------------------
# Fixture: reset Cognee cached singletons between integration tests
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_cognee_caches():
    """Clear Cognee's lru_cached singletons so each test gets fresh connections.

    Only clears graph engine (Neo4j driver) and vector engine caches.
    Does NOT clear embedding config/engine — those are set once by setup_cognee().
    """
    yield
    # After each test, clear adapters that hold event-loop-bound connections.
    try:
        from cognee.infrastructure.databases.graph.get_graph_engine import (
            _create_graph_engine,
        )

        _create_graph_engine.cache_clear()
    except ImportError:
        pass
    try:
        from cognee.infrastructure.databases.graph.config import get_graph_config

        get_graph_config.cache_clear()
    except ImportError:
        pass
    try:
        from cognee.infrastructure.databases.vector.create_vector_engine import (
            _create_vector_engine,
        )

        _create_vector_engine.cache_clear()
    except ImportError:
        pass
    try:
        from cognee.infrastructure.databases.vector.config import get_vectordb_config

        get_vectordb_config.cache_clear()
    except ImportError:
        pass
    try:
        from cognee.infrastructure.databases.relational.config import get_relational_config

        get_relational_config.cache_clear()
    except ImportError:
        pass
    try:
        from cognee.infrastructure.databases.relational.create_relational_engine import (
            create_relational_engine,
        )

        create_relational_engine.cache_clear()
    except ImportError:
        pass
    # Reset our own config flag so setup_cognee() runs fresh
    try:
        import src.shared.cognee_toolkit.config as _cognee_cfg

        _cognee_cfg._CONFIGURED = False
    except ImportError:
        pass

# ---------------------------------------------------------------------------
# Test documents — three fictional topics for ECL testing
# ---------------------------------------------------------------------------

DOC_SYNTHEX = (
    "SynthEx Corp è un'azienda fondata nel 2022 a Zurigo, Svizzera. "
    "Si occupa di semiconduttori quantistici di terza generazione. "
    "Il CEO è Markus Heller, ex-ricercatore del CERN. "
    "SynthEx ha raccolto 320 milioni di dollari nel round Series C, "
    "guidato dal fondo Horizon Ventures. L'azienda impiega 450 dipendenti "
    "in 3 laboratori: Zurigo, Singapore e Austin, Texas."
)

DOC_PROTOKOL = (
    "Protokol-9 è un protocollo di comunicazione sviluppato nel 2023 "
    "dall'Istituto Fraunhofer per reti mesh decentralizzate. "
    "Utilizza crittografia post-quantistica basata su reticoli (lattice-based) "
    "e raggiunge una latenza media di 3ms su reti fino a 10.000 nodi. "
    "È stato adottato da 7 operatori europei di telecomunicazioni e "
    "la specifica è pubblicata come RFC-9847."
)

DOC_CERULEA = (
    "L'Operazione Cerulea è un programma di restauro ecologico marino "
    "avviato nel 2024 dal governo della Nuova Zelanda. "
    "Copre 15.000 km² di barriera corallina nel Pacifico meridionale. "
    "Il budget è di 280 milioni di dollari neozelandesi su 5 anni. "
    "Il progetto utilizza droni sottomarini autonomi sviluppati dall'Università "
    "di Auckland per monitorare la biodiversità e impiantare frammenti di corallo."
)

TEST_DOCUMENTS = [DOC_SYNTHEX, DOC_PROTOKOL, DOC_CERULEA]

TEST_QUERY_SYNTHEX = "Chi è il CEO di SynthEx Corp e quanto ha raccolto nel Series C?"
TEST_DATASET = "test_knowledge_agent"


# ---------------------------------------------------------------------------
# Unit tests — no infrastructure needed
# ---------------------------------------------------------------------------


class TestAgentGraph:
    """Test the Graph API agent compiles."""

    def test_graph_compiles(self):
        from src.agents.knowledge_agent.agent import graph

        assert graph is not None

    def test_graph_is_callable(self):
        from src.agents.knowledge_agent.agent import graph

        assert hasattr(graph, "invoke")


class TestTools:
    """Test that tools are importable."""

    def test_execute_cmd_importable(self):
        from src.agents.knowledge_agent.tools import execute_cmd

        assert execute_cmd is not None
        assert execute_cmd.name == "execute_cmd"

    def test_knowledge_tools_factory(self):
        from src.agents.knowledge_agent.tools import get_knowledge_agent_tools

        tools = get_knowledge_agent_tools()
        tool_names = [t.name for t in tools]
        assert "cognee_add" in tool_names
        assert "cognee_search" in tool_names
        assert "cognee_cognify" in tool_names
        assert "execute_cmd" in tool_names
        assert len(tools) == 4


class TestAgentState:
    """Test state definition."""

    def test_state_has_messages(self):
        assert "messages" in AgentState.__annotations__


# ---------------------------------------------------------------------------
# Integration tests — requires Neo4j + LLM proxy (make build)
# ---------------------------------------------------------------------------


class TestCogneeECLIsolated:
    """Test the Cognee ECL (Extract-Cognify-Load) pipeline in isolation.

    All async Cognee operations run in a single event loop to avoid
    Neo4j async driver "attached to different loop" errors.
    Cleanup via cognee.prune at the end.

    Run with: pytest src/agents/knowledge_agent/tests/ -v -k "ecl"
    """

    def test_ecl_add_cognify_search(self):
        """Full ECL pipeline: add → cognify → search → verify → prune."""

        async def _run_ecl_test():
            import cognee

            from src.shared.cognee_toolkit import CogneeSettings, get_cognee_memory, setup_cognee

            settings = CogneeSettings(default_dataset=TEST_DATASET)
            setup_cognee(settings=settings)
            memory = get_cognee_memory(settings=settings)

            try:
                # --- CLEAN SLATE: Remove any leftover state from previous runs ---
                # prune_data may fail if relational tables don't exist yet
                try:
                    await cognee.prune.prune_data()
                except Exception:
                    pass
                await cognee.prune.prune_system(graph=True, vector=True)

                # --- EXTRACT: Add 3 documents ---
                for doc in TEST_DOCUMENTS:
                    await memory.add(doc, dataset_name=TEST_DATASET)

                # --- COGNIFY: Build the knowledge graph ---
                await memory.cognify(datasets=TEST_DATASET)

                # --- SEARCH: Query the knowledge graph ---
                results = await memory.search(
                    TEST_QUERY_SYNTHEX,
                    search_type="CHUNKS",
                    top_k=5,
                )

                # Print results for inspection
                result_texts = [str(r) for r in results]
                test_result = {
                    "query": TEST_QUERY_SYNTHEX,
                    "num_results": len(results),
                    "results_preview": result_texts[:3],
                }
                print("\n" + "=" * 60)
                print("COGNEE ECL TEST RESULT")
                print("=" * 60)
                print(json.dumps(test_result, indent=2, ensure_ascii=False, default=str))
                print("=" * 60)

                # Verify results
                assert len(results) > 0, "Expected search results from knowledge graph"

                all_text = " ".join(str(r) for r in results).lower()
                assert any(
                    term in all_text for term in ["synthex", "markus", "320", "heller"]
                ), f"Expected SynthEx-related content in results: {all_text[:500]}"

            finally:
                # --- CLEANUP: Always prune, even on failure ---
                try:
                    await cognee.prune.prune_data()
                except Exception:
                    pass
                await cognee.prune.prune_system(graph=True, vector=True)

        asyncio.run(_run_ecl_test())


class TestPGVectorBackend:
    """Tests verifying PGVector is the active vector storage backend.

    Validates that setup_cognee() correctly wires PGVector (not SQLite/LanceDB),
    that vector similarity search returns ranked results, and that prune
    clears the PGVector data.

    Run with: pytest src/agents/knowledge_agent/tests/ -v -k "pgvector"
    """

    def test_vector_engine_is_pgvector(self):
        """Verify the vector engine is PGVectorAdapter, not LanceDB/SQLite."""

        async def _run():
            from src.shared.cognee_toolkit import CogneeSettings, setup_cognee

            settings = CogneeSettings(default_dataset=TEST_DATASET)
            setup_cognee(settings=settings)

            from cognee.infrastructure.databases.vector.get_vector_engine import (
                get_vector_engine,
            )

            engine = get_vector_engine()
            class_name = type(engine).__name__
            print(f"\nVector engine class: {class_name}")
            assert "PGVector" in class_name, (
                f"Expected PGVectorAdapter, got {class_name}"
            )

        asyncio.run(_run())

    def test_relational_engine_is_postgres(self):
        """Verify the relational engine uses PostgreSQL dialect, not SQLite."""

        async def _run():
            from src.shared.cognee_toolkit import CogneeSettings, setup_cognee

            settings = CogneeSettings(default_dataset=TEST_DATASET)
            setup_cognee(settings=settings)

            from cognee.infrastructure.databases.relational.config import get_relational_config

            rel_config = get_relational_config()
            print(f"\nRelational DB provider: {rel_config.db_provider}")
            assert rel_config.db_provider == "postgres", (
                f"Expected postgres, got {rel_config.db_provider}"
            )

        asyncio.run(_run())

    def test_pgvector_search_returns_ranked_results(self):
        """Verify PGVector returns results with the most relevant doc first."""

        async def _run():
            import cognee

            from src.shared.cognee_toolkit import CogneeSettings, get_cognee_memory, setup_cognee

            settings = CogneeSettings(default_dataset=TEST_DATASET)
            setup_cognee(settings=settings)
            memory = get_cognee_memory(settings=settings)

            try:
                # Prune may fail if tables don't exist yet (first run)
                try:
                    await cognee.prune.prune_data()
                except Exception:
                    pass
                await cognee.prune.prune_system(graph=True, vector=True)

                for doc in TEST_DOCUMENTS:
                    await memory.add(doc, dataset_name=TEST_DATASET)
                await memory.cognify(datasets=TEST_DATASET)

                # Query about Protokol-9 — should rank Protokol doc first
                results = await memory.search(
                    "Che cos'è Protokol-9 e quale latenza raggiunge?",
                    search_type="CHUNKS",
                    top_k=3,
                )
                assert len(results) > 0, "Expected search results"
                first_result_text = str(results[0]).lower()
                assert "protokol" in first_result_text, (
                    f"Expected Protokol-9 as top result, got: {first_result_text[:200]}"
                )

            finally:
                try:
                    await cognee.prune.prune_data()
                except Exception:
                    pass
                await cognee.prune.prune_system(graph=True, vector=True)

        asyncio.run(_run())

    def test_pgvector_prune_does_not_error(self):
        """Verify prune runs successfully on PGVector without SQLite errors."""

        async def _run():
            import cognee

            from src.shared.cognee_toolkit import CogneeSettings, get_cognee_memory, setup_cognee

            settings = CogneeSettings(default_dataset=TEST_DATASET)
            setup_cognee(settings=settings)
            memory = get_cognee_memory(settings=settings)

            # Add and cognify some data, then prune — should not raise
            try:
                await cognee.prune.prune_data()
            except Exception:
                pass
            await cognee.prune.prune_system(graph=True, vector=True)

            await memory.add(DOC_SYNTHEX, dataset_name=TEST_DATASET)
            await memory.cognify(datasets=TEST_DATASET)

            # Prune should succeed without any SQLite dialect errors
            await cognee.prune.prune_data()
            await cognee.prune.prune_system(graph=True, vector=True)

        asyncio.run(_run())


class TestKnowledgeAgentIsolated:
    """End-to-end agent test with knowledge graph.

    Pre-loads knowledge → invokes ReAct agent → verifies answer → prunes.
    All operations run in a single event loop using ainvoke() for the agent.

    Run with: pytest src/agents/knowledge_agent/tests/ -v -k "agent_isolated"
    """

    def test_agent_uses_knowledge_graph(self):
        """Agent searches the KG and answers based on stored knowledge."""

        async def _run():
            import cognee
            from langchain_core.messages import HumanMessage

            from src.agents.knowledge_agent.agent import build_graph
            from src.shared.cognee_toolkit import CogneeSettings, get_cognee_memory, setup_cognee

            settings = CogneeSettings(default_dataset=TEST_DATASET)
            setup_cognee(settings=settings)
            memory = get_cognee_memory(settings=settings)

            try:
                # --- CLEAN SLATE ---
                try:
                    await cognee.prune.prune_data()
                except Exception:
                    pass
                await cognee.prune.prune_system(graph=True, vector=True)

                # --- SETUP: Pre-load knowledge ---
                for doc in TEST_DOCUMENTS:
                    await memory.add(doc, dataset_name=TEST_DATASET)
                await memory.cognify(datasets=TEST_DATASET)

                # --- INVOKE: Ask the agent (async to support async tools) ---
                # Retry up to 3 times because free-tier LLM providers
                # may not always support tool calling reliably (e.g. Groq
                # sometimes generates malformed tool calls).
                agent_graph = build_graph()
                last_result = None
                last_error = None
                for attempt in range(3):
                    try:
                        result = await agent_graph.ainvoke({
                            "messages": [HumanMessage(content=TEST_QUERY_SYNTHEX)],
                        })
                    except Exception as e:
                        last_error = e
                        continue
                    # Check if the agent actually used tools
                    tool_calls = [
                        msg for msg in result["messages"]
                        if hasattr(msg, "tool_calls") and msg.tool_calls
                    ]
                    if tool_calls:
                        last_result = result
                        break
                    last_result = result

                if last_result is None:
                    pytest.skip(
                        f"Agent failed after 3 attempts (LLM provider issue): {last_error}"
                    )
                result = last_result

                response = result["messages"][-1].content

                # Check that the agent used cognee_search tool
                tool_calls = [
                    msg for msg in result["messages"]
                    if hasattr(msg, "tool_calls") and msg.tool_calls
                ]
                tool_names_used = [
                    tc["name"]
                    for msg in tool_calls
                    for tc in msg.tool_calls
                ]

                test_result = {
                    "query": TEST_QUERY_SYNTHEX,
                    "response": response,
                    "tools_used": tool_names_used,
                }
                print("\n" + "=" * 60)
                print("KNOWLEDGE AGENT TEST RESULT")
                print("=" * 60)
                print(json.dumps(test_result, indent=2, ensure_ascii=False))
                print("=" * 60)

                # Verify the agent used cognee_search (the key integration point)
                assert "cognee_search" in tool_names_used, (
                    f"Agent should use cognee_search tool. Tools used: {tool_names_used}"
                )

                # Verify tool results contain relevant data (from the KG)
                tool_results = [
                    msg.content for msg in result["messages"]
                    if msg.__class__.__name__ == "ToolMessage"
                    and "synthex" in msg.content.lower()
                ]
                assert len(tool_results) > 0, (
                    "cognee_search should return SynthEx-related data from KG"
                )

            finally:
                # --- CLEANUP ---
                try:
                    await cognee.prune.prune_data()
                except Exception:
                    pass
                await cognee.prune.prune_system(graph=True, vector=True)

        asyncio.run(_run())
