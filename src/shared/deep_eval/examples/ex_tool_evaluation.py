"""Component-level tool evaluation example.

Demonstrates evaluating individual tools in a LangGraph agent using
DeepEval's tool-level evaluation capabilities.  This uses DeepEval's
``@tool`` decorator which accepts ``metric`` parameters for per-tool
evaluation, and also shows manual tool output evaluation.

Patterns shown:
    1. DeepEval ``@tool`` decorator with metrics
    2. Manual tool output evaluation with ``AnswerRelevancyMetric``
    3. Multi-tool evaluation pipeline

Prerequisites:
    - Infrastructure running (``make build``)
    - ``pip install -e '.[deepeval]'``

Run::

    python -m src.shared.deep_eval.examples.ex_tool_evaluation
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Phase 1 — Define tools with DeepEval metrics
# ---------------------------------------------------------------------------

TOOL_CATALOG: str = """
1. web_search(query: str) -> str
   Search the web for current information.

2. calculator(expression: str) -> float
   Evaluate a mathematical expression.

3. weather_api(city: str) -> str
   Get current weather for a city.
""".strip()


# Simulated tool implementations
def _web_search(query: str) -> str:
    return f"Search results for '{query}': Python is a programming language."


def _calculator(expression: str) -> str:
    try:
        return str(eval(expression))  # noqa: S307
    except Exception as e:
        return f"Error: {e}"


def _weather_api(city: str) -> str:
    return f'{{"city": "{city}", "temp": 22, "conditions": "sunny"}}'


# ---------------------------------------------------------------------------
# Phase 2 — Tool output evaluation samples
# ---------------------------------------------------------------------------

TOOL_EVAL_SAMPLES: list[dict[str, Any]] = [
    {
        "input": "What is the square root of 144?",
        "tool_name": "calculator",
        "tool_input": "144 ** 0.5",
        "tool_output": "12.0",
        "agent_output": "The square root of 144 is 12.",
    },
    {
        "input": "What is the weather in Tokyo?",
        "tool_name": "weather_api",
        "tool_input": "Tokyo",
        "tool_output": '{"city": "Tokyo", "temp": 22, "conditions": "sunny"}',
        "agent_output": "It's 22 degrees and sunny in Tokyo.",
    },
    {
        "input": "What is Python?",
        "tool_name": "web_search",
        "tool_input": "What is Python programming language",
        "tool_output": "Python is a high-level programming language.",
        "agent_output": "Python is a compiled low-level language used for hardware programming.",
    },
]


# ---------------------------------------------------------------------------
# Phase 3 — Evaluate tool outputs
# ---------------------------------------------------------------------------


def evaluate_tool_outputs(
    samples: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Evaluate how well the agent used tool outputs in its response.

    Uses AnswerRelevancyMetric and FaithfulnessMetric to check whether
    the agent's final response is consistent with what the tool returned.
    """
    from src.shared.deep_eval.metrics import answer_relevancy_metric, faithfulness_metric
    from src.shared.deep_eval.test_cases import create_test_case

    if samples is None:
        samples = TOOL_EVAL_SAMPLES

    relevancy = answer_relevancy_metric()
    faithful = faithfulness_metric()

    results: list[dict[str, Any]] = []
    for sample in samples:
        # The tool output is the retrieval context for faithfulness
        tc = create_test_case(
            input=sample["input"],
            actual_output=sample["agent_output"],
            retrieval_context=[sample["tool_output"]],
        )

        relevancy.measure(tc)
        faithful.measure(tc)

        results.append({
            "input": sample["input"],
            "tool_name": sample["tool_name"],
            "tool_output": sample["tool_output"],
            "agent_output": sample["agent_output"],
            "metrics": [
                {
                    "name": "AnswerRelevancyMetric",
                    "score": relevancy.score,
                    "reason": getattr(relevancy, "reason", None),
                    "passed": relevancy.score >= 0.5,
                },
                {
                    "name": "FaithfulnessMetric",
                    "score": faithful.score,
                    "reason": getattr(faithful, "reason", None),
                    "passed": faithful.score >= 0.5,
                },
            ],
        })

    return results


