"""SSHRunner -- execute experiments on a remote host via SSH.

The setup directory is copied to the remote host with ``rsync``, the training
script is executed over SSH with ``HPARAM_*`` env vars, and logs are collected
back via SSH.
"""

from __future__ import annotations

import shlex
import subprocess
from pathlib import Path
from typing import Any

from src.agents.autoresearch.runners.base import BaseRunner, RunHandle, RunStatus


class SSHRunner(BaseRunner):
    """Run experiments on a remote machine over SSH."""

    def __init__(
        self,
        host: str,
        user: str | None = None,
        key_path: Path | str | None = None,
        remote_workdir: str = "~/autoresearch_runs",
    ) -> None:
        self._host = host
        self._user = user
        self._key_path = Path(key_path) if key_path else None
        self._remote_workdir = remote_workdir
        self._handles: dict[str, dict[str, Any]] = {}

    # ---- SSH command helpers ----

    def _ssh_base(self) -> list[str]:
        """Build the base ``ssh`` command with optional key and user."""
        cmd = ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "BatchMode=yes"]
        if self._key_path:
            cmd += ["-i", str(self._key_path)]
        target = f"{self._user}@{self._host}" if self._user else self._host
        cmd.append(target)
        return cmd

    def _rsync_base(self) -> list[str]:
        """Build the base ``rsync`` command."""
        cmd = ["rsync", "-az", "--delete"]
        if self._key_path:
            cmd += ["-e", f"ssh -i {shlex.quote(str(self._key_path))} -o StrictHostKeyChecking=no"]
        return cmd

    def _remote_target(self) -> str:
        return f"{self._user}@{self._host}" if self._user else self._host

    # ---- BaseRunner interface ----

    def submit(
        self,
        run_id: str,
        setup_path: Path,
        hparams: dict[str, Any],
        timeout_seconds: float | None = None,
    ) -> RunHandle:
        setup_path = Path(setup_path).resolve()
        remote_run_dir = f"{self._remote_workdir}/{run_id}"
        remote_setup = f"{remote_run_dir}/setup"

        # 1. Create remote directory
        self._ssh_exec(f"mkdir -p {shlex.quote(remote_setup)}")

        # 2. Rsync setup to remote
        rsync_cmd = self._rsync_base() + [
            f"{setup_path}/",
            f"{self._remote_target()}:{remote_setup}/",
        ]
        subprocess.run(rsync_cmd, check=True, capture_output=True)

        # 3. Build the remote command
        env_exports = " ".join(
            f"{k}={shlex.quote(v)}" for k, v in self._build_env(hparams, timeout_seconds).items()
        )
        entrypoint = self._resolve_remote_entrypoint(remote_setup)
        remote_log = f"{remote_run_dir}/output.log"
        remote_pid = f"{remote_run_dir}/pid"

        # Wrap with timeout(1) if per-experiment limit is set
        train_cmd = f"python {entrypoint}"
        if timeout_seconds is not None:
            train_cmd = f"timeout {int(timeout_seconds)} {train_cmd}"

        # Run in background, save PID
        remote_cmd = (
            f"cd {shlex.quote(remote_setup)} && "
            f"nohup env {env_exports} {train_cmd} "
            f"> {shlex.quote(remote_log)} 2>&1 & echo $! > {shlex.quote(remote_pid)}"
        )
        self._ssh_exec(remote_cmd)

        # Read PID
        pid_str = self._ssh_exec(f"cat {shlex.quote(remote_pid)}").strip()
        pid = int(pid_str) if pid_str.isdigit() else None

        self._handles[run_id] = {
            "remote_run_dir": remote_run_dir,
            "remote_log": remote_log,
            "remote_pid": remote_pid,
            "pid": pid,
        }

        return RunHandle(
            run_id=run_id,
            backend="ssh",
            pid=pid,
            extra={"host": self._host, "remote_run_dir": remote_run_dir},
        )

    def poll(self, handle: RunHandle) -> RunStatus:
        info = self._handles.get(handle.run_id)
        if info is None or info.get("pid") is None:
            return RunStatus.FAILED

        # Check if process is still running
        try:
            result = self._ssh_exec(f"kill -0 {info['pid']} 2>/dev/null && echo ALIVE || echo DEAD")
            result = result.strip()
        except subprocess.CalledProcessError:
            return RunStatus.FAILED

        if result == "ALIVE":
            return RunStatus.RUNNING

        # Process ended -- check exit status from log heuristics
        # Look for EXPERIMENT_STATUS line in logs
        try:
            logs = self.get_logs(handle)
            if "EXPERIMENT_STATUS=completed" in logs:
                return RunStatus.COMPLETED
            if "EXPERIMENT_STATUS=failed" in logs:
                return RunStatus.FAILED
        except Exception:
            pass

        return RunStatus.COMPLETED

    def get_logs(self, handle: RunHandle) -> str:
        info = self._handles.get(handle.run_id)
        if info is None:
            return ""
        try:
            return self._ssh_exec(f"cat {shlex.quote(info['remote_log'])} 2>/dev/null || true")
        except subprocess.CalledProcessError:
            return ""

    def cancel(self, handle: RunHandle) -> None:
        info = self._handles.get(handle.run_id)
        if info is None or info.get("pid") is None:
            return
        try:
            self._ssh_exec(f"kill {info['pid']} 2>/dev/null || true")
        except subprocess.CalledProcessError:
            pass

    # ---- internal ----

    def _ssh_exec(self, command: str) -> str:
        """Execute a command on the remote host and return stdout."""
        full_cmd = self._ssh_base() + [command]
        result = subprocess.run(full_cmd, check=True, capture_output=True, text=True)
        return result.stdout

    def _resolve_remote_entrypoint(self, remote_setup: str) -> str:
        """Check which entrypoint script exists on the remote host."""
        for candidate in ("train.py", "run.py", "main.py"):
            try:
                result = self._ssh_exec(
                    f"test -f {shlex.quote(remote_setup)}/{candidate} && echo YES || echo NO"
                )
                if result.strip() == "YES":
                    return candidate
            except subprocess.CalledProcessError:
                continue
        return "train.py"
