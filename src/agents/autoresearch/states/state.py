"""LangGraph state definition for all autoresearch pipeline variants."""

from __future__ import annotations

from typing import Annotated, Any, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


class AutoresearchState(TypedDict, total=False):
    """Shared state flowing through all autoresearch pipeline variants.

    Uses ``total=False`` so nodes can return partial updates.
    The ``messages`` field uses the standard LangGraph ``add_messages`` reducer.
    """

    # Core messages channel (LangGraph convention)
    messages: Annotated[list[AnyMessage], add_messages]

    # Session identity
    session_id: str
    sweep_config: dict[str, Any]

    # Wave control
    wave_number: int
    wave_configs: list[dict[str, Any]]
    wave_results: list[dict[str, Any]]

    # Trajectory (N-1 previous experiments for data-driven decisions)
    trajectory: list[dict[str, Any]]

    # Budget tracking
    experiments_completed: int
    experiments_remaining: int
    wall_time_used_hours: float

    # Best result
    best_run_id: str | None
    best_metric_value: float | None
    best_hyperparams: dict[str, Any]

    # Analysis
    parameter_importance: dict[str, float]
    crash_patterns: list[str]
    blacklist: list[dict[str, Any]]

    # Loop control
    loop_action: str  # next_wave | stop | pause | request_diagnostics
    loop_reason: str
    should_continue: bool

    # Escalation
    escalation_stage: int
    active_search_space: dict[str, Any]

    # Knowledge
    similar_experiments: list[dict[str, Any]]
    prior_knowledge: list[dict[str, Any]]

    # Token budget
    token_usage: dict[str, int]

    # Grid-specific
    grid_configs: list[dict[str, Any]]
    grid_offset: int
