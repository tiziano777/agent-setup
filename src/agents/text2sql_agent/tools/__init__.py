"""Tools for text2sql agent.

This module exports SQL tools that LLM nodes can bind and use dynamically.
The text2sql_agent integrates 4 focused SQL tools into its LLM nodes:

- execute_query: Execute SELECT/INSERT/UPDATE/DELETE queries
- get_schema: Get table DDL (columns, PKs, FKs, indexes)
- get_catalog: Get full database catalog with relationships
- get_table_stats: Get row counts and storage statistics

**Design Pattern**:
- Deterministic nodes (catalog_extraction, graph_expansion, query_executor) call SQLClient directly
- LLM nodes (table_selection, sql_generator, feedback_loop) bind these tools for dynamic schema exploration
- Tool binding enables LLM to refine queries based on real database metadata

**Why 4 tools instead of 1?**
Multiple focused tools improve LLM accuracy and error handling over a single unified tool.
Each tool has a clear purpose and structured response format.
"""

from src.shared.sql import get_sql_tools

__all__ = ["get_sql_tools"]
