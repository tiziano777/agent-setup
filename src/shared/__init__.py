"""Shared utilities for the agent-setup project.

Provides common LLM clients, memory infrastructure,
agent registry, multi-agent orchestration utilities,
and retrieval infrastructure.
"""

from src.shared.llm import get_llm
from src.shared.registry import AgentRegistry

__all__ = ["get_llm", "AgentRegistry"]

# Retrieval utilities are imported lazily to avoid pulling in heavy
# dependencies (sentence-transformers, qdrant-client, etc.) when they
# are not installed.  Use ``from src.shared.retrieval import ...`` directly.

# Evaluation toolkit (phoenix evals) is also lazy-imported.
# Use ``from src.shared.phoenix_eval import ...`` directly.
# Requires: pip install -e '.[phoenix]'

# DeepEval evaluation toolkit is lazy-imported.
# Use ``from src.shared.deep_eval import ...`` directly.
# Requires: pip install -e '.[deepeval]'

# Sandbox toolkit (Docker-based shell execution) is lazy-imported.
# Use ``from src.shared.sandbox import ...`` directly.
# Requires: pip install -e '.[sandbox]'
