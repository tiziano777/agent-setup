"""Phoenix LLM bridge for evaluation.

Creates a ``phoenix.evals.LLM`` instance pointed at the project's LiteLLM
proxy so that all Phoenix evaluators use the same rotated provider pool
as the agents themselves.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache

logger = logging.getLogger(__name__)

try:
    from phoenix.evals import LLM

    _AVAILABLE = True
except ImportError:
    _AVAILABLE = False

_INSTALL_HINT = "Install phoenix evals: pip install -e '.[phoenix]'"


def _check_available() -> None:
    if not _AVAILABLE:
        raise ImportError(_INSTALL_HINT)


@lru_cache(maxsize=4)
def get_eval_llm(
    model: str | None = None,
    temperature: float = 0.0,
) -> "LLM":
    """Return a Phoenix ``LLM`` pointed at the LiteLLM proxy.

    Args:
        model: Model name as configured in ``proxy_config.yml``.
               Defaults to ``DEFAULT_MODEL`` env var (usually ``"llm"``).
        temperature: Sampling temperature.  Defaults to 0.0 for
                     deterministic evaluation.

    Returns:
        A ``phoenix.evals.LLM`` backed by the local proxy.

    Raises:
        ImportError: If ``arize-phoenix-evals`` is not installed.
    """
    _check_available()

    base_url = os.getenv("LITELLM_BASE_URL", "http://localhost:4000/v1")
    if model is None:
        model = os.getenv("DEFAULT_MODEL", "llm")

    return LLM(
        provider="openai",
        model=model,
        temperature=temperature,
        sync_client_kwargs={"base_url": base_url, "api_key": "not-needed"},
        async_client_kwargs={"base_url": base_url, "api_key": "not-needed"},
    )
