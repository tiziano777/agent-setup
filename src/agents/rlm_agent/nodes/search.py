"""RLM Agent execution node."""

from langchain_core.messages import AIMessage, HumanMessage

from src.agents.rlm_agent.prompts.system import SYSTEM_PROMPT
from src.agents.rlm_agent.states import RLMAgentState
from src.shared.rlm import rlm_completion, get_rlm_metadata, RLMSettings


async def search_node(state: RLMAgentState) -> dict:
    """Execute RLM completion on context to find answer.

    Args:
        state: Current agent state with prompt and context.

    Returns:
        Partial state update with RLM results.
    """
    # Build full system+user prompt
    full_prompt = f"{SYSTEM_PROMPT}\n\nTask: {state['prompt']}"

    # Execute RLM completion
    result = rlm_completion(
        prompt=full_prompt,
        context=state["context"],
        settings=RLMSettings(
            max_iterations=10,
            verbose=True,
        ),
    )

    # Extract metadata for logging
    metadata = get_rlm_metadata(result)

    # Build messages for history
    user_msg = HumanMessage(content=f"Prompt: {state['prompt']}\nContext length: {len(state['context'])} chars")

    if result["status"] == "success":
        ai_msg = AIMessage(
            content=result["response"],
            metadata={
                "execution_time": result["execution_time"],
                "total_iterations": metadata["total_iterations"],
                "recursive_calls": len(metadata["recursive_calls"]),
            },
        )
        rlm_status = "success"
    else:
        ai_msg = AIMessage(
            content=f"Error: {result['error']}",
            metadata={"error": result["error"]},
        )
        rlm_status = "error"

    return {
        "messages": [user_msg, ai_msg],
        "rlm_response": result["response"],
        "rlm_metadata": result["metadata"],
        "rlm_status": rlm_status,
    }
