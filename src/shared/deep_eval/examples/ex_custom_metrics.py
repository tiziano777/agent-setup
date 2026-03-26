"""Custom metrics with GEval example.

Demonstrates creating custom evaluation metrics using DeepEval's ``GEval``
and extending ``BaseDeepEvaluator`` for project-specific evaluation patterns.

Patterns shown:
    1. ``geval_metric()`` factory for quick custom criteria
    2. Extending ``BaseDeepEvaluator`` for reusable custom evaluators
    3. Combining built-in + custom metrics in a single evaluation

Prerequisites:
    - Infrastructure running (``make build``)
    - ``pip install -e '.[deepeval]'``

Run::

    python -m src.shared.deep_eval.examples.ex_custom_metrics
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Phase 1 — Sample data
# ---------------------------------------------------------------------------

SAMPLES: list[dict[str, str]] = [
    {
        "input": "Explain machine learning to a 10-year-old.",
        "actual_output": (
            "Machine learning is like teaching a computer to learn from examples. "
            "Imagine showing a computer lots of pictures of cats and dogs. After "
            "seeing enough pictures, it learns to tell them apart on its own!"
        ),
    },
    {
        "input": "What is quantum computing?",
        "actual_output": (
            "Quantum computing utilizes quantum-mechanical phenomena such as "
            "superposition and entanglement to perform computation. Qubits, "
            "unlike classical bits, can exist in multiple states simultaneously, "
            "enabling exponential parallelism for certain problem classes."
        ),
    },
    {
        "input": "How do I make pasta?",
        "actual_output": (
            "I'm sorry, but as an AI focused on technology topics, I cannot "
            "provide cooking instructions. Please consult a cooking resource."
        ),
    },
]


# ---------------------------------------------------------------------------
# Phase 2 — Custom metrics with geval_metric()
# ---------------------------------------------------------------------------


def build_custom_metrics() -> list[Any]:
    """Create custom GEval metrics for specific evaluation criteria."""
    from src.shared.deep_eval.metrics import geval_metric

    simplicity = geval_metric(
        name="simplicity",
        criteria=(
            "Is the response written in simple, accessible language that "
            "a non-expert could understand?"
        ),
        evaluation_steps=[
            "Check if technical jargon is used without explanation",
            "Assess if the response uses analogies or simple examples",
            "Evaluate overall readability for a general audience",
        ],
        threshold=0.5,
    )

    helpfulness = geval_metric(
        name="helpfulness",
        criteria=(
            "Does the response actually help the user accomplish their goal? "
            "A refusal with no alternative is NOT helpful."
        ),
        evaluation_steps=[
            "Determine the user's intent from the input",
            "Check if the response addresses that intent",
            "Assess if the response provides actionable information",
        ],
        threshold=0.5,
    )

    return [simplicity, helpfulness]


# ---------------------------------------------------------------------------
# Phase 3 — Custom evaluator via BaseDeepEvaluator
# ---------------------------------------------------------------------------


def build_response_quality_evaluator() -> Any:
    """Create a custom evaluator combining built-in + GEval metrics.

    Demonstrates extending ``BaseDeepEvaluator`` inline for quick
    project-specific evaluation patterns.
    """
    from src.shared.deep_eval.base import BaseDeepEvaluator
    from src.shared.deep_eval.metrics import answer_relevancy_metric, geval_metric

    class ResponseQualityEvaluator(BaseDeepEvaluator):
        """Evaluates response quality: relevancy + clarity + completeness."""

        def _setup_metrics(self, **kwargs: Any) -> None:
            self._metrics = [
                answer_relevancy_metric(model=self._model, threshold=self._threshold),
                geval_metric(
                    name="clarity",
                    criteria="Is the response well-structured and clear?",
                    model=self._model,
                    threshold=self._threshold,
                ),
                geval_metric(
                    name="completeness",
                    criteria=(
                        "Does the response fully answer the question without "
                        "leaving important aspects unaddressed?"
                    ),
                    model=self._model,
                    threshold=self._threshold,
                ),
            ]

        def create_test_case(self, **kwargs: Any) -> Any:
            from deepeval.test_case import LLMTestCase

            return LLMTestCase(
                input=kwargs["input"],
                actual_output=kwargs["actual_output"],
                expected_output=kwargs.get("expected_output"),
            )

    return ResponseQualityEvaluator(threshold=0.5)


# ---------------------------------------------------------------------------
# Phase 4 — Run evaluations
# ---------------------------------------------------------------------------


def run_geval_evaluation(
    samples: list[dict[str, str]] | None = None,
) -> list[dict[str, Any]]:
    """Run custom GEval metrics on samples."""
    from src.shared.deep_eval.test_cases import create_test_case

    if samples is None:
        samples = SAMPLES

    metrics = build_custom_metrics()
    results: list[dict[str, Any]] = []

    for sample in samples:
        tc = create_test_case(input=sample["input"], actual_output=sample["actual_output"])
        sample_results = []
        for metric in metrics:
            metric.measure(tc)
            sample_results.append({
                "metric": metric.__class__.__name__,
                "name": getattr(metric, "name", "unknown"),
                "score": metric.score,
                "reason": getattr(metric, "reason", None),
                "passed": metric.score >= 0.5,
            })
        results.append({
            "input": sample["input"],
            "output": sample["actual_output"],
            "metrics": sample_results,
        })

    return results


def run_custom_evaluator(
    samples: list[dict[str, str]] | None = None,
) -> list[list[dict[str, Any]]]:
    """Run the custom ResponseQualityEvaluator on samples."""
    if samples is None:
        samples = SAMPLES

    evaluator = build_response_quality_evaluator()
    return evaluator.evaluate_batch(samples)


# ---------------------------------------------------------------------------
# Phase 5 — Display
# ---------------------------------------------------------------------------


def display_geval_results(results: list[dict[str, Any]]) -> None:
    """Print GEval metric results."""
    print("=" * 80)
    print("CUSTOM GEVAL METRICS — simplicity & helpfulness")
    print("=" * 80)
    print()

    for i, result in enumerate(results):
        print(f"--- Sample {i + 1} ---")
        print(f"  Input  : {result['input'][:65]}")
        print(f"  Output : {result['output'][:65]}")
        for m in result["metrics"]:
            score = f"{m['score']:.3f}" if m["score"] is not None else "N/A"
            passed = "PASS" if m["passed"] else "FAIL"
            print(f"  {m['name']:20s}  score={score}  {passed}")
        print()


def display_evaluator_results(results: list[list[dict[str, Any]]]) -> None:
    """Print ResponseQualityEvaluator results."""
    print("=" * 80)
    print("CUSTOM EVALUATOR — ResponseQualityEvaluator")
    print("=" * 80)
    print()

    for i, sample_results in enumerate(results):
        print(f"--- Sample {i + 1} ---")
        for m in sample_results:
            score = f"{m['score']:.3f}" if m["score"] is not None else "N/A"
            passed = "PASS" if m["passed"] else "FAIL"
            print(f"  {m['metric']:30s}  score={score}  {passed}")
        print()


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    geval_results = run_geval_evaluation()
    display_geval_results(geval_results)

    print("\n")

    evaluator_results = run_custom_evaluator()
    display_evaluator_results(evaluator_results)
