# RDF Memory — Semantic Dispatcher Tool

Structured RDF memory module for LangGraph agents, backed by Apache Jena Fuseki.

## Architecture

```
┌─────────────────────────────────────────────────┐
│                 LangGraph Agent                  │
│                                                  │
│  rdf_query("SELECT ...", target="persistent:math")│
└──────────────────┬──────────────────────────────┘
                   │
        ┌──────────▼──────────┐
        │   langchain_tool.py │  ← single @tool, policy-filtered targets
        └──────────┬──────────┘
                   │
        ┌──────────▼──────────┐
        │    dispatcher.py    │  ← classify → policy check → inject graph → execute
        └──────────┬──────────┘
                   │
     ┌─────────────┼─────────────┐
     │             │             │
┌────▼────┐ ┌─────▼─────┐ ┌─────▼──────┐
│ fuseki  │ │  otel     │ │  graph     │
│ client  │ │  hooks    │ │  lifecycle │
└─────────┘ └───────────┘ └────────────┘
```

## Named Graphs

Single Fuseki dataset, logically separated by named graphs:

| Graph URI | Lifecycle | Description |
|---|---|---|
| `<urn:graph:session:{uuid}>` | session | Ephemeral KB, cleared at session end |
| `<urn:graph:staging:{uuid}>` | staging | Candidate triples for promotion |
| `<urn:graph:persistent:{name}>` | persistent | Long-term validated knowledge (N graphs) |

Persistent graphs are defined in configuration: `math`, `ner`, `geo`, `core`, etc.

## Policy System

Per-lifecycle access control configurable per agent:

```python
from src.shared.rdf_memory import get_rdf_tools, default_policy, read_write_policy

# Default: LLM reads/writes session, reads persistent (read-only), staging hidden
tools = get_rdf_tools(session_uuid="sess-123")

# Custom: full read/write on both session + persistent
from src.shared.rdf_memory import RDFMemorySettings, read_write_policy
settings = RDFMemorySettings(
    persistent_graphs=["math", "ner"],
    policy=read_write_policy(),
)
tools = get_rdf_tools(settings=settings, session_uuid="sess-123")
```

Presets: `default_policy()`, `read_write_policy()`, `admin_policy()`

## Observability & Tracing

RDF operations are automatically traced as child spans of LangGraph execution via
OpenTelemetry. When an agent invokes the `rdf_query` tool, the trace hierarchy in
Phoenix will show:

```
Trace: agent.invoke()
├─ Span: langchain.chat_model.ChatOpenAI
├─ Span: langchain.tool::rdf_query
│  └─ Span: rdf.SELECT
│     └─ [Fuseki HTTP request]
└─ Span: langchain.chat_model.ChatOpenAI (next iteration)
```

### How It Works

1. **Implicit Context Propagation**: RDF spans are automatically nested under their
   parent node/tool via OpenTelemetry's contextvars. No manual span linkage needed.

2. **Span Attributes**: Each RDF span includes:
   - `rdf.operation` — SPARQL operation type (SELECT, INSERT, DELETE, etc.)
   - `rdf.target_lifecycle` — target lifecycle (session, staging, persistent)
   - `rdf.query_preview` — first 300 chars of query (for debugging)
   - `rdf.success` — success/failure status
   - `langchain.run_id` — (if available) LangChain execution ID

3. **Trace Visibility**: Phoenix UI at http://localhost:6006 shows full agent trajectory
   with RDF operations as part of the unified trace tree (not orphaned).

### Best Practices

**For agents using RDF:**

1. **Call `setup_tracing()` first** (before importing agent graph):
   ```python
   from src.shared.tracing import setup_tracing
   setup_tracing()  # ← Do this FIRST

   from src.agents.my_agent.agent import graph  # ← Then import
   ```

2. **Use `get_rdf_tools()` factory**:
   ```python
   from src.shared.rdf_memory import get_rdf_tools
   tools = get_rdf_tools(session_uuid="my-session")
   agent = create_react_agent(llm, tools)
   ```

3. **RDF spans will be traced automatically** — no additional code needed.

### Debugging Traces

If RDF spans appear **orphaned** (not nested under node/tool spans):

1. Verify `setup_tracing()` is called before graph import
2. Check Phoenix project name in env var `PHOENIX_PROJECT_NAME` (default: `agent-setup`)
3. Verify LiteLLM proxy is running (`make llm-up`)
4. Review trace context: Click on RDF span and check `Attributes` → `rdf.query_preview`

