"""Retrieve the N-1 experiment trajectory from PostgreSQL."""

from __future__ import annotations

from typing import Any

from src.agents.autoresearch.db.connector import PostgresConnector
from src.agents.autoresearch.db.repositories import ExperimentRepository
from src.agents.autoresearch.schemas.entities import ExperimentStatus
from src.agents.autoresearch.states.state import AutoresearchState


def query_trajectory(state: AutoresearchState) -> dict[str, Any]:
    """Fetch the last N experiments as the training trajectory.

    Also recomputes best result and parameter importance from the trajectory.
    """
    connector = PostgresConnector()
    repo = ExperimentRepository(connector)

    session_id = state["session_id"]
    experiments = repo.get_trajectory(session_id, n=100)

    trajectory = [exp.to_state_dict() for exp in experiments]

    # Recompute best result
    sweep_config = state.get("sweep_config", {})
    metric_name = sweep_config.get("metric", {}).get("name", "")
    goal = sweep_config.get("metric", {}).get("goal", "maximize")

    best_run_id = state.get("best_run_id")
    best_metric = state.get("best_metric_value")
    best_hp = state.get("best_hyperparams", {})

    completed = [
        e for e in experiments if e.status == ExperimentStatus.COMPLETED
    ]
    for exp in completed:
        val = exp.metrics.get(metric_name)
        if val is None:
            continue
        if best_metric is None:
            best_metric = val
            best_run_id = exp.run_id
            best_hp = exp.hyperparams
        elif goal == "maximize" and val > best_metric:
            best_metric = val
            best_run_id = exp.run_id
            best_hp = exp.hyperparams
        elif goal == "minimize" and val < best_metric:
            best_metric = val
            best_run_id = exp.run_id
            best_hp = exp.hyperparams

    # Crash patterns
    crashed = [e for e in experiments if e.status == ExperimentStatus.CRASHED]
    crash_rate = len(crashed) / len(experiments) if experiments else 0.0
    patterns = state.get("crash_patterns", [])
    if crash_rate > 0:
        patterns = [f"{len(crashed)}/{len(experiments)} experiments crashed"]

    # Simple parameter importance via variance analysis
    importance: dict[str, float] = {}
    if len(completed) >= 3 and metric_name:
        from src.agents.autoresearch.tracking.aggregator import (
            parameter_importance,
        )

        importance = parameter_importance(completed, metric_name)

    return {
        "trajectory": trajectory,
        "best_run_id": best_run_id,
        "best_metric_value": best_metric,
        "best_hyperparams": best_hp,
        "parameter_importance": importance,
        "crash_patterns": patterns,
        "experiments_completed": len(experiments),
    }
