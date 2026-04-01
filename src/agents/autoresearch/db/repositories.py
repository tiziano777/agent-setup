"""Repository classes for autoresearch PostgreSQL tables.

Each repository wraps a single table in the ``autoresearch`` schema and
exposes typed CRUD methods using the shared ``PostgresConnector``.
"""

from __future__ import annotations

import json
from typing import Any

from src.agents.autoresearch.db.connector import PostgresConnector
from src.agents.autoresearch.schemas.entities import (
    AgentDecision,
    Checkpoint,
    Experiment,
    ExperimentStatus,
    KnowledgeLearned,
    SweepSession,
)

# ---------------------------------------------------------------------------
# SweepSessionRepository
# ---------------------------------------------------------------------------

class SweepSessionRepository:
    """CRUD for ``autoresearch.sweep_sessions``."""

    def __init__(self, connector: PostgresConnector) -> None:
        self._db = connector

    def create(self, session: SweepSession) -> None:
        d = session.to_db_dict()
        cols = ", ".join(d.keys())
        placeholders = ", ".join(["%s"] * len(d))
        self._db.execute(
            f"INSERT INTO autoresearch.sweep_sessions ({cols}) VALUES ({placeholders})",
            tuple(d.values()),
        )

    def get(self, session_id: str) -> SweepSession | None:
        rows, cols = self._db.execute_returning(
            "SELECT * FROM autoresearch.sweep_sessions WHERE session_id = %s",
            (session_id,),
        )
        if not rows:
            return None
        return SweepSession.from_db_row(rows[0], cols)

    def update(self, session: SweepSession) -> None:
        d = session.to_db_dict()
        sets = ", ".join(f"{k} = %s" for k in d if k != "session_id")
        vals = [v for k, v in d.items() if k != "session_id"]
        vals.append(d["session_id"])
        self._db.execute(
            f"UPDATE autoresearch.sweep_sessions SET {sets} WHERE session_id = %s",
            tuple(vals),
        )

    def list_active(self) -> list[SweepSession]:
        rows, cols = self._db.execute_returning(
            "SELECT * FROM autoresearch.sweep_sessions WHERE status = 'active' "
            "ORDER BY created_at DESC",
        )
        return [SweepSession.from_db_row(r, cols) for r in rows]


# ---------------------------------------------------------------------------
# ExperimentRepository
# ---------------------------------------------------------------------------

class ExperimentRepository:
    """CRUD for ``autoresearch.experiments``."""

    def __init__(self, connector: PostgresConnector) -> None:
        self._db = connector

    def save(self, experiment: Experiment) -> None:
        d = experiment.to_db_dict()
        cols = ", ".join(d.keys())
        placeholders = ", ".join(["%s"] * len(d))
        conflict_sets = ", ".join(
            f"{k} = EXCLUDED.{k}" for k in d if k != "run_id"
        )
        self._db.execute(
            f"INSERT INTO autoresearch.experiments ({cols}) VALUES ({placeholders}) "
            f"ON CONFLICT (run_id) DO UPDATE SET {conflict_sets}",
            tuple(d.values()),
        )

    def get(self, run_id: str) -> Experiment | None:
        rows, cols = self._db.execute_returning(
            "SELECT * FROM autoresearch.experiments WHERE run_id = %s",
            (run_id,),
        )
        if not rows:
            return None
        return Experiment.from_db_row(rows[0], cols)

    def list_by_session(
        self,
        session_id: str,
        status: ExperimentStatus | None = None,
        limit: int | None = None,
    ) -> list[Experiment]:
        clauses = ["session_id = %s"]
        params: list[Any] = [session_id]
        if status is not None:
            clauses.append("status = %s")
            params.append(status.value)
        query = (
            f"SELECT * FROM autoresearch.experiments "
            f"WHERE {' AND '.join(clauses)} ORDER BY created_at DESC"
        )
        if limit is not None:
            query += f" LIMIT {limit}"
        rows, cols = self._db.execute_returning(query, tuple(params))
        return [Experiment.from_db_row(r, cols) for r in rows]

    def list_by_sweep(
        self,
        sweep_name: str,
        status: ExperimentStatus | None = None,
        limit: int | None = None,
    ) -> list[Experiment]:
        clauses = ["sweep_name = %s"]
        params: list[Any] = [sweep_name]
        if status is not None:
            clauses.append("status = %s")
            params.append(status.value)
        query = (
            f"SELECT * FROM autoresearch.experiments "
            f"WHERE {' AND '.join(clauses)} ORDER BY created_at DESC"
        )
        if limit is not None:
            query += f" LIMIT {limit}"
        rows, cols = self._db.execute_returning(query, tuple(params))
        return [Experiment.from_db_row(r, cols) for r in rows]

    def get_best(
        self,
        session_id: str,
        metric_name: str,
        goal: str = "maximize",
        top_k: int = 1,
    ) -> list[Experiment]:
        """Return top-k experiments by a specific metric within a session."""
        experiments = self.list_by_session(
            session_id, status=ExperimentStatus.COMPLETED
        )
        scored: list[tuple[float, Experiment]] = []
        for exp in experiments:
            val = exp.metrics.get(metric_name)
            if val is not None:
                scored.append((val, exp))
        scored.sort(key=lambda t: t[0], reverse=(goal == "maximize"))
        return [e for _, e in scored[:top_k]]

    def update_status(
        self,
        run_id: str,
        status: ExperimentStatus,
        metrics: dict[str, float] | None = None,
        wall_time_seconds: float | None = None,
    ) -> None:
        sets = ["status = %s"]
        params: list[Any] = [status.value]
        if metrics is not None:
            sets.append("metrics = %s")
            params.append(json.dumps(metrics))
        if wall_time_seconds is not None:
            sets.append("wall_time_seconds = %s")
            params.append(wall_time_seconds)
        params.append(run_id)
        self._db.execute(
            f"UPDATE autoresearch.experiments SET {', '.join(sets)} WHERE run_id = %s",
            tuple(params),
        )

    def get_trajectory(self, session_id: str, n: int = 50) -> list[Experiment]:
        """Return the last ``n`` experiments chronologically (oldest first)."""
        rows, cols = self._db.execute_returning(
            "SELECT * FROM ("
            "  SELECT * FROM autoresearch.experiments "
            "  WHERE session_id = %s ORDER BY created_at DESC LIMIT %s"
            ") sub ORDER BY created_at ASC",
            (session_id, n),
        )
        return [Experiment.from_db_row(r, cols) for r in rows]

    def count(self, session_id: str | None = None) -> int:
        if session_id:
            rows = self._db.execute(
                "SELECT COUNT(*) FROM autoresearch.experiments WHERE session_id = %s",
                (session_id,),
            )
        else:
            rows = self._db.execute("SELECT COUNT(*) FROM autoresearch.experiments")
        return rows[0][0] if rows else 0


