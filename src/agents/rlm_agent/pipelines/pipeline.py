"""RLM Agent: Functional API definition.

Defines the agent as a @entrypoint/@task workflow.
Use this when you prefer plain Python control flow with
LangGraph persistence, streaming, and human-in-the-loop.
"""

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.func import entrypoint, task

from src.agents.rlm_agent.prompts.system import SYSTEM_PROMPT
from src.agents.rlm_agent.states import RLMAgentState
from src.shared.rlm import RLMSettings, get_rlm_metadata, rlm_completion


@task
def execute_rlm_search(prompt: str, context: str) -> dict:
    """Task that executes RLM completion on the context."""
    full_prompt = f"{SYSTEM_PROMPT}\n\nTask: {prompt}"

    result = rlm_completion(
        prompt=full_prompt,
        context=context,
        settings=RLMSettings(
            max_iterations=10,
            verbose=True,
        ),
    )

    metadata = get_rlm_metadata(result)
    return {
        "response": result["response"],
        "status": result["status"],
        "metadata": result["metadata"],
        "execution_time": result["execution_time"],
        "error": result.get("error"),
    }


checkpointer = InMemorySaver()


@entrypoint(checkpointer=checkpointer)
def workflow(inputs: RLMAgentState) -> dict:
    """Functional API workflow for RLM Agent.

    Args:
        inputs: RLMAgentState with "prompt" and "context" keys.

    Returns:
        dict with response, status, and metadata.
    """
    prompt = inputs.get("prompt", "")
    context = inputs.get("context", "")

    result = execute_rlm_search(prompt, context).result()
    return result
