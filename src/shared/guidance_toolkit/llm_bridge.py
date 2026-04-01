"""Guidance LLM bridge.

Creates a ``guidance.models.OpenAI`` instance pointed at the project's LiteLLM
proxy so that all guidance programs use the same rotated provider pool as the
agents themselves.
"""

from __future__ import annotations

import logging
from functools import lru_cache

from src.shared.guidance_toolkit.config import _check_available, get_settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=4)
def get_guidance_model(
    model: str | None = None,
    temperature: float | None = None,
):
    """Return a guidance ``OpenAI`` model pointed at the LiteLLM proxy.

    Args:
        model: Model name as configured in ``proxy_config.yml``.
               Defaults to ``DEFAULT_MODEL`` env var (usually ``"llm"``).
        temperature: Sampling temperature.  Defaults to settings value.

    Returns:
        A ``guidance.models.OpenAI`` backed by the local proxy.

    Raises:
        ImportError: If ``guidance`` is not installed.
    """
    _check_available()
    from guidance.models import OpenAI

    settings = get_settings()

    if model is None:
        model = settings.default_model
    if temperature is None:
        temperature = settings.default_temperature

    return OpenAI(
        model=model,
        api_key=settings.api_key,
        base_url=settings.litellm_base_url,
    )


def create_guidance_model(
    model: str | None = None,
    temperature: float | None = None,
    **kwargs,
):
    """Create a guidance ``OpenAI`` model with custom kwargs (uncached).

    Use this when you need to pass extra arguments to the underlying
    ``openai.OpenAI`` constructor (e.g. ``organization``, ``timeout``).

    Args:
        model: Model name.  Defaults to ``DEFAULT_MODEL``.
        temperature: Sampling temperature.
        **kwargs: Additional kwargs forwarded to ``guidance.models.OpenAI()``.

    Returns:
        A ``guidance.models.OpenAI`` backed by the local proxy.
    """
    _check_available()
    from guidance.models import OpenAI

    settings = get_settings()

    if model is None:
        model = settings.default_model
    if temperature is None:
        temperature = settings.default_temperature

    return OpenAI(
        model=model,
        api_key=settings.api_key,
        base_url=settings.litellm_base_url,
        **kwargs,
    )