# ---------------------------------------------------------------------------
# AgentDecisionRepository
# ---------------------------------------------------------------------------

class AgentDecisionRepository:
    """CRUD for ``autoresearch.agent_decisions``."""

    def __init__(self, connector: PostgresConnector) -> None:
        self._db = connector

    def save(self, decision: AgentDecision) -> None:
        d = decision.to_db_dict()
        cols = ", ".join(d.keys())
        placeholders = ", ".join(["%s"] * len(d))
        self._db.execute(
            f"INSERT INTO autoresearch.agent_decisions ({cols}) VALUES ({placeholders})",
            tuple(d.values()),
        )

    def list_by_session(
        self,
        session_id: str,
        agent_role: str | None = None,
        limit: int | None = None,
    ) -> list[AgentDecision]:
        clauses = ["session_id = %s"]
        params: list[Any] = [session_id]
        if agent_role is not None:
            clauses.append("agent_role = %s")
            params.append(agent_role)
        query = (
            f"SELECT * FROM autoresearch.agent_decisions "
            f"WHERE {' AND '.join(clauses)} ORDER BY created_at DESC"
        )
        if limit is not None:
            query += f" LIMIT {limit}"
        rows, cols = self._db.execute_returning(query, tuple(params))
        return [AgentDecision.from_db_row(r, cols) for r in rows]


# ---------------------------------------------------------------------------
# KnowledgeRepository
# ---------------------------------------------------------------------------

class KnowledgeRepository:
    """CRUD for ``autoresearch.knowledge``."""

    def __init__(self, connector: PostgresConnector) -> None:
        self._db = connector

    def save(self, entry: KnowledgeLearned) -> None:
        d = entry.to_db_dict()
        cols = ", ".join(d.keys())
        placeholders = ", ".join(["%s"] * len(d))
        self._db.execute(
            f"INSERT INTO autoresearch.knowledge ({cols}) VALUES ({placeholders})",
            tuple(d.values()),
        )

    def find_relevant(
        self, base_setup: str, metric_name: str
    ) -> list[KnowledgeLearned]:
        rows, cols = self._db.execute_returning(
            "SELECT * FROM autoresearch.knowledge "
            "WHERE base_setup = %s AND metric_name = %s "
            "ORDER BY created_at DESC",
            (base_setup, metric_name),
        )
        return [KnowledgeLearned.from_db_row(r, cols) for r in rows]


# ---------------------------------------------------------------------------
# CheckpointRepository
# ---------------------------------------------------------------------------

class CheckpointRepository:
    """CRUD for ``autoresearch.checkpoints``."""

    def __init__(self, connector: PostgresConnector) -> None:
        self._db = connector

    def save(self, checkpoint: Checkpoint) -> None:
        d = checkpoint.to_db_dict()
        cols = ", ".join(d.keys())
        placeholders = ", ".join(["%s"] * len(d))
        self._db.execute(
            f"INSERT INTO autoresearch.checkpoints ({cols}) VALUES ({placeholders})",
            tuple(d.values()),
        )

    def get_latest(self, session_id: str) -> Checkpoint | None:
        rows, cols = self._db.execute_returning(
            "SELECT * FROM autoresearch.checkpoints "
            "WHERE session_id = %s ORDER BY created_at DESC LIMIT 1",
            (session_id,),
        )
        if not rows:
            return None
        return Checkpoint.from_db_row(rows[0], cols)
