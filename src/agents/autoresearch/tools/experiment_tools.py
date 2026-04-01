"""Tools for running and querying experiments."""

from __future__ import annotations

import json

from langchain_core.tools import tool

from src.agents.autoresearch.db.connector import PostgresConnector
from src.agents.autoresearch.db.repositories import ExperimentRepository
from src.agents.autoresearch.schemas.entities import ExperimentStatus


@tool
def query_history(
    sweep_name: str, status: str = "completed", limit: int = 20
) -> str:
    """Query experiment history from the database.

    Args:
        sweep_name: Name of the sweep to query.
        status: Filter by status (pending/running/completed/crashed/cancelled).
        limit: Maximum number of results.
    """
    connector = PostgresConnector()
    repo = ExperimentRepository(connector)
    experiments = repo.list_by_sweep(
        sweep_name,
        status=ExperimentStatus(status) if status else None,
        limit=limit,
    )
    return json.dumps([e.to_state_dict() for e in experiments], indent=2)


@tool
def get_trajectory(session_id: str, n: int = 50) -> str:
    """Retrieve the last N experiments as the training trajectory.

    Args:
        session_id: The sweep session ID.
        n: Number of recent experiments to retrieve.
    """
    connector = PostgresConnector()
    repo = ExperimentRepository(connector)
    experiments = repo.get_trajectory(session_id, n=n)
    return json.dumps([e.to_state_dict() for e in experiments], indent=2)


@tool
def get_best_config(
    session_id: str, metric_name: str, goal: str = "maximize", top_k: int = 3
) -> str:
    """Get the best experiment configurations for a metric.

    Args:
        session_id: The sweep session ID.
        metric_name: Name of the metric to optimize.
        goal: 'maximize' or 'minimize'.
        top_k: Number of top results.
    """
    connector = PostgresConnector()
    repo = ExperimentRepository(connector)
    best = repo.get_best(session_id, metric_name, goal, top_k)
    results = []
    for exp in best:
        results.append({
            "run_id": exp.run_id,
            "hyperparams": exp.hyperparams,
            "metrics": exp.metrics,
            "wall_time_seconds": exp.wall_time_seconds,
        })
    return json.dumps(results, indent=2)
