# Recursive Language Models (RLM)

RLM (Recursive Language Models) integration provides a powerful way to handle ultra-long contexts (50k+ lines) through intelligent recursive decomposition. The RLM agent breaks down complex tasks into subproblems, solves them recursively, and combines results.

## Features

- **Ultra-Long Context Support** - Handles 50k+ line documents via progressive compaction
- **Recursive Decomposition** - Automatically breaks complex queries into sub-tasks
- **Full OTEL Tracing** - Execution trajectory tracked in Phoenix with full observability
- **LiteLLM Integration** - Automatic provider rotation across 12+ free providers
- **Message History** - Complete message chain for debugging and observability

## Architecture

**Location**: `src/shared/rlm/` (backend) + `src/agents/rlm_agent/` (example agent)

### Files

- `config.py` — `RLMSettings` dataclass (backend, environment, max_iterations, compaction, Phoenix config)
- `client.py` — `get_rlm()`, `rlm_completion()`, `get_rlm_metadata()` with OTEL tracing
- `agent.py` — Single-node StateGraph: Input → search_node (RLM execution) → Output

### Key Features

- Handles 50k+ line contexts via progressive compaction (auto-trigger at 85% token fill)
- Recursive decomposition (max_depth=2) with full trajectory tracking
- LiteLLM proxy integration → automatic provider rotation
- Phoenix OTEL tracing AUTOMATIC via `setup_tracing()` at module import
- Full message history logged to state for observability

## Usage

### Graph API (StateGraph)

```python
from src.agents.rlm_agent import graph
from src.agents.rlm_agent.states import RLMAgentState

# Build input state
state: RLMAgentState = {
    "prompt": "Find MAGIC_NUMBER in this text",
    "context": long_text_3000_lines,
    "messages": [],
    "rlm_response": None,
    "rlm_metadata": None,
    "rlm_status": "pending",
}

# Run agent
result = await graph.ainvoke(state)

# Access results
print(result['rlm_response'])      # Final answer
print(result['rlm_metadata'])      # Execution trajectory
print(result['rlm_status'])        # "success" or "error"
print(result['messages'])          # Full message chain
```

### Functional API (Pipelines)

```python
from src.agents.rlm_agent.pipelines.pipeline import workflow

result = workflow({
    "prompt": "Find SECRET in this text",
    "context": long_text,
})

print(result['response'])    # Final answer
print(result['metadata'])    # Execution details
```

## Testing

**Mocked tests** (no proxy required):

```bash
source .venv/bin/activate
pytest src/agents/rlm_agent/tests/test_rlm_search.py -v
```

**Full integration demo** (with Phoenix tracing):

```bash
# Start infrastructure
make build

# Run demo (requires .env configured)
python demo_rlm.py
```

## Configuration

Via `RLMSettings`:

```python
from src.shared.rlm import RLMSettings, rlm_completion

settings = RLMSettings(
    backend="local",                    # or "remote"
    max_iterations=10,                  # per invocation
    max_depth=2,                        # recursive depth
    compaction_trigger=0.85,            # auto-trigger at 85% token fill
    verbose=True,                       # detailed logging
)

result = rlm_completion(
    prompt="Find X in text",
    context=long_text,
    settings=settings,
)
```

## Environment Variables

```bash
# LiteLLM proxy (auto-rotation)
LITELLM_BASE_URL=http://localhost:4000/v1
DEFAULT_MODEL=llm

# Phoenix tracing (optional)
PHOENIX_COLLECTOR_ENDPOINT=http://localhost:6006
PHOENIX_PROJECT_NAME=agent-setup
PHOENIX_TRACING_ENABLED=true
```

## Phoenix Observability

Execution traces appear in Phoenix UI at `http://localhost:6006`:

```
agent.ainvoke()
├─ search (node)
│  └─ rlm.completion (spans traced via tracer wrapper)
│     └─ RLM internal iterations (stored in metadata)
└─ message stream into LangChain for logging
```

## Performance Characteristics

| Context Size | Approach | Typical Time |
|--------------|----------|--------------|
| < 20k chars | Single pass | < 2s |
| 20-100k chars | Recursive decomposition | 2-5s |
| 100k+ chars | Progressive compaction | 5-10s |

## Troubleshooting

**"Token limit exceeded"**
- RLM compaction is triggered at 85% token fill. Check `COMPACTION_TRIGGER` setting.

**"No answer found"**
- RLM may need more iterations. Increase `max_iterations` in RLMSettings.

**Phoenix traces not appearing**
- Ensure `setup_tracing()` was called at module import (automatic in `__init__.py`).
- Verify `PHOENIX_TRACING_ENABLED=true` in `.env`.

## Further Reading

- [RLMSettings API Reference](api-reference.md#RLMSettings)
- [Phoenix Observability](arize-phoenix.md)
- [LiteLLM Provider Configuration](https://docs.litellm.ai/)
