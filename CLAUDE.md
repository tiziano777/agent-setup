# Agent Setup - Claude Code Context

## Project Overview

Modular LangGraph agent development environment with LiteLLM proxy for automatic LLM provider rotation across 12+ free providers.

## Architecture

Three-layer architecture, each layer depends only on layers above:

```
src/shared/     Infrastructure: LLM client, memory, retrieval, registry, orchestration
src/agents/     Agent modules: each is a standalone LangGraph StateGraph
src/app/        Application layer: FastAPI REST API (serve.py)
```

All agents use `get_llm()` from `src/shared/llm.py` which points at the LiteLLM proxy on localhost:4000. Never call LLM providers directly.

## Key Commands

```bash
make build              # Start LiteLLM proxy + Qdrant + PostgreSQL + Phoenix
make down               # Stop infrastructure
make test               # Run all tests
make new-agent name=X   # Create new agent from template
make list-agents        # List available agents
make env-check          # Validate .env configuration
make external-setup     # Clone external docs and skills
make external-update    # Update external repos to latest
make external-status    # Show external repos commit info
make lint               # Ruff lint
make fmt                # Ruff auto-format
make phoenix-logs       # Phoenix container logs
make test-phoenix       # Phoenix healthcheck
make k8s-apply-all      # Deploy everything to Kubernetes via Kustomize
make k8s-logs-phoenix   # Phoenix logs in Kubernetes
make k8s-port-forward-phoenix  # Access Phoenix UI on localhost:6006 via K8s
```

## Code Conventions

- **Python 3.11+** with type annotations
- **Ruff** for linting and formatting (line-length 100)
- **Pydantic v2** for I/O schemas
- **TypedDict** with `Annotated[list[AnyMessage], add_messages]` for agent state
- **Graph API** (`agent.py`) as primary, **Functional API** (`pipelines/pipeline.py`) as alternative
- Tests in each agent's `tests/` directory, run via pytest
- System prompts in `prompts/system.py`, not inline
- One agent = one self-contained Python sub-package under `src/agents/`

## Agent Structure (follow this for new agents)

```
src/agents/<name>/
  __init__.py      # Exports graph + workflow; calls setup_tracing() for auto-instrumentation
  agent.py         # StateGraph: build_graph() -> compile()
  config/          # AgentSettings dataclass
  states/          # AgentState(TypedDict) with add_messages reducer
  nodes/           # Node functions: (state) -> partial update dict
  tools/           # @tool decorated functions
  prompts/         # SYSTEM_PROMPT constant
  schemas/         # Pydantic AgentInput/AgentOutput
  pipelines/       # @entrypoint/@task Functional API
  scorers/         # Scoring functions
  memory/          # Long-term memory namespace config
  tests/           # pytest tests
```

## Observability - Arize Phoenix

Phoenix provides full LLM observability via OpenTelemetry. Tracing is **automatic**:

- Each agent's `__init__.py` calls `setup_tracing()` before graph compilation
- `phoenix.otel.register(auto_instrument=True)` instruments all LangChain/LangGraph
  operations at the framework level (LLM calls, node executions, tool invocations, chains)
- No per-node or per-tool hooks are needed; the auto-instrumentor handles everything
- `setup_tracing()` is idempotent — safe to call from multiple modules
- Phoenix UI: http://localhost:6006 (dev) or via `make k8s-port-forward-phoenix` (K8s)
- Backend: PostgreSQL (database `phoenix`), not SQLite

Key files:
- `src/shared/tracing.py` - `setup_tracing()` and `get_tracer()` utilities
- `deploy/docker/init-phoenix-db.sql` - Creates `phoenix` database in PostgreSQL
- `docs/arize-phoenix-llms.txt` - Arize AX documentation reference index

## Environment Variables

All LLM API keys go in `.env` (never committed). Copy from `.env.template`.
At least one provider key must be set. The proxy rotates among all configured providers.

Key infrastructure vars (all have defaults):
- `LITELLM_BASE_URL` (default: http://localhost:4000/v1)
- `DEFAULT_MODEL` (default: llm)
- `QDRANT_URL` (default: http://localhost:6333)
- `PGVECTOR_URI` (default: postgresql://postgres:postgres@localhost:5433/vectors)
- `PHOENIX_COLLECTOR_ENDPOINT` (default: http://localhost:6006)
- `PHOENIX_PROJECT_NAME` (default: agent-setup)
- `PHOENIX_TRACING_ENABLED` (default: true, set false to disable)

Run `make env-check` to validate configuration.

## External Documentation (reference, not part of this project)

After running `make external-setup`, reference docs are available at:

- `external/docs/src/oss/langgraph/` - LangGraph official docs (StateGraph, persistence, streaming, etc.)
- `external/docs/src/oss/langchain/` - LangChain official docs (agents, tools, middleware)
- `external/docs/src/oss/deepagents/` - Deep Agents docs (harness, memory, orchestration)
- `external/docs/src/oss/concepts/` - Conceptual docs (memory, context, product comparison)
- `external/langchain-skills/config/skills/` - 11 SKILL.md files with patterns and working code

Most relevant skills for this project:
- `langgraph-fundamentals` - StateGraph patterns (this project's core)
- `langgraph-persistence` - Checkpointers and memory (used in memory.py)
- `langgraph-human-in-the-loop` - Interrupt/resume patterns
- `langchain-rag` - RAG patterns (used in src/shared/retrieval/)
- `deep-agents-orchestration` - Multi-agent patterns (used in orchestration.py)

## Important Files

- `proxy_config.yml` - LiteLLM config for all 12 LLM providers
- `Makefile` - All project commands
- `serve.py` - FastAPI server wrapping agent1's graph
- `docker-compose.yml` - Dev infrastructure (proxy + Qdrant + PostgreSQL + Phoenix)
- `docker-compose.prod.yml` - Full production stack
- `src/shared/llm.py` - Central LLM client factory
- `src/shared/registry.py` - Agent auto-discovery
- `src/shared/orchestration.py` - Multi-agent composition factories
- `src/shared/retrieval/pipeline.py` - RAG pipeline with RRF fusion
- `src/shared/env_validation.py` - Environment variable validation
- `src/shared/tracing.py` - Phoenix OTEL tracing setup (call `setup_tracing()` at startup)
- `deploy/docker/init-phoenix-db.sql` - Phoenix database init for PostgreSQL
- `deploy/kubernetes/infra.yml` - K8s infrastructure (LiteLLM + Qdrant + PostgreSQL + Phoenix)
- `deploy/kubernetes/configmap.yml` - K8s non-sensitive config (includes Phoenix endpoint)

## Do NOT

- Modify `.env` files (they contain user secrets)
- Call LLM providers directly (always use get_llm() via the proxy)
- Edit `src/agents/_template/` unless changing the scaffold for all future agents
- Add dependencies without updating pyproject.toml
