"""Centralized LLM client factory.

All agents call get_llm() to obtain a ChatOpenAI-compatible client
pointed at the LiteLLM proxy (localhost:4000). This gives automatic
provider rotation, retries, and fallback across all configured providers.
"""

import os
from functools import lru_cache

from langchain_openai import ChatOpenAI

LITELLM_BASE_URL = os.getenv("LITELLM_BASE_URL", "http://localhost:4000/v1")
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "llm")


@lru_cache(maxsize=8)
def get_llm(
    model: str = DEFAULT_MODEL,
    temperature: float = 0.7,
    max_tokens: int = 2048,
) -> ChatOpenAI:
    """Return a cached ChatOpenAI instance pointed at the LiteLLM proxy.

    Args:
        model: Model name as configured in proxy_config.yml.
               Default "llm" uses the rotation pool.
        temperature: Sampling temperature.
        max_tokens: Max tokens for the response.

    Returns:
        A ChatOpenAI instance configured for the local proxy.
    """
    return ChatOpenAI(
        model=model,
        base_url=LITELLM_BASE_URL,
        api_key=None,
        temperature=temperature,
        max_tokens=max_tokens,
    )
