"""__AGENT_NAME__: Preparation & exposure module for REST API.

Validates env, loads config, and exposes the compiled graph for serve.py.
"""

import logging
from typing import NamedTuple

from src.agents._template.agent import graph
from src.agents._template.config.settings import settings
from src.shared.env_validation import validate_env
from src.shared.tracing import setup_tracing

logger = logging.getLogger(__name__)


class AgentMetadata(NamedTuple):
    """Metadata for REST API exposure."""

    name: str
    description: str
    version: str
    graph_obj: object


def prepare() -> AgentMetadata:
    """Prepare the agent for REST API deployment.

    Validates environment, loads config, initializes tracing,
    and returns metadata for serve.py.

    Returns:
        AgentMetadata with graph and metadata.
    """
    env_result = validate_env()
    if env_result["errors"]:
        raise RuntimeError(
            f"Env validation failed: {env_result['errors']}"
        )

    setup_tracing()

    return AgentMetadata(
        name="__AGENT_NAME__",
        description="__AGENT_DESCRIPTION__",
        version="0.1.0",
        graph_obj=graph,
    )
