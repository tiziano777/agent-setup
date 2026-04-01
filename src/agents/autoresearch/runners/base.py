"""Abstract base class for experiment runners.

Every runner backend (local, SSH, SLURM, SkyPilot) implements this interface.
The orchestrator interacts exclusively through these methods, keeping the
backend choice transparent.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class RunStatus(str, Enum):
    """Lifecycle states of a single experiment run."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class RunHandle:
    """Opaque handle returned by :meth:`BaseRunner.submit`.

    Runners may attach arbitrary backend-specific data via *extra*.
    """
    run_id: str
    backend: str
    pid: int | None = None
    job_id: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


class BaseRunner(ABC):
    """Abstract runner that can submit, poll, log, and cancel experiment runs."""

    # ---- lifecycle ----

    @abstractmethod
    def submit(
        self,
        run_id: str,
        setup_path: Path,
        hparams: dict[str, Any],
        timeout_seconds: float | None = None,
    ) -> RunHandle:
        """Launch an experiment and return a handle for tracking.

        *setup_path* is the L1 ``setup_*`` directory (treated as a black-box).
        Hyperparameters are passed to the training process via ``HPARAM_*``
        environment variables.  If *timeout_seconds* is set, the runner should
        kill the experiment after that many seconds of wall time.
        """

    @abstractmethod
    def poll(self, handle: RunHandle) -> RunStatus:
        """Query the current status of a previously submitted run."""

    @abstractmethod
    def get_logs(self, handle: RunHandle) -> str:
        """Return the combined stdout/stderr captured so far."""

    @abstractmethod
    def cancel(self, handle: RunHandle) -> None:
        """Best-effort cancellation of a running experiment."""

    # ---- helpers ----

    @staticmethod
    def _build_env(
        hparams: dict[str, Any],
        timeout_seconds: float | None = None,
    ) -> dict[str, str]:
        """Convert a hyperparameter dict into ``HPARAM_*`` env vars.

        If *timeout_seconds* is set, ``HPARAM_MAX_TRAIN_TIME`` is injected so
        that the training script can implement its own graceful stop.
        """
        env: dict[str, str] = {}
        for key, value in hparams.items():
            env_key = f"HPARAM_{key.upper()}"
            env[env_key] = str(value)
        if timeout_seconds is not None:
            env["HPARAM_MAX_TRAIN_TIME"] = str(int(timeout_seconds))
        return env
