"""SLURMRunner -- submit experiments via ``sbatch`` and poll with ``sacct``.

The runner generates an sbatch script that exports ``HPARAM_*`` environment
variables, invokes the training entrypoint inside the setup directory, and
captures stdout/stderr to a log file.
"""

from __future__ import annotations

import math
import subprocess
import textwrap
from pathlib import Path
from typing import Any

from src.agents.autoresearch.runners.base import BaseRunner, RunHandle, RunStatus

_SLURM_STATUS_MAP: dict[str, RunStatus] = {
    "PENDING": RunStatus.PENDING,
    "RUNNING": RunStatus.RUNNING,
    "COMPLETING": RunStatus.RUNNING,
    "COMPLETED": RunStatus.COMPLETED,
    "FAILED": RunStatus.FAILED,
    "CANCELLED": RunStatus.CANCELLED,
    "CANCELLED+": RunStatus.CANCELLED,
    "TIMEOUT": RunStatus.FAILED,
    "NODE_FAIL": RunStatus.FAILED,
    "OUT_OF_MEMORY": RunStatus.FAILED,
}


class SLURMRunner(BaseRunner):
    """Submit and manage experiments through the SLURM workload manager."""

    def __init__(
        self,
        partition: str | None = None,
        account: str | None = None,
        log_dir: Path | str = "autoresearch/.slurm_runs",
        extra_sbatch_args: dict[str, str] | None = None,
    ) -> None:
        self._partition = partition
        self._account = account
        self._log_dir = Path(log_dir)
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._extra_sbatch_args = extra_sbatch_args or {}
        self._handles: dict[str, dict[str, Any]] = {}

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

        entrypoint = self._resolve_entrypoint(setup_path)
        script_path = self._log_dir / f"{run_id}.sbatch"
        log_path = self._log_dir / f"{run_id}.log"

        # Generate sbatch script
        script_content = self._generate_sbatch_script(
            run_id=run_id,
            setup_path=setup_path,
            entrypoint=entrypoint,
            hparams=hparams,
            log_path=log_path,
            timeout_seconds=timeout_seconds,
        )
        script_path.write_text(script_content)

        # Submit
        result = subprocess.run(
            ["sbatch", "--parsable", str(script_path)],
            check=True,
            capture_output=True,
            text=True,
        )
        job_id = result.stdout.strip().split(";")[0]  # parsable may include cluster name

        self._handles[run_id] = {
            "job_id": job_id,
            "log_path": str(log_path),
            "script_path": str(script_path),
        }

        return RunHandle(
            run_id=run_id,
            backend="slurm",
            job_id=job_id,
            extra={"log_path": str(log_path)},
        )

    def poll(self, handle: RunHandle) -> RunStatus:
        if handle.job_id is None:
            return RunStatus.FAILED
        try:
            result = subprocess.run(
                [
                    "sacct",
                    "-j", handle.job_id,
                    "--format=State",
                    "--noheader",
                    "--parsable2",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            return RunStatus.FAILED

        lines = [line.strip() for line in result.stdout.strip().splitlines() if line.strip()]
        if not lines:
            return RunStatus.PENDING

        # The first line is the overall job state
        raw_state = lines[0].rstrip("+")
        return _SLURM_STATUS_MAP.get(raw_state, RunStatus.FAILED)

    def get_logs(self, handle: RunHandle) -> str:
        info = self._handles.get(handle.run_id)
        if info is None:
            return ""
        log_path = Path(info["log_path"])
        if log_path.exists():
            return log_path.read_text(errors="replace")
        return ""

    def cancel(self, handle: RunHandle) -> None:
        if handle.job_id is None:
            return
        try:
            subprocess.run(
                ["scancel", handle.job_id],
                check=False,
                capture_output=True,
            )
        except FileNotFoundError:
            pass

    # ---- internal ----

    def _generate_sbatch_script(
        self,
        run_id: str,
        setup_path: Path,
        entrypoint: Path,
        hparams: dict[str, Any],
        log_path: Path,
        timeout_seconds: float | None = None,
    ) -> str:
        """Build the full sbatch shell script."""
        header_lines = [
            "#!/bin/bash",
            f"#SBATCH --job-name=ar-{run_id}",
            f"#SBATCH --output={log_path}",
            f"#SBATCH --error={log_path}",
        ]

        if self._partition:
            header_lines.append(f"#SBATCH --partition={self._partition}")
        if self._account:
            header_lines.append(f"#SBATCH --account={self._account}")
        if timeout_seconds is not None:
            # Add 2 min buffer for startup/teardown
            minutes = math.ceil(timeout_seconds / 60) + 2
            header_lines.append(f"#SBATCH --time={minutes}")

        for key, val in self._extra_sbatch_args.items():
            header_lines.append(f"#SBATCH --{key}={val}")

        # Environment variable exports
        env_lines = []
        for key, val in self._build_env(hparams, timeout_seconds).items():
            env_lines.append(f"export {key}={val!r}")

        body = textwrap.dedent(f"""\
            cd {setup_path}
            python {entrypoint.name}
        """)

        return "\n".join(header_lines) + "\n\n" + "\n".join(env_lines) + "\n\n" + body

    @staticmethod
    def _resolve_entrypoint(setup_path: Path) -> Path:
        """Locate the training script inside a setup directory."""
        for name in ("train.py", "run.py", "main.py"):
            candidate = setup_path / name
            if candidate.is_file():
                return candidate
        raise FileNotFoundError(
            f"No training entrypoint (train.py / run.py / main.py) found in {setup_path}"
        )
