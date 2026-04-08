# SQL Toolkit Documentation

## Overview

The SQL toolkit (`src/shared/sql/`) provides a type-safe PostgreSQL client with connection pooling, schema introspection, and LangGraph-compatible tools for query execution. All operations are automatically traced to Phoenix/OTEL via the `tracing.py` utilities.

## Architecture

```
src/shared/sql/
  config.py       # SQLSettings dataclass (connection params)
  client.py       # SQLClient with pooling + introspection
  tools.py        # LangGraph @tool factory returning [execute_query, ...]
  __init__.py     # Lazy re-exports for clean imports
```

## Quick Start

### Basic Client Usage

```python
from src.shared.sql import SQLClient

client = SQLClient()

# Get database catalog
catalog = client.get_full_catalog()
print(catalog["tables"])

# Get table schema
schema = client.get_table_schema("users")
print(schema["columns"])

# Execute SELECT query
result = client.execute_query("SELECT * FROM users WHERE id = :user_id", params={"user_id": 42})
if result["success"]:
    for row in result["rows"]:
        print(row)

# Execute INSERT/UPDATE/DELETE
result = client.execute_update(
    "INSERT INTO logs (msg) VALUES (:msg)",
    params={"msg": "hello"}
)
print(f"Rows affected: {result['rows_affected']}")
```

### LangGraph Agent Integration

```python
from src.shared.sql import get_sql_tools
from langgraph.graph import StateGraph
from langchain.agents import create_react_agent
from src.shared.llm import get_llm

# Get SQL tools
tools = get_sql_tools()  # Returns [execute_query, get_schema, get_catalog, get_table_stats]

# Create agent
agent = create_react_agent(get_llm(), tools)

# Run agent
result = agent.invoke({
    "input": "How many users are there?",
    "messages": []
})
```

## Configuration

All settings are environment variables with sensible defaults:

```bash
# Connection
SQL_HOST=localhost                    # PostgreSQL server host
SQL_PORT=5432                         # PostgreSQL server port
SQL_DATABASE=agent_db                 # Database name
SQL_USERNAME=postgres                 # Username
SQL_PASSWORD=postgres                 # Password

# Pool
SQL_POOL_SIZE=5                       # Connection pool size
SQL_MAX_OVERFLOW=10                   # Max connections beyond pool_size
SQL_POOL_TIMEOUT=30                   # Connection acquisition timeout (seconds)

# Execution
SQL_QUERY_TIMEOUT=30                  # Query timeout (seconds)

# Schema
SQL_SCHEMA=public                     # Default schema for introspection

# Debug
SQL_ECHO=false                        # Echo SQL statements for debugging
```

## Components

### SQLSettings (config.py)

Dataclass holding all configuration with environment variable defaults:

```python
@dataclass
class SQLSettings:
    host: str = "localhost"
    port: int = 5432
    database: str = "agent_db"
    username: str = "postgres"
    password: str = "postgres"
    pool_size: int = 5
    max_overflow: int = 10
    pool_timeout: int = 30
    query_timeout: int = 30
    schema: str = "public"
    echo: bool = False

    @property
    def connection_string(self) -> str:
        # Returns: postgresql+psycopg://user:pass@host:port/db
```

### SQLClient (client.py)

Core client with automatic Phoenix tracing on all operations:

#### Methods

**Query Execution:**

- **`execute_query(query, params=None) -> dict`** — Execute SELECT query
  - Returns: `{"success": bool, "rows": list[dict], "row_count": int, "error": str | None, "error_type": str | None, "execution_time_ms": float}`
  - Rows are returned as list of dictionaries (column names as keys)

- **`execute_update(query, params=None) -> dict`** — Execute INSERT/UPDATE/DELETE
  - Returns: `{"success": bool, "rows_affected": int, "error": str | None, "error_type": str | None, "execution_time_ms": float}`

**Schema Introspection:**

- **`get_tables() -> list[str]`** — Get all table names in configured schema

- **`get_table_schema(table_name) -> dict`** — Get full DDL for one table
  - Returns: `{"table_name": str, "columns": [...], "primary_keys": [...], "foreign_keys": [...], "indexes": [...]}`
  - Columns: `{"name": str, "type": str, "nullable": bool, "primary_key": bool}`
  - Foreign keys: `{"column": str, "references": str}` (e.g., "references: users(id)")

- **`get_full_catalog() -> dict`** — Get complete database schema
  - Returns: `{"schema": str, "tables": [...], "schemas": {table_name: {...}}, "relationships": [...]}`
  - Relationships: `{"from": "table.col", "to": "referenced_table"}`

- **`get_table_statistics(table_name) -> dict`** — Get row count + size
  - Returns: `{"table_name": str, "row_count": int, "estimated_size_mb": float}`

**Utilities:**

- **`health_check() -> bool`** — Check database connectivity
- **`close()`** — Dispose connection pool

### SQL Tools (tools.py)

LangGraph-compatible `@tool` functions for agent integration:

**`execute_query(query, query_type="SELECT", params=None) -> str`**
- Execute SELECT/INSERT/UPDATE/DELETE
- Returns JSON-formatted result
- query_type: "SELECT", "INSERT", "UPDATE", or "DELETE"
- Supports PostgreSQL `information_schema` queries for metadata exploration

**`get_schema(table_name) -> str`**
- Fetch DDL for one table
- Returns JSON-formatted schema

**`get_catalog() -> str`**
- Fetch full database catalog with all relationships
- Returns JSON-formatted catalog

**`get_table_stats(table_name) -> str`**
- Fetch row count and size
- Returns JSON-formatted statistics

