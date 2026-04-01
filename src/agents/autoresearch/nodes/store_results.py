"""Store wave results to PostgreSQL and update session counters."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage

from src.agents.autoresearch.db.connector import PostgresConnector
from src.agents.autoresearch.db.repositories import (
    ExperimentRepository,
    SweepSessionRepository,
)
from src.agents.autoresearch.schemas.entities import Experiment, ExperimentStatus
from src.agents.autoresearch.states.state import AutoresearchState


def store_results(state: AutoresearchState) -> dict[str, Any]:
    """Persist wave results to the experiments table and update session."""
    connector = PostgresConnector()
    exp_repo = ExperimentRepository(connector)
    session_repo = SweepSessionRepository(connector)

    session_id = state["session_id"]
    wave_results = state.get("wave_results", [])
    sweep_config = state.get("sweep_config", {})

    saved_count = 0
    for result in wave_results:
        exp = Experiment(
            run_id=result.get("run_id", ""),
            session_id=session_id,
            sweep_name=sweep_config.get("name", ""),
            base_setup=str(sweep_config.get("base_setup", "")),
            hyperparams=result.get("hyperparams", {}),
            status=ExperimentStatus(result.get("status", "completed")),
            wave_number=result.get("wave_number"),
            metrics=result.get("metrics", {}),
            wall_time_seconds=result.get("wall_time_seconds"),
            agent_reasoning=result.get("agent_reasoning"),
        )
        exp_repo.save(exp)
        saved_count += 1

    # Update session counters
    session = session_repo.get(session_id)
    if session:
        session.total_experiments += saved_count

        # Update best
        metric_name = sweep_config.get("metric", {}).get("name", "")
        goal = sweep_config.get("metric", {}).get("goal", "maximize")
        best = exp_repo.get_best(session_id, metric_name, goal, top_k=1)
        if best:
            session.best_run_id = best[0].run_id
            session.best_metric_value = best[0].metrics.get(metric_name)
            session.best_hyperparams = best[0].hyperparams

        session_repo.update(session)

    total = state.get("experiments_completed", 0) + saved_count
    max_exp = sweep_config.get("budget", {}).get("max_experiments", 100)

    return {
        "experiments_completed": total,
        "experiments_remaining": max(0, max_exp - total),
        "messages": [
            AIMessage(content=f"Stored {saved_count} results. Total: {total}/{max_exp}."),
        ],
    }
