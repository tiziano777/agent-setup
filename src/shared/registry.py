"""Agent registry for dynamic agent loading and discovery.

The registry discovers agent modules under src/agents/ and provides
methods to look them up by name, list available agents, and retrieve
their compiled graphs or functional workflows.
"""

from __future__ import annotations

import importlib
import pkgutil
from dataclasses import dataclass
from typing import Any


@dataclass
class AgentEntry:
    """Metadata about a registered agent."""

    name: str
    module_path: str
    graph: Any = None
    workflow: Any = None


class AgentRegistry:
    """Registry that discovers and loads agent modules."""

    def __init__(self):
        self._agents: dict[str, AgentEntry] = {}

    def discover(self, package_path: str = "src.agents") -> None:
        """Auto-discover agent modules under the given package.

        Scans for sub-packages (excluding _template) that expose
        a `graph` and/or `workflow` attribute in their __init__.py.
        """
        package = importlib.import_module(package_path)
        for _importer, modname, ispkg in pkgutil.iter_modules(
            package.__path__, prefix=package.__name__ + "."
        ):
            if not ispkg or modname.endswith("_template"):
                continue

            try:
                mod = importlib.import_module(modname)
                entry = AgentEntry(
                    name=modname.split(".")[-1],
                    module_path=modname,
                    graph=getattr(mod, "graph", None),
                    workflow=getattr(mod, "workflow", None),
                )
                self._agents[entry.name] = entry
            except Exception as exc:
                print(f"Warning: could not load agent '{modname}': {exc}")

    def get(self, name: str) -> AgentEntry | None:
        """Get a registered agent by name."""
        return self._agents.get(name)

    def list_agents(self) -> list[str]:
        """Return names of all registered agents."""
        return list(self._agents.keys())

    def get_graph(self, name: str) -> Any:
        """Get the compiled graph for an agent."""
        entry = self.get(name)
        if entry is None:
            raise KeyError(f"Agent '{name}' not found in registry")
        if entry.graph is None:
            raise ValueError(f"Agent '{name}' does not expose a Graph API graph")
        return entry.graph

    def get_workflow(self, name: str) -> Any:
        """Get the functional workflow for an agent."""
        entry = self.get(name)
        if entry is None:
            raise KeyError(f"Agent '{name}' not found in registry")
        if entry.workflow is None:
            raise ValueError(f"Agent '{name}' does not expose a Functional API workflow")
        return entry.workflow


# Module-level singleton
registry = AgentRegistry()
