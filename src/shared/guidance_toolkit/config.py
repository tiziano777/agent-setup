"""Configuration for the guidance-ai structured generation toolkit.

Provides :class:`GuidanceSettings` dataclass and :func:`setup_guidance` to
configure the guidance runtime to use the project's LiteLLM proxy.

All guidance LLM calls are routed through the LiteLLM proxy -- never
directly to a provider.

Usage::

    from src.shared.guidance_toolkit.config import setup_guidance

    setup_guidance()  # auto-configures from env vars
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ── Guarded import ────────────────────────────────────────────────────

try:
    import guidance  # noqa: F401

    _AVAILABLE = True
except ImportError:
    _AVAILABLE = False

_INSTALL_HINT = "Install guidance: pip install -e '.[guidance]'"


def _check_available() -> None:
    if not _AVAILABLE:
        raise ImportError(_INSTALL_HINT)


# ── Settings ──────────────────────────────────────────────────────────


@dataclass
class GuidanceSettings:
    """Central configuration for the guidance-ai integration.

    Reads defaults from environment variables where appropriate.
    """

    # -- LLM (routes through LiteLLM proxy) --
    litellm_base_url: str = field(
        default_factory=lambda: os.getenv("LITELLM_BASE_URL", "http://localhost:4000/v1"),
    )
    default_model: str = field(
        default_factory=lambda: os.getenv("DEFAULT_MODEL", "llm"),
    )
    api_key: str = field(
        default_factory=lambda: os.getenv("OPENAI_API_KEY", "sk-not-needed"),
    )

    # -- Generation defaults --
    default_temperature: float = 0.7
    default_max_tokens: int = 2048


# ── Setup ─────────────────────────────────────────────────────────────

_CONFIGURED = False
_SETTINGS: GuidanceSettings | None = None


def setup_guidance(settings: GuidanceSettings | None = None) -> GuidanceSettings:
    """Configure guidance to use the project's LiteLLM proxy (idempotent).

    Args:
        settings: Configuration dataclass.  Uses defaults when *None*.

    Returns:
        The active settings instance.
    """
    global _CONFIGURED, _SETTINGS
    _check_available()

    if settings is None:
        settings = GuidanceSettings()

    _SETTINGS = settings
    _CONFIGURED = True
    logger.info(
        "Guidance configured: model=%s via %s",
        settings.default_model,
        settings.litellm_base_url,
    )
    return settings


def _ensure_configured() -> GuidanceSettings:
    """Auto-configure if not yet done.  Returns the active settings."""
    global _SETTINGS
    if not _CONFIGURED:
        setup_guidance()
    assert _SETTINGS is not None
    return _SETTINGS


def get_settings() -> GuidanceSettings:
    """Return the active settings, configuring if necessary."""
    return _ensure_configured()
