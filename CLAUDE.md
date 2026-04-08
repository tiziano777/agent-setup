# Agent Setup - Claude Code Context

## Project Overview

Modular LangGraph agent development environment with LiteLLM proxy for automatic LLM provider rotation across 12+ free providers.

## Architecture

Three-layer architecture, each layer depends only on layers above:

```
src/shared/     Infrastructure: LLM client, memory, retrieval, registry, orchestration
src/agents/     Agent modules: each is a standalone LangGraph StateGraph
src/app/        Application layer (empty): FastAPI REST API ( use for now serve.py in root project)
```

All agents use `get_llm()` from `src/shared/llm.py` which points at the LiteLLM proxy on localhost:4000. Never call LLM providers directly.

## Key Commands

```bash
make build              # Start full dev ecosystem (all services)
make down               # Stop full dev ecosystem
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
make sandbox-pull       # Pre-pull sandbox Docker image
make sandbox-ps         # List running sandbox containers
make sandbox-clean      # Clean up orphaned sandbox containers
make test-sandbox       # Run sandbox integration tests
make k8s-apply-all      # Deploy everything to Kubernetes via Kustomize
make k8s-logs-phoenix   # Phoenix logs in Kubernetes
make k8s-port-forward-phoenix  # Access Phoenix UI on localhost:6006 via K8s

# Modular infrastructure (docker-parts/) — selective startup
make help-modules                        # Show all modules + dependency matrix
make llm-up                              # Start LLM proxy module only
make database-up                         # Start PostgreSQL + pgvector only
make observability-up                    # Start Phoenix + PostgreSQL (auto-included)
make up-all / down-all                   # All modules via docker-parts/
```

## Code Conventions

- **Python 3.11+** with type annotations
- **Ruff** for linting and formatting (line-length 100)
- **Pydantic v2** for I/O schemas
- **TypedDict** with `Annotated[list[AnyMessage], add_messages]` for agent state
- **Graph API** (`agent.py`) as primary (uses `create_react_agent` with `execute_cmd` tool by default), **Functional API** (`pipelines/pipeline.py`) as alternative
- Tests in each agent's `tests/` directory, run via pytest
- System prompts in `prompts/system.py`, not inline
- One agent = one self-contained Python sub-package under `src/agents/`

## Agent Structure (follow this for new agents)

