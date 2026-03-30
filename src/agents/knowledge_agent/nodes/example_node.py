"""Custom node example for knowledge_agent.

NOT wired into the default agent graph (which uses create_react_agent).
Use this pattern when building custom StateGraph flows with explicit
node/edge control instead of the default ReAct agent.

Example usage in a custom agent.py::

    from langgraph.graph import END, START, StateGraph
    from src.agents.knowledge_agent.nodes.example_node import process
    from src.agents.knowledge_agent.states.state import AgentState

    builder = StateGraph(AgentState)
    builder.add_node("process", process)
    builder.add_edge(START, "process")
    builder.add_edge("process", END)
    graph = builder.compile()
"""

from src.agents.knowledge_agent.prompts.system import SYSTEM_PROMPT
from src.agents.knowledge_agent.states.state import AgentState
from src.shared.llm import get_llm


def process(state: AgentState) -> dict:
    """Call the LLM with the current messages and return its response."""
    llm = get_llm()
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + state["messages"]
    response = llm.invoke(messages)
    return {"messages": [response]}
