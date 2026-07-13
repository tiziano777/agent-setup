"""Protocol and spec for pluggable lineage node trackers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Protocol, runtime_checkable

# emit(node_type, payload, edge_type) -> None
EmitFn = Callable[[str, dict[str, Any], str], None]


@runtime_checkable
class NodeTracker(Protocol):
    """Protocol for a tracker that produces a callback object to be injected
    into the wrapped run function.
    """

    node_type: str

    def build_callback(self, ctx: "ExecutionContext", emit: EmitFn) -> Any:
        """Ritorna l'oggetto (es. un TrainerCallback) da iniettare nella
        funzione decorata, già legato alla emit function."""
        ...


@dataclass
class NodeSpec:
    """Specification for a node tracker to be injected into a decorated run."""

    tracker: NodeTracker
    kwarg_name: str
    enabled: bool = True