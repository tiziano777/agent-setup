# Requirements — agent-setup v1.0

## v1 Requirements

### App Integration (Phase 1)

- [ ] **APP-01** — User can interact with agents via REST API endpoint `/api/agents/{agent_name}/invoke`
- [ ] **APP-02** — User can see agent execution trace (message history, tool calls, final output) in response
- [ ] **APP-07** — Health check endpoint `/api/health` returns agent registry status

### App Integration (Phase 2)

- [ ] **APP-03** — Streamlit dashboard displays available agents with descriptions
- [ ] **APP-04** — User can invoke agents from Streamlit UI with text input → display results
- [ ] **APP-05** — Multi-agent supervisor pattern exposed: user selects source agent → supervisor routes to child agents
- [ ] **APP-06** — Session management: conversation history persisted per user/thread

### Multiple Deployment (Phase 3)

- [ ] **DEPLOY-01** — Docker Compose dev setup documented and working (PostgreSQL, Qdrant, Neo4j, Oxigraph, Phoenix, LiteLLM)
- [ ] **DEPLOY-02** — Kubernetes manifests for single-node deployment (agents, LiteLLM proxy, databases, Phoenix)
- [ ] **DEPLOY-03** — LangGraph Cloud-compatible agent exports (invocation signature verified)
- [ ] **DEPLOY-04** — Environment config documented: .env.example covering all agent settings
- [ ] **DEPLOY-05** — Health checks on all service dependencies (DB connections, LiteLLM proxy reachability)
- [ ] **DEPLOY-06** — Observability setup documented (Phoenix UI access, metric dashboard config)

### Documentation Review (Phase 3)

- [ ] **DOCS-01** — README translated to English or maintained in English (currently Italian)
- [ ] **DOCS-02** — All 8 agents have dedicated `docs/{agent_name}.md` with pipeline visualization, state, usage examples
- [ ] **DOCS-03** — `docs/sql_toolkit.md` updated: add section for each toolkit (cognee, retrieval, deep_eval, sandbox)
- [ ] **DOCS-04** — Architecture and Structure docs verified against .planning/codebase/ mapping
- [ ] **DOCS-05** — CONCERNS.md findings addressed: test gaps filled, security hardening applied, orphaned files cleaned
- [ ] **DOCS-06** — Unified CLAUDE.md written with project philosophy, agent structure guide, TDD patterns, deployment checklists

---

## v2 Requirements (Deferred)

- [ ] **AGENTS-02** — Fine-tuning harness for domain-specific models (agent logic optimization)
- [ ] **EVAL-02** — Automated eval suite with LLM-as-judge scoring (beyond DeepEval metrics)
- [ ] **PERF-01** — Performance optimization: agent invocation latency < 500ms p95 (currently not benchmarked)
- [ ] **FEATURES-01** — Multi-tenancy: shared infrastructure with per-tenant agent isolation
- [ ] **SECURITY-01** — RBAC and audit logging for enterprise deployments

---

## Out of Scope

- **LLM fine-tuning** — Agent capability comes from prompts + RAG, not model training
- **Premium observability** — Datadog/New Relic integrations; Phoenix covers our needs
- **Real-time agent-to-agent pub/sub** — Async handoffs via store; no WebSocket messaging layer
- **Enterprise SSO/audit** — Assumed team/research environment; no multi-tenant access control
- **GPU inference servers** — Agents call external LLM API only; no local model hosting

---

## Requirement Traceability

| REQ-ID | Category | Phase | Status | Verified |
|--------|----------|-------|--------|----------|
| APP-01 | App Integration | 1 | Pending | — |
| APP-02 | App Integration | 1 | Pending | — |
| APP-03 | App Integration | 2 | Pending | — |
| APP-04 | App Integration | 2 | Pending | — |
| APP-05 | App Integration | 2 | Pending | — |
| APP-06 | App Integration | 2 | Pending | — |
| APP-07 | App Integration | 1 | Pending | — |
| DEPLOY-01 | Multiple Deployment | 3 | Pending | — |
| DEPLOY-02 | Multiple Deployment | 3 | Pending | — |
| DEPLOY-03 | Multiple Deployment | 3 | Pending | — |
| DEPLOY-04 | Multiple Deployment | 3 | Pending | — |
| DEPLOY-05 | Multiple Deployment | 3 | Pending | — |
| DEPLOY-06 | Multiple Deployment | 3 | Pending | — |
| DOCS-01 | Documentation Review | 3 | Pending | — |
| DOCS-02 | Documentation Review | 3 | Pending | — |
| DOCS-03 | Documentation Review | 3 | Pending | — |
| DOCS-04 | Documentation Review | 3 | Pending | — |
| DOCS-05 | Documentation Review | 3 | Pending | — |
| DOCS-06 | Documentation Review | 3 | Pending | — |

**Coverage: 19/19 v1 requirements mapped**

---

## UAT Success Criteria [From ROADMAP]

### Phase 1: REST API Foundation
1. User can POST to `/api/agents/{agent_name}/invoke` with JSON payload and receive agent response with status code 200
2. Response includes `execution_trace` with message history, all tool calls made, and final output
3. All 8 agents (code_runner, rag_agent, knowledge_agent, autoresearch, deepconf_agent, rlm_agent, text2sql_agent, _template) are callable via REST without code modification
4. Health check endpoint `/api/health` returns `{"status": "healthy", "agents_available": N, "dependencies": {"llm_proxy": bool, "databases": bool}}`
5. API validates input schema and returns 400 with descriptive error messages on malformed requests

### Phase 2: User Interface & Orchestration
1. User opens Streamlit dashboard and sees grid/list of all agents with name, description, and status
2. User selects an agent, enters text input, clicks invoke, and sees streamed response in real-time
3. User can see full execution trace panel (messages, tool calls, iterations) after invocation completes
4. User selects "supervisor" mode where they pick a primary agent that routes requests to child agents based on request intent
5. Conversation history is persisted per user session and survives Streamlit reruns and browser refresh
6. User can switch between agents mid-session; each agent maintains separate conversation thread

### Phase 3: Deployment & Documentation
1. Developer can run `docker-compose -f docker-compose.yml up` and all services reach healthy state within 60 seconds
2. Developer can deploy to Kubernetes cluster using provided manifests; all agent pods reach `Ready` and `Running` status
3. Agents can be exported to LangGraph Cloud with verified invocation signatures
4. Developer creates `.env` file with custom values; all services respect env var overrides with no hardcoded secrets
5. Health checks validate all service dependencies; GET `/api/health` returns 200 with dependency status
6. Developer can access Phoenix UI at endpoint in docs and see distributed traces for all agent invocations
7. All 8 agents have dedicated documentation files with pipeline diagrams, state schemas, code examples
8. README.md is in English and lists all agents in features section with links to their documentation
9. CONCERNS.md findings are resolved: orphaned files deleted, test coverage gaps addressed, security hardening applied
10. CLAUDE.md documents agent structure patterns, TDD approach, deployment checklists, and onboarding guide

---

*Last updated: 2026-04-14 after roadmap creation*
