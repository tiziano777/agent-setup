"""LangGraph-compatible tools for SQL query execution.

Factory function returns ``@tool``-decorated functions ready to attach
to any LangGraph agent's tool list.

Usage::

    from src.shared.sql import get_sql_tools

    tools = get_sql_tools()
    agent = create_react_agent(get_llm(), tools)
"""

from __future__ import annotations

import atexit
import json
from typing import Any, Optional

from langchain_core.tools import tool

from src.shared.sql.client import SQLClient
from src.shared.sql.config import SQLSettings


def get_sql_tools(
    settings: SQLSettings | None = None,
) -> list:
    """Return a list of LangGraph-compatible SQL tools.

    Returns ``[execute_query, get_schema, get_catalog, get_table_stats]``.
    The SQL client instance is captured in the tool closure and cleaned up
    at process exit via ``atexit``.

    Args:
        settings: SQL configuration dataclass. Uses defaults when *None*.
    """
    client = SQLClient(settings=settings)
    atexit.register(client.close)

    @tool
    def execute_query(
        query: str,
        query_type: str = "SELECT",
        params: dict[str, Any] | None = None,
    ) -> str:
        """Execute a SQL query against PostgreSQL database.

        Use this tool to run SELECT, INSERT, UPDATE, or DELETE queries.
        The query is executed against the configured database schema.

        Query execution includes:
        - Automatic parameter binding (use :param_name syntax)
        - Connection pooling for efficiency
        - Full Phoenix tracing for observability
        - Error handling with detailed messages

        Examples:
            execute_query("SELECT * FROM users WHERE id = :user_id", params={"user_id": 42})
            execute_query("SELECT COUNT(*) as cnt FROM orders")
            execute_query("INSERT INTO logs (msg) VALUES (:msg)", query_type="INSERT", params={"msg": "hello"})

        Args:
            query: SQL query string. For SELECT use column aliases like "SELECT col AS name".
            query_type: Type of query ("SELECT", "INSERT", "UPDATE", "DELETE"). Defaults to "SELECT".
            params: Optional dictionary of parameters to bind to the query.

        Returns:
            JSON-formatted result object with success/failure, rows/error details.
        """
        # Normalize query type
        query_type_upper = query_type.upper().strip()

        # Route to appropriate executor
        if query_type_upper in ("SELECT", ""):
            result = client.execute_query(query, params)
        elif query_type_upper in ("INSERT", "UPDATE", "DELETE"):
            result = client.execute_update(query, params)
        else:
            return json.dumps(
                {
                    "success": False,
                    "error": f"Unknown query type: {query_type}. Use SELECT, INSERT, UPDATE, or DELETE.",
                    "error_type": "ValueError",
                }
            )

        return json.dumps(result)

    @tool
    def get_schema(table_name: str) -> str:
        """Get DDL schema information for a specific table.

        Returns column definitions, primary keys, foreign keys, and indexes
        for the specified table.

        Args:
            table_name: Name of the table to inspect.

        Returns:
            JSON-formatted schema document.
        """
        schema = client.get_table_schema(table_name)
        return json.dumps(schema, indent=2)

    @tool
    def get_catalog() -> str:
        """Get complete database catalog.

        Returns all tables in the configured schema, their DDL schemas,
        and the full relationship graph (foreign keys).

        Useful for understanding table structures before writing queries.

        Returns:
            JSON-formatted catalog with tables, schemas, and relationships.
        """
        catalog = client.get_full_catalog()
        return json.dumps(catalog, indent=2)

    @tool
    def get_table_stats(table_name: str) -> str:
        """Get row count and storage statistics for a table.

        Args:
            table_name: Name of the table.

        Returns:
            JSON-formatted statistics object with row_count and estimated_size_mb.
        """
        stats = client.get_table_statistics(table_name)
        return json.dumps(stats, indent=2)

    return [execute_query, get_schema, get_catalog, get_table_stats]
