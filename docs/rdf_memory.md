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

## Quick Start

```python
from src.shared.rdf_memory import get_rdf_tools

# For a ReAct agent
tools = get_rdf_tools(session_uuid="my-session")
agent = create_react_agent(llm, tools)
```

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
