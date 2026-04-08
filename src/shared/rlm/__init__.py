"""RLM (Recursive Language Models) integration.

Provides factories for RLM instances configured with LiteLLM proxy backend
and Phoenix OTEL tracing for full execution visibility.
"""

from src.shared.rlm.client import get_rlm, get_rlm_metadata, rlm_completion
from src.shared.rlm.config import RLMSettings

__all__ = [
    "RLMSettings",
    "get_rlm",
    "rlm_completion",
    "get_rlm_metadata",
]
