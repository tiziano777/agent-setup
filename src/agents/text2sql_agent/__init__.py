"""Text2SQL agent: natural language to SQL query converter.

Converts natural language questions into SQL queries through a
multi-stage pipeline:

1. Catalog extraction → schema discovery
2. Table selection → NER-based table identification
3. Graph expansion → find connector tables via FK relationships
4. Context building → compact schema representation
5. SQL generation → LLM writes query
6. Query execution → run and validate (retry on error)

Quick start::

    from src.agents.text2sql_agent import graph

    state = {
        "prompt": "Show my top 10 customers by revenue",
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

    result = await graph.ainvoke(state)
    print(result["final_query"])
    print(result["final_result"])
"""

from src.shared.tracing import setup_tracing

# Auto-instrument with Phoenix
setup_tracing()

# Import graph directly for easy access
from src.agents.text2sql_agent.agent import graph

__all__ = ["graph"]
