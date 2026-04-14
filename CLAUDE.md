

<!-- GSD:project-start source:PROJECT.md -->
## Project

**Agent Setup**

**agent-setup** is an incubator framework for building, testing, and deploying LangGraph-based agents at scale. It provides standardized templates, shared infrastructure (LLM routing, observability, evaluation, persistent memory), and multi-deployment targets (local, on-prem, Kubernetes, LangGraph Cloud) — enabling teams to focus on agent logic rather than infrastructure plumbing.

**Core Value:** **Extensible agent patterns with reusable infrastructure** — every new agent should inherit shared modules (LLM access, retrieval, SQL, tracing) and follow a predictable structure, reducing cognitive load and accelerating iteration.

### Constraints

- **Python 3.11+** — Type hints, async/await, TypedDict
- **LangGraph >= 0.1.0** — StateGraph, message routing, tool_calling
- **PostgreSQL for production** — Dev uses in-memory, tests use isolated schemas
- **Async-first agents** — Use ainvoke() in production; invoke() for synchronous testing
- **Cloud-agnostic LLM setup** — LiteLLM proxy abstracts provider details; no OpenAI SDK direct calls
<!-- GSD:project-end -->

<!-- GSD:stack-start source:codebase/STACK.md -->
## Technology Stack

## Languages
- Python 3.11+ - All application code, agents, and utilities
## Runtime & Package Management
- Python 3.11+ (specified in `pyproject.toml` as `requires-python = ">=3.11"`)
- Virtual environment (`.venv`) - project uses pip with setuptools
- pip (with `pyproject.toml` configuration)
- Lockfile: No lockfile enforced; version ranges specified via `[N.M,<N+1.0)` pattern
## Core Framework Dependencies
- `langgraph>=0.4,<1.0` - Multi-agent workflow orchestration with StateGraph
- `langgraph-checkpoint>=2.0,<3.0` - State persistence and replay
- `langchain-core>=0.3,<1.0` - Core LLM chains and message types
- `langchain-openai>=0.3,<1.0` - ChatOpenAI client (via LiteLLM proxy)
- `pydantic>=2.0,<3.0` - Data validation and settings schemas
- `python-dotenv>=1.0` - Environment variable loading from `.env` files
## Optional Dependencies
## Build & Development Tools
- Tool: `ruff>=0.8`
- Configuration: `pyproject.toml` lines 105-110
- Tool: `mypy>=1.13`
- Configuration: `pyproject.toml` lines 118-121
- Runner: `pytest>=8.0`
- Async support: `pytest-asyncio>=0.24`
- Configuration: `pyproject.toml` lines 112-116
- Backend: `setuptools>=75.0`
- Configuration: `pyproject.toml` lines 97-103
- Package discovery: `setuptools.find_packages()` with `src*` pattern
## Configuration & Secrets
- Template file: `.env.template` - API key configuration
- Docker template: `.env.docker.template` - Production environment
- Validation: `src/shared/env_validation.py` - Pre-startup checks
- `pyproject.toml` - Dependencies, build, tool config
- `proxy_config.yml` - LiteLLM provider routing (12+ models)
- `Makefile` - Development, testing, infrastructure commands
- `GROQ_API_KEY`, `CEREBRAS_API_KEY`, `GOOGLE_API_KEY`, `NVIDIA_API_KEY`, `MISTRAL_API_KEY`, `COHERE_API_KEY`, `GITHUB_TOKEN`, `CLOUDFLARE_API_KEY`, etc.
- `QDRANT_URL` - Qdrant vector DB endpoint
- `QDRANT_API_KEY` - Qdrant auth (optional)
- `PGVECTOR_URI` - PostgreSQL pgvector connection string
- `OPENAI_API_KEY` - OpenAI embeddings (optional)
- `OPENAI_EMBEDDING_MODEL=text-embedding-3-small` (default)
- `PHOENIX_COLLECTOR_ENDPOINT=http://localhost:6006` - Phoenix OTEL endpoint
- `PHOENIX_PROJECT_NAME=agent-setup` - Tracing project name
- `PHOENIX_TRACING_ENABLED=true` - Toggle tracing on/off
- `SQL_HOST=localhost`, `SQL_PORT=5432`, `SQL_DATABASE=agent_db`, `SQL_USERNAME=postgres`, `SQL_PASSWORD=postgres`
- `SQL_POOL_SIZE=5`, `SQL_MAX_OVERFLOW=10`, `SQL_POOL_TIMEOUT=30`, `SQL_QUERY_TIMEOUT=30`
- `SQL_SCHEMA=public`, `SQL_ECHO=false`
- `SANDBOX_IMAGE=python:3.11-slim` - Container image
- `SANDBOX_TIMEOUT=30` - Execution timeout (seconds)
- `SANDBOX_MEM_LIMIT=256m` - Memory limit
- `SANDBOX_CPU_LIMIT=0.5` - CPU limit (cores)
- `SANDBOX_WORKSPACE_SIZE=128M` - tmpfs workspace size
- `SANDBOX_NETWORK=none` - Network isolation mode
- `LITELLM_BASE_URL=http://localhost:4000/v1` - Proxy endpoint (default)
- `DEFAULT_MODEL=llm` - Rotation pool identifier (default)
## Settings Dataclasses
- `SQLSettings` - PostgreSQL connection pooling and execution parameters
- Reads: `SQL_*` environment variables
- `RetrievalSettings` - Embeddings, vector store, search parameters
- Supports: Qdrant or pgvector backends
- Embedding providers: sentence-transformer or OpenAI
- `SandboxSettings` - Docker container resource limits and isolation
- Reads: `SANDBOX_*` environment variables
- `DeepConf` - Reasoning model wrapper (DeepThinkLLM or fallback)
- `DeepConfOutput` - Structured reasoning output with voting strategies
## Deployment & Containerization
- `docker-compose.yml` - Root compose (all services)
- `Makefile` - Orchestration commands (`make build`, `make down`, etc.)
- `docker-compose.prod.yml` - Production stack
- `llm.yml` - LiteLLM proxy gateway (prerequisite)
- `vectordb.yml` - Qdrant vector database
- `database.yml` - PostgreSQL + pgvector
- `observability.yml` - Arize Phoenix tracing
- `graphdb.yml` - Neo4j graph database
- `oxigraph.yml` - Oxigraph RDF triple store
- Docker Compose (development & on-prem production)
- Kubernetes manifests available: `deploy/kubernetes/`
## Platform Requirements
- Docker & Docker Compose (for infrastructure)
- Python 3.11+
- pip & virtualenv
- Optional: PostgreSQL 16+, Qdrant, Neo4j, Phoenix (via Docker)
- Docker & Docker Compose OR Kubernetes 1.20+
- PostgreSQL 16+ (persistent)
- ~2GB disk for vector embeddings (depends on collection size)
- 2+ CPU cores, 4GB RAM minimum
## Installation & Project Setup
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

