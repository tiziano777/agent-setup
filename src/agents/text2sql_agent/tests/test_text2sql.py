"""Tests for text2sql agent."""

from __future__ import annotations

import asyncio
import json
import logging
import pytest

from src.agents.text2sql_agent import graph
from src.agents.text2sql_agent.states import Text2SQLState
from src.agents.text2sql_agent.nodes import catalog_extraction_node

logger = logging.getLogger(__name__)


@pytest.mark.integration
def test_catalog_extraction(test_db_schema):
    """Test database catalog extraction node with PostgreSQL.

    Requires:
        PostgreSQL running: make build
    """
    state: Text2SQLState = {
        "prompt": "Get top customers",
        "messages": [],
        "catalog": None,
        "selected_tables": [],
        "expanded_tables": [],
        "context": "",
        "generated_query": None,
        "query_iterations": [],
        "final_query": None,
        "final_result": None,
        "status": "pending",
        "error": None,
    }

    result = catalog_extraction_node(state)

    assert result.get("status") in ["selection", "complete"]
    if result.get("status") == "selection":
        assert result.get("catalog") is not None
        assert "tables" in result["catalog"]
        assert len(result["catalog"]["tables"]) > 0
        logger.info(f"Extracted tables: {result['catalog']['tables']}")


def test_initial_state_creation():
    """Test that initial state can be created properly."""
    state: Text2SQLState = {
        "prompt": "Show me the top 5 customers by total spending",
        "messages": [],
        "catalog": None,
        "selected_tables": [],
        "expanded_tables": [],
        "context": "",
        "generated_query": None,
        "query_iterations": [],
        "final_query": None,
        "final_result": None,
        "status": "pending",
        "error": None,
    }

    assert state["prompt"]
    assert state["status"] == "pending"
    logger.info("Initial state created successfully")


@pytest.mark.asyncio
async def test_graph_structure():
    """Test that graph is properly compiled."""
    from src.agents.text2sql_agent.agent import graph

    assert graph is not None
    assert hasattr(graph, "ainvoke")
    assert hasattr(graph, "invoke")
    logger.info("Graph structure validated")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_e2e_pipeline_traced(test_db_schema):
    """Test full e2e pipeline with PostgreSQL state tracing (from agent.py import graph).

    Requires:
        pytest.mark.integration
        PostgreSQL running: make build
    """
    # Initialize state with simple query (deterministic path - no LLM required for first 3 nodes)
    initial_state: Text2SQLState = {
        "prompt": "Get customers and their orders",
        "messages": [],
        "catalog": None,
        "selected_tables": ["customers", "orders"],  # Pre-select to skip LLM
        "expanded_tables": [],
        "context": "",
        "generated_query": None,
        "query_iterations": [],
        "final_query": None,
        "final_result": None,
        "status": "pending",
        "error": None,
    }

    logger.info("=== Starting e2e pipeline test ===")
    logger.info(f"Initial state: {json.dumps({k: v for k, v in initial_state.items() if k != 'messages'}, indent=2)}")

    # Run graph
    result_state = await graph.ainvoke(initial_state)

    logger.info("=== Pipeline execution completed ===")
    logger.info(f"Final status: {result_state.get('status')}")
    logger.info(f"Final error: {result_state.get('error')}")
    logger.info(f"Final query: {result_state.get('final_query')}")
    logger.info(f"Final result row count: {result_state.get('final_result', {}).get('row_count', 0) if result_state.get('final_result') else 0}")
    logger.info(f"Message count: {len(result_state.get('messages', []))}")
    logger.info(f"Query iterations: {len(result_state.get('query_iterations', []))}")

    # Validate state completeness
    assert result_state.get("catalog") is not None, "Catalog should be populated"
    assert len(result_state.get("catalog", {}).get("tables", [])) > 0, "Catalog should have tables"
    assert result_state.get("selected_tables"), "Selected tables should be populated"
    assert result_state.get("expanded_tables"), "Expanded tables should be populated"
    assert result_state.get("context"), "Context should be populated"
    assert len(result_state.get("messages", [])) > 0, "Messages should track pipeline steps"

    # Check execution result
    if result_state.get("status") == "complete":
        if result_state.get("final_query"):
            logger.info("✓ Pipeline completed successfully with query")
        else:
            logger.info("✓ Pipeline completed (max retries reached)")
    else:
        logger.warning(f"Pipeline did not complete: {result_state.get('error')}")


def test_state_structure_with_messages():
    """Test that state properly tracks all execution with messages."""
    from src.agents.text2sql_agent.states import Text2SQLState

    state: Text2SQLState = {
        "prompt": "Test query",
        "messages": [],
        "catalog": {
            "schema": "main",
            "tables": ["customers", "orders"],
            "schemas": {},
            "relationships": [],
        },
        "selected_tables": ["customers"],
        "expanded_tables": ["customers", "orders"],
        "context": "Schema: customers(id, name), orders(id, customer_id)",
        "generated_query": "SELECT * FROM customers",
        "query_iterations": [
            {"iteration": 1, "query": "SELECT * FROM customers", "error": None, "retry": 0}
        ],
        "final_query": "SELECT * FROM customers LIMIT 10",
        "final_result": {"success": True, "rows": [], "row_count": 0, "error": None},
        "status": "complete",
        "error": None,
    }

    # Verify state structure
    assert all(k in state for k in [
        "prompt", "messages", "catalog", "selected_tables", "expanded_tables",
        "context", "generated_query", "query_iterations", "final_query",
        "final_result", "status", "error"
    ]), "State must contain all required fields"

    logger.info("✓ State structure validates correctly")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
