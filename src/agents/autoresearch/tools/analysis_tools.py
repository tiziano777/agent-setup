"""Tools for analysis and reporting."""

from __future__ import annotations

import json

from langchain_core.tools import tool

from src.agents.autoresearch.db.connector import PostgresConnector
from src.agents.autoresearch.db.repositories import ExperimentRepository
from src.agents.autoresearch.tracking.aggregator import parameter_importance
from src.agents.autoresearch.tracking.reporter import generate_report


@tool
def compute_parameter_importance(session_id: str, metric_name: str) -> str:
    """Compute parameter importance scores via variance analysis.

    Args:
        session_id: The sweep session ID.
        metric_name: Name of the metric to analyze.
    """
    connector = PostgresConnector()
    repo = ExperimentRepository(connector)
    experiments = repo.list_by_session(session_id)
    importance = parameter_importance(experiments, metric_name)
    return json.dumps(importance, indent=2)


@tool
def generate_sweep_report(
    session_id: str, metric_name: str, goal: str = "maximize"
) -> str:
    """Generate a full markdown sweep report.

    Args:
        session_id: The sweep session ID.
        metric_name: Name of the metric to optimize.
        goal: 'maximize' or 'minimize'.
    """
    connector = PostgresConnector()
    repo = ExperimentRepository(connector)
    experiments = repo.list_by_session(session_id)
    sweep_name = experiments[0].sweep_name if experiments else "Unknown"
    return generate_report(
        experiments,
        metric_name=metric_name,
        goal=goal,
        sweep_name=sweep_name,
    )