## Code Style
- Line length: **100 characters max** - Enforced across entire codebase
- Error codes enabled: `E` (PEP8), `F` (PyFlakes), `I` (import sorting), `W` (warnings)
- Target: Python 3.11+
- Auto-formatting: `make fmt` runs ruff format + ruff check --fix
- Run via Makefile: `make fmt` (auto-formats), `make lint` (check only)
- Applied to `src/` directory only
- Comments aligned to conventions visible in docstrings (see below)
## Naming Patterns
- Modules: `snake_case` (e.g., `llm.py`, `client.py`, `config.py`)
- Classes: Organized in package `__init__.py` files with `__all__` exports
- Test files: `test_*.py` prefix (e.g., `test_agent.py`, `test_text2sql.py`)
- Function names: `snake_case` (e.g., `get_llm()`, `execute_query()`, `_execute_tool_call()`)
- Private/internal helpers: `_leading_underscore()` (e.g., `_execute_tool_call()`, `_run_llm_with_tools()`)
- Factory functions: `get_*()` pattern (e.g., `get_llm()`, `get_tracer()`, `get_sql_tools()`)
- Local variables: `snake_case` (e.g., `schema_name`, `connection_string`, `final_query`)
- Constants: `UPPER_CASE` (e.g., `LITELLM_BASE_URL`, `DEFAULT_MODEL`)
- Type hints: Use inline for clarity (e.g., `state: Text2SQLState`, `tools: list`)
- Dictionary keys: `snake_case` (e.g., `prompt`, `selected_tables`, `generated_query`, `final_result`)
- State fields: Documented with docstring comments above each field
- Required vs optional: Indicated via type hints (`str | None`, `list[str]`)
- Class names: `PascalCase` (e.g., `SQLClient`, `Text2SQLState`)
- Dataclasses with settings: `SQLSettings`, `AgentState` pattern
- Abstract/base classes: Prefixed with descriptive name (e.g., `SQLClient`)
## Import Organization
- All imports use **absolute paths from project root** `src.`
- No relative imports (no `from . import`, no `from .. import`)
- Consistent across all files (see `src/agents/text2sql_agent/nodes/__init__.py` lines 12-16)
- Used in conditional/error handling paths (e.g., `from src.shared.sql.config import SQLSettings` inside function at line 118)
- Prevents circular dependencies and defers expensive imports
- Each agent exports main graph via `__init__.py` (e.g., `src/agents/text2sql_agent/__init__.py` line 43-45)
- Pattern: `from src.agents.text2sql_agent.agent import graph` then `__all__ = ["graph"]`
- Shared modules export factories: `get_llm()`, `get_tracer()`, `get_sql_tools()`
## Type Hints
- Use `|` for unions (not `Union[A, B]`) - Python 3.10+ style
- Use `dict[str, Any]` instead of `Dict[str, Any]`
- Use `list[str]` instead of `List[str]`
- Optional values: `str | None` (not `Optional[str]`)
- Annotated types for state reducer fields: `Annotated[list[AnyMessage], add_messages]`
- `mypy` enabled in `pyproject.toml` (lines 118-121):
- Recommended but not enforced in CI
## State Management
- Message field uses `add_messages` reducer for automatic message list merging
- All fields documented with docstring comments (lines 15-21)
- Status field tracks pipeline stage: `"pending" | "catalog" | "selection" | "expansion" | "context" | "generation" | "feedback" | "complete"`
- Error field stores exception messages for debugging
- Descriptive names: `selected_tables` (not `tables`), `expanded_tables` (intermediate state), `final_query` (output)
- Intermediate state fields grouped with comments
- Related fields co-located (e.g., all iteration tracking: `query_iterations`, `generated_query`, `final_query`)
## Error Handling
- Log at appropriate level: `logger.info()` for successes, `logger.error()` for failures, `logger.warning()` for retries
- Return partial state (dict) updating only failed fields + `status` + `error` + `messages`
- Never raise exceptions in nodes — always catch and return error state
- Include context in error messages: `f"Tool execution failed: {tool_name} with input {tool_input}: {e}"`
- Use built-in Python exceptions (`ImportError`, `ValueError`, etc.)
- Wrap with context message for debugging
- Always include `type(e).__name__` in JSON error responses for client debugging
## Docstrings
- One-line summary
- Optional extended description (blank line, then details)
- Always document Args and Returns
- Use triple quotes `"""`
- No type hints in docstring (already in signature)
- Include examples for public APIs (Quick start section)
## Constants & Configuration
- Use `@dataclass` for multi-field config objects
- Use `field(default_factory=...)` for env var lookups with defaults
- Constants defined at module level (UPPER_CASE)
- All configuration reads from `os.getenv()` with sensible defaults
- `@property` methods for derived values (connection strings, etc.)
- No secrets in code — all via env vars (see forbidden files: `.env` never read)
## Factory Functions
- Use `@lru_cache` for expensive initialization (LLM clients)
- Graceful fallback for optional dependencies (OpenTelemetry)
- Default parameters for common use cases
- Factory returns fully-configured, ready-to-use instance
- All factories accessed via `get_*()` function name
## Logging
- Use `logger = logging.getLogger(__name__)` at module level
- Include context: `f"Extracted {len(tables)} tables from {schema_name}"`
- Log at `debug` level for iteration details (LLM loops)
- Log at `info` level for successful milestones
- Log at `warning` level for retries or fallbacks
- Log at `error` level for exceptions (with full traceback if needed)
- All logs are auto-instrumented to Phoenix (OpenTelemetry) when tracing enabled
## Spans & Tracing
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

