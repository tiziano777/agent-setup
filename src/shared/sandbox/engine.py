"""Docker sandbox engine.

Manages container lifecycle (create, exec, cleanup) and enforces
resource limits both at the Docker level and via subprocess rlimits
inside the container.
"""

from __future__ import annotations

import logging
import textwrap
import threading
from typing import Any

from src.shared.sandbox.config import SandboxSettings, _check_available

logger = logging.getLogger(__name__)


class DockerSandbox:
    """Manages a sandboxed Docker container for command execution.

    Lifecycle:
        - ``ensure_running()`` — lazy-creates the container on first use.
        - ``execute(cmd)`` — runs a command inside the warm container.
        - ``cleanup()`` — stops and removes the container.

    The container is configured with:
        - ``read_only=True`` (immutable root FS)
        - Writable ``/workspace`` (tmpfs)
        - Writable ``/tmp`` (tmpfs, 64M)
        - ``network_mode='none'`` (no network by default)
        - Memory, CPU, PID limits
        - All kernel capabilities dropped
        - ``no-new-privileges`` security option
        - Runs as ``nobody`` user

    Thread safety:
        A lock guards container creation so concurrent tool invocations
        share the same container safely.  ``exec_run`` itself is
        thread-safe in the Docker SDK.
    """

    def __init__(self, settings: SandboxSettings | None = None) -> None:
        _check_available()
        self._settings = settings or SandboxSettings()
        self._container: Any = None
        self._client: Any = None
        self._lock = threading.Lock()

    @property
    def settings(self) -> SandboxSettings:
        return self._settings

    def _get_client(self) -> Any:
        """Lazily initialise the Docker client."""
        if self._client is None:
            import docker

            self._client = docker.from_env()
        return self._client

    def ensure_running(self) -> None:
        """Create and start the sandbox container if not already running.

        Idempotent — safe to call multiple times.
        """
        with self._lock:
            if self._container is not None:
                try:
                    self._container.reload()
                    if self._container.status == "running":
                        return
                except Exception:
                    self._container = None

            s = self._settings
            client = self._get_client()

            # Pull image if not present
            try:
                client.images.get(s.image)
            except Exception:
                logger.info("Pulling sandbox image: %s", s.image)
                client.images.pull(s.image)

            nano_cpus = int(s.cpu_limit * 1_000_000_000)

            self._container = client.containers.run(
                image=s.image,
                command="sleep infinity",
                detach=True,
                read_only=True,
                tmpfs={
                    "/tmp": "size=64M,noexec=false",
                    "/workspace": f"size={s.workspace_size},noexec=false",
                },
                working_dir="/workspace",
                network_mode=s.network_mode,
                mem_limit=s.mem_limit,
                nano_cpus=nano_cpus,
                pids_limit=s.pids_limit,
                cap_drop=["ALL"],
                security_opt=["no-new-privileges"],
                user=s.user,
                labels={"managed-by": "agent-setup-sandbox"},
                remove=False,
            )
            logger.info(
                "Sandbox container started: id=%s image=%s",
                self._container.short_id,
                s.image,
            )

    def execute(self, cmd: str) -> dict[str, Any]:
        """Execute a command inside the sandbox container.

        Args:
            cmd: Shell command string to execute.

        Returns:
            Dict with keys: ``exit_code``, ``stdout``, ``stderr``, ``timed_out``.
        """
        self.ensure_running()
        s = self._settings

        # Wrapper script: enforces rlimits inside the container as defense-in-depth.
        wrapper = textwrap.dedent(f"""\
            import resource, subprocess, sys

            def set_limits():
                resource.setrlimit(resource.RLIMIT_CPU, ({s.timeout}, {s.timeout}))
                resource.setrlimit(resource.RLIMIT_FSIZE, (16777216, 16777216))
                resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
                try:
                    resource.setrlimit(resource.RLIMIT_NPROC, (32, 32))
                except (ValueError, AttributeError):
                    pass

            try:
                result = subprocess.run(
                    {cmd!r},
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout={s.timeout},
                    cwd="/workspace",
                    preexec_fn=set_limits,
                )
                sys.stdout.write(result.stdout)
                sys.stderr.write(result.stderr)
                sys.exit(result.returncode)
            except subprocess.TimeoutExpired:
                sys.stderr.write("TIMEOUT: command exceeded {s.timeout}s limit")
                sys.exit(124)
        """)

        try:
            exit_code, output = self._container.exec_run(
                cmd=["python3", "-c", wrapper],
                workdir="/workspace",
                demux=True,
            )

            stdout_raw = output[0] if output[0] else b""
            stderr_raw = output[1] if output[1] else b""
            stdout = stdout_raw.decode("utf-8", errors="replace")
            stderr = stderr_raw.decode("utf-8", errors="replace")
            timed_out = exit_code == 124

            max_chars = s.max_output_chars
            if len(stdout) > max_chars:
                stdout = stdout[:max_chars] + "\n... [truncated]"
            if len(stderr) > max_chars:
                stderr = stderr[:max_chars] + "\n... [truncated]"

            return {
                "exit_code": exit_code,
                "stdout": stdout,
                "stderr": stderr,
                "timed_out": timed_out,
            }

        except Exception as exc:
            logger.error("Sandbox execution error: %s", exc, exc_info=True)
            return {
                "exit_code": -1,
                "stdout": "",
                "stderr": f"Sandbox error: {exc}",
                "timed_out": False,
            }

    def cleanup(self) -> None:
        """Stop and remove the sandbox container."""
        with self._lock:
            if self._container is not None:
                try:
                    self._container.stop(timeout=5)
                    self._container.remove(force=True)
                    logger.info("Sandbox container removed: %s", self._container.short_id)
                except Exception:
                    logger.warning("Failed to clean up sandbox container", exc_info=True)
                finally:
                    self._container = None

    def __del__(self) -> None:
        """Best-effort cleanup on garbage collection."""
        try:
            self.cleanup()
        except Exception:
            pass