## Quick Start

```python
from src.shared.rdf_memory import get_rdf_tools

# For a ReAct agent
tools = get_rdf_tools(session_uuid="my-session")
agent = create_react_agent(llm, tools)
```

## Observability & Tracing

All RDF Memory operations are automatically traced in Phoenix. The `rdf_query` tool is auto-instrumented by LangChain, creating unified trace hierarchies.

### Unified Trace Hierarchy

When agents call RDF operations through the `rdf_query` tool, Phoenix shows:

```
LangGraph Agent Trace
├─ extract (node)
│  └─ langchain.tool::rdf_query (tool call)
│     └─ rdf.INSERT (OTel span)
│        ├─ Fuseki HTTP request
│        └─ graph injection/validation
│
└─ query (node)
   └─ langchain.tool::rdf_query (tool call, reused)
      └─ rdf.SELECT (OTel span)
         ├─ SPARQL-to-Fuseki mapping
         └─ result formatting
```

### How It Works

1. **Node Execution**: StateGraph nodes receive `config: RunnableConfig | None` parameter
2. **Config Propagation**: LangGraph automatically provides RunnableConfig to nodes that accept it
3. **Tool Invocation**: Nodes pass `config` to `rdf_query.invoke(input, config=config)`
4. **Run Manager Extraction**: Tool extracts `run_manager` from `get_callback_manager()`
5. **Explicit Linkage**: Dispatcher passes `run_manager` to `traced_sparql()` which sets `langchain.run_id` attribute
6. **Phoenix Linking**: Phoenix UI links RDF operation spans to parent tool call span via `langchain.run_id`

### Setup Requirements

Ensure Phoenix tracing is initialized before graph compilation:

```python
from src.shared.tracing import setup_tracing

# Call once at module load time
setup_tracing()

# Then compile graph
from src.agents.rdf_reader import graph
```

This is done automatically by agent `__init__.py` files that call `setup_tracing()` before importing the graph.

### Trace Attributes

All RDF operation spans include:

| Attribute | Description |
|---|---|
| `rdf.operation` | SPARQL operation type (SELECT, INSERT, DELETE, etc.) |
| `rdf.target_lifecycle` | Graph lifecycle (session, staging, persistent) |
| `rdf.query_preview` | First 300 chars of SPARQL query |
| `rdf.session_graph` | Named graph URI for this operation |
| `langchain.run_id` | LangChain RunManager ID (for trace linking) |
| `rdf.success` | true/false indicating operation success |

### Best Practices

1. **Always dispatch through rdf_query tool**, never call dispatcher directly from nodes
   - Graph → Node → Tool → Dispatcher → RDF
   - Enables automatic trace linkage
2. **Pass config parameter**: Accept `config: RunnableConfig | None` in node signatures
3. **Monitor Phoenix UI**: Check trace hierarchy at http://localhost:6006
4. **Profile traces**: Use span duration to identify slow RDF operations

### Debugging Traces

If RDF operations don't appear as child spans:

1. Verify `setup_tracing()` was called before graph compilation
2. Check that nodes accept `config: RunnableConfig | None` parameter
3. Ensure tool invocations pass `config` parameter: `rdf_query.invoke(input, config=config)`
4. Monitor network: Verify Fuseki requests arrive (check timestamps)
5. Check Phoenix logs: Look for span creation errors

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `FUSEKI_URL` | `http://localhost:3030` | Fuseki base URL |
| `FUSEKI_DATASET` | `knowledge` | Dataset name |
| `FUSEKI_ADMIN_USER` | `admin` | Admin username |
| `FUSEKI_ADMIN_PASSWORD` | `admin` | Admin password |
| `FUSEKI_PERSISTENT_GRAPHS` | `core` | Comma-separated persistent graph names |
| `FUSEKI_DEFAULT_GRAPH` | `core` | Default persistent graph |

## Docker

```bash
make rdf-up         # Start Fuseki module (docker-parts/rdf.yml)
make rdf-down       # Stop
make rdf-logs       # Logs
make test-rdf       # Run tests
```

> Legacy aliases `make fuseki-up`, `fuseki-down`, `fuseki-logs` still work.

Fuseki UI: http://localhost:3030

## Dependencies

```bash
pip install -e '.[rdf]'         # rdflib + SPARQLWrapper + httpx
pip install -e '.[rdf-shacl]'   # + pySHACL for validation
```
