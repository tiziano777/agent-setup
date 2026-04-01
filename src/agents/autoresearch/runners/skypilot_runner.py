"""SkyPilotRunner -- run experiments on cloud GPU clusters via SkyPilot.

This is a structured stub that implements the full ``BaseRunner`` interface
using SkyPilot CLI commands (``sky launch``, ``sky status``, ``sky logs``,
``sky cancel``).  The runner renders the Jinja2 task template for each
experiment and manages cluster lifecycle.

Requires the ``skypilot`` optional dependency::

    pip install "finetuning-envelope[autoresearch]"
"""

from __future__ import annotations

import json
import subprocess
import time as _time
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from src.agents.autoresearch.runners.base import BaseRunner, RunHandle, RunStatus

_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "skypilot" / "templates"


def _check_skypilot() -> None:
    """Raise a clear error if skypilot is not importable."""
    try:
        import sky  # noqa: F401
    except ImportError:
        raise ImportError(
            "SkyPilot is required for the 'skypilot' backend but is not installed.\n"
            "Install it with: pip install 'finetuning-envelope[autoresearch]'\n"
            "Then run: sky check"
        )


class SkyPilotRunner(BaseRunner):
    """Run experiments on cloud clusters via SkyPilot.

    Each experiment gets its own SkyPilot task YAML rendered from the
    ``experiment_task.yaml.j2`` template.  The runner shells out to
    ``sky`` CLI commands for lifecycle management.
    """

    def __init__(
        self,
        accelerators: str = "A100:1",
        cloud: str | None = None,
        region: str | None = None,
        instance_type: str | None = None,
        use_spot: bool = False,
        num_nodes: int = 1,
        log_dir: Path | str = "autoresearch/.skypilot_runs",
    ) -> None:
        _check_skypilot()
        self._accelerators = accelerators
        self._cloud = cloud
        self._region = region
        self._instance_type = instance_type
        self._use_spot = use_spot
        self._num_nodes = num_nodes
        self._log_dir = Path(log_dir)
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._handles: dict[str, dict[str, Any]] = {}

    # ---- Template rendering ----

    def _render_task_yaml(
        self,
        run_id: str,
        setup_path: Path,
        hparams: dict[str, Any],
        timeout_seconds: float | None = None,
    ) -> Path:
        """Render the SkyPilot task YAML for a single experiment.

        Returns the path to the rendered YAML file.
        """
        env = Environment(
            loader=FileSystemLoader(str(_TEMPLATE_DIR)),
            keep_trailing_newline=True,
        )
        template = env.get_template("experiment_task.yaml.j2")

        rendered = template.render(
            sweep_name="ar",
            run_id=run_id,
            gpu_type=(
                self._accelerators.split(":")[0]
                if ":" in self._accelerators
                else self._accelerators
            ),
            gpu_count=(
                int(self._accelerators.split(":")[1])
                if ":" in self._accelerators
                else 1
            ),
            cloud=self._cloud,
            region=self._region,
            instance_type=self._instance_type,
            use_spot=self._use_spot,
            num_nodes=self._num_nodes,
            setup_dir=str(setup_path),
            hparams=hparams,
            entrypoint="train.py",
            timeout_seconds=int(timeout_seconds) if timeout_seconds else None,
        )

        yaml_path = self._log_dir / f"{run_id}.yaml"
        yaml_path.write_text(rendered)
        return yaml_path

    # ---- CLI helpers ----

    @staticmethod
    def _run_sky_cmd(args: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
        """Execute a ``sky`` CLI command and return the result."""
        full_cmd = ["sky"] + args
        return subprocess.run(
            full_cmd,
            check=check,
            capture_output=True,
            text=True,
            timeout=120,
        )

    def _cluster_name(self, run_id: str) -> str:
        """Derive the SkyPilot cluster name from the run ID."""
        return f"ar-{run_id}"

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

        yaml_path = self._render_task_yaml(run_id, setup_path, hparams, timeout_seconds)
        cluster = self._cluster_name(run_id)

        # Launch (detached: -d flag means don't wait for completion)
        self._run_sky_cmd(["launch", "-y", "-d", "-c", cluster, str(yaml_path)])

        self._handles[run_id] = {
            "cluster": cluster,
            "yaml_path": str(yaml_path),
            "start_time": _time.time(),
            "timeout": timeout_seconds,
        }

        return RunHandle(
            run_id=run_id,
            backend="skypilot",
            extra={
                "cluster": cluster,
                "start_time": _time.time(),
                "timeout": timeout_seconds,
            },
        )

    def poll(self, handle: RunHandle) -> RunStatus:
        cluster = handle.extra.get("cluster")
        if not cluster:
            return RunStatus.FAILED

        try:
            result = self._run_sky_cmd(["status", cluster, "--format", "json"], check=False)
            if result.returncode != 0:
                # Cluster not found or already terminated
                return RunStatus.COMPLETED
        except subprocess.TimeoutExpired:
            return RunStatus.RUNNING

        status_text = result.stdout.strip()
        return self._parse_sky_status(status_text)

    def get_logs(self, handle: RunHandle) -> str:
        cluster = handle.extra.get("cluster")
        if not cluster:
            return ""
        try:
            result = self._run_sky_cmd(["logs", cluster, "--no-follow"], check=False)
            return result.stdout
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
            return ""

    def cancel(self, handle: RunHandle) -> None:
        cluster = handle.extra.get("cluster")
        if not cluster:
            return
        try:
            self._run_sky_cmd(["cancel", cluster, "-y"], check=False)
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
            pass

    def teardown(self, handle: RunHandle) -> None:
        """Tear down the cluster to stop incurring costs."""
        cluster = handle.extra.get("cluster")
        if not cluster:
            return
        try:
            self._run_sky_cmd(["down", cluster, "-y"], check=False)
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
            pass

    # ---- Status parsing ----

    @staticmethod
    def _parse_sky_status(status_json: str) -> RunStatus:
        """Parse ``sky status --format json`` output to a RunStatus."""
        try:
            data = json.loads(status_json)
        except (json.JSONDecodeError, TypeError):
            return RunStatus.FAILED

        if not data:
            return RunStatus.COMPLETED

        # sky status returns a list of cluster dicts
        cluster_info = data[0] if isinstance(data, list) else data
        status = cluster_info.get("status", "").upper()

        if status in ("UP", "INIT"):
            return RunStatus.RUNNING
        if status == "STOPPED":
            return RunStatus.COMPLETED
        return RunStatus.FAILED
