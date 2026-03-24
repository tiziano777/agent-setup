"""Example tool for __AGENT_NAME__.

Tools are decorated with @tool from langchain_core.
They can be bound to an LLM via `llm.bind_tools([...])` or
passed to `create_react_agent(model, tools=[...])`.
"""

from langchain_core.tools import tool


@tool
def example_tool(query: str) -> str:
    """A placeholder tool. Replace with real logic."""
    return f"Tool received: {query}"
