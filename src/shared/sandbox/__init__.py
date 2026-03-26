"""Sandboxed shell execution toolkit.

Provides a Docker-based sandbox for safe code/command execution by
LangGraph agents.  The container runs with a read-only root filesystem,
writable /workspace tmpfs, network isolation, and strict resource limits.

Quick start::

    from src.shared.sandbox import get_sandbox_tools

    tools = get_sandbox_tools()
    agent = create_react_agent(get_llm(), tools)

    # Or use the tool directly:
    tools = get_sandbox_tools()
    result = tools[0].invoke({"cmd": "python3 -c 'print(1+1)'"})

Dependencies:
    Requires ``pip install -e '.[sandbox]'``.  All imports are lazy --
    ``ImportError`` is raised only when a function is actually called.
"""

from src.shared.sandbox.config import SandboxSettings

__all__ = [
    "SandboxSettings",
    "DockerSandbox",
    "get_sandbox_tools",
]


# ── Lazy re-exports ──────────────────────────────────────────────────


def get_sandbox_tools(settings: SandboxSettings | None = None) -> list:
    """Return ``[execute_cmd]`` tool for sandboxed shell execution."""
    from src.shared.sandbox.tools import get_sandbox_tools as _factory

    return _factory(settings=settings)


def DockerSandbox(settings: SandboxSettings | None = None):  # type: ignore[misc]
    """Create a :class:`~src.shared.sandbox.engine.DockerSandbox` instance."""
    from src.shared.sandbox.engine import DockerSandbox as _cls

    return _cls(settings=settings)
