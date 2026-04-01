"""rdf_reader: Functional API definition.

Defines the agent as a @entrypoint/@task workflow.
Use this when you prefer plain Python control flow with
LangGraph persistence, streaming, and human-in-the-loop.
"""

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.func import entrypoint, task

from src.agents.rdf_reader.prompts.system import EXTRACT_PROMPT
from src.shared.llm import get_llm


@task
def call_llm(messages: list) -> str:
    """Task that calls the LLM and returns the content string."""
    llm = get_llm()
    full_messages = [{"role": "system", "content": EXTRACT_PROMPT}] + messages
    response = llm.invoke(full_messages)
    return response.content


checkpointer = InMemorySaver()


@entrypoint(checkpointer=checkpointer)
def workflow(inputs: dict) -> dict:
    """Functional API workflow for rdf_reader.

    Args:
        inputs: dict with key "messages" (list of message dicts).

    Returns:
        dict with "response" key.
    """
    messages = inputs.get("messages", [])
    result = call_llm(messages).result()
    return {"response": result}
