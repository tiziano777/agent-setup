"""Configuration for the Docker sandbox.

Provides :class:`SandboxSettings` dataclass with configurable resource
limits and container parameters.  All fields read from environment
variables with safe defaults.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ── Guarded import ────────────────────────────────────────────────────

try:
    import docker  # noqa: F401

    _AVAILABLE = True
except ImportError:
    _AVAILABLE = False

_INSTALL_HINT = "Install docker: pip install -e '.[sandbox]'"


def _check_available() -> None:
    if not _AVAILABLE:
        raise ImportError(_INSTALL_HINT)


# ── Settings ──────────────────────────────────────────────────────────


@dataclass
class SandboxSettings:
    """Container and resource configuration for the Docker sandbox."""

    # Docker image
    image: str = field(
        default_factory=lambda: os.getenv("SANDBOX_IMAGE", "python:3.11-slim"),
    )

    # Execution timeout (seconds)
    timeout: int = field(
        default_factory=lambda: int(os.getenv("SANDBOX_TIMEOUT", "30")),
    )

    # Memory limit (Docker format: "256m", "1g")
    mem_limit: str = field(
        default_factory=lambda: os.getenv("SANDBOX_MEM_LIMIT", "256m"),
    )

    # CPU limit as a float (0.5 = half a core)
    cpu_limit: float = field(
        default_factory=lambda: float(os.getenv("SANDBOX_CPU_LIMIT", "0.5")),
    )

    # Workspace tmpfs size (Docker tmpfs format: "128M")
    workspace_size: str = field(
        default_factory=lambda: os.getenv("SANDBOX_WORKSPACE_SIZE", "128M"),
    )

    # Network mode: "none" for full isolation, "bridge" to allow network
    network_mode: str = field(
        default_factory=lambda: os.getenv("SANDBOX_NETWORK", "none"),
    )

    # PID limit (fork bomb prevention)
    pids_limit: int = 64

    # Container user
    user: str = "nobody"

    # Maximum output length in characters returned to the agent
    max_output_chars: int = 10_000
