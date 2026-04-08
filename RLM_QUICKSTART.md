"""RLM AGENT - Quick Start Guide

## TL;DR

Find hidden values in 50k+ line texts using RLM's recursive decomposition + Phoenix observability.

---

## Installation

```bash
pip install -e ".[rlm]"
```

---

## Usage

### Simple API

```python
from src.shared.rlm import rlm_completion

# Find value in long text
result = rlm_completion(
    prompt="Find the SECRET_NUMBER in the text",
    context=very_long_text_50k_lines
)

print(result['response'])        # Answer
print(result['execution_time'])  # How long it took
print(result['metadata'])        # Full execution trajectory
```

### With LangGraph Agent

```python
import asyncio
from src.agents.rlm_agent import get_agent
from src.agents.rlm_agent.states import RLMAgentState

async def main():
    agent = get_agent()
    result = await agent.ainvoke({
        "prompt": "Find MAGIC_NUMBER",
        "context": long_text,
        "messages": [],
        # ... other fields (rlm_response, rlm_metadata, rlm_status: None)
    })

    print(result['rlm_response'])  # Answer
    print(result['messages'])      # Full trace for Phoenix

asyncio.run(main())
```

---

## Run Tests

```bash
# Mocked tests (no proxy required)
pytest src/agents/rlm_agent/tests/ -v

# Standalone integration test (no proxy)
python test_rlm_standalone.py

# Full demo (requires: make build to start proxy)
python demo_rlm.py
```

---

## View Traces

Phoenix shows full execution trace when enabled:

```bash
# 1. Start infrastructure
make build

# 2. In another terminal, run agent
python demo_rlm.py

# 3. View traces at
# http://localhost:6006
```

**What you'll see**:
- rlm.completion span (elapsed time)
- search_node execution
- Message chain with metadata
- Full trajectory in span events

---

## Configuration

env vars (all optional):

```bash
RLM_BACKEND=openai                                  # LLM backend
RLM_MODEL=llm                                       # Model (auto-rotated via proxy)
RLM_ENVIRONMENT=local                              # local | docker | modal | e2b
RLM_LOG_DIR=./logs                                 # Execution logging
LITELLM_BASE_URL=http://localhost:4000/v1         # Proxy URL
PHOENIX_TRACING_ENABLED=true                       # Observability
```

---

## Files

```
src/shared/rlm/
├── config.py              → Settings dataclass
├── client.py              → Factories (get_rlm, rlm_completion)
└── __init__.py            → Public API

src/agents/rlm_agent/
├── states.py              → RLMAgentState
├── schemas.py             → Input/Output validation
├── prompts/system.py      → System prompt
├── nodes/search.py        → RLM execution node
├── agent.py               → Graph definition
└── tests/                 → Pytest tests
```

---

## Example Output

```
[1] Generating test haystack...
    ✓ Generated 363,022 chars (3001 lines)
    ✓ Hidden value at line 1256: SECRET_42_FOUND

[6] RESULTS:
    Status: success
    RLM Response: Found the magic value: SECRET_42_FOUND

[8] MESSAGE CHAIN (for observability):
    Message 0: HumanMessage
    Message 1: AIMessage
      Metadata: {
        'execution_time': 2.34,
        'total_iterations': 3,
        'recursive_calls': 0
      }

[9] RLM EXECUTION TRAJECTORY:
    Iterations: 3
      • {"step": 1, "action": "sample_lines"}
      • {"step": 2, "action": "regex_search"}
      • {"step": 3, "action": "extract_value"}

✅ ALL TESTS PASSED
```

---

## Key Features

✅ Handles 50k+ lines via progressive compaction
✅ Recursive decomposition (RLM calling itself)
✅ Full execution trajectory captured
✅ LiteLLM proxy integration (automatic provider rotation)
✅ Phoenix OTEL tracing (automatic at import)
✅ Message history (HumanMessage + AIMessage)
✅ Execution metadata stored in message payload
✅ Mocked tests (no proxy required)

---

## Troubleshooting

### "rlm_completion returned None"
→ Ensure OPENAI_API_KEY env var set or LiteLLM proxy running

### "Phoenix spans not showing"
→ Phoenix disabled? Set PHOENIX_TRACING_ENABLED=true

### "Import error: No module named 'rlm'"
→ Run: pip install -e ".[rlm]"

### "Test fails with proxy_not_available"
→ Expected for standalone tests. They use mocks. Run:
  pytest src/agents/rlm_agent/tests/ -v

---

## Resources

- Full docs: RLM_INTEGRATION.md
- RLM repo: https://github.com/alexzhang13/rlm
- Agent Setup CLAUDE.md: Architecture
- Memory: auto-memory for learnings
"""
