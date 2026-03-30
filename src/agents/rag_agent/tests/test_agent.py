"""Tests for rag_agent.

The integration test (TestRAGAgentIsolated) is fully isolated:
- Documents are loaded into an in-memory retriever (no Qdrant/PostgreSQL)
- The retriever is injected into the graph via build_graph(retriever=...)
- When the test ends, everything is garbage-collected — zero residual data
"""

import json

import pytest
from langchain_core.messages import HumanMessage

from src.agents.rag_agent.agent import build_graph
from src.agents.rag_agent.states.state import AgentState
from src.shared.retrieval import get_retriever

# ---------------------------------------------------------------------------
# Test documents — three completely fictional topics
# ---------------------------------------------------------------------------

DOC_AURORA = {
    "id": "aurora-1",
    "content": (
        "Il Progetto Aurora è una missione spaziale europea lanciata nel 2024. "
        "L'obiettivo principale è raccogliere campioni dal suolo di Marte e "
        "riportarli sulla Terra entro il 2031. Il budget totale è di 4.8 miliardi "
        "di euro, finanziato da 14 paesi membri dell'ESA. La sonda Aurora-1 "
        "utilizza un innovativo sistema di propulsione ionica che riduce il tempo "
        "di viaggio a 7 mesi."
    ),
}

DOC_ZEPHYR = {
    "id": "zephyr-1",
    "content": (
        "Zephyr è un linguaggio di programmazione creato nel 2023 specificamente "
        "per lo sviluppo di sistemi embedded real-time. La sua caratteristica "
        "principale è il modello di memoria 'borrow-and-release' che elimina il "
        "garbage collector mantenendo la sicurezza della memoria. Zephyr compila "
        "nativamente per ARM Cortex-M e RISC-V, e supporta la concorrenza tramite "
        "'lightweight fibers' con un overhead massimo di 2KB per fiber."
    ),
}

DOC_NORDIC_DIET = {
    "id": "nordic-diet-1",
    "content": (
        "La dieta nordica è un regime alimentare basato sui cibi tradizionali dei "
        "paesi scandinavi. I pilastri sono: pesce grasso (salmone, aringhe) 3 volte "
        "a settimana, frutti di bosco, cereali integrali come segale e avena, e olio "
        "di colza al posto dell'olio d'oliva. Studi dell'Università di Copenaghen "
        "nel 2022 hanno dimostrato che riduce il colesterolo LDL del 15% e "
        "l'infiammazione sistemica del 20% dopo 6 mesi."
    ),
}

TEST_DOCUMENTS = [DOC_AURORA, DOC_ZEPHYR, DOC_NORDIC_DIET]

# Query that requires context — "Progetto Aurora" is fictional
TEST_QUERY = "Qual è il budget del Progetto Aurora e quanti paesi lo finanziano?"


# ---------------------------------------------------------------------------
# Unit tests — no LLM needed
# ---------------------------------------------------------------------------


class TestAgentGraph:
    """Test the Graph API agent."""

    def test_graph_compiles(self):
        from src.agents.rag_agent.agent import graph

        assert graph is not None

    def test_graph_is_callable(self):
        from src.agents.rag_agent.agent import graph

        assert hasattr(graph, "invoke")


class TestAgentState:
    """Test state definition."""

    def test_state_has_messages(self):
        assert "messages" in AgentState.__annotations__

    def test_state_has_context(self):
        assert "context" in AgentState.__annotations__

    def test_state_has_sources(self):
        assert "sources" in AgentState.__annotations__


class TestRetrieval:
    """Test retrieval with in-memory pipeline (no LLM needed)."""

    def test_retriever_returns_relevant_docs(self):
        """Verify hybrid search finds the Aurora doc for an Aurora query."""
        retriever = get_retriever()
        retriever.add_documents(TEST_DOCUMENTS)

        results = retriever.search(TEST_QUERY, k=3)

        # The Aurora document should be the top result
        result_ids = [doc["id"] for doc in results]
        assert "aurora-1" in result_ids, f"Expected 'aurora-1' in results, got {result_ids}"

    def test_retriever_is_isolated(self):
        """Verify that a new retriever starts empty (no cross-contamination)."""
        retriever = get_retriever()
        results = retriever.search("anything", k=3)
        assert len(results) == 0


# ---------------------------------------------------------------------------
# Integration test — requires LLM proxy (make build)
# ---------------------------------------------------------------------------


class TestRAGAgentIsolated:
    """End-to-end RAG test with full isolation.

    Prerequisites: LLM proxy running (make build).
    Run with: pytest src/agents/rag_agent/tests/ -v -k "isolated"
    """

    @pytest.fixture
    def loaded_retriever(self):
        """Create an in-memory retriever pre-loaded with test documents."""
        retriever = get_retriever()
        retriever.add_documents(TEST_DOCUMENTS)
        return retriever

    def test_rag_retrieval_and_generation(self, loaded_retriever):
        """Full RAG pipeline: retrieve relevant docs -> generate grounded answer.

        Verifies that:
        1. The agent retrieves the correct document (Aurora)
        2. The LLM answer mentions specific facts from the context
        3. Sources are tracked in the state
        4. No data persists after the test (in-memory retriever)
        """
        # Build graph with injected retriever
        rag_graph = build_graph(retriever=loaded_retriever)

        # Invoke the graph
        result = rag_graph.invoke({
            "messages": [HumanMessage(content=TEST_QUERY)],
        })

        # Extract response
        response = result["messages"][-1].content
        sources = result.get("sources", [])

        # Save test result for inspection
        test_result = {
            "query": TEST_QUERY,
            "response": response,
            "sources": sources,
            "context": result.get("context", ""),
        }
        print("\n" + "=" * 60)
        print("RAG TEST RESULT")
        print("=" * 60)
        print(json.dumps(test_result, indent=2, ensure_ascii=False))
        print("=" * 60)

        # Verify the response is grounded in context
        response_lower = response.lower()
        assert (
            "4.8" in response or "4,8" in response or "4.8 miliardi" in response_lower
        ), f"Expected budget '4.8 miliardi' in response: {response}"

        assert "14" in response, f"Expected '14 paesi' in response: {response}"

        # Verify sources were tracked
        assert len(sources) > 0, "Expected at least one source document"
        assert "aurora-1" in sources, f"Expected 'aurora-1' in sources: {sources}"
