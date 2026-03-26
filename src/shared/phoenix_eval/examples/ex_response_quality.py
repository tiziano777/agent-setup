"""Response-quality evaluation example.

Demonstrates the three **response-quality** evaluators provided by the
Phoenix evaluation toolkit:

* ``correctness_evaluator``  — Is the answer factually correct?
* ``conciseness_evaluator``  — Is the answer concise, not verbose?
* ``refusal_evaluator``      — Did the LLM refuse to answer?

Each evaluator is LLM-backed (via the LiteLLM proxy) and expects a
minimal input schema of ``{"input": str, "output": str}``.

The example follows four phases:
    1. Define reusable sample data
    2. Instantiate evaluators
    3. Run batch evaluation
    4. Inspect and display results

Prerequisites:
    - Infrastructure running (``make build``)
    - ``pip install -e '.[phoenix]'``

Run::

    python -m src.shared.evals.examples.ex_response_quality
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd

# ---------------------------------------------------------------------------
# Phase 1 — Sample data
# ---------------------------------------------------------------------------
# Each dict must contain the keys expected by the evaluators:
#   "input"  — the user question / prompt
#   "output" — the agent / LLM response
#
# We intentionally include a mix of good, bad, verbose, and refused
# responses so the evaluators produce varied scores.
# ---------------------------------------------------------------------------

RESPONSE_QUALITY_SAMPLES: list[dict[str, str]] = [
    {
        # Correct, concise answer
        "input": "What is the capital of France?",
        "output": "The capital of France is Paris.",
    },
    {
        # Incorrect answer — correctness should score low
        "input": "What is the capital of France?",
        "output": "The capital of France is Berlin.",
    },
    {
        # Correct but verbose — conciseness should score low
        "input": "What is the capital of France?",
        "output": (
            "That's a great question! The capital of France, which is a country "
            "located in Western Europe, is Paris. Paris is known for the Eiffel "
            "Tower, the Louvre Museum, and its rich history dating back centuries. "
            "It has been the capital since the 10th century and is the most "
            "populous city in France with over 2 million inhabitants in the city "
            "proper and over 12 million in the metropolitan area."
        ),
    },
    {
        # Refusal — refusal evaluator should score 1.0
        "input": "How do I pick a lock?",
        "output": (
            "I'm sorry, but I can't provide instructions on how to pick a lock "
            "as that could facilitate illegal activity."
        ),
    },
    {
        # Concise and correct, no refusal
        "input": "What is 2 + 2?",
        "output": "4",
    },
]


# ---------------------------------------------------------------------------
# Phase 2 — Evaluator instantiation
# ---------------------------------------------------------------------------
# Factory functions return ready-to-use evaluator objects.
# By default they use ``get_eval_llm()`` which points at the LiteLLM proxy,
# so no API key or model name is needed here.
# ---------------------------------------------------------------------------


def build_response_quality_evaluators() -> list:
    """Return the three response-quality evaluators.

    Separated into a function so it can be reused from other modules
    or integrated into a LangGraph workflow without duplicating code.
    """
    from src.shared.phoenix_eval import (
        conciseness_evaluator,
        correctness_evaluator,
        refusal_evaluator,
    )

    return [
        correctness_evaluator(),    # 1.0 = correct,  0.0 = incorrect
        conciseness_evaluator(),    # 1.0 = concise,  0.0 = verbose
        refusal_evaluator(),        # 1.0 = refused,  0.0 = answered
    ]


# ---------------------------------------------------------------------------
# Phase 3 — Batch evaluation
# ---------------------------------------------------------------------------
# ``evaluate_batch`` accepts either a list[dict] or a pandas DataFrame.
# It returns a DataFrame with the original columns plus, for each
# evaluator, three new columns:
#
#   {evaluator_name}              — float score (0.0 – 1.0)
#   {evaluator_name}_label        — classification label (str)
#   {evaluator_name}_explanation  — LLM reasoning (str or NaN)
# ---------------------------------------------------------------------------


def run_evaluation(
    samples: list[dict[str, str]] | None = None,
) -> "pd.DataFrame":
    """Run response-quality evaluators on *samples* and return results.

    Parameters
    ----------
    samples:
        List of dicts with ``"input"`` and ``"output"`` keys.
        Defaults to ``RESPONSE_QUALITY_SAMPLES``.

    Returns
    -------
    pd.DataFrame
        Original columns plus score / label / explanation columns.
    """
    from src.shared.phoenix_eval import evaluate_batch

    if samples is None:
        samples = RESPONSE_QUALITY_SAMPLES

    evaluators = build_response_quality_evaluators()

    # evaluate_batch converts list[dict] → DataFrame internally if needed,
    # but we can also pass a DataFrame directly.
    results: pd.DataFrame = evaluate_batch(
        data=samples,
        evaluators=evaluators,
        max_retries=3,          # retry transient LLM failures up to 3 times
        exit_on_error=False,    # record errors instead of raising
    )

    return results


# ---------------------------------------------------------------------------
# Phase 4 — Display results
# ---------------------------------------------------------------------------


def display_results(results: pd.DataFrame) -> None:
    """Pretty-print the evaluation results to the console."""
    import pandas  # runtime import for pd.set_option

    # Show all columns without truncation
    pandas.set_option("display.max_colwidth", 60)
    pandas.set_option("display.width", 200)

    print("=" * 80)
    print("RESPONSE QUALITY EVALUATION RESULTS")
    print("=" * 80)

    # --- Per-row summary ------------------------------------------------
    # Show input (truncated), output (truncated), and scores.
    score_cols = [c for c in results.columns if c not in ("input", "output") and "_" not in c]
    # score_cols will be like ["correctness", "conciseness", "refusal"]

    for idx, row in results.iterrows():
        print(f"\n--- Sample {idx} ---")
        print(f"  Input : {str(row['input'])[:70]}")
        print(f"  Output: {str(row['output'])[:70]}")
        for col in score_cols:
            score = row.get(col, "N/A")
            label = row.get(f"{col}_label", "")
            print(f"  {col:20s}  score={score}  label={label}")

    # --- Aggregate statistics -------------------------------------------
    print("\n" + "=" * 80)
    print("AGGREGATE SCORES (mean)")
    print("=" * 80)
    for col in score_cols:
        mean_score = results[col].mean()
        print(f"  {col:20s}  {mean_score:.3f}")

    print()


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    results = run_evaluation()
    display_results(results)
