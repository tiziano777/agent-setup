# Text2SQL Agent - Natural Language to SQL Query Generation

Generate SQL queries from natural language questions with automatic schema exploration, table selection, graph expansion, and error correction feedback loops.

## Overview

The text2sql_agent is a 7-stage multi-node StateGraph that converts natural language prompts into executable SQL queries. Each stage performs deterministic or LLM-based processing:

1. **Catalog Extraction** (deterministic) - Extract full database schema and relationships
2. **Table Selection** (LLM + tools) - Identify which tables needed for the question
3. **Graph Expansion** (deterministic) - Find intermediate connector tables via BFS
4. **Context Builder** (deterministic) - Format schema as compact DDL
5. **SQL Generator** (LLM + tools) - Write SQL query with schema access
6. **Query Executor** (deterministic) - Execute query and check for errors
7. **Feedback Loop** (LLM + tools, up to 3 retries) - Fix errors and regenerate

## Architecture

```
INPUT: User Question
  ↓
[1] Catalog Extraction (deterministic)
  └─ Reads full database schema from information_schema
  └─ Builds relationship graph (foreign keys)
  └─ Output: catalog { tables, relationships, full schema }

[2] Table Selection (LLM + tools)
  └─ LLM reads tables + relationships from catalog
  └─ Tools available: get_schema, get_catalog, get_table_stats
  └─ LLM can explore specific tables to understand columns
  └─ Output: selected_tables [ "customers", "orders" ]

[3] Graph Expansion (deterministic)
  └─ BFS to find intermediate tables connecting selected tables
  └─ Ensures no orphaned tables (all connected)
  └─ Output: expanded_tables [ "customers", "orders", "order_items" ]

[4] Context Builder (deterministic)
  └─ Fetch DDL for expanded tables only
  └─ Format as Compact Table Schema (CTS)
  └─ Output: context "customers(id, name), orders(id, customer_id, amount)..."

[5] SQL Generator (LLM + tools)
  └─ LLM writes SQL based on question + context
  └─ Tools available: execute_query (for testing), get_schema, get_table_stats
  └─ Output: generated_query "SELECT customers.name..."

[6] Query Executor (deterministic)
  └─ Execute generated query
  └─ If success: return results, DONE
  └─ If error: route to Feedback Loop

[7] Feedback Loop (LLM + tools, max 3 retries)
  └─ LLM reads error message
  └─ Tools available: execute_query (for testing/fixing), get_schema
  └─ LLM regenerates corrected query
  └─ Loop back to Executor until success or max retries

OUTPUT: { final_query, final_result, status, message_chain }
```

## Key Features

- **Tool Integration**: LLM nodes (table_selection, sql_generator, feedback_loop) have runtime access to SQL tools for dynamic schema exploration
- **Error Correction**: Automatic 3-retry feedback loop with LLM-based error analysis
- **Phoenix Tracing**: All stages automatically traced via OpenTelemetry
- **PostgreSQL-First**: Tests use PostgreSQL (production-like), not SQLite
- **Schema-Aware**: Tool access to table details, relationships, and statistics

## Usage

### Graph API

```python
from src.agents.text2sql_agent import graph
from src.agents.text2sql_agent.states import Text2SQLState

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

# Sync invocation
result = graph.invoke(state)
print(result["final_query"])
print(result["final_result"]["rows"])

# Async invocation
import asyncio
result = await graph.ainvoke(state)
```

### Configuration

Set environment variables:

```bash
export SQL_HOST=localhost
export SQL_PORT=5432
export SQL_DATABASE=agent_db
export SQL_USERNAME=postgres
export SQL_PASSWORD=postgres
export SQL_SCHEMA=public
export SQL_ECHO=false
```

## Tools Available to LLM Nodes

The following tools are bound to `table_selection_node`, `sql_generator_node`, and `feedback_loop_node`:

### execute_query(query: str, query_type: str = "SELECT")

Execute a SQL query (SELECT/INSERT/UPDATE/DELETE) and get results or modify statements.

**Use cases:**
- Verify table/column exists before writing main query
- Test aggregation/filtering logic
- Validate FK relationships
- For metadata queries, you can use information_schema:

```sql
-- List all tables
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'

-- Get columns for a table
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'customers'

-- Get foreign key relationships
SELECT kcu.column_name, ccu.table_name as referenced_table
FROM information_schema.key_column_usage kcu
JOIN information_schema.constraint_column_usage ccu
  ON kcu.constraint_name = ccu.constraint_name
WHERE kcu.table_name = 'orders'
```

### get_schema(table_name: str)

Get structured DDL schema for a specific table:

```python
{
    "table_name": "customers",
    "columns": [
        {"name": "id", "type": "INTEGER", "nullable": false, "primary_key": true},
        {"name": "name", "type": "VARCHAR", "nullable": false, "primary_key": false}
    ],
    "primary_keys": ["id"],
    "foreign_keys": [],
    "indexes": ["idx_customers_email"]
}
```

### get_catalog()

Get full database catalog with all tables and relationships.

```python
{
    "schema": "public",
    "tables": ["customers", "orders", "order_items", "products"],
    "relationships": [
        {"from": "orders.customer_id", "to": "customers"},
        {"from": "order_items.order_id", "to": "orders"}
    ]
}
```

### get_table_stats(table_name: str)

Get operational statistics:

