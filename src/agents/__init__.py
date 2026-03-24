"""Agent package.

Provides auto-discovery of all agent modules via the shared registry.

    from src.agents import discover_agents
    agents = discover_agents()
"""

from src.shared.registry import registry


def discover_agents() -> list[str]:
    """Discover and register all agent modules. Returns list of agent names."""
    registry.discover("src.agents")
    return registry.list_agents()
