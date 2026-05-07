"""Centralized LLM client factory with multi-provider support.

All agents call get_llm() to obtain a ChatOpenAI-compatible client
pointed at the LiteLLM proxy (localhost:4000). This gives automatic
provider rotation, retries, and fallback across all configured providers.

Model selection strategies:
  - "llm" (default): Proxy rotation (Gemini → tier2 → tier3 → local)
  - "local": Explicit local model (vLLM on localhost:8001)
  - "remote": Skip local, use remote providers only
  - Custom name: Use specific model from proxy_config.yml
"""

import os
from functools import lru_cache

from langchain_openai import ChatOpenAI

LITELLM_BASE_URL = os.getenv("LITELLM_BASE_URL", "http://localhost:4000/v1")
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "llm")
MODEL_STRATEGY = os.getenv("MODEL_STRATEGY", "auto")  # auto|local|remote


@lru_cache(maxsize=8)
def get_llm(
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 2048,
    force_remote: bool = False,
) -> ChatOpenAI:
    """Return cached ChatOpenAI instance at LiteLLM proxy.

    Model selection logic:
      1. force_remote=True → model="llm" (skip local)
      2. MODEL_STRATEGY="local" → model="local" (offline-first)
      3. MODEL_STRATEGY="remote" → model="llm" (cloud-first)
      4. MODEL_STRATEGY="auto" (default) → model="llm" (proxy handles)
      5. Explicit model param → use as-is

    Args:
        model: Model name (llm, local, remote, or custom).
                If None uses DEFAULT_MODEL + strategy.
        temperature: Sampling temperature.
        max_tokens: Max tokens per response.
        force_remote: Override strategy, always use remote.

    Returns:
        ChatOpenAI instance configured for LiteLLM proxy.
    """
    # Resolve model via strategy
    if model is None:
        if force_remote:
            model = "llm"  # Proxy rotation (skip local)
        elif MODEL_STRATEGY == "local":
            model = "local"  # Explicit local fallback
        elif MODEL_STRATEGY == "remote":
            model = "llm"  # Proxy (all remote tiers)
        else:  # "auto" (default)
            model = DEFAULT_MODEL  # Proxy rotation (all tiers)

    return ChatOpenAI(
        model=model,
        base_url=LITELLM_BASE_URL,
        api_key=os.getenv("OPENAI_API_KEY", "sk-not-needed"),
        temperature=temperature,
        max_tokens=max_tokens,
    )


def get_llm_for_agent(
    agent_name: str,
    temperature: float = 0.7,
    max_tokens: int = 2048,
) -> ChatOpenAI:
    """Get LLM for specific agent with optional agent-specific config.

    Allows per-agent LLM selection via env vars:
      LLM_{AGENT_NAME}=local  → force local for this agent
      LLM_{AGENT_NAME}=groq/llama-3.3-70b-versatile → specific model

    Args:
        agent_name: Agent identifier (code_runner, text2sql_agent, etc.)
        temperature: Sampling temperature.
        max_tokens: Max tokens per response.

    Returns:
        ChatOpenAI instance (agent-specific or default strategy).
    """
    agent_model = os.getenv(f"LLM_{agent_name.upper()}")
    return get_llm(
        model=agent_model,
        temperature=temperature,
        max_tokens=max_tokens,
    )
