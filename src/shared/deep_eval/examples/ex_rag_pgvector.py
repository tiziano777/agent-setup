"""RAG evaluation with PGVector example.

Demonstrates evaluating retrieval quality using the ``PGVectorRAGEvaluator``
which retrieves context from PostgreSQL + pgvector and runs DeepEval
contextual metrics.

Pipeline:
    1. Define sample data and expected outputs
    2. Retrieve context from PGVector table
    3. Generate responses using the LLM
    4. Evaluate with contextual metrics

Prerequisites:
    - Infrastructure running (``make build``) — includes PostgreSQL with pgvector
    - ``pip install -e '.[deepeval,pgvector]'``
    - A populated PGVector table (see ``src/shared/retrieval/``)

Run::

    python -m src.shared.deep_eval.examples.ex_rag_pgvector
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Phase 1 — Sample data
# ---------------------------------------------------------------------------

EVAL_QUERIES: list[dict[str, str]] = [
    {
        "input": "What are the advantages of PGVector over standalone vector databases?",
        "expected_output": (
            "PGVector integrates directly with PostgreSQL, combining vector "
            "search with relational queries, transactions, and existing "
            "database infrastructure."
        ),
    },
    {
        "input": "How does PGVector perform similarity search?",
        "expected_output": (
            "PGVector uses distance operators like cosine similarity (<->) "
            "to order results by vector proximity."
        ),
    },
]

# Simulated retrieval context for when PGVector is not populated.
FALLBACK_CONTEXTS: dict[str, list[str]] = {
    "What are the advantages of PGVector over standalone vector databases?": [
        "PGVector brings vector search to PostgreSQL, allowing combined "
        "relational and vector queries.",
        "Integration with PostgreSQL means ACID transactions, backup, "
        "and existing tooling work with vector data.",
        "No need for a separate vector database service in simple deployments.",
    ],
    "How does PGVector perform similarity search?": [
        "PGVector uses the <-> operator for cosine distance ordering.",
        "Vector search enables high-precision semantic retrieval.",
        "Indexing options include IVFFlat and HNSW for scalable search.",
    ],
}


# ---------------------------------------------------------------------------
# Phase 2 — Evaluate with PGVector
# ---------------------------------------------------------------------------


def run_pgvector_evaluation(
    table_name: str = "documents",
    top_k: int = 3,
    queries: list[dict[str, str]] | None = None,
) -> list[dict[str, Any]]:
    """Run RAG evaluation using PGVector retrieval.

    Falls back to simulated context if PGVector is unavailable.

    Args:
        table_name: PostgreSQL table with vector embeddings.
        top_k: Number of results to retrieve.
        queries: Evaluation queries (defaults to ``EVAL_QUERIES``).

    Returns:
        List of result dicts with metrics for each query.
    """
    from src.shared.deep_eval.rag_evaluators import PGVectorRAGEvaluator
    from src.shared.llm import get_llm

    if queries is None:
        queries = EVAL_QUERIES

    evaluator = PGVectorRAGEvaluator(table_name=table_name, top_k=top_k)
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
            "metrics": eval_results,
        })

    return results


# ---------------------------------------------------------------------------
# Phase 3 — Display
# ---------------------------------------------------------------------------


def display_results(results: list[dict[str, Any]]) -> None:
    """Print a formatted summary of PGVector RAG evaluation."""
    print("=" * 80)
    print("PGVECTOR RAG EVALUATION — DeepEval Contextual Metrics")
    print("=" * 80)
    print()

    for i, result in enumerate(results):
        print(f"--- Query {i + 1} ---")
        print(f"  Input          : {result['input'][:65]}")
        print(f"  Output         : {result['output'][:65]}")
        print(f"  Context chunks : {result['context_count']}")
        for m in result["metrics"]:
            score = f"{m['score']:.3f}" if m["score"] is not None else "N/A"
            passed = "PASS" if m["passed"] else "FAIL"
            print(f"  {m['metric']:30s}  score={score}  {passed}")
        print()


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    results = run_pgvector_evaluation()
    display_results(results)
