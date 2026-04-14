# STATE — agent-setup v1.0 Roadmap Execution

**Project Reference:** agent-setup — LangGraph agent incubator framework
**Current Milestone:** v1.0 (Foundation → UI → Production)
**Last Updated:** 2026-04-14

---

## Project Position

**Roadmap Status:** 3 phases planned, 0/3 started
**Current Phase:** Phase 1 (REST API Foundation)
**Current Plan:** None (awaiting `/gsd-plan-phase 1`)

### Progress Overview

```
Phase 1 (REST API)        [████░░░░░░░░░░░░░░] 0%
Phase 2 (UI & Orchestration) [░░░░░░░░░░░░░░░░░░░░] 0%
Phase 3 (Deployment & Docs) [░░░░░░░░░░░░░░░░░░░░] 0%

Total: 0/19 requirements completed
```

---

## What We're Building

**Phase 1 Outcome:** REST API exposing all 8 agents with execution tracing
- Users invoke agents programmatically via HTTP
- Full trace visibility (messages, tool calls, outputs)
- Health checks for deployment monitoring

**Phase 2 Outcome:** Interactive Streamlit dashboard + multi-agent supervisor
- Users discover and invoke agents from web UI
- Supervisor patterns enable intelligent agent routing
- Persistent conversation history per session

**Phase 3 Outcome:** Production deployment + complete documentation
- Docker, Kubernetes, LangGraph Cloud deployment options
- All 8 agents documented with examples
- Tech debt resolved; CONCERNS.md findings addressed

---

## Current Focus

### Phase 1: REST API Foundation

**Entry Condition:**
- All 8 agents implemented and tested ✓
- 11 shared modules available ✓
- Phoenix tracing infrastructure ready ✓

**Exit Condition (when Phase 1 complete):**
- REST API framework deployed (FastAPI or similar)
- All agents callable via HTTP endpoints
- Health checks operational
- Execution traces returned in responses
- API tests 100% pass

**Key Decisions:**
- Which REST framework? (FastAPI recommended for async)
- How to structure agent invocation routes?
- Where to store execution traces? (State store or ephemeral?)

**Blockers:** None identified

---

## Key Learnings & Patterns

### Agent Structure Pattern

Every agent follows `.../agent.py` with:
```python
# Exports at module level:
graph: StateGraph = ...
# Optional functional API:
@entrypoint
def invoke_agent(input: str) -> dict: ...
```

**For REST API:** Import `graph` from each agent and bind to routes.

### Shared Module Dependencies

All agents depend ONLY on `src/shared/`:
- `llm.py` — LiteLLM proxy access (provider rotation automatic)
- `types.py` — `BaseAgentState` + `TypedDict` patterns
- `memory.py` — Checkpointer/store for persistence
- `registry.py` — Agent discovery
- `sql.py` — PostgreSQL client + tools
- `retrieval.py` — RAG pipeline
- `cognee_toolkit.py` — Knowledge graphs
- Other toolkits as needed

**No cross-agent imports.** All agents are independent.

### Testing Pattern

Each agent has `conftest.py` with:
- `test_db_schema()` fixture — PostgreSQL test schema (auto-cleanup)
- Marked with `@pytest.mark.integration` for large tests
- Mocked tests for LLM logic (no provider calls)

**For REST API tests:** Mock the agent graph and test HTTP contracts.

### TDD Approach

1. Write test first (HTTP contract + expected response shape)
2. Implement endpoint + agent invocation
3. Verify trace capture
4. Add error cases

---

## Performance Metrics

**Baseline (from codebase analysis):**
- Agent invocation latency: Not benchmarked yet (Phase 3 concern)
- API throughput: Not measured yet
- Trace overhead: Minimal (Phoenix OTEL async)

**Goals (for Phase 1):**
- REST API p99 latency < 5s per invocation
- Health checks respond < 100ms
- Concurrent agent limit: Monitored via SQL connection pool

---

## Accumulated Context

### From Codebase Mapping (gsd-map-codebase)

**Documentation gaps to resolve in Phase 3:**
- README in Italian; translate to English
- `text2sql_agent` needs dedicated doc file
- `deepconf_agent` references missing from README
- Test organization: `deepconf_agent` tests in `__init__.py` (fix in Phase 3)

**Security considerations:**
- SQL injection mitigated (SQLAlchemy parameterized)
- Table authorization missing (add in future phase)
- Error messages may leak schema details (scrub in Phase 3)
- Hardcoded dev credentials in compose (mitigated by .env override)

**Performance concerns:**
- Message accumulation in state (no size limits yet)
- Connection pool defaults (5/10) may not scale
- Large monolithic nodes file in text2sql_agent (refactor in Phase 3)

**Orphaned files to clean in Phase 3:**
- `_test_pgvector.py`, `demo_rlm.py`, `test_rlm_enhanced.py`
- `langgraph.json`, `new_agent_plan.md`, `skills-lock.json`

### Dependencies

**External:**
- FastAPI (for REST API) — add to pyproject.toml Phase 1
- Streamlit (for dashboard) — add to pyproject.toml Phase 2
- Kubernetes client (optional, for Phase 3)

**Internal:**
- Phase 1 depends on: All 8 agents + shared modules (already exist)
- Phase 2 depends on: Phase 1 (REST API)
- Phase 3 depends on: Phase 1 + Phase 2 (complete feature set)

---

## Session Continuity

**After Phase 1 Kickoff (via `/gsd-plan-phase 1`):**
1. `/gsd-plan-phase 1` creates PLAN.md with executable tasks
2. Plans decomposed into must_haves, nice_to_haves, deferred
3. Implementation proceeds plan-phase by plan-phase
4. Update STATE.md after each plan completes

**Between Sessions:**
- STATE.md is the source of truth for current position
- ROADMAP.md remains static unless revised
- PLAN.md (per phase) is created fresh per phase and retired at phase end

---

## Next Steps

1. **Approve this roadmap** (or provide feedback for revision)
2. **Invoke `/gsd-plan-phase 1`** to create executable plan for REST API
3. **Execute Phase 1 plans** with Claude implementation
4. **Transition Phase 1 → 2** via `/gsd-transition` (update STATE.md + PROJECT.md)
5. **Repeat for Phases 2 and 3**

---

## Blockers

None currently. Ready to proceed with Phase 1 planning.

---

*STATE.md is project memory. Update after each phase transition.*
