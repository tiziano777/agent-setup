"""Shell execution tool for __AGENT_NAME__.

Imports the sandboxed execute_cmd tool from the shared sandbox module.
The sandbox runs commands in an isolated Docker container with:
- Read-only root filesystem, writable /workspace
- No network access by default
- Memory, CPU, and time limits

Requires: pip install -e '.[sandbox]'
"""

from src.shared.sandbox import get_sandbox_tools

_tools = get_sandbox_tools()
execute_cmd = _tools[0]
