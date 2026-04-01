"""Pydantic I/O schemas for autoresearch agent invocation."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AutoresearchInput(BaseModel):
    """Input schema for invoking the autoresearch agent."""

    sweep_config_path: str | None = Field(
        default=None,
        description="Path to a YAML sweep config file.",
    )
    sweep_config: dict[str, Any] | None = Field(
        default=None,
        description="Inline sweep config (alternative to file path).",
    )
    session_id: str | None = Field(
        default=None,
        description="Resume an existing session by ID.",
    )
    strategy_override: str | None = Field(
        default=None,
        description="Override strategy type: 'agent', 'random', or 'grid'.",
    )


class AutoresearchOutput(BaseModel):
    """Output schema returned after a sweep completes."""

    session_id: str
    sweep_name: str
    strategy: str
    experiments_completed: int
    best_run_id: str | None = None
    best_metric_value: float | None = None
    best_hyperparams: dict[str, Any] = Field(default_factory=dict)
    parameter_importance: dict[str, float] = Field(default_factory=dict)
    summary: str = ""
