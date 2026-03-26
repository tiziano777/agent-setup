"""RAG evaluation with Qdrant vector search example.

Demonstrates evaluating retrieval quality using the ``QdrantRAGEvaluator``
which retrieves context from Qdrant and runs DeepEval contextual metrics.

Pipeline:
    1. Define sample data and expected outputs
    2. Retrieve context from Qdrant collection
    3. Generate responses using the LLM
    4. Evaluate with contextual metrics
    5. Compare different top_k values

Prerequisites:
    - Infrastructure running (``make build``) — includes Qdrant
    - ``pip install -e '.[deepeval,qdrant]'``
    - A populated Qdrant collection (see ``src/shared/retrieval/``)

Run::

    python -m src.shared.deep_eval.examples.ex_rag_qdrant
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Phase 1 — Sample data
# ---------------------------------------------------------------------------

EVAL_QUERIES: list[dict[str, str]] = [
    {
        "input": "How does Qdrant handle vector indexing?",
        "expected_output": (
            "Qdrant uses HNSW (Hierarchical Navigable Small World) for "
            "efficient high-dimensional vector indexing."
        ),
    },
    {
        "input": "What storage options does Qdrant support?",
        "expected_output": (
            "Qdrant supports disk-based storage for handling large datasets "
            "alongside in-memory storage for faster search."
        ),
    },
]

# Simulated retrieval context (used when Qdrant is not populated).
FALLBACK_CONTEXTS: dict[str, list[str]] = {
    "How does Qdrant handle vector indexing?": [
        "Qdrant is a vector database optimized for fast similarity search.",
        "It uses HNSW for efficient high-dimensional vector indexing.",
        "HNSW provides logarithmic search complexity with high recall.",
    ],
    "What storage options does Qdrant support?": [
        "Qdrant supports disk-based storage for handling large datasets.",
        "In-memory mode provides fastest search performance.",
        "Hybrid storage combines speed with capacity.",
    ],
}


# ---------------------------------------------------------------------------
# Phase 2 — Evaluate with Qdrant
# ---------------------------------------------------------------------------


def run_qdrant_evaluation(
    collection_name: str = "documents",
    top_k: int = 3,
    queries: list[dict[str, str]] | None = None,
) -> list[dict[str, Any]]:
    """Run RAG evaluation using Qdrant retrieval.

    Falls back to simulated context if Qdrant is unavailable.

    Args:
        collection_name: Qdrant collection to search.
        top_k: Number of results to retrieve.
        queries: Evaluation queries (defaults to ``EVAL_QUERIES``).

    Returns:
        List of result dicts with metrics for each query.
    """
    from src.shared.deep_eval.rag_evaluators import QdrantRAGEvaluator
    from src.shared.llm import get_llm

    if queries is None:
        queries = EVAL_QUERIES

    evaluator = QdrantRAGEvaluator(collection_name=collection_name, top_k=top_k)
    llm = get_llm(temperature=0.0)

    results: list[dict[str, Any]] = []
    for query in queries:
        # Try real retrieval; fall back to simulated context
        try:
            context = evaluator.retrieve_context(query["input"], top_k=top_k)
        except Exception:
            context = FALLBACK_CONTEXTS.get(query["input"], ["No context available."])

        # Generate response
        prompt = (
            f"Answer the user question based on the context.\n\n"
            f"Context: {' '.join(context)}\n\n"
            f"Question: {query['input']}"
        )
        response = llm.invoke(prompt)
        actual_output = response.content

        # Evaluate
        eval_results = evaluator.evaluate(
            input=query["input"],
            actual_output=actual_output,
            expected_output=query.get("expected_output"),
            retrieval_context=context,
        )
        results.append({
            "input": query["input"],
            "output": actual_output,
            "context_count": len(context),
            "top_k": top_k,
            "metrics": eval_results,
        })

    return results


# ---------------------------------------------------------------------------
# Phase 3 — Compare top_k values
# ---------------------------------------------------------------------------


def compare_top_k(top_k_values: list[int] | None = None) -> dict[int, list[dict[str, Any]]]:
    """Compare evaluation results across different top_k values.

    Returns dict mapping top_k -> results list.
    """
    if top_k_values is None:
        top_k_values = [1, 3, 5]

    all_results: dict[int, list[dict[str, Any]]] = {}
    for k in top_k_values:
        print(f"Evaluating with top_k={k}...")
        all_results[k] = run_qdrant_evaluation(top_k=k)

    return all_results


# ---------------------------------------------------------------------------
# Phase 4 — Display
# ---------------------------------------------------------------------------


def display_results(results: list[dict[str, Any]], title: str = "") -> None:
    """Print a formatted summary of Qdrant RAG evaluation."""
    header = title or "QDRANT RAG EVALUATION — DeepEval Contextual Metrics"
    print("=" * 80)
    print(header)
    print("=" * 80)
    print()

    for i, result in enumerate(results):
        print(f"--- Query {i + 1} (top_k={result.get('top_k', 'N/A')}) ---")
        print(f"  Input          : {result['input'][:65]}")
        print(f"  Output         : {result['output'][:65]}")
        print(f"  Context chunks : {result['context_count']}")
        for m in result["metrics"]:
            score = f"{m['score']:.3f}" if m["score"] is not None else "N/A"
            passed = "PASS" if m["passed"] else "FAIL"
            print(f"  {m['metric']:30s}  score={score}  {passed}")
        print()


def display_comparison(all_results: dict[int, list[dict[str, Any]]]) -> None:
    """Print a comparison of results across top_k values."""
    print("=" * 80)
    print("TOP_K COMPARISON — Impact on Contextual Metrics")
    print("=" * 80)
    print()

    for k, results in sorted(all_results.items()):
        avg_scores: dict[str, list[float]] = {}
        for result in results:
            for m in result["metrics"]:
                if m["score"] is not None:
                    avg_scores.setdefault(m["metric"], []).append(m["score"])

        print(f"  top_k={k}:")
        for metric_name, scores in avg_scores.items():
            avg = sum(scores) / len(scores)
            print(f"    {metric_name:30s}  avg={avg:.3f}")
        print()


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    results = run_qdrant_evaluation()
    display_results(results)

    print("\n")
    all_results = compare_top_k()
    display_comparison(all_results)
