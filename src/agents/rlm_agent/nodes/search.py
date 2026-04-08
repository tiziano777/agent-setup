"""RLM Agent execution node."""

from langchain_core.messages import AIMessage, HumanMessage

from src.agents.rlm_agent.prompts.system import SYSTEM_PROMPT
from src.agents.rlm_agent.states import RLMAgentState
from src.shared.rlm import RLMSettings, get_rlm_metadata, rlm_completion


def extract_iteration_details(metadata: dict) -> list[dict]:
    """Extract code + output from RLM metadata iterations.

    Transforms raw RLM metadata into observable iteration details showing
    the exact code executed and its output/response.

    Args:
        metadata: RLM execution metadata dict.

    Returns:
        List of iteration details with code and output:
            [
                {
                    "iteration": 1,
                    "code_executed": "lines = context.split('\\n')",
                    "exec_response": "Total lines: 1000",
                    "execution_time": 0.0012,
                    "stderr": ""
                },
                ...
            ]
    """
    details = []

    if not metadata or "iterations" not in metadata:
        return details

    for iter_idx, iteration in enumerate(metadata["iterations"], 1):
        for code_block in iteration.get("code_blocks", []):
            result = code_block.get("result", {})

            details.append({
                "iteration": iter_idx,
                "code_executed": code_block.get("code", ""),
                "exec_response": result.get("stdout", ""),
                "execution_time": result.get("execution_time", 0),
                "stderr": result.get("stderr", ""),
            })

    return details


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

    # Extract detailed iteration information (code + output)
    iteration_details = extract_iteration_details(result["metadata"])

    # Build messages for history
    user_msg = HumanMessage(content=f"Prompt: {state['prompt']}\nContext length: {len(state['context'])} chars")

    if result["status"] == "success":
        ai_msg = AIMessage(
            content=result["response"],
            metadata={
                "execution_time": result["execution_time"],
                "total_iterations": metadata["total_iterations"],
                "recursive_calls": len(metadata["recursive_calls"]),
                "iteration_details": iteration_details,
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
