"""Tool-use evaluation example.

Demonstrates the three **tool-use** evaluators provided by the Phoenix
evaluation toolkit:

* ``tool_selection_evaluator``   — Did the agent pick the right tool?
* ``tool_invocation_evaluator``  — Were the tool parameters correct?
* ``tool_response_evaluator``    — Did the agent handle the tool's output
                                   correctly in its final response?

Two distinct input schemas are used:

    Tool Selection / Invocation
        ``{"input": str, "available_tools": str, "tool_selection": str}``

    Tool Response Handling
        ``{"input": str, "tool_call": str, "tool_result": str, "output": str}``

All fields are **strings** — tool definitions and selections are passed
as human-readable text descriptions, not structured JSON.

The example follows four phases:
    1. Define reusable tool definitions and sample data
    2. Instantiate evaluators
    3. Run batch evaluations
    4. Inspect and display results

Prerequisites:
    - Infrastructure running (``make build``)
    - ``pip install -e '.[phoenix]'``

Run::

    python -m src.shared.evals.examples.ex_tool_use
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd

# ---------------------------------------------------------------------------
# Phase 1 — Sample data
# ---------------------------------------------------------------------------
# Tool definitions describe the tools available to the agent.
# These are passed as a single string in the "available_tools" field.
# The evaluator LLM reads this description to judge whether the agent
# made a reasonable tool choice.
# ---------------------------------------------------------------------------

# Reusable tool catalog — same tools across all samples.
TOOL_CATALOG: str = """
1. web_search(query: str) -> str
   Search the web for current information. Returns top search results
   as a text summary. Use for factual lookups, news, real-time data.

2. calculator(expression: str) -> float
   Evaluate a mathematical expression. Supports +, -, *, /, **, sqrt(),
   sin(), cos(), log(). Use for any arithmetic or math computation.

3. weather_api(city: str, country_code: str = "US") -> dict
   Get current weather for a city. Returns temperature, humidity, wind
   speed, and conditions. Use for weather-related queries.

4. file_reader(path: str) -> str
   Read the contents of a local file. Returns the file text. Use when
   the user asks about a specific file on the system.
