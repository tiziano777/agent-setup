"""Generate node for rag_agent.

Composes a prompt from the system prompt + retrieved context + user question,
calls the LLM, and returns the response as a message.
"""

from src.agents.rag_agent.config import settings
from src.agents.rag_agent.prompts.system import get_prompt
from src.agents.rag_agent.states.state import AgentState
from src.shared.llm import get_llm


def generate(state: AgentState) -> dict:
    """Generate an answer grounded in the retrieved context."""
    llm = get_llm(temperature=settings.temperature)
    system_prompt = get_prompt(context=state.get("context", ""))
    user_question = state["messages"][-1].content

    response = llm.invoke([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_question},
    ])

    return {"messages": [response]}
