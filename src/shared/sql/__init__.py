"""PostgreSQL SQL toolkit.

Provides a type-safe SQL client with connection pooling, schema introspection,
and LangGraph-compatible tools for query execution.

Quick start::

    from src.shared.sql import get_sql_tools

    tools = get_sql_tools()
    agent = create_react_agent(get_llm(), tools)

    # Or use the client directly:
    from src.shared.sql import SQLClient

    client = SQLClient()
    result = client.execute_query("SELECT * FROM users LIMIT 10")
    catalog = client.get_full_catalog()

Dependencies:
    Requires ``pip install -e '.[sql]'``. Imports are lazy --
    ``ImportError`` is raised only when a function is actually called.
"""

from src.shared.sql.config import SQLSettings

__all__ = [
    "SQLSettings",
    "SQLClient",
    "get_sql_tools",
]


# ── Lazy re-exports ──────────────────────────────────────────────────


def get_sql_tools(settings: SQLSettings | None = None) -> list:
    """Return ``[execute_query, get_schema, get_catalog, get_table_stats]`` tools."""
    from src.shared.sql.tools import get_sql_tools as _factory

    return _factory(settings=settings)


def SQLClient(settings: SQLSettings | None = None):  # type: ignore[misc]
    """Create a :class:`~src.shared.sql.client.SQLClient` instance."""
    from src.shared.sql.client import SQLClient as _cls

    return _cls(settings=settings)