""".strip()


# --- 1a. Tool selection / invocation samples ---
# Required keys: "input", "available_tools", "tool_selection"
#
# "tool_selection" is what the agent actually chose.  The evaluator
# judges whether that choice is correct given the query and available tools.

TOOL_SELECTION_SAMPLES: list[dict[str, str]] = [
    {
        # Correct selection — math question → calculator
        "input": "What is the square root of 144?",
        "available_tools": TOOL_CATALOG,
        "tool_selection": "calculator(expression='sqrt(144)')",
    },
    {
        # Correct selection — weather question → weather_api
        "input": "What's the weather like in Tokyo right now?",
        "available_tools": TOOL_CATALOG,
        "tool_selection": "weather_api(city='Tokyo', country_code='JP')",
    },
    {
        # Wrong selection — weather question but agent chose web_search
        "input": "What's the temperature in London today?",
        "available_tools": TOOL_CATALOG,
        "tool_selection": "web_search(query='London temperature today')",
    },
    {
        # Correct selection — factual lookup → web_search
        "input": "Who won the 2024 Nobel Prize in Physics?",
        "available_tools": TOOL_CATALOG,
        "tool_selection": "web_search(query='2024 Nobel Prize Physics winner')",
    },
]


# --- 1b. Tool response handling samples ---
# Required keys: "input", "tool_call", "tool_result", "output"
#
# "tool_call" is the tool the agent invoked (with parameters).
# "tool_result" is the raw output the tool returned.
# "output" is the agent's final response incorporating the tool result.

TOOL_RESPONSE_SAMPLES: list[dict[str, str]] = [
    {
        # Good handling — correctly interprets calculator result
        "input": "What is 15% of 250?",
        "tool_call": "calculator(expression='250 * 0.15')",
        "tool_result": "37.5",
        "output": "15% of 250 is 37.5.",
    },
    {
        # Bad handling — agent ignores tool result and makes up an answer
        "input": "What is 15% of 250?",
        "tool_call": "calculator(expression='250 * 0.15')",
        "tool_result": "37.5",
        "output": "15% of 250 is approximately 40.",
    },
    {
        # Good handling — correctly summarises weather data
        "input": "Is it raining in Paris?",
        "tool_call": "weather_api(city='Paris', country_code='FR')",
        "tool_result": (
            '{"temperature": 12, "humidity": 85, "wind_speed": 15, '
            '"conditions": "light rain"}'
        ),
        "output": (
            "Yes, it is currently raining lightly in Paris. "
            "The temperature is 12C with 85% humidity."
        ),
    },
]


# ---------------------------------------------------------------------------
# Phase 2 — Evaluator instantiation
# ---------------------------------------------------------------------------


def build_selection_evaluators() -> list:
    """Return tool selection and invocation evaluators.

    Both operate on the same schema:
        {"input", "available_tools", "tool_selection"}

    - selection: judges whether the RIGHT tool was picked
    - invocation: judges whether the PARAMETERS were correct
    """
    from src.shared.phoenix_eval import tool_invocation_evaluator, tool_selection_evaluator

    return [
        tool_selection_evaluator(),    # 1.0 = correct tool chosen
        tool_invocation_evaluator(),   # 1.0 = correct parameters
    ]


def build_response_evaluators() -> list:
    """Return the tool response handling evaluator.

    Operates on:
        {"input", "tool_call", "tool_result", "output"}
    """
    from src.shared.phoenix_eval import tool_response_evaluator

    return [
        tool_response_evaluator(),  # 1.0 = correctly used tool output
    ]


# ---------------------------------------------------------------------------
# Phase 3 — Batch evaluation
# ---------------------------------------------------------------------------
# Two separate runs because the schemas differ.
# ---------------------------------------------------------------------------


def run_selection_evaluation(
    samples: list[dict[str, str]] | None = None,
) -> "pd.DataFrame":
    """Evaluate tool selection and invocation quality.

    Returns
    -------
    pd.DataFrame
        Columns include tool_selection_eval, tool_invocation scores.
    """
    from src.shared.phoenix_eval import evaluate_batch

    if samples is None:
        samples = TOOL_SELECTION_SAMPLES

    return evaluate_batch(
        data=samples,
        evaluators=build_selection_evaluators(),
        max_retries=3,
        exit_on_error=False,
    )


def run_response_evaluation(
    samples: list[dict[str, str]] | None = None,
) -> "pd.DataFrame":
    """Evaluate how well the agent handled tool output.

    Returns
    -------
    pd.DataFrame
        Columns include tool_response_handling score.
    """
    from src.shared.phoenix_eval import evaluate_batch

    if samples is None:
        samples = TOOL_RESPONSE_SAMPLES

    return evaluate_batch(
        data=samples,
        evaluators=build_response_evaluators(),
        max_retries=3,
        exit_on_error=False,
    )


# ---------------------------------------------------------------------------
# Phase 4 — Display results
# ---------------------------------------------------------------------------


def display_selection_results(results: "pd.DataFrame") -> None:
    """Print tool selection and invocation evaluation results."""
    print("=" * 80)
    print("TOOL SELECTION & INVOCATION EVALUATION")
    print("=" * 80)
    print()

    for idx, row in results.iterrows():
        print(f"--- Sample {idx} ---")
        print(f"  Query    : {str(row['input'])[:70]}")
        print(f"  Selected : {str(row['tool_selection'])[:70]}")

        # Print all score columns (exclude input fields and *_label/*_explanation)
        for col in results.columns:
            if col.endswith(("_label", "_explanation")):
                continue
            if col in ("input", "available_tools", "tool_selection"):
                continue
            score = row.get(col, "N/A")
            label = row.get(f"{col}_label", "")
            print(f"  {col:28s}  score={score}  label={label}")
        print()


def display_response_results(results: "pd.DataFrame") -> None:
    """Print tool response handling evaluation results."""
    print("=" * 80)
    print("TOOL RESPONSE HANDLING EVALUATION")
    print("=" * 80)
    print()

    for idx, row in results.iterrows():
        print(f"--- Sample {idx} ---")
        print(f"  Query      : {str(row['input'])[:70]}")
        print(f"  Tool call  : {str(row['tool_call'])[:70]}")
        print(f"  Tool result: {str(row['tool_result'])[:70]}")
        print(f"  Output     : {str(row['output'])[:70]}")

        for col in results.columns:
            if col.endswith(("_label", "_explanation")):
                continue
            if col in ("input", "tool_call", "tool_result", "output"):
                continue
            score = row.get(col, "N/A")
            label = row.get(f"{col}_label", "")
            print(f"  {col:28s}  score={score}  label={label}")
        print()


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    sel_results = run_selection_evaluation()
    display_selection_results(sel_results)

    resp_results = run_response_evaluation()
    display_response_results(resp_results)