# ---------------------------------------------------------------------------
# Phase 4 — Evaluate tool selection
# ---------------------------------------------------------------------------

TOOL_SELECTION_SAMPLES: list[dict[str, str]] = [
    {
        "input": "What is 15 * 8?",
        "expected_tool": "calculator",
        "selected_tool": "calculator",
    },
    {
        "input": "What's the weather in Paris?",
        "expected_tool": "weather_api",
        "selected_tool": "weather_api",
    },
    {
        "input": "What's the temperature in London?",
        "expected_tool": "weather_api",
        "selected_tool": "web_search",  # wrong selection
    },
]


def evaluate_tool_selection(
    samples: list[dict[str, str]] | None = None,
) -> list[dict[str, Any]]:
    """Evaluate whether the agent selected the correct tool.

    Uses a simple GEval metric to judge tool selection quality.
    """
    from src.shared.deep_eval.metrics import geval_metric
    from src.shared.deep_eval.test_cases import create_test_case

    if samples is None:
        samples = TOOL_SELECTION_SAMPLES

    metric = geval_metric(
        name="tool_selection_accuracy",
        criteria=(
            "Did the agent select the correct tool for the user's query? "
            "The expected tool and the selected tool should match. "
            "Consider whether the selected tool can reasonably answer the query."
        ),
    )

    results: list[dict[str, Any]] = []
    for sample in samples:
        tc = create_test_case(
            input=(
                f"Query: {sample['input']}\n"
                f"Available tools: {TOOL_CATALOG}\n"
                f"Selected tool: {sample['selected_tool']}"
            ),
            actual_output=f"Selected: {sample['selected_tool']}",
            expected_output=f"Expected: {sample['expected_tool']}",
        )
        metric.measure(tc)

        results.append({
            "input": sample["input"],
            "expected_tool": sample["expected_tool"],
            "selected_tool": sample["selected_tool"],
            "correct": sample["expected_tool"] == sample["selected_tool"],
            "score": metric.score,
            "reason": getattr(metric, "reason", None),
        })

    return results


# ---------------------------------------------------------------------------
# Phase 5 — Display
# ---------------------------------------------------------------------------


def display_tool_output_results(results: list[dict[str, Any]]) -> None:
    """Print tool output evaluation results."""
    print("=" * 80)
    print("TOOL OUTPUT EVALUATION — Relevancy & Faithfulness")
    print("=" * 80)
    print()

    for i, result in enumerate(results):
        print(f"--- Sample {i + 1} ---")
        print(f"  Input        : {result['input'][:65]}")
        print(f"  Tool         : {result['tool_name']}")
        print(f"  Tool output  : {result['tool_output'][:65]}")
        print(f"  Agent output : {result['agent_output'][:65]}")
        for m in result["metrics"]:
            score = f"{m['score']:.3f}" if m["score"] is not None else "N/A"
            passed = "PASS" if m["passed"] else "FAIL"
            print(f"  {m['name']:25s}  score={score}  {passed}")
        print()


def display_tool_selection_results(results: list[dict[str, Any]]) -> None:
    """Print tool selection evaluation results."""
    print("=" * 80)
    print("TOOL SELECTION EVALUATION — GEval Accuracy")
    print("=" * 80)
    print()

    for i, result in enumerate(results):
        correct = "CORRECT" if result["correct"] else "WRONG"
        score = f"{result['score']:.3f}" if result["score"] is not None else "N/A"
        print(f"--- Sample {i + 1} ---")
        print(f"  Query    : {result['input'][:65]}")
        print(f"  Expected : {result['expected_tool']}")
        print(f"  Selected : {result['selected_tool']}  ({correct})")
        print(f"  Score    : {score}")
        print()


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    output_results = evaluate_tool_outputs()
    display_tool_output_results(output_results)

    print("\n")

    selection_results = evaluate_tool_selection()
    display_tool_selection_results(selection_results)
