"""Escalation tracker — progressive search space expansion.

Tracks which escalation stage the sweep is in and decides when to advance
based on plateau detection (no improvement after patience threshold).
"""

from __future__ import annotations

from src.agents.autoresearch.config.models import (
    EscalationConfig,
    ParameterSpec,
    SweepConfig,
)
from src.agents.autoresearch.schemas.entities import Experiment, ExperimentStatus


class EscalationTracker:
    """Tracks escalation stage and decides when to expand search space."""

    def __init__(self, config: SweepConfig) -> None:
        self._config: EscalationConfig = config.escalation
        self._full_space = config.search_space
        self._metric_name = config.metric.name
        self._goal = config.metric.goal.value
        self._current_stage_index = 0
        self._best_metric: float | None = None
        self._patience_counter = 0

    @property
    def enabled(self) -> bool:
        return self._config.enabled and len(self._config.stages) > 0

    @property
    def current_stage_index(self) -> int:
        return self._current_stage_index

    @property
    def current_stage_name(self) -> str:
        if not self.enabled:
            return "all"
        return self._config.stages[self._current_stage_index].name

    def active_search_space(self) -> dict[str, ParameterSpec]:
        """Return only the parameters active in the current + previous stages."""
        if not self.enabled:
            return self._full_space
        active_params: set[str] = set()
        for i in range(self._current_stage_index + 1):
            if i < len(self._config.stages):
                active_params.update(self._config.stages[i].parameters)
        return {k: v for k, v in self._full_space.items() if k in active_params}

    def update_after_wave(self, entries: list[Experiment]) -> bool:
        """Update state after a wave completes. Returns True if escalated."""
        if not self.enabled:
            return False

        stage = self._config.stages[self._current_stage_index]
        completed = [
            e for e in entries if e.status == ExperimentStatus.COMPLETED
        ]
        if not completed:
            return False

        for entry in completed:
            val = entry.metrics.get(self._metric_name)
            if val is None:
                continue
            improved = False
            if self._best_metric is None:
                improved = True
            elif (
                self._goal == "maximize"
                and val > self._best_metric * (1 + stage.plateau_threshold)
            ):
                improved = True
            elif (
                self._goal == "minimize"
                and val < self._best_metric * (1 - stage.plateau_threshold)
            ):
                improved = True

            if improved:
                self._best_metric = val
                self._patience_counter = 0

        self._patience_counter += len(completed)

        if self._patience_counter >= stage.plateau_patience:
            return self._escalate()
        return False

    def _escalate(self) -> bool:
        """Move to the next stage. Returns True if successfully escalated."""
        if self._current_stage_index < len(self._config.stages) - 1:
            self._current_stage_index += 1
            self._patience_counter = 0
            return True
        return False
