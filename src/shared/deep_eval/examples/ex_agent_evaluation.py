"""End-to-end LangGraph agent evaluation example.

Demonstrates evaluating a LangGraph ReAct agent with tools using
DeepEval's ``TaskCompletionMetric`` via the ``AgentEvaluator`` class.

Pipeline:
    1. Define tools (weather, calculator)
    2. Build a LangGraph ReAct agent
    3. Evaluate with ``AgentEvaluator`` (sync)
    4. Display results

Prerequisites:
    - Infrastructure running (``make build``)
    - ``pip install -e '.[deepeval]'``

Run::

    python -m src.shared.deep_eval.examples.ex_agent_evaluation
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Phase 1 — Define tools
# ---------------------------------------------------------------------------


def get_weather(city: str) -> str:
    """Returns the weather in a city."""
    return f"It's 22°C and sunny in {city}."


def calculator(expression: str) -> str:
    """Evaluate a mathematical expression."""
    try:
        result = eval(expression)  # noqa: S307
        return str(result)
    except Exception as e:
        return f"Error: {e}"


# ---------------------------------------------------------------------------
# Phase 2 — Build agent
# ---------------------------------------------------------------------------


def build_demo_agent() -> Any:
    """Build a simple ReAct agent with weather and calculator tools.

    Returns a compiled LangGraph graph ready for invocation.
    """
    from langchain_core.tools import tool
    from langgraph.prebuilt import create_react_agent

    from src.shared.llm import get_llm

    @tool
    def weather_tool(city: str) -> str:
        """Get current weather for a city."""
        return get_weather(city)

    @tool
    def calc_tool(expression: str) -> str:
        """Evaluate a math expression."""
        return calculator(expression)

    llm = get_llm(temperature=0.0)
    agent = create_react_agent(
        model=llm,
        tools=[weather_tool, calc_tool],
        prompt="You are a helpful assistant with access to weather and calculator tools.",
    )
    return agent


# ---------------------------------------------------------------------------
# Phase 3 — Evaluate
# ---------------------------------------------------------------------------

EVAL_INPUTS: list[str] = [
    "What is the weather in Paris, France?",
    "What is 15 multiplied by 8?",
    "What's the temperature in Tokyo right now?",
]


def run_agent_evaluation(
    inputs: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Run agent evaluation with TaskCompletionMetric.

    Returns list of result dicts with input, output, and metric scores.
    """
    from src.shared.deep_eval.agent_evaluators import AgentEvaluator
    from src.shared.deep_eval.metrics import task_completion_metric

    if inputs is None:
        inputs = EVAL_INPUTS

    agent = build_demo_agent()
    evaluator = AgentEvaluator(
        graph=agent,
        metrics=[task_completion_metric()],
    )
    return evaluator.evaluate(inputs)


# ---------------------------------------------------------------------------
# Phase 4 — Display
# ---------------------------------------------------------------------------


def display_results(results: list[dict[str, Any]]) -> None:
    """Print a formatted summary of agent evaluation results."""
    print("=" * 80)
    print("LANGGRAPH AGENT EVALUATION — DeepEval TaskCompletionMetric")
    print("=" * 80)
    print()

    for i, result in enumerate(results):
        print(f"--- Test {i + 1} ---")
        print(f"  Input  : {result['input'][:70]}")
        print(f"  Output : {result['output'][:70]}")
        for m in result["metrics"]:
            score = f"{m['score']:.3f}" if m["score"] is not None else "N/A"
            print(f"  {m['name']:30s}  score={score}")
            if m.get("reason"):
                print(f"  {'':30s}  reason={m['reason'][:60]}")
        print()


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    results = run_agent_evaluation()
    display_results(results)
