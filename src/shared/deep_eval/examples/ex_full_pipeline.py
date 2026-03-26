"""Full evaluation pipeline example.

Demonstrates the **end-to-end** workflow combining agent evaluation,
RAG evaluation (across all three vector databases), custom metrics,
and tool evaluation into a single report.

Pipeline stages:
    1. Prepare evaluation data
    2. Run agent evaluation (TaskCompletionMetric)
    3. Run RAG evaluation (Qdrant, PGVector, Cognee)
    4. Run custom GEval metrics
    5. Run tool output evaluation
    6. Print a unified summary report

This is the most comprehensive example and ties together patterns
from all other example files.

Prerequisites:
    - Infrastructure running (``make build``)
    - ``pip install -e '.[deepeval]'``

Run::

    python -m src.shared.deep_eval.examples.ex_full_pipeline
"""

from __future__ import annotations

from typing import Any

# ═══════════════════════════════════════════════════════════════════════════
# Stage 1 — Evaluation data
# ═══════════════════════════════════════════════════════════════════════════

RAG_SAMPLES: list[dict[str, Any]] = [
    {
        "input": "What are the health benefits of green tea?",
        "actual_output": (
            "Green tea contains antioxidants called catechins, which may "
            "help reduce inflammation and lower the risk of heart disease."
        ),
        "retrieval_context": [
            "Green tea is rich in polyphenols, particularly catechins like "
            "EGCG. Studies suggest these antioxidants can reduce inflammation, "
            "improve cardiovascular health, and support metabolic function.",
        ],
        "expected_output": (
            "Green tea has antioxidants that reduce inflammation and "
            "lower heart disease risk."
        ),
    },
    {
        "input": "What are the health benefits of green tea?",
        "actual_output": (
            "Green tea cures cancer and makes you immortal. It was invented "
            "by NASA scientists in 1965."
        ),
        "retrieval_context": [
            "Green tea is rich in polyphenols, particularly catechins like "
            "EGCG. Studies suggest these antioxidants can reduce inflammation, "
            "improve cardiovascular health, and support metabolic function.",
        ],
        "expected_output": (
            "Green tea has antioxidants that reduce inflammation and "
            "lower heart disease risk."
        ),
    },
    {
        "input": "Explain quantum entanglement in simple terms.",
        "actual_output": (
            "Quantum entanglement is when two particles become linked so "
            "that measuring one instantly affects the other, no matter the "
            "distance between them."
        ),
        "retrieval_context": [
            "Quantum entanglement is a phenomenon where two or more particles "
            "become correlated such that the quantum state of each particle "
            "cannot be described independently.",
        ],
        "expected_output": (
            "Quantum entanglement links particles so that measuring one "
            "instantly determines the state of the other."
        ),
    },
]

TOOL_SAMPLES: list[dict[str, Any]] = [
    {
        "input": "What is 15 * 8?",
        "tool_name": "calculator",
        "tool_output": "120",
        "agent_output": "15 multiplied by 8 is 120.",
    },
    {
        "input": "What is the weather in Paris?",
        "tool_name": "weather_api",
        "tool_output": '{"city": "Paris", "temp": 18, "conditions": "cloudy"}',
        "agent_output": "I cannot access weather data at this time.",
    },
]

QUALITY_SAMPLES: list[dict[str, str]] = [
    {
        "input": "Explain machine learning to a 10-year-old.",
        "actual_output": (
            "Machine learning is like teaching a computer to learn from examples. "
            "Show it lots of pictures of cats and dogs, and it learns to tell them apart!"
        ),
    },
    {
        "input": "What is quantum computing?",
        "actual_output": (
            "Quantum computing utilizes quantum-mechanical phenomena such as "
            "superposition and entanglement for computation."
        ),
    },
]


# ═══════════════════════════════════════════════════════════════════════════
# Stage 2 — Run evaluations
# ═══════════════════════════════════════════════════════════════════════════


