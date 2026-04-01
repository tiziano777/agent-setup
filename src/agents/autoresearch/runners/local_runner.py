"""LocalRunner -- execute experiments as local subprocesses.

Hyperparameters are injected via ``HPARAM_*`` environment variables.
Structured output lines (``EXPERIMENT_*``) are captured from stdout.
"""

from __future__ import annotations

import os
import signal
import subprocess
import time as _time
from pathlib import Path
from typing import Any

from src.agents.autoresearch.runners.base import BaseRunner, RunHandle, RunStatus


class LocalRunner(BaseRunner):
    """Run experiments as local subprocesses."""

    def __init__(self, log_dir: Path | str = "autoresearch/.runs") -> None:
        self._log_dir = Path(log_dir)
        self._log_dir.mkdir(parents=True, exist_ok=True)
        # Map run_id -> subprocess.Popen
        self._processes: dict[str, subprocess.Popen[bytes]] = {}

    # ---- BaseRunner interface ----

    def submit(
        self,
        run_id: str,
        setup_path: Path,
        hparams: dict[str, Any],
        timeout_seconds: float | None = None,
    ) -> RunHandle:
        setup_path = Path(setup_path).resolve()
        if not setup_path.is_dir():
            raise FileNotFoundError(f"Setup directory not found: {setup_path}")

        # Determine the training entrypoint
        entrypoint = self._resolve_entrypoint(setup_path)

        # Build environment: inherit current env + HPARAM_* overrides
        env = {**os.environ, **self._build_env(hparams, timeout_seconds)}

        # Log files
        log_file = self._log_dir / f"{run_id}.log"

        with open(log_file, "wb") as fh:
            proc = subprocess.Popen(
                ["python", str(entrypoint)],
                cwd=str(setup_path),
                env=env,
                stdout=fh,
                stderr=subprocess.STDOUT,
            )

        self._processes[run_id] = proc

        return RunHandle(
            run_id=run_id,
            backend="local",
            pid=proc.pid,
            extra={
                "start_time": _time.time(),
                "timeout": timeout_seconds,
            },
        )

    def poll(self, handle: RunHandle) -> RunStatus:
        proc = self._processes.get(handle.run_id)
        if proc is None:
            return RunStatus.FAILED

        retcode = proc.poll()
        if retcode is None:
            # Check per-experiment timeout
            timeout = handle.extra.get("timeout")
            start_time = handle.extra.get("start_time")
            if timeout and start_time:
                elapsed = _time.time() - start_time
                if elapsed > timeout:
                    self.cancel(handle)
                    return RunStatus.CANCELLED
            return RunStatus.RUNNING
        if retcode == 0:
            return RunStatus.COMPLETED
        return RunStatus.FAILED

    def get_logs(self, handle: RunHandle) -> str:
        log_file = self._log_dir / f"{handle.run_id}.log"
        if log_file.exists():
            return log_file.read_text(errors="replace")
        return ""

    def cancel(self, handle: RunHandle) -> None:
        proc = self._processes.get(handle.run_id)
        if proc is None:
            return
        try:
            proc.send_signal(signal.SIGTERM)
            proc.wait(timeout=10)
        except (ProcessLookupError, subprocess.TimeoutExpired):
            proc.kill()

    # ---- internal ----

    @staticmethod
    def _resolve_entrypoint(setup_path: Path) -> Path:
        """Locate the training script inside a setup directory.

        Looks for (in priority order):
          1. ``train.py``
          2. ``run.py``
          3. ``main.py``
        """
        for name in ("train.py", "run.py", "main.py"):
            candidate = setup_path / name
            if candidate.is_file():
                return candidate
        raise FileNotFoundError(
            f"No training entrypoint (train.py / run.py / main.py) found in {setup_path}"
        )
