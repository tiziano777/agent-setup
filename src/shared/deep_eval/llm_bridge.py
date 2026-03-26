"""DeepEval LLM bridge.

Creates a ``deepeval.models.LiteLLMModel`` pointed at the project's LiteLLM
proxy so that all DeepEval metrics use the same rotated provider pool as the
agents themselves.
"""

from __future__ import annotations

import logging
from functools import lru_cache

from src.shared.deep_eval.config import _check_available, get_settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=4)
def get_deepeval_model(
    model: str | None = None,
    temperature: float = 0.0,
):
    """Return a DeepEval ``LiteLLMModel`` pointed at the LiteLLM proxy.

    Args:
        model: Model name as configured in ``proxy_config.yml``.
               Defaults to ``DEFAULT_MODEL`` env var (usually ``"llm"``).
        temperature: Sampling temperature.  Defaults to 0.0 for
                     deterministic evaluation.

    Returns:
        A ``deepeval.models.LiteLLMModel`` backed by the local proxy.

    Raises:
        ImportError: If ``deepeval`` is not installed.
    """
    _check_available()
    from deepeval.models import LiteLLMModel

    settings = get_settings()

    if model is None:
        model = settings.default_model

    return LiteLLMModel(
        model=f"openai/{model}",
        base_url=settings.litellm_base_url,
        api_key="not-needed",
        temperature=temperature,
    )