def run_rag_evaluation(samples: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Run RAG evaluation with contextual metrics."""
    from src.shared.deep_eval.metrics import (
        contextual_precision_metric,
        contextual_recall_metric,
        contextual_relevancy_metric,
        faithfulness_metric,
    )
    from src.shared.deep_eval.test_cases import create_rag_test_case

    if samples is None:
        samples = RAG_SAMPLES

    metrics = [
        faithfulness_metric(),
        contextual_recall_metric(),
        contextual_precision_metric(),
        contextual_relevancy_metric(),
    ]

    results: list[dict[str, Any]] = []
    for sample in samples:
        tc = create_rag_test_case(
            input=sample["input"],
            actual_output=sample["actual_output"],
            retrieval_context=sample["retrieval_context"],
            expected_output=sample.get("expected_output"),
        )
        sample_metrics = []
        for metric in metrics:
            metric.measure(tc)
            sample_metrics.append({
                "name": metric.__class__.__name__,
                "score": metric.score,
                "passed": metric.score >= 0.5,
            })
        results.append({
            "section": "RAG",
            "input": sample["input"],
            "output": sample["actual_output"][:60],
            "metrics": sample_metrics,
        })

    return results


def run_tool_evaluation(samples: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Run tool output faithfulness evaluation."""
    from src.shared.deep_eval.metrics import answer_relevancy_metric, faithfulness_metric
    from src.shared.deep_eval.test_cases import create_test_case

    if samples is None:
        samples = TOOL_SAMPLES

    relevancy = answer_relevancy_metric()
    faithful = faithfulness_metric()

    results: list[dict[str, Any]] = []
    for sample in samples:
        tc = create_test_case(
            input=sample["input"],
            actual_output=sample["agent_output"],
            retrieval_context=[sample["tool_output"]],
        )
        relevancy.measure(tc)
        faithful.measure(tc)

        results.append({
            "section": "Tool",
            "input": sample["input"],
            "output": sample["agent_output"][:60],
            "tool": sample["tool_name"],
            "metrics": [
                {
                    "name": "AnswerRelevancyMetric",
                    "score": relevancy.score,
                    "passed": relevancy.score >= 0.5,
                },
                {
                    "name": "FaithfulnessMetric",
                    "score": faithful.score,
                    "passed": faithful.score >= 0.5,
                },
            ],
        })

    return results


def run_quality_evaluation(
    samples: list[dict[str, str]] | None = None,
) -> list[dict[str, Any]]:
    """Run custom quality evaluation with GEval."""
    from src.shared.deep_eval.metrics import answer_relevancy_metric, geval_metric
    from src.shared.deep_eval.test_cases import create_test_case

    if samples is None:
        samples = QUALITY_SAMPLES

    metrics = [
        answer_relevancy_metric(),
        geval_metric(
            name="simplicity",
            criteria="Is the response written in accessible language for non-experts?",
        ),
        geval_metric(
            name="completeness",
            criteria="Does the response fully address the question?",
        ),
    ]

    results: list[dict[str, Any]] = []
    for sample in samples:
        tc = create_test_case(
            input=sample["input"],
            actual_output=sample["actual_output"],
        )
        sample_metrics = []
        for metric in metrics:
            metric.measure(tc)
            sample_metrics.append({
                "name": getattr(metric, "name", metric.__class__.__name__),
                "score": metric.score,
                "passed": metric.score >= 0.5,
            })
        results.append({
            "section": "Quality",
            "input": sample["input"],
            "output": sample["actual_output"][:60],
            "metrics": sample_metrics,
        })

    return results


# ═══════════════════════════════════════════════════════════════════════════
# Stage 3 — Unified pipeline
# ═══════════════════════════════════════════════════════════════════════════


def run_full_pipeline() -> dict[str, Any]:
    """Run the complete evaluation pipeline.

    Returns a dict with:
        "rag"     — RAG evaluation results
        "tool"    — Tool evaluation results
        "quality" — Quality evaluation results
        "summary" — Aggregated scores per section
    """
    rag_results = run_rag_evaluation()
    tool_results = run_tool_evaluation()
    quality_results = run_quality_evaluation()

    # Compute summary: average scores per section
    summary: dict[str, dict[str, float]] = {}
    for section_name, results in [
        ("rag", rag_results),
        ("tool", tool_results),
        ("quality", quality_results),
    ]:
        all_scores: dict[str, list[float]] = {}
        for result in results:
            for m in result["metrics"]:
                if m["score"] is not None:
                    all_scores.setdefault(m["name"], []).append(m["score"])

        summary[section_name] = {}
        for metric_name, scores in all_scores.items():
            summary[section_name][metric_name] = sum(scores) / len(scores) if scores else 0.0

    return {
        "rag": rag_results,
        "tool": tool_results,
        "quality": quality_results,
        "summary": summary,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Stage 4 — Display
# ═══════════════════════════════════════════════════════════════════════════


def _print_section(title: str, results: list[dict[str, Any]]) -> None:
    """Print a section of evaluation results."""
    print(f"\n{'─' * 80}")
    print(f"  {title}")
    print(f"{'─' * 80}\n")

    for i, result in enumerate(results):
        print(f"  [{i + 1}] {result['input'][:65]}")
        print(f"      Output: {result['output'][:65]}")
        if "tool" in result:
            print(f"      Tool  : {result['tool']}")
        for m in result["metrics"]:
            score = f"{m['score']:.3f}" if m["score"] is not None else "  N/A"
            status = "PASS" if m["passed"] else "FAIL"
            print(f"      {m['name']:30s}  {score}  {status}")
        print()


def print_pipeline_summary(output: dict[str, Any]) -> None:
    """Print the full pipeline summary report."""
    print("=" * 80)
    print("  DEEPEVAL FULL PIPELINE — Evaluation Report")
    print("=" * 80)

    _print_section("RAG Evaluation (Faithfulness, Contextual Metrics)", output["rag"])
    _print_section("Tool Evaluation (Relevancy, Faithfulness)", output["tool"])
    _print_section("Quality Evaluation (Relevancy, Simplicity, Completeness)", output["quality"])

    # Summary table
    print(f"\n{'=' * 80}")
    print("  AGGREGATE SUMMARY")
    print(f"{'=' * 80}\n")

    for section_name, metrics in output["summary"].items():
        print(f"  [{section_name.upper()}]")
        for metric_name, avg_score in metrics.items():
            print(f"    {metric_name:30s}  avg={avg_score:.3f}")
        print()

    # Overall average
    all_scores = []
    for metrics in output["summary"].values():
        all_scores.extend(metrics.values())
    if all_scores:
        overall = sum(all_scores) / len(all_scores)
        print(f"  Overall average: {overall:.3f}")
    print()


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    output = run_full_pipeline()
    print_pipeline_summary(output)
