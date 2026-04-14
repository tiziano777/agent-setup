# agent-setup v1.0 — Roadmap

**Created:** 2026-04-14
**Granularity:** Standard (5-8 phases, planning first 3)
**Coverage:** 19/19 v1 requirements mapped

---

## Phases

- [ ] **Phase 1: REST API Foundation** - Expose all 8 agents via HTTP with execution tracing
- [ ] **Phase 2: User Interface & Orchestration** - Streamlit dashboard with multi-agent supervisor routing
- [ ] **Phase 3: Deployment & Documentation** - Production manifests and complete reference docs

---

## Phase Details

### Phase 1: REST API Foundation

**Goal**: Users can programmatically invoke any agent and retrieve execution traces via standardized REST API

**Depends on**: Nothing (builds on existing agents + shared modules)

**Requirements**: APP-01, APP-02, APP-07

**Success Criteria** (what must be TRUE):
  1. User can POST to `/api/agents/{agent_name}/invoke` with JSON payload and receive agent response with status code 200
  2. Response includes `execution_trace` with message history, all tool calls made, and final output
  3. All 8 agents (code_runner, rag_agent, knowledge_agent, autoresearch, deepconf_agent, rlm_agent, text2sql_agent, _template) are callable via REST without code modification
  4. Health check endpoint `/api/health` returns `{"status": "healthy", "agents_available": N, "dependencies": {"llm_proxy": bool, "databases": bool}}`
  5. API validates input schema and returns 400 with descriptive error messages on malformed requests

**Plans**: TBD

---

### Phase 2: User Interface & Orchestration

**Goal**: Users can discover agents, invoke them interactively, and leverage supervisor patterns for multi-agent workflows through a web dashboard

**Depends on**: Phase 1

**Requirements**: APP-03, APP-04, APP-05, APP-06

**Success Criteria** (what must be TRUE):
  1. User opens Streamlit dashboard and sees grid/list of all agents with name, description, and status
  2. User selects an agent, enters text input, clicks invoke, and sees streamed response in real-time
  3. User can see full execution trace panel (messages, tool calls, iterations) after invocation completes
  4. User selects "supervisor" mode where they pick a primary agent that routes requests to child agents based on request intent
  5. Conversation history is persisted per user session and survives Streamlit reruns and browser refresh
  6. User can switch between agents mid-session; each agent maintains separate conversation thread

**Plans**: TBD

**UI hint**: yes

---

### Phase 3: Deployment & Documentation

**Goal**: Users can deploy agent-setup to any target environment with complete reference documentation and no unresolved tech debt

**Depends on**: Phase 1, Phase 2

**Requirements**: DEPLOY-01, DEPLOY-02, DEPLOY-03, DEPLOY-04, DEPLOY-05, DEPLOY-06, DOCS-01, DOCS-02, DOCS-03, DOCS-04, DOCS-05, DOCS-06

**Success Criteria** (what must be TRUE):
  1. Developer can run `docker-compose -f docker-compose.yml up` and all services reach healthy state within 60 seconds; stack includes PostgreSQL, Qdrant, Neo4j, Oxigraph, Phoenix, LiteLLM proxy
  2. Developer can deploy to Kubernetes cluster using provided manifests; all agent pods reach `Ready` and `Running` status; services are accessible from outside cluster
  3. Agents can be exported to LangGraph Cloud with verified invocation signatures; deployment guide provided
  4. Developer creates `.env` file with custom values; all services respect env var overrides with no hardcoded secrets
  5. Health checks validate all service dependencies: GET `/api/health` returns 200 with dependency status; failed dependencies trigger alerts
  6. Developer can access Phoenix UI at endpoint in docs and see distributed traces for all agent invocations with tool calls visible
  7. All 8 agents have dedicated documentation files (`docs/{agent_name}.md`) with pipeline diagrams, state schemas, code examples, and invocation patterns
  8. README.md is in English and lists all agents in features section with links to their documentation
  9. CONCERNS.md findings are resolved: orphaned files deleted, test coverage gaps addressed, security hardening applied, sensitive information scrubbed from error messages
  10. CLAUDE.md documents agent structure patterns, TDD approach with conftest.py fixtures, deployment checklists, and onboarding guide for new developers

**Plans**: TBD

---

## Progress Tracking

| Phase | Goal | Status | Completed |
|-------|------|--------|-----------|
| 1 - REST API Foundation | Expose agents via HTTP | Not started | - |
| 2 - User Interface & Orchestration | Streamlit dashboard + supervisor | Not started | - |
| 3 - Deployment & Documentation | Production readiness + docs | Not started | - |

---

## Requirement Traceability

| REQ-ID | Category | Phase | Status |
|--------|----------|-------|--------|
| APP-01 | App Integration | 1 | Pending |
| APP-02 | App Integration | 1 | Pending |
| APP-03 | App Integration | 2 | Pending |
| APP-04 | App Integration | 2 | Pending |
| APP-05 | App Integration | 2 | Pending |
| APP-06 | App Integration | 2 | Pending |
| APP-07 | App Integration | 1 | Pending |
| DEPLOY-01 | Multiple Deployment | 3 | Pending |
| DEPLOY-02 | Multiple Deployment | 3 | Pending |
| DEPLOY-03 | Multiple Deployment | 3 | Pending |
| DEPLOY-04 | Multiple Deployment | 3 | Pending |
| DEPLOY-05 | Multiple Deployment | 3 | Pending |
| DEPLOY-06 | Multiple Deployment | 3 | Pending |
| DOCS-01 | Documentation Review | 3 | Pending |
| DOCS-02 | Documentation Review | 3 | Pending |
| DOCS-03 | Documentation Review | 3 | Pending |
| DOCS-04 | Documentation Review | 3 | Pending |
| DOCS-05 | Documentation Review | 3 | Pending |
| DOCS-06 | Documentation Review | 3 | Pending |

**Coverage:** 19/19 requirements mapped ✓

---

*Roadmap derives phases from requirements; all v1 features map to exactly one phase; no orphaned requirements*
