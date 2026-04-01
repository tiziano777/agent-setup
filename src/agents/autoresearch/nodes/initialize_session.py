"""Initialize (or resume) a sweep session, loading prior knowledge."""

from __future__ import annotations

import uuid
from typing import Any

from langchain_core.messages import AIMessage

from src.agents.autoresearch.config.models import SweepConfig
from src.agents.autoresearch.db.connector import PostgresConnector
from src.agents.autoresearch.db.repositories import (
    KnowledgeRepository,
    SweepSessionRepository,
)
from src.agents.autoresearch.schemas.entities import SweepSession
from src.agents.autoresearch.states.state import AutoresearchState


def _get_connector() -> PostgresConnector:
    connector = PostgresConnector()
    connector.apply_schema()
    return connector


def initialize_session(state: AutoresearchState) -> dict[str, Any]:
    """Create or resume a sweep session and load prior knowledge."""
    connector = _get_connector()
    session_repo = SweepSessionRepository(connector)
    knowledge_repo = KnowledgeRepository(connector)

    session_id = state.get("session_id", "")
    sweep_config_dict = state.get("sweep_config", {})

    if session_id:
        session = session_repo.get(session_id)
        if session is None:
            raise ValueError(f"Session {session_id} not found")
    else:
        config = SweepConfig.model_validate(sweep_config_dict)
        session_id = uuid.uuid4().hex[:16]
        session = SweepSession(
            session_id=session_id,
            sweep_name=config.name,
            config_json=sweep_config_dict,
            strategy_type=config.strategy.type.value,
            budget_max_experiments=config.budget.max_experiments,
            budget_max_wall_time_hours=config.budget.max_wall_time_hours,
        )
        session_repo.create(session)

    config_data = session.config_json
    config = SweepConfig.model_validate(config_data)

    prior = knowledge_repo.find_relevant(
        str(config.base_setup), config.metric.name
    )
    prior_dicts = []
    for k in prior:
        prior_dicts.append({
            "sweep_name": k.sweep_name,
            "best_config": k.best_config,
            "best_metric_value": k.best_metric_value,
            "parameter_importance": k.parameter_importance,
            "crash_patterns": k.crash_patterns,
        })

    search_space = {
        name: spec.model_dump(mode="json")
        for name, spec in config.search_space.items()
    }

    return {
        "session_id": session_id,
        "sweep_config": config_data,
        "wave_number": 0,
        "experiments_completed": session.total_experiments,
        "experiments_remaining": (
            config.budget.max_experiments - session.total_experiments
        ),
        "wall_time_used_hours": session.wall_time_used_s / 3600.0,
        "best_run_id": session.best_run_id,
        "best_metric_value": session.best_metric_value,
        "best_hyperparams": session.best_hyperparams,
        "escalation_stage": session.escalation_stage,
        "active_search_space": search_space,
        "prior_knowledge": prior_dicts,
        "parameter_importance": {},
        "crash_patterns": [],
        "blacklist": [],
        "should_continue": True,
        "loop_action": "next_wave",
        "loop_reason": "",
        "token_usage": {"prompt_tokens": 0, "completion_tokens": 0, "calls": 0},
        "messages": [
            AIMessage(
                content=f"Sweep session '{session.sweep_name}' initialized "
                f"(id={session_id}, strategy={session.strategy_type})."
            ),
        ],
    }