```python
{
    "table_name": "customers",
    "row_count": 1500,
    "estimated_size_mb": 2.5
}
```

## Testing

### Prerequisites

PostgreSQL must be running:

```bash
make build  # Starts all services including PostgreSQL on :5432
```

### Running Tests

**Unit tests** (no DB required):

```bash
pytest src/agents/text2sql_agent/tests/test_text2sql.py::test_initial_state_creation -v
pytest src/agents/text2sql_agent/tests/test_text2sql.py::test_graph_structure -v
```

**Integration tests** (requires `make build`):

```bash
# Run all integration tests
pytest src/agents/text2sql_agent/tests/ -v -m integration

# Run specific integration test
pytest src/agents/text2sql_agent/tests/test_text2sql.py::test_catalog_extraction -v -m integration
pytest src/agents/text2sql_agent/tests/test_text2sql.py::test_e2e_pipeline_traced -v -m integration
```

### Test Schema

The `test_db_schema` fixture (in `conftest.py`) automatically:
1. Creates an isolated PostgreSQL schema with unique name: `test_schema_<uuid>`
2. Creates DDL tables: customers, products, orders, order_items
3. Populates dummy data (3 customers, 4 products, 4 orders, 6 order items)
4. Cleans up schema after test completes

### Adding New Tests

```python
@pytest.mark.integration
def test_my_feature(test_db_schema):
    """Test with PostgreSQL fixture."""
    from src.agents.text2sql_agent.nodes import catalog_extraction_node
    from src.agents.text2sql_agent.states import Text2SQLState

    state: Text2SQLState = {
        "prompt": "My test question",
        "messages": [],
        # ... other fields
    }

    result = catalog_extraction_node(state)
    assert result["status"] == "selection"
```

The fixture automatically:
- Creates a test schema
- Overrides `SQLSettings` to use the test schema
- Cleans up after the test

## Phoenix Tracing

All stages are automatically traced via OpenTelemetry:

```python
from src.shared.tracing import setup_tracing
setup_tracing()  # Called at module import in agent.py

# Traces visible in Phoenix UI:
# - text2sql.catalog_extraction
# - text2sql.table_selection (+ individual tool calls)
# - text2sql.graph_expansion
# - text2sql.context_builder
# - text2sql.sql_generator (+ individual tool calls)
# - text2sql.query_executor
# - text2sql.feedback_loop (+ individual tool calls)
```

Access Phoenix UI: http://localhost:6006

## State Structure

```typescript
interface Text2SQLState {
  prompt: string                    // User's natural language question
  messages: HumanMessage[]         // Message history for tracing
  catalog: {                       // Full database schema
    schema: string                 // "public"
    tables: string[]               // ["customers", "orders"]
    schemas: Record<...>           // Full schema per table
    relationships: {               // Foreign key relationships
      from: "orders.customer_id"
      to: "customers"
    }[]
  }
  selected_tables: string[]        // Tables LLM selected
  expanded_tables: string[]        // Selected + intermediate tables
  context: string                  // Formatted DDL for LLM
  generated_query: string          // SQL from LLM
  query_iterations: {              // Retry history
    iteration: number
    query: string
    error?: string
    error_type?: string
    retry: number
  }[]
  final_query: string              // Successful query
  final_result: {                  // Query results
    success: boolean
    rows: Record<string, any>[]
    row_count: number
    error?: string
  }
  status: "pending" | "selection" | "expansion" | "context" | "iteration" | "feedback" | "complete"
  error?: string                   // Final error message (if any)
}
```

## Best Practices

1. **Tool Prompting**: LLM prompts in nodes list available tools and their purpose
   ```python
   """You have access to tools:
   - execute_query: Run SELECT/INSERT/UPDATE/DELETE
   - get_schema: Get table DDL
   - get_table_stats: Get row counts
   """
   ```

2. **Error Messages**: Include query + error in feedback loop for accurate corrections
   ```python
   correction_prompt = f"""
   Query failed: {error}
   Previous query: {last_query}
   Please fix it.
   """
   ```

3. **Retry Logic**: Max 3 retries prevents infinite loops on unsolvable errors

4. **Schema Size**: Compact Table Schema (CTS) reduces token usage vs full DDL

## Troubleshooting

### "PostgreSQL connection failed" during tests

Ensure PostgreSQL is running:

```bash
make build      # Starts all services
make postgres   # Or just Postgres (if using docker-parts)
```

### "No catalog available" error

Catalog extraction failed to read database. Check:
- SQL_DATABASE name correct
- SQL_SCHEMA exists in database
- Credentials correct (SQL_USERNAME, SQL_PASSWORD)

### "Max retries exceeded" in feedback loop

Query could not be fixed after 3 attempts. Common causes:
- Table/column doesn't exist (schema mismatch)
- Complex aggregation not handled by LLM
- Ambiguous business logic in prompt

Solutions:
- Refine user prompt (be more specific)
- Check database schema matches LLM's schema context
- Add table metadata comments to schema context

## Contributing

When modifying the agent:
1. Keep deterministic nodes (extraction, expansion, execution) pure SQL operations
2. Tool binding is for LLM nodes only (selection, generation, feedback)
3. All traces via `get_tracer(__name__).start_as_current_span(...)`
4. Add integration tests with @pytest.mark.integration
5. Update message chain for each state update
