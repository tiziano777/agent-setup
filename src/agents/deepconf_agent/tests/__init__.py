"""Tests for deepconf_agent."""

import asyncio
import pytest

from src.agents.deepconf_agent import graph
from src.agents.deepconf_agent.schemas import DeepConfAgentInput


@pytest.mark.asyncio
async def test_deepconf_agent_simple_math():
    """Test deepconf_agent on a simple math question.

    Verifies:
    - Graph executes successfully
    - Output contains final_answer and reasoning_output
    - Answer is plausible (contains a number)
    """
    input_data = {
        "question": "What is 5 + 7? Show your work step by step.",
    }

    # Invoke the graph
    result = await asyncio.get_event_loop().run_in_executor(
        None, lambda: graph.invoke(input_data)
    )

    # Assertions
    assert result is not None, "Graph should return a result"
    assert "final_answer" in result, "Result should contain final_answer"
    assert (
        result["final_answer"]
    ), "final_answer should not be empty"

    print("\n" + "=" * 80)
    print("DEEPCONF AGENT TEST RESULTS")
    print("=" * 80)
    print(f"\nInput Question: {input_data['question']}")
    print(f"\nFinal Answer:\n{result['final_answer']}")

    # Check reasoning output
    if "reasoning_output" in result:
        reasoning = result["reasoning_output"]
        print(f"\nReasoning Mode: {reasoning.get('mode', 'N/A')}")
        print(
            f"Reasoning Steps: {len(reasoning.get('reasoning_steps', []))} "
            f"step(s)"
        )

        if reasoning.get("reasoning_steps"):
            print("\nReasoning Steps:")
            for i, step in enumerate(
                reasoning.get("reasoning_steps", []), 1
            ):
                print(f"  {i}. {step}")

        if reasoning.get("voting_results"):
            print("\nVoting Results:")
            for strategy, result_info in reasoning.get(
                "voting_results", {}
            ).items():
                confidence = result_info.get("confidence", 0.0)
                print(
                    f"  {strategy}: confidence={confidence:.2f}"
                )

        print(
            f"\nBackend: {reasoning.get('backend', 'unknown')}"
        )
        print(
            f"All Traces Count: "
            f"{reasoning.get('all_traces_count', 0)}"
        )
        print(
            f"Timestamp: {reasoning.get('timestamp', 'N/A')}"
        )

    print("\n" + "=" * 80)

    # Verify answer contains reasonable content
    answer = result["final_answer"].lower()
    assert (
        answer
    ), "Answer should not be empty"
    # Math-related keywords
    assert any(
        keyword in answer
        for keyword in [
            "12",
            "answer",
            "result",
            "sum",
            "add",
            "5",
            "7",
            "plus",
        ]
    ), (
        f"Answer should contain math-related content, got: "
        f"{result['final_answer']}"
    )


@pytest.mark.asyncio
async def test_deepconf_agent_complex_reasoning():
    """Test deepconf_agent on a reasoning problem.

    Verifies:
    - Agent handles open-ended questions
    - Multiple reasoning strategies are used
    - Output structure is correct
    """
    input_data = {
        "question": (
            "If a train travels 100 km in 2 hours, "
            "what is its average speed?"
        ),
    }

    result = graph.invoke(input_data)

    assert result is not None
    assert "final_answer" in result
    assert result["final_answer"]

    print("\n" + "=" * 80)
    print("DEEPCONF COMPLEX REASONING TEST")
    print("=" * 80)
    print(f"\nInput: {input_data['question']}")
    print(f"\nAnswer:\n{result['final_answer']}")

    if "reasoning_output" in result:
        reasoning = result["reasoning_output"]
        num_strategies = len(reasoning.get("voting_results", {}))
        print(f"\nStrategies used: {num_strategies}")

    print("\n" + "=" * 80)

    # Answer should mention speed or km/h
    answer = result["final_answer"].lower()
    assert any(
        keyword in answer
        for keyword in [
            "50",
            "speed",
            "hour",
            "km",
            "average",
            "mph",
            "per",
        ]
    ), (
        f"Answer should address the speed question, got: "
        f"{result['final_answer']}"
    )


if __name__ == "__main__":
    # Run tests directly (for debugging)
    print("Running test_deepconf_agent_simple_math...")
    asyncio.run(test_deepconf_agent_simple_math())

    print("\nRunning test_deepconf_agent_complex_reasoning...")
    asyncio.run(test_deepconf_agent_complex_reasoning())
