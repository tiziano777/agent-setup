"""LangGraph-compatible tools for sandboxed shell execution.

Factory function returns ``@tool``-decorated functions ready to attach
to any LangGraph agent's tool list.

Usage::

    from src.shared.sandbox import get_sandbox_tools

    tools = get_sandbox_tools()
    agent = create_react_agent(get_llm(), tools)
"""

from __future__ import annotations

import atexit

from langchain_core.tools import tool

from src.shared.sandbox.config import SandboxSettings
from src.shared.sandbox.engine import DockerSandbox


def get_sandbox_tools(
    settings: SandboxSettings | None = None,
) -> list:
    """Return a list of LangGraph-compatible sandbox tools.

    Returns ``[execute_cmd]``.
    The sandbox instance is captured in the tool closure and cleaned up
    at process exit via ``atexit``.

    Args:
        settings: Configuration dataclass.  Uses defaults when *None*.
    """
    sandbox = DockerSandbox(settings=settings)
    atexit.register(sandbox.cleanup)

    @tool
    def execute_cmd(cmd: str) -> str:
        """Execute a shell command in a sandboxed Docker container.

        The sandbox has:
        - A writable /workspace directory for creating and running files
        - Python 3.11 available
        - No network access (isolated)
        - Read-only root filesystem
        - Memory, CPU, and time limits

        Use this tool to:
        - Write and execute code (Python, shell scripts, etc.)
        - Run shell commands (ls, cat, echo, grep, etc.)
        - Process data and files in /workspace
        - Install Python packages with pip

        Examples:
            execute_cmd("echo 'print(42)' > test.py && python3 test.py")
            execute_cmd("python3 -c 'import math; print(math.pi)'")
            execute_cmd("ls -la /workspace")

        Args:
            cmd: The shell command to execute.

        Returns:
            Command output (stdout + stderr) and exit code.
        """
        result = sandbox.execute(cmd)

        parts = []
        if result["stdout"]:
            parts.append(result["stdout"])
        if result["stderr"]:
            parts.append(f"[stderr] {result['stderr']}")
        if result["timed_out"]:
            parts.append("[TIMEOUT] Command exceeded time limit.")

        output = "\n".join(parts) if parts else "(no output)"
        exit_info = f"[exit code: {result['exit_code']}]"

        return f"{output}\n{exit_info}"

    return [execute_cmd]
