"""Persist learned knowledge to PostgreSQL and optionally Cognee."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage

from src.agents.autoresearch.db.connector import PostgresConnector
from src.agents.autoresearch.db.repositories import (
    KnowledgeRepository,
    SweepSessionRepository,
)
from src.agents.autoresearch.schemas.entities import KnowledgeLearned, SessionStatus
from src.agents.autoresearch.states.state import AutoresearchState


def persist_knowledge(state: AutoresearchState) -> dict[str, Any]:
    """Save sweep learnings to PostgreSQL and mark session complete.

    Optionally writes to Cognee knowledge graph for semantic retrieval.
    """
    connector = PostgresConnector()
    knowledge_repo = KnowledgeRepository(connector)
    session_repo = SweepSessionRepository(connector)

    session_id = state["session_id"]
    sweep_config = state.get("sweep_config", {})
    metric_name = sweep_config.get("metric", {}).get("name", "")

    # Save knowledge entry
    entry = KnowledgeLearned(
        sweep_name=sweep_config.get("name", ""),
        base_setup=str(sweep_config.get("base_setup", "")),
        metric_name=metric_name,
        best_config=state.get("best_hyperparams", {}),
        best_metric_value=state.get("best_metric_value"),
        parameter_importance=state.get("parameter_importance", {}),
        crash_patterns=state.get("crash_patterns", []),
        total_experiments=state.get("experiments_completed", 0),
    )
    knowledge_repo.save(entry)

    # Mark session complete
    session = session_repo.get(session_id)
    if session:
        session.status = SessionStatus.COMPLETED.value
        session.best_run_id = state.get("best_run_id")
        session.best_metric_value = state.get("best_metric_value")
        session.best_hyperparams = state.get("best_hyperparams", {})
        session.total_experiments = state.get("experiments_completed", 0)
        session_repo.update(session)

    # Try Cognee integration
    try:
        from src.shared.cognee_toolkit.memory import CogneeMemory

        memory = CogneeMemory()
        knowledge_text = (
            f"Sweep '{entry.sweep_name}' on setup '{entry.base_setup}': "
            f"best {metric_name}={entry.best_metric_value} "
            f"with config {entry.best_config}. "
            f"Parameter importance: {entry.parameter_importance}. "
            f"Total experiments: {entry.total_experiments}."
        )
        memory.add_and_cognify_sync(knowledge_text, dataset_name="autoresearch")
    except Exception:
        pass  # Cognee optional

    return {
        "messages": [
            AIMessage(
                content=f"Knowledge persisted for sweep "
                f"'{sweep_config.get('name', '')}'. "
                f"Best {metric_name}={state.get('best_metric_value')}."
            ),
        ],
    }
