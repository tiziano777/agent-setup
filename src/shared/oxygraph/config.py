"""Configuration for the Oxigraph triple store."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class OxigraphSettings:
    """Connection and runtime configuration for Oxigraph."""

    base_url: str = field(
        default_factory=lambda: os.getenv("OXIGRAPH_URL", "http://localhost:7878")
    )
    default_graph: str = field(default_factory=lambda: os.getenv("OXIGRAPH_DEFAULT_GRAPH", ""))
    timeout: int = field(default_factory=lambda: int(os.getenv("OXIGRAPH_TIMEOUT", "10")))
    max_retries: int = field(default_factory=lambda: int(os.getenv("OXIGRAPH_MAX_RETRIES", "2")))