```
src/agents/<name>/
  __init__.py      # Exports graph + workflow; calls setup_tracing() for auto-instrumentation
  agent.py         # ReAct agent via create_react_agent() with execute_cmd tool
  config/          # AgentSettings dataclass
  images/          # used to visualize langgraph pipeline
  db/              # connector with DB in a dedicated schema 
  states/          # AgentState(TypedDict) with add_messages reducer
  nodes/           # Node functions: (state) -> partial update dict (for custom StateGraph flows)
  tools/           # Imports execute_cmd from src/shared/sandbox; add agent-specific tools here
  prompts/         # SYSTEM_PROMPT constant if multiple behaviours, you can usepersonas/*
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
- `src/shared/phoenix_eval/` - Evaluation toolkit (LLM-as-Judge, RAG evals, tool evals, batch runner)
- `deploy/docker/init-db.sql` - Creates `phoenix` database in PostgreSQL
- `docs/arize-phoenix-llms.txt` - Arize AX documentation reference index

### Evaluation Toolkit (`src/shared/phoenix_eval/`)

Modular evaluation toolkit built on `arize-phoenix-evals`. All evaluators use the LiteLLM proxy.

Files:
- `llm_bridge.py` - `get_eval_llm()` creates Phoenix LLM via proxy (foundation for all LLM evaluators)
- `builtin.py` - Factory functions for built-in evaluators (conciseness, correctness, faithfulness, etc.)
- `custom.py` - `create_llm_judge()` for custom LLM-as-Judge, `create_code_evaluator()` for deterministic evals
- `runner.py` - `evaluate_batch()` / `async_evaluate_batch()` for running evaluators on data
- `annotations.py` - `to_phoenix_annotations()` for logging results to Phoenix traces

Usage: `from src.shared.phoenix_eval import correctness_evaluator, evaluate_batch`

### DeepEval Toolkit (`src/shared/deep_eval/`)

Extensible evaluation toolkit built on `deepeval`. All evaluators use the LiteLLM proxy via `LiteLLMModel`. Provides a `BaseDeepEvaluator` ABC for custom evaluators, factory functions for all built-in metrics, and specialized RAG evaluators for Cognee, Qdrant, and PGVector.

Files:
- `config.py` - `DeepEvalSettings` dataclass + `configure_deepeval()` with env var defaults
- `llm_bridge.py` - `get_deepeval_model()` creates `LiteLLMModel` via proxy (foundation for all metrics)
- `base.py` - `BaseDeepEvaluator` ABC: extend `_setup_metrics()` + `create_test_case()` for custom evaluators
- `metrics.py` - Factory functions: `answer_relevancy_metric()`, `faithfulness_metric()`, `hallucination_metric()`, `contextual_recall_metric()`, `contextual_precision_metric()`, `contextual_relevancy_metric()`, `toxicity_metric()`, `bias_metric()`, `task_completion_metric()`, `geval_metric()`
- `rag_evaluators.py` - `CogneeRAGEvaluator`, `QdrantRAGEvaluator`, `PGVectorRAGEvaluator` with `retrieve_context()` + RAG metrics
- `agent_evaluators.py` - `AgentEvaluator` for end-to-end LangGraph evaluation (sync + async), `evaluate_langgraph_agent()` / `aevaluate_langgraph_agent()` convenience functions
- `runner.py` - `evaluate()` / `evaluate_dataset()` batch runners wrapping `deepeval.evaluate()`
- `test_cases.py` - `create_test_case()`, `create_rag_test_case()`, `create_test_cases_from_dicts()` helpers

Usage: `from src.shared.deep_eval import get_deepeval_model, answer_relevancy_metric, evaluate`

## Cognee Knowledge Graph Memory (`src/shared/cognee_toolkit/`)

Knowledge graph memory toolkit powered by Cognee. Transforms text into structured knowledge graphs with entities, relationships, and semantic search. Routes all LLM calls through the LiteLLM proxy, uses PGVector (existing PostgreSQL) for vectors (LanceDB as optional fallback), and Neo4j for the graph database.

Files:
- `config.py` - `CogneeSettings` dataclass + `setup_cognee()` infrastructure wiring (LiteLLM proxy, PGVector, Neo4j)
- `memory.py` - `CogneeMemory` class wrapping add/cognify/search/memify with async + sync interfaces
- `tools.py` - `get_cognee_tools()` and `get_cognee_memory_tools()` factories for LangGraph @tool functions
- `search.py` - `CogneeSearchType` enum (14 search types), `search_with_fallback()`, `multi_search()`

Usage: `from src.shared.cognee_toolkit import get_cognee_memory, get_cognee_tools`

Infrastructure: Neo4j Browser UI at http://localhost:7474, Bolt at localhost:7687

## Sandbox Toolkit (`src/shared/sandbox/`)

Docker-based sandboxed shell execution for LangGraph agents. Every agent created via `make new-agent` ships with `execute_cmd` as its default tool. Philosophy: one powerful shell tool instead of many specialized tools, reducing context length and covering 90%+ of use cases (code execution, file I/O, data processing).

The sandbox container runs with: read-only root filesystem, writable `/workspace` tmpfs, no network access, memory/CPU/PID limits, all capabilities dropped, `no-new-privileges`, runs as `nobody`.

Files:
- `config.py` - `SandboxSettings` dataclass with env var defaults (image, timeout, memory, CPU, network, workspace size)
- `engine.py` - `DockerSandbox` class managing container lifecycle (warm container strategy, thread-safe, auto-recovery)
- `tools.py` - `get_sandbox_tools()` factory returning `[execute_cmd]` tool with `atexit` cleanup

Usage: `from src.shared.sandbox import get_sandbox_tools`

Env vars (all optional, have defaults):
- `SANDBOX_IMAGE` (default: python:3.11-slim)
- `SANDBOX_TIMEOUT` (default: 30)
- `SANDBOX_MEM_LIMIT` (default: 256m)
- `SANDBOX_CPU_LIMIT` (default: 0.5)
- `SANDBOX_WORKSPACE_SIZE` (default: 128M)
- `SANDBOX_NETWORK` (default: none)

## Guidance Structured Generation Toolkit (`src/shared/guidance_toolkit/`)

Constrained text generation powered by guidance-ai. Forces LLM outputs to match JSON schemas, regex patterns, or fixed option sets via grammar-based decoding. Routes all LLM calls through the LiteLLM proxy using `guidance.models.OpenAI`.

Files:
- `config.py` - `GuidanceSettings` dataclass + `setup_guidance()` with env var defaults
- `llm_bridge.py` - `get_guidance_model()` creates `guidance.models.OpenAI` via proxy (cached)
- `programs.py` - Built-in programs: `structured_json()`, `constrained_select()`, `regex_generate()`, `grammar_generate()`, `cfg_generate()`, `build_cfg_grammar()`
- `tools.py` - `get_guidance_tools()` factory for LangGraph @tool functions
- `nodes.py` - Node factories: `create_guidance_structured_node()`, `create_guidance_select_node()`

Usage: `from src.shared.guidance_toolkit import structured_json, get_guidance_tools`

## Oxigraph Triple Store Toolkit (`src/shared/oxygraph/`)

HTTP client and LangGraph tools for Oxigraph SPARQL endpoint. Used by agents that operate on triple stores.

Files:
- `config.py` - `OxigraphSettings` dataclass with env var defaults (OXIGRAPH_URL, timeout, retries)
- `client.py` - `OxigraphClient` with query/update/load_triples/health_check methods
- `tools.py` - `get_oxigraph_tools()` factory returning `[execute_sparql, load_turtle]`

Usage: `from src.shared.oxygraph import OxigraphClient, get_oxigraph_tools`

Infrastructure: Oxigraph SPARQL UI at http://localhost:7878

## RDF Validation Toolkit (`src/shared/rdf_validation/`)

Reusable RDF validation (syntax + SHACL) for any agent working with RDF triples.

Files:
- `syntax.py` - `check_syntax(triples)` validates Turtle syntax via rdflib
- `shacl.py` - `check_shacl(triples, shapes_path)` validates against SHACL shapes via pyshacl
- `validator.py` - `validate_rdf(triples, shapes_path)` combines both phases

Usage: `from src.shared.rdf_validation import check_syntax, check_shacl, validate_rdf`

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
- `NEO4J_URL` (default: bolt://localhost:7687)
- `NEO4J_USERNAME` (default: neo4j)
- `NEO4J_PASSWORD` (default: password)
- `COGNEE_VECTOR_DB_HOST` (default: localhost)
- `COGNEE_VECTOR_DB_PORT` (default: 5433)
- `COGNEE_VECTOR_DB_NAME` (default: vectors)
- `COGNEE_VECTOR_DB_USERNAME` (default: postgres)
- `COGNEE_VECTOR_DB_PASSWORD` (default: postgres)
- `OXIGRAPH_URL` (default: http://localhost:7878)

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

## Important Files

- `proxy_config.yml` - LiteLLM config for all 12 LLM providers
- `Makefile` - All project commands (run `make help-modules` for modular infra guide)
- `serve.py` - FastAPI server wrapping agent1's graph
- `docker-compose.yml` - Dev infrastructure, full ecosystem (proxy + Qdrant + PostgreSQL + Phoenix + Neo4j + Oxigraph)
- `docker-compose.prod.yml` - Full production stack (app + all infrastructure)
- `docker-parts/` - Modular compose files for selective startup (llm, vectordb, database, observability, graphdb, oxigraph)
- `src/shared/llm.py` - Central LLM client factory
- `src/shared/registry.py` - Agent auto-discovery
- `src/shared/orchestration.py` - Multi-agent composition factories
- `src/shared/retrieval/pipeline.py` - RAG pipeline with RRF fusion
- `src/shared/env_validation.py` - Environment variable validation
- `src/shared/tracing.py` - Phoenix OTEL tracing setup (call `setup_tracing()` at startup)
- `src/shared/phoenix_eval/` - Phoenix evaluation toolkit (see Evaluation Toolkit section above)
- `src/shared/deep_eval/` - DeepEval evaluation toolkit (see DeepEval Toolkit section above)
- `src/shared/cognee_toolkit/` - Cognee knowledge graph memory (see Cognee section above)
- `src/shared/sandbox/` - Docker sandboxed shell execution (see Sandbox Toolkit section above)
- `deploy/docker/init-db.sql` - Phoenix database init for PostgreSQL
- `deploy/kubernetes/infra.yml` - K8s infrastructure (LiteLLM + Qdrant + PostgreSQL + Phoenix + Oxigraph)
- `deploy/kubernetes/configmap.yml` - K8s non-sensitive config (includes Phoenix + Oxigraph endpoints)
- `src/shared/oxygraph/` - Oxigraph triple store client and SPARQL tools
- `src/shared/rdf_validation/` - RDF syntax + SHACL validation toolkit

## Do NOT

- Modify `.env` files (they contain user secrets)
- Call LLM providers directly (always use get_llm() via the proxy)
- Edit `src/agents/_template/` unless changing the scaffold for all future agents
- Add dependencies without updating pyproject.toml
