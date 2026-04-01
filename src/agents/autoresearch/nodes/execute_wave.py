"""Execute a wave of experiments via runners or sandbox."""

from __future__ import annotations

import time
import uuid
from typing import Any

from langchain_core.messages import AIMessage

from src.agents.autoresearch.config.models import HardwareBackend
from src.agents.autoresearch.runners.base import RunStatus
from src.agents.autoresearch.runners.local_runner import LocalRunner
from src.agents.autoresearch.schemas.entities import Experiment, ExperimentStatus
from src.agents.autoresearch.states.state import AutoresearchState
from src.agents.autoresearch.tracking.result_parser import parse_experiment_output


def execute_wave(state: AutoresearchState) -> dict[str, Any]:
    """Submit experiments, poll until done, parse results.

    Uses the appropriate runner based on ``sweep_config.hardware.backend``.
    """
    wave_configs = state.get("wave_configs", [])
    session_id = state["session_id"]
    sweep_config = state.get("sweep_config", {})
    wave_number = state.get("wave_number", 0)

    base_setup = str(sweep_config.get("base_setup", "."))
    backend = sweep_config.get("hardware", {}).get("backend", "local")
    timeout = sweep_config.get("budget", {}).get("max_run_time_seconds")

    # Create runner
    runner = _create_runner(backend, sweep_config.get("hardware", {}))

    results: list[dict[str, Any]] = []
    experiments: list[Experiment] = []

    # Submit all experiments
    handles = []
    for config in wave_configs:
        run_id = uuid.uuid4().hex[:16]
        exp = Experiment(
            run_id=run_id,
            session_id=session_id,
            sweep_name=sweep_config.get("name", ""),
            base_setup=base_setup,
            hyperparams=config,
            status=ExperimentStatus.RUNNING,
            wave_number=wave_number,
            runner_backend=backend,
        )
        experiments.append(exp)

        handle = runner.submit(
            run_id=run_id,
            setup_path=base_setup,
            hparams=config,
            timeout_seconds=int(timeout) if timeout else None,
        )
        handles.append((handle, exp))

    # Poll until all complete
    poll_interval = 5.0
    max_polls = 720  # 1 hour at 5s intervals
    for _ in range(max_polls):
        all_done = True
        for handle, exp in handles:
            if exp.status not in (
                ExperimentStatus.COMPLETED,
                ExperimentStatus.CRASHED,
                ExperimentStatus.CANCELLED,
            ):
                status = runner.poll(handle)
                if status == RunStatus.COMPLETED:
                    exp.status = ExperimentStatus.COMPLETED
                    logs = runner.get_logs(handle)
                    parsed = parse_experiment_output(logs)
                    exp.metrics = parsed.get("metrics", {})
                    exp.wall_time_seconds = parsed.get("wall_time_seconds")
                elif status == RunStatus.FAILED:
                    exp.status = ExperimentStatus.CRASHED
                elif status in (RunStatus.RUNNING, RunStatus.PENDING):
                    all_done = False
        if all_done:
            break
        time.sleep(poll_interval)

    # Build results
    for exp in experiments:
        results.append(exp.to_state_dict())

    return {
        "wave_results": results,
        "messages": [
            AIMessage(
                content=f"Wave {wave_number}: {len(results)} experiments completed. "
                f"{sum(1 for e in experiments if e.status == ExperimentStatus.COMPLETED)} "
                f"succeeded, "
                f"{sum(1 for e in experiments if e.status == ExperimentStatus.CRASHED)} "
                f"crashed."
            ),
        ],
    }


def _create_runner(backend: str, hardware_config: dict[str, Any]):
    """Create the appropriate runner based on backend type."""
    if backend == HardwareBackend.LOCAL.value:
        return LocalRunner()
    elif backend == HardwareBackend.SSH.value:
        from src.agents.autoresearch.runners.ssh_runner import SSHRunner

        return SSHRunner(
            host=hardware_config.get("ssh_host", ""),
            user=hardware_config.get("ssh_user", ""),
            key_path=hardware_config.get("ssh_key_path"),
        )
    elif backend == HardwareBackend.SLURM.value:
        from src.agents.autoresearch.runners.slurm_runner import SLURMRunner

        return SLURMRunner(partition=hardware_config.get("partition"))
    elif backend == HardwareBackend.SKYPILOT.value:
        from src.agents.autoresearch.runners.skypilot_runner import SkyPilotRunner

        return SkyPilotRunner(config=hardware_config.get("skypilot", {}))
    return LocalRunner()