**Tool Integration Pattern**:
Tools are typically used in two ways:

1. **ReAct Agents** — Bind tools to LLM for runtime access:
   ```python
   from src.shared.sql import get_sql_tools
   from langgraph.prebuilt import create_react_agent
   from src.shared.llm import get_llm

   tools = get_sql_tools()
   agent = create_react_agent(get_llm(), tools)
   ```

2. **StateGraph Nodes** — Bind tools in specific LLM nodes:
   ```python
   def sql_generator_node(state):
       tools = get_sql_tools()
       llm_with_tools = get_llm().bind_tools(tools)
       response = llm_with_tools.invoke(messages)
       # LLM can now call tools for schema exploration
   ```

See `src/agents/text2sql_agent/` for a full example of tool binding in a multi-node StateGraph.

## Phoenix Tracing

All SQL operations automatically emit OpenTelemetry spans:

```
sql.execute_query
├─ "rows_returned": 42
└─ [error handling if failed]

sql.execute_update
├─ "rows_affected": 5
└─ [error handling if failed]

sql.get_tables
sql.get_table_schema
sql.get_full_catalog
sql.get_table_statistics
```

To view traces: http://localhost:6006 (after running `make build`)

## Error Handling

All methods return structured error information:

```python
result = client.execute_query("SELECT * FROM nonexistent")

if not result["success"]:
    print(result["error"])        # User-friendly message
    print(result["error_type"])   # Exception class name
    print(result["execution_time_ms"])  # How long it took
```

Common errors:

- **ProgrammingError** — SQL syntax error or missing table/column
- **IntegrityError** — Foreign key or constraint violation
- **DatabaseError** — Connection lost or permission denied
- **TimeoutError** — Query exceeded timeout

## Best Practices

### 1. Always use parameters for user input

```python
# ✓ GOOD
result = client.execute_query(
    "SELECT * FROM users WHERE email = :email",
    params={"email": user_input}
)

# ✗ BAD (SQL injection risk)
result = client.execute_query(f"SELECT * FROM users WHERE email = '{user_input}'")
```

### 2. Check schema before querying

```python
# Get table structure first
schema = client.get_table_schema("orders")
print(schema["columns"])

# Only then write queries
result = client.execute_query("SELECT id, amount FROM orders WHERE status = :status")
```

### 3. Handle timeouts gracefully

```python
result = client.execute_query("SELECT COUNT(*) FROM huge_table")
if result["error_type"] == "TimeoutError":
    print(f"Query took {result['execution_time_ms']}ms, exceeding limit")
```

### 4. Pool cleanup (automatic, but explicit if needed)

```python
client = SQLClient()
# ... use client ...
client.close()  # Dispose connection pool
```

## PostgreSQL-Specific Notes

- Uses `psycopg` (PEP 249-compliant driver) via SQLAlchemy
- Connection strings: `postgresql+psycopg://user:password@host:port/database`
- Type coercion: Use `::type` syntax (PostgreSQL-specific)
  ```python
  client.execute_query("SELECT COUNT(*)::text FROM users")
  ```
- JSON operators: `->`, `->>` fully supported
- Window functions: Fully supported
- CTEs (WITH clauses): Fully supported

### information_schema for Metadata Queries

The `execute_query` tool can run queries against PostgreSQL's `information_schema` for dynamic metadata exploration. This is useful when LLM nodes need to verify table/column existence or explore relationships:

**List all tables:**
```sql
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
ORDER BY table_name
```

**Get columns for a table:**
```sql
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_schema = 'public' AND table_name = 'customers'
ORDER BY ordinal_position
```

**Get primary keys:**
```sql
SELECT column_name FROM information_schema.key_column_usage
WHERE table_schema = 'public' AND table_name = 'customers'
  AND constraint_type = 'PRIMARY KEY'
```

**Get foreign key relationships:**
```sql
SELECT kcu.table_name, kcu.column_name,
       ccu.table_name as referenced_table, ccu.column_name as referenced_column
FROM information_schema.key_column_usage kcu
JOIN information_schema.constraint_column_usage ccu
  ON kcu.constraint_name = ccu.constraint_name
  AND kcu.table_schema = ccu.table_schema
WHERE kcu.table_schema = 'public'
  AND kcu.constraint_type = 'FOREIGN KEY'
```

**Get row counts and sizes:**
```sql
SELECT t.table_name, s.n_live_tup as row_count,
       pg_total_relation_size(t.table_schema||'.'||t.table_name) / (1024.0*1024.0) as size_mb
FROM information_schema.tables t
LEFT JOIN pg_stat_user_tables s
  ON s.tablename = t.table_name AND s.schemaname = t.table_schema
WHERE t.table_schema = 'public'
ORDER BY s.n_live_tup DESC NULLS LAST
```

Example LLM-driven query:
```python
tools = get_sql_tools()
# LLM can call: execute_query with information_schema queries
# Result: structured metadata for decision-making
result = tools[0].invoke({  # execute_query tool
    "query": "SELECT column_name FROM information_schema.columns WHERE table_name = 'orders'",
    "query_type": "SELECT"
})
```

## Testing

Example test with in-memory SQLite (requires minimal setup):

```python
from sqlalchemy import create_engine, text

engine = create_engine("sqlite:///:memory:")
with engine.connect() as conn:
    conn.execute(text("""
        CREATE TABLE test (id INTEGER PRIMARY KEY, value TEXT)
    """))
    conn.execute(text("INSERT INTO test VALUES (1, 'hello')"))
    conn.commit()
```

For PostgreSQL integration tests, use a test container or local dev database.
