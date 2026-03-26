"""__AGENT_NAME__: Graph API definition.

Defines the agent as a LangGraph ReAct agent with sandboxed tool support.
The execute_cmd tool provides shell execution in an isolated Docker
container (read-only FS, writable /workspace, no network, resource limits).

For custom StateGraph flows with explicit node/edge control, see
nodes/example_node.py as a starting point.
"""

from langgraph.prebuilt import create_react_agent

from src.agents.__AGENT_NAME__.prompts.system import SYSTEM_PROMPT
from src.agents.__AGENT_NAME__.tools import execute_cmd
from src.shared.llm import get_llm


def build_graph():
    """Construct a ReAct agent with sandboxed tools."""
    llm = get_llm()
    tools = [execute_cmd]
    return create_react_agent(llm, tools, prompt=SYSTEM_PROMPT)


graph = build_graph()
