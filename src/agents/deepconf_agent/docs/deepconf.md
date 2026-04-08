# DeepConf - Agent Configuration & Composition

DeepConf provides a type-safe, hierarchical configuration system for composing and wiring LangGraph agents. It enables declarative, layered config with environment-aware defaults and clean agent handoff patterns.

## Features

- **Type-Safe Config** - Pydantic-based schemas with validation
- **Hierarchical Composition** - Agents can depend on other agents cleanly
- **Environment-Aware** - Automatic loading from `.env` with sensible defaults
- **Reusable Patterns** - Pre-built supervisor, swarm, and independent agent configs
- **Runtime Override** - Config can be overridden at agent invocation time

## Architecture

**Location**: `src/shared/deepconf/`

### Files

- `config.py` — Base `AgentConfig` class for composition
- `settings.py` — Environment-aware settings (`DeepConfSettings`)
- `supervisor.py` — Supervisor config with agent routing
- `swarm.py` — Swarm/peer-to-peer agent patterns
- `independent.py` — Single-agent independent patterns

## Usage

### Basic Config

```python
from src.shared.deepconf import AgentConfig, DeepConfSettings

class MyAgentConfig(AgentConfig):
    """Configuration for my agent."""
    temperature: float = 0.7
    max_tokens: int = 2048
    top_p: float = 0.95

# Load from environment
config = MyAgentConfig.from_env()

# Or override
config = MyAgentConfig(
    temperature=0.5,
    max_tokens=4096,
)
```

### Multi-Agent Supervisor Config

```python
from src.shared.deepconf.supervisor import SupervisorConfig

supervisor_config = SupervisorConfig(
    supervisor_llm_model="llm",
    agents={
        "researcher": {"agent": research_agent, "description": "Research queries"},
        "writer": {"agent": write_agent, "description": "Write content"},
        "reviewer": {"agent": review_agent, "description": "Review and edit"},
    },
    routing_logic="hierarchical",  # or "round_robin", "custom"
)

supervisor = build_supervisor_from_config(supervisor_config)
result = await supervisor.ainvoke(task)
```

### Swarm Pattern

```python
from src.shared.deepconf.swarm import SwarmConfig

swarm_config = SwarmConfig(
    agents=[agent1, agent2, agent3],
    consensus_model="majority",  # or "unanimous", "llm_judge"
    max_iterations=5,
)

swarm = build_swarm_from_config(swarm_config)
result = await swarm.ainvoke(task)
```

### Independent Agent Pattern

```python
from src.shared.deepconf.independent import IndependentConfig

agent_config = IndependentConfig(
    agent=my_agent,
    max_iterations=3,
    retry_on_error=True,
)

result = await agent_config.run(task)
```

## Integration with RLM Agent

```python
from src.agents.rlm_agent import graph as rlm_graph
from src.shared.deepconf.independent import IndependentConfig

rlm_config = IndependentConfig(
    agent=rlm_graph,
    max_iterations=2,  # RLM handles internal recursion
)

result = await rlm_config.run({
    "prompt": "Find SECRET in this text",
    "context": long_text,
})
```

## Environment Variables

DeepConf loads from `.env`:

```bash
# Agent defaults
DEEPCONF_DEFAULT_TEMPERATURE=0.7
DEEPCONF_DEFAULT_MAX_TOKENS=2048
DEEPCONF_DEFAULT_MODEL=llm

# Supervisor routing
DEEPCONF_SUPERVISOR_ROUTING=hierarchical

# Swarm consensus
DEEPCONF_SWARM_CONSENSUS=majority
DEEPCONF_SWARM_MAX_ITERATIONS=5

# Independent agent retry
DEEPCONF_RETRY_ON_ERROR=true
```

## Configuration Inheritance

Create specialized configs by inheriting:

```python
from src.shared.deepconf import AgentConfig

class RAGAgentConfig(AgentConfig):
    """Specialized config for RAG agents."""
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    vector_db_host: str = "localhost"
    vector_db_port: int = 6333
    retriever_top_k: int = 5

    @classmethod
    def from_env(cls):
        """Load from environment with RAG-specific defaults."""
        return cls(
            embedding_model=os.getenv("RAG_EMBEDDING_MODEL", cls.embedding_model),
            vector_db_host=os.getenv("RAG_VDB_HOST", cls.vector_db_host),
            # ...
        )

# Use
rag_config = RAGAgentConfig.from_env()
```

## Best Practices

1. **Use Type Annotations** - Enable IDE validation and auto-completion
2. **Provide Defaults** - All config fields should have sensible defaults
3. **Separate Concerns** - Keep agent logic separate from config
4. **Validate Early** - DeepConf validates on instantiation
5. **Document Settings** - Add docstrings to config classes

## Troubleshooting

**"Missing required config field"**
- All non-optional fields must be provided or have defaults.

**"Invalid type for field X"**
- DeepConf uses Pydantic v2 strict validation. Check field types.

**"Environment variable not found"**
- Use `field(default=value)` in Pydantic to provide fallback values.

## Further Reading

- [Agent Development Guide](agent-development.md)
- [Multi-Agent Patterns](multi-agent.md)
- [API Reference - AgentConfig](api-reference.md#AgentConfig)
- [Pydantic v2 Documentation](https://docs.pydantic.dev/latest/)
