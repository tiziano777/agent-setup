# Requirements — agent-setup v1.0

## v1 Requirements

### App Integration (Phase X)

- [ ] **APP-01** — User can interact with agents via REST API endpoint `/api/agents/{agent_name}/invoke`
- [ ] **APP-02** — User can see agent execution trace (message history, tool calls, final output) in response
- [ ] **APP-03** — Streamlit dashboard displays available agents with descriptions
- [ ] **APP-04** — User can invoke agents from Streamlit UI with text input → display results
- [ ] **APP-05** — Multi-agent supervisor pattern exposed: user selects source agent → supervisor routes to child agents
- [ ] **APP-06** — Session management: conversation history persisted per user/thread
- [ ] **APP-07** — Health check endpoint `/api/health` returns agent registry status

### Multiple Deployment (Phase Y)

- [ ] **DEPLOY-01** — Docker Compose dev setup documented and working (PostgreSQL, Qdrant, Neo4j, Oxigraph, Phoenix, LiteLLM)
- [ ] **DEPLOY-02** — Kubernetes manifests for single-node deployment (agents, LiteLLM proxy, databases, Phoenix)
- [ ] **DEPLOY-03** — LangGraph Cloud-compatible agent exports (invocation signature verified)
- [ ] **DEPLOY-04** — Environment config documented: .env.example covering all agent settings
- [ ] **DEPLOY-05** — Health checks on all service dependencies (DB connections, LiteLLM proxy reachability)
- [ ] **DEPLOY-06** — Observability setup documented (Phoenix UI access, metric dashboard config)

### Documentation Review (Phase Z)

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

(Populated by ROADMAP.md after phase planning)

| REQ-ID | Phase | Status | Verified |
|--------|-------|--------|----------|
| APP-01 | Phase X | — | — |
| ... | ... | ... | ... |

---

## UAT Success Criteria [From ROADMAP]

(Populated by roadmap after phase definition)

---

*Last updated: 2026-04-14 after brownfield requirements gathering*
