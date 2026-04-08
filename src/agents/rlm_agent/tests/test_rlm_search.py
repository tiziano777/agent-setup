"""Test RLM Agent on text search task."""

import random
import string
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.rlm_agent.agent import get_agent
from src.agents.rlm_agent.states import RLMAgentState


def generate_haystack(size: int = 5000, secret: str = "SECRET_NUMBER_42") -> tuple[str, int]:
    """Generate long text with hidden secret.

    Args:
        size: Number of filler lines.
        secret: Secret string to hide.

    Returns:
        (haystack_text, insertion_index)
    """
    filler_lines = [
        "".join(random.choices(string.ascii_lowercase + " ", k=120))
        for _ in range(size)
    ]

    # Insert secret at random location in middle third
    insert_at = random.randint(len(filler_lines) // 3, 2 * len(filler_lines) // 3)
    filler_lines.insert(insert_at, f"MAGIC: {secret}")

    return "\n".join(filler_lines), insert_at


@pytest.mark.asyncio
@patch("src.agents.rlm_agent.nodes.search.rlm_completion")
async def test_rlm_agent_finds_secret(mock_rlm_completion):
    """Test that RLM Agent can find hidden value in long text (mocked)."""
    secret = "MAGIC_42_FOUND"
    haystack, insert_idx = generate_haystack(5000, secret)

    # Mock RLM completion result
    mock_rlm_completion.return_value = {
        "response": f"Found: {secret}",
        "execution_time": 2.5,
        "metadata": {
            "iterations": [
                {"step": 1, "action": "sample"},
                {"step": 2, "action": "regex_search"},
            ],
            "rlm_calls": [],
        },
        "status": "success",
        "error": None,
    }

    # Create agent
    agent = get_agent()

    # Build input state
    initial_state: RLMAgentState = {
        "prompt": "Find and return ONLY the MAGIC value.",
        "context": haystack,
        "rlm_response": None,
        "rlm_metadata": None,
        "rlm_status": "pending",
        "messages": [],
    }

    # Run agent
    result = await agent.ainvoke(initial_state)

    # Verify results
    assert result["rlm_status"] == "success", f"RLM failed: {result.get('rlm_response')}"
    assert result["rlm_response"] is not None
    assert secret in result["rlm_response"], f"Secret not found in response: {result['rlm_response']}"

    # Log execution trajectory
    metadata = result["rlm_metadata"]
    if metadata:
        iterations = len(metadata.get("iterations", []))
        print(f"\n✓ Found secret '{secret}' at line {insert_idx}")
        print(f"✓ RLM iterations: {iterations}")
        print(f"✓ Response: {result['rlm_response']}")

    # Check message history for full observability
    messages = result["messages"]
    assert len(messages) >= 2, "Expected at least user + AI messages"
    print(f"✓ Message history: {len(messages)} messages logged")

    for i, msg in enumerate(messages):
        print(f"  Message {i}: {msg.__class__.__name__}")


@pytest.mark.asyncio
@patch("src.agents.rlm_agent.nodes.search.rlm_completion")
async def test_rlm_agent_message_chain(mock_rlm_completion):
    """Test that message chain is properly tracked for Phoenix."""
    haystack, _ = generate_haystack(1000, "TEST_123")

    # Mock RLM response
    mock_rlm_completion.return_value = {
        "response": "TEST_123 found successfully",
        "execution_time": 1.8,
        "metadata": {
            "iterations": [
                {"step": 1, "action": "read_lines"},
                {"step": 2, "action": "pattern_match"},
            ],
            "rlm_calls": [],
        },
        "status": "success",
        "error": None,
    }

    agent = get_agent()

    initial_state: RLMAgentState = {
        "prompt": "Find TEST_123 in the text.",
        "context": haystack,
        "rlm_response": None,
        "rlm_metadata": None,
        "rlm_status": "pending",
        "messages": [],
    }

    result = await agent.ainvoke(initial_state)

    # Verify full message chain
    messages = result["messages"]
    assert len(messages) >= 2

    # Last message should be AI response
    assert messages[-1].__class__.__name__ == "AIMessage"

    # Check metadata in AI message
    ai_msg = messages[-1]
    assert ai_msg.metadata is not None
    print(f"\n✓ AI Message metadata: {ai_msg.metadata}")

    # Check execution metrics
    if ai_msg.metadata:
        if "execution_time" in ai_msg.metadata:
            print(f"✓ Execution time: {ai_msg.metadata['execution_time']:.2f}s")
        if "total_iterations" in ai_msg.metadata:
            print(f"✓ Total iterations: {ai_msg.metadata['total_iterations']}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(test_rlm_agent_finds_secret())
    asyncio.run(test_rlm_agent_message_chain())
    print("\n✓ All tests passed!")
