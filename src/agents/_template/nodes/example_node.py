"""Example node for __AGENT_NAME__.

Each node is a function that receives the current state and returns
a partial state update dict. Nodes should NOT mutate state directly.
"""

from src.agents.__AGENT_NAME__.prompts.system import SYSTEM_PROMPT
from src.agents.__AGENT_NAME__.states.state import AgentState
from src.shared.llm import get_llm


def process(state: AgentState) -> dict:
    """Call the LLM with the current messages and return its response."""
    llm = get_llm()
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + state["messages"]
    response = llm.invoke(messages)
    return {"messages": [response]}
