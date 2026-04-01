"""Dual-purpose entity dataclasses for PostgreSQL storage and LangGraph state.

Each dataclass maps 1:1 to a table in the ``autoresearch`` schema and provides
``to_db_dict()`` / ``from_db_row()`` for psycopg3 serialization, while also
serving as structured payloads within the LangGraph ``AutoresearchState``.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return uuid.uuid4().hex[:16]


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ExperimentStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    CRASHED = "crashed"
    CANCELLED = "cancelled"


class SessionStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class StrategyType(str, Enum):
    AGENT = "agent"
    RANDOM = "random"
    GRID = "grid"


# ---------------------------------------------------------------------------
# SweepSession
# ---------------------------------------------------------------------------

@dataclass
class SweepSession:
    """A sweep session groups a set of experiments under one configuration."""

    session_id: str = field(default_factory=_new_id)
    sweep_name: str = ""
    config_json: dict[str, Any] = field(default_factory=dict)
    strategy_type: str = "agent"
    status: str = "active"
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)
    wall_time_used_s: float = 0.0
    escalation_stage: int = 0
    total_experiments: int = 0
    budget_max_experiments: int = 100
    budget_max_wall_time_hours: float = 8.0
    best_run_id: str | None = None
    best_metric_value: float | None = None
    best_hyperparams: dict[str, Any] = field(default_factory=dict)

    def to_db_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "sweep_name": self.sweep_name,
            "config_json": json.dumps(self.config_json),
            "strategy_type": self.strategy_type,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "wall_time_used_s": self.wall_time_used_s,
            "escalation_stage": self.escalation_stage,
            "total_experiments": self.total_experiments,
            "budget_max_experiments": self.budget_max_experiments,
            "budget_max_wall_time_hours": self.budget_max_wall_time_hours,
            "best_run_id": self.best_run_id,
            "best_metric_value": self.best_metric_value,
            "best_hyperparams": json.dumps(self.best_hyperparams),
        }

    @classmethod
    def from_db_row(cls, row: tuple, columns: list[str]) -> SweepSession:
        d = dict(zip(columns, row))
        return cls(
            session_id=d["session_id"],
            sweep_name=d["sweep_name"],
            config_json=(
                json.loads(d["config_json"])
                if isinstance(d["config_json"], str)
                else d.get("config_json", {})
            ),
            strategy_type=d["strategy_type"],
            status=d["status"],
            created_at=str(d.get("created_at", "")),
            updated_at=str(d.get("updated_at", "")),
            wall_time_used_s=d.get("wall_time_used_s", 0.0) or 0.0,
            escalation_stage=d.get("escalation_stage", 0) or 0,
            total_experiments=d.get("total_experiments", 0) or 0,
            budget_max_experiments=d["budget_max_experiments"],
            budget_max_wall_time_hours=d["budget_max_wall_time_hours"],
            best_run_id=d.get("best_run_id"),
            best_metric_value=d.get("best_metric_value"),
            best_hyperparams=(
                json.loads(d["best_hyperparams"])
                if isinstance(d.get("best_hyperparams"), str)
                else d.get("best_hyperparams", {})
            ),
        )


# ---------------------------------------------------------------------------
# Experiment
# ---------------------------------------------------------------------------

@dataclass
class Experiment:
    """A single experiment run -- both DB row and LangGraph state element.

    Extends the original ``HistoryEntry`` with session_id, wave_number,
    started_at/completed_at timestamps, runner_backend, and log_path.
    """

    run_id: str = field(default_factory=_new_id)
    session_id: str = ""
    sweep_name: str = ""
    base_setup: str = ""
    hyperparams: dict[str, Any] = field(default_factory=dict)
    status: ExperimentStatus = ExperimentStatus.PENDING
    parent_run_id: str | None = None
    wave_number: int | None = None
    metrics: dict[str, float] = field(default_factory=dict)
    created_at: str = field(default_factory=_now_iso)
    started_at: str | None = None
    completed_at: str | None = None
    wall_time_seconds: float | None = None
    agent_reasoning: str | None = None
    hardware_used: str | None = None
    notes: str | None = None
    code_diff: str | None = None
    runner_backend: str | None = None
    log_path: str | None = None

    def to_db_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "session_id": self.session_id,
            "sweep_name": self.sweep_name,
            "base_setup": self.base_setup,
            "hyperparams": json.dumps(self.hyperparams),
            "status": (
                self.status.value if isinstance(self.status, ExperimentStatus) else self.status
            ),
            "parent_run_id": self.parent_run_id,
            "wave_number": self.wave_number,
            "metrics": json.dumps(self.metrics),
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "wall_time_seconds": self.wall_time_seconds,
            "agent_reasoning": self.agent_reasoning,
            "hardware_used": self.hardware_used,
            "notes": self.notes,
            "code_diff": self.code_diff,
            "runner_backend": self.runner_backend,
            "log_path": self.log_path,
        }

    @classmethod
    def from_db_row(cls, row: tuple, columns: list[str]) -> Experiment:
        d = dict(zip(columns, row))
        return cls(
            run_id=d["run_id"],
            session_id=d["session_id"],
            sweep_name=d["sweep_name"],
            base_setup=d["base_setup"],
            hyperparams=(
                json.loads(d["hyperparams"])
                if isinstance(d["hyperparams"], str)
                else d.get("hyperparams", {})
            ),
            status=ExperimentStatus(d.get("status", "pending")),
            parent_run_id=d.get("parent_run_id"),
            wave_number=d.get("wave_number"),
            metrics=(
                json.loads(d["metrics"])
                if isinstance(d["metrics"], str)
                else d.get("metrics", {})
            ),
            created_at=str(d.get("created_at", "")),
            started_at=str(d["started_at"]) if d.get("started_at") else None,
            completed_at=str(d["completed_at"]) if d.get("completed_at") else None,
            wall_time_seconds=d.get("wall_time_seconds"),
            agent_reasoning=d.get("agent_reasoning"),
            hardware_used=d.get("hardware_used"),
            notes=d.get("notes"),
            code_diff=d.get("code_diff"),
            runner_backend=d.get("runner_backend"),
            log_path=d.get("log_path"),
        )

    def to_state_dict(self) -> dict[str, Any]:
        """Lightweight dict for embedding in LangGraph state trajectory."""
        return {
            "run_id": self.run_id,
            "wave_number": self.wave_number,
            "hyperparams": self.hyperparams,
            "metrics": self.metrics,
            "status": (
                self.status.value if isinstance(self.status, ExperimentStatus) else self.status
            ),
            "wall_time_seconds": self.wall_time_seconds,
            "agent_reasoning": self.agent_reasoning,
        }


# ---------------------------------------------------------------------------
# AgentDecision
# ---------------------------------------------------------------------------

@dataclass
class AgentDecision:
    """Audit trail entry for every LLM agent invocation."""

    decision_id: str = field(default_factory=_new_id)
    session_id: str = ""
    agent_role: str = ""
    decision_type: str = ""
    input_summary: str | None = None
    output_json: dict[str, Any] = field(default_factory=dict)
    reasoning: str | None = None
    wave_number: int | None = None
    token_usage: dict[str, int] = field(default_factory=dict)
    created_at: str = field(default_factory=_now_iso)

    def to_db_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "session_id": self.session_id,
            "agent_role": self.agent_role,
            "decision_type": self.decision_type,
            "input_summary": self.input_summary,
            "output_json": json.dumps(self.output_json),
            "reasoning": self.reasoning,
            "wave_number": self.wave_number,
            "token_usage": json.dumps(self.token_usage),
            "created_at": self.created_at,
        }

    @classmethod
    def from_db_row(cls, row: tuple, columns: list[str]) -> AgentDecision:
        d = dict(zip(columns, row))
        return cls(
            decision_id=d["decision_id"],
            session_id=d["session_id"],
            agent_role=d["agent_role"],
            decision_type=d["decision_type"],
            input_summary=d.get("input_summary"),
            output_json=(
                json.loads(d["output_json"])
                if isinstance(d["output_json"], str)
                else d.get("output_json", {})
            ),
            reasoning=d.get("reasoning"),
            wave_number=d.get("wave_number"),
            token_usage=(
                json.loads(d["token_usage"])
                if isinstance(d["token_usage"], str)
                else d.get("token_usage", {})
            ),
            created_at=str(d.get("created_at", "")),
        )


# ---------------------------------------------------------------------------
# KnowledgeLearned
# ---------------------------------------------------------------------------

@dataclass
class KnowledgeLearned:
    """Persistent knowledge accumulated across sweep sessions."""

    knowledge_id: str = field(default_factory=_new_id)
    sweep_name: str = ""
    base_setup: str = ""
    metric_name: str = ""
    best_config: dict[str, Any] = field(default_factory=dict)
    best_metric_value: float | None = None
    parameter_importance: dict[str, float] = field(default_factory=dict)
    parameter_recommendations: dict[str, str] = field(default_factory=dict)
    crash_patterns: list[str] = field(default_factory=list)
    total_experiments: int = 0
    notes: str = ""
    created_at: str = field(default_factory=_now_iso)

    def to_db_dict(self) -> dict[str, Any]:
        return {
            "knowledge_id": self.knowledge_id,
            "sweep_name": self.sweep_name,
            "base_setup": self.base_setup,
            "metric_name": self.metric_name,
            "best_config": json.dumps(self.best_config),
            "best_metric_value": self.best_metric_value,
            "parameter_importance": json.dumps(self.parameter_importance),
            "parameter_recommendations": json.dumps(self.parameter_recommendations),
            "crash_patterns": json.dumps(self.crash_patterns),
            "total_experiments": self.total_experiments,
            "notes": self.notes,
            "created_at": self.created_at,
        }

    @classmethod
    def from_db_row(cls, row: tuple, columns: list[str]) -> KnowledgeLearned:
        d = dict(zip(columns, row))
        return cls(
            knowledge_id=d["knowledge_id"],
            sweep_name=d["sweep_name"],
            base_setup=d["base_setup"],
            metric_name=d["metric_name"],
            best_config=(
                json.loads(d["best_config"])
                if isinstance(d["best_config"], str)
                else d.get("best_config", {})
            ),
            best_metric_value=d.get("best_metric_value"),
            parameter_importance=(
                json.loads(d["parameter_importance"])
                if isinstance(d["parameter_importance"], str)
                else d.get("parameter_importance", {})
            ),
            parameter_recommendations=(
                json.loads(d["parameter_recommendations"])
                if isinstance(d["parameter_recommendations"], str)
                else d.get("parameter_recommendations", {})
            ),
            crash_patterns=(
                json.loads(d["crash_patterns"])
                if isinstance(d["crash_patterns"], str)
                else d.get("crash_patterns", [])
            ),
            total_experiments=d.get("total_experiments", 0) or 0,
            notes=d.get("notes", ""),
            created_at=str(d.get("created_at", "")),
        )


# ---------------------------------------------------------------------------
# Checkpoint
# ---------------------------------------------------------------------------

@dataclass
class Checkpoint:
    """Session checkpoint for resume/handoff across sessions."""

    checkpoint_id: str = field(default_factory=_new_id)
    session_id: str = ""
    checkpoint_data: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_now_iso)

    def to_db_dict(self) -> dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "session_id": self.session_id,
            "checkpoint_data": json.dumps(self.checkpoint_data),
            "created_at": self.created_at,
        }

    @classmethod
    def from_db_row(cls, row: tuple, columns: list[str]) -> Checkpoint:
        d = dict(zip(columns, row))
        return cls(
            checkpoint_id=d["checkpoint_id"],
            session_id=d["session_id"],
            checkpoint_data=(
                json.loads(d["checkpoint_data"])
                if isinstance(d["checkpoint_data"], str)
                else d.get("checkpoint_data", {})
            ),
            created_at=str(d.get("created_at", "")),
        )
