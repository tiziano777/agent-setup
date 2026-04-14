# Agent Setup

## What This Is

**agent-setup** is an incubator framework for building, testing, and deploying LangGraph-based agents at scale. It provides standardized templates, shared infrastructure (LLM routing, observability, evaluation, persistent memory), and multi-deployment targets (local, on-prem, Kubernetes, LangGraph Cloud) — enabling teams to focus on agent logic rather than infrastructure plumbing.

## Core Value

**Extensible agent patterns with reusable infrastructure** — every new agent should inherit shared modules (LLM access, retrieval, SQL, tracing) and follow a predictable structure, reducing cognitive load and accelerating iteration.

## Requirements

### Validated

- ✓ **Template agent structure** — Standardized directory layout (`states/`, `nodes/`, `tools/`, `schemas/`, `config/`, tests) with `_template/` reference
- ✓ **8 implemented agents** — code_runner, rag_agent, knowledge_agent, autoresearch, deepconf_agent, rlm_agent, text2sql_agent, and decorator-based functional APIs
- ✓ **11 shared modules** — LLM (LiteLLM proxy), registry (discovery), types (BaseAgentState), memory (checkpointer/store), p2p_orchestration (supervisor/network/independent patterns), sql (PostgreSQL client + tools), retrieval (RAG pipeline), cognee_toolkit (knowledge graphs), phoenix_eval (observability), deep_eval (metrics), sandbox (exec)
- ✓ **Multi-provider LLM rotation** — LiteLLM proxy (localhost:4000) with 12 providers (Groq, Gemini, Mistral, Cohere, GitHub Models, etc.), failover + 5 retries, automatic provider cycling
- ✓ **TDD-first testing** — Each agent has conftest.py fixtures + integrated PostgreSQL tests (isolated schema per test, auto-cleanup)
- ✓ **Phoenix OTEL tracing** — Built-in on all SQL/LLM operations; automatic trace linkage for tool calls and subgraph nodes
- ✓ **Type-safe configuration** — DeepConf for hierarchical agent config composition; BaseAgentState + TypedDict patterns with mypy enforcement

### Active

- [ ] **App Layer (Phase X)** — Streamlit/FastAPI frontend + multi-agent orchestrator (supervisor patterns from research); expose agents via REST + chat UI
- [ ] **Multiple Deployment (Phase Y)** — Standardize Docker/K8s/LangGraph Cloud deployment manifests; document dev/staging/prod patterns; add health checks + observability setup
- [ ] **Documentation Review (Phase Z)** — Align docs/*.md with actual codebase; verify all 8 agents documented; address CONCERNS.md findings (test gaps, security hardening, orphaned files cleanup)

### Out of Scope

- **LLM fine-tuning** — No proprietary model training; use off-the-shelf providers only
- **Premium observability features** — No Datadog/New Relic integrations; Phoenix (free tier) + internal metrics only
- **VectorDB multi-tenancy** — Single-tenant Qdrant/vectorstore per deployment; no sharding or cross-tenant slices
- **Real-time agent communication** — No WebSocket-based agent-to-agent messaging; async handoffs via store only
- **Enterprise features** — No RBAC, audit logs, or SSO; assumed team/research environment

## Context

### Current State

- **Codebase maturity:** Pre-production; agents tested individually but not orchestrated end-to-end
- **Infrastructure:** Docker-compose dev setup with PostgreSQL (5433), Qdrant (6333), Neo4j (7687), Oxigraph (7878), Phoenix (6006), LiteLLM proxy (4000)
- **Documentation gaps identified:** [CONCERNS.md findings]
  - Missing `text2sql_agent` dedicated doc (only `sql_toolkit.md` exists)
  - README.md in Italian while code is all English
  - Missing refs for `text2sql_agent` and `deepconf_agent` in features section
  - `deepconf_agent` tests use non-standard `__init__.py` pattern (should be `test_agent.py`)
  - SQL toolkit lacks unit test coverage (only integration tests via text2sql_agent conftest)
- **Known tech debt:** Orphaned test files (_test_pgvector.py, demo_rlm.py); hardcoded dev passwords in compose files (mitigated by .env override)

### Established Patterns

- **Agent structure:** Every agent has agents/{name}/(states, nodes, tools, schemas, config, memory, pipelines, scorers, images, tests)
- **State management:** TypedDict + add_messages reducer for message accumulation
- **LLM integration:** All nodes use get_llm() → LiteLLM proxy (provider rotation automatic)
- **Tool binding:** LLM nodes use llm.bind_tools() + agentic loop (_run_llm_with_tools max 3 iterations)
- **Dependencies:** Minimal — agents should depend on src/shared/ only, never cross-agent imports
- **Entry points:** Graph API (graph.invoke/ainvoke) + Functional API (@entrypoint decorators)

## Constraints

- **Python 3.11+** — Type hints, async/await, TypedDict
- **LangGraph >= 0.1.0** — StateGraph, message routing, tool_calling
- **PostgreSQL for production** — Dev uses in-memory, tests use isolated schemas
- **Async-first agents** — Use ainvoke() in production; invoke() for synchronous testing
- **Cloud-agnostic LLM setup** — LiteLLM proxy abstracts provider details; no OpenAI SDK direct calls

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| **Template-based agents** | Reduces boilerplate, enables discovery via registry, easier to reason about structure | ✓ Good — all new agents follow it; discovery works |
| **Shared modules over duplication** | Prevents divergent implementations (e.g., 3 different LLM client wrappers); centralizes observability setup | ✓ Good — all agents share same llm.py, memory.py, tracing config |
| **LiteLLM proxy vs SDK direct** | Decouples from vendor; enables automatic provider rotation; reduces integration tests friction | — Pending — need prod validation with high-load scenarios |
| **PostgreSQL for state (not in-memory)** | Production requirement for distributed agents; dev uses in-memory for speed | — Pending — deploy to staging and measure latency impact |
| **Phoenix (free tier) for tracing** | Lightweight, built-in OTEL support, sufficient for agent debugging + evals | ✓ Good — integrated successfully; traces help understanding agent decisions |
| **DeepConf over raw dicts** | Type-safe config composition; makes agent config dependencies explicit | — Pending — adoption by all agents (currently only rlm_agent + deepconf_agent use it) |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-14 after brownfield initialization*