## Pattern Overview
- Multi-agent capability with supervisor, network (p2p), and independent patterns
- Deterministic + LLM nodes with tool-binding agentic loops
- Message-based state accumulation (add_messages reducer)
- Centralized LLM proxy access via LiteLLM (localhost:4000)
- Phoenix OpenTelemetry auto-instrumentation
- Pluggable memory (checkpointer) and long-term stores
## Layers
- Purpose: Shared utilities for all agents—LLM access, memory, tool factories, retrieval, SQL, tracing
- Location: `src/shared/`
- Contains: Type definitions, registry, factories, multi-agent orchestrators, evaluation toolkits
- Depends on: LangChain, LangGraph, external SDKs (OpenAI, Qdrant, PostgreSQL, etc.)
- Used by: All agents and app layer
- Purpose: Autonomous LangGraph StateGraph implementations with standardized structure
- Location: `src/agents/{agent_name}/`
- Contains: Graph definition, nodes, state, schemas, tools, prompts, config, tests
- Depends on: `src/shared/` infrastructure, LangGraph, LLM via `get_llm()`
- Used by: Registry (discovery), app layer (exposure)
- Purpose: REST API entry point and deployment infrastructure
- Location: `serve.py`, `src/app/`
- Contains: FastAPI router, request/response schemas, health checks
- Depends on: Agent graphs from registry, LangGraph
- Used by: External clients (HTTP calls)
## Data Flow
```
```
- **Short-term (per-thread):** `InMemorySaver()` checkpointer tracks conversation state and enables interrupts/resume
- **Long-term (cross-thread):** `InMemoryStore()` for persistent knowledge
## Key Abstractions
- Purpose: Standard TypedDict base for all agent states
- Location: `src/shared/types.py`
- Pattern: `class AgentState(BaseAgentState): ...` extends with agent-specific keys
- Usage: All agent state definitions inherit to get `messages: Annotated[list[AnyMessage], add_messages]`
- Purpose: Multi-agent handoff metadata
- Location: `src/shared/types.py`
- Pattern: `{"target_agent": "name", "messages": [...], "metadata": {...}}`
- Usage: `build_supervisor()`, `build_network()` handoff tools
- Purpose: Dynamic agent discovery and loading
- Location: `src/shared/registry.py`
- Pattern: `registry.discover("src.agents")` scans for subpackages, loads `graph` and `workflow` attributes
- Methods:
- Purpose: Multi-index search orchestration with Reciprocal Rank Fusion
- Location: `src/shared/retrieval/pipeline.py`
- Pattern: Composes BM25Index + VectorIndex + optional Reranker
- Usage: Hybrid retrieval for RAG agents (BM25 for keyword, Vector for semantic, RRF to merge)
- Purpose: PostgreSQL connection pooling + schema introspection + tracing
- Location: `src/shared/sql/client.py`
- Methods: `execute_query()`, `execute_update()`, `get_table_schema()`, `get_full_catalog()`, `get_table_statistics()`
- Usage: Deterministic data access nodes in text2sql_agent
## Entry Points
- Location: `serve.py`
- Endpoint: `POST /code_runner` with `InvokeRequest(messages=[])`
- Tracing: Initializes via `setup_tracing()` before app creation
- Response: `InvokeResponse(messages=[{"role": str, "content": str}, ...])`
- Location: `from src.agents.{agent_name} import graph`
- Invocation: `graph.invoke({"messages": [...]})` or `await graph.ainvoke(...)`
- Config: Optional `config=RunnableConfig(configurable={...})` for thread/namespace isolation
- Returns: Final state dict with all accumulated values
- Location: `from src.agents.{agent_name} import workflow`
- Invocation: `workflow({"messages": [...]})` (automatically checkpointed)
- Pattern: `@entrypoint(checkpointer=...) def workflow(inputs): ...`
- Composed of `@task` decorated functions
- Location: `from src.shared import AgentRegistry`
- Pattern:
## Multi-Agent Patterns
- Implementation: `src/shared/p2p_orchestration.build_supervisor()`
- Flow: START → Supervisor (ReAct) → handoff tools route to workers → worker executes → result back to supervisor
- Use case: Centralized LLM routing (e.g., "Should I use RAG or SQL?")
- Code:
- Implementation: `src/shared/p2p_orchestration.build_network()`
- Flow: Any agent can hand off to any other via transfer tools
- Use case: Decentralized agent collaboration
- Each agent gets handoff tools for all peers
- Implementation: `src/shared/p2p_orchestration.build_independent()`
- Flow: All agents run in parallel from START, results merged at END
- Use case: Ensemble approaches, competitive ranking
## Message Flow
- All communication uses `BaseMessage` subclasses: `HumanMessage`, `AIMessage`, `ToolMessage`, `SystemMessage`
- Chain stored in state["messages"] → deterministic via `add_messages` reducer
- Signature: `Annotated[list[AnyMessage], add_messages]`
- Behavior: Intelligently merges new messages (dedups consecutive AIMessages, appends ToolMessages)
- Location: `src/shared/types.BaseAgentState`
- Benefit: Prevents conversation corruption on parallel/conditional edges
- Pattern (in LLM nodes):
- Examples: `text2sql_agent` table_selection_node, sql_generator_node, feedback_loop_node
## State Management Detailed
- Default: `InMemorySaver()` from `src/shared/memory.get_checkpointer()`
- Tracks: Message history, interrupt points, retry context within a conversation thread
- Config: `RunnableConfig(configurable={"thread_id": "user_123"})`
- Lifecycle: Per user session or per conversation ID
- Production: Replace with `PostgresSaver(conn_string=...)`
- Default: `InMemoryStore()` from `src/shared/memory.get_store()`
- Tracks: Cross-conversation knowledge (facts, embeddings, summaries)
- Namespace: Isolated by `namespace=["user_id", "doc_id"]` or `store.put(key, value, namespace=[...])`
- Lookup: `store.search(key, namespace=[...])`
- Optional: Semantic search if `embed_fn` provided
- Pattern: `config=RunnableConfig(configurable={"namespace": ["org_id", "user_id"]})`
- Benefit: Multi-tenant safety, state isolation between projects/users
## Cross-Cutting Concerns
- Approach: Python stdlib `logging`
- Convention: Each module defines `logger = logging.getLogger(__name__)`
- Usage: `logger.info()`, `logger.warning()`, `logger.error()` with structured context
- Examples: `src/agents/text2sql_agent/nodes/__init__.py` logs query iterations
- Env validation: `src/shared/env_validation.validate_env()` runs at startup (serve.py)
- State validation: TypedDict enforces structure, pydantic for API schemas
- Tool input validation: `_execute_tool_call()` handles JSON parsing errors gracefully
- Approach: None in core (infrastructure detail)
- LiteLLM proxy auth: Configured via `proxy_config.yml` (external)
- API auth: FastAPI can layer middleware (not yet implemented)
- Node-level: Try/except returns `dict(status="complete", error="...", messages=[...])`
- Tool-level: `_execute_tool_call()` catches exceptions, returns JSON `{"error": "..."}`
- LLM-level: Tool binding retries up to `max_iterations` (default 3)
- API-level: FastAPI raises HTTPException(500, detail=str(e))
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->
## Project Skills

| Skill | Description | Path |
|-------|-------------|------|
| skypilot | "Use when launching cloud VMs, Kubernetes pods, or Slurm jobs for GPU/TPU/CPU workloads, training or fine-tuning models on cloud GPUs, deploying inference servers (vllm, TGI, etc.) with autoscaling, writing or debugging SkyPilot task YAML files, using spot/preemptible instances for cost savings, comparing GPU prices across clouds, managing compute across 25+ clouds, Kubernetes, Slurm, and on-prem clusters with failover between them, troubleshooting resource availability or SkyPilot errors, or optimizing cost and GPU availability." | `.claude/skills/skypilot/SKILL.md` |
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->

<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
