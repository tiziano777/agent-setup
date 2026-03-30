"""Tools for knowledge_agent.

Combines Cognee knowledge graph tools (add, search, cognify) with
the sandboxed execute_cmd tool for code execution.
"""

from src.shared.cognee_toolkit import get_cognee_tools
from src.shared.sandbox import get_sandbox_tools


def get_knowledge_agent_tools(session_id: str | None = None) -> list:
    """Build the full tool set: 3 Cognee tools + 1 sandbox tool."""
    cognee_tools = get_cognee_tools(session_id=session_id)
    sandbox_tools = get_sandbox_tools()
    return cognee_tools + sandbox_tools
