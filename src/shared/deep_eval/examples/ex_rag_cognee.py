"""RAG evaluation with Cognee knowledge graph example.

Demonstrates evaluating retrieval quality using the ``CogneeRAGEvaluator``
which retrieves context from Cognee's semantic knowledge graph and runs
DeepEval contextual metrics (recall, precision, relevancy).

Pipeline:
    1. Ingest sample data into Cognee
    2. Retrieve context for evaluation queries
    3. Generate responses using the LLM
    4. Evaluate with contextual metrics
    5. Display results

Prerequisites:
    - Infrastructure running (``make build``) — includes Neo4j for Cognee
    - ``pip install -e '.[deepeval,cognee]'``

Run::

    python -m src.shared.deep_eval.examples.ex_rag_cognee
"""

from __future__ import annotations

import asyncio
from typing import Any

# ---------------------------------------------------------------------------
# Phase 1 — Sample data
# ---------------------------------------------------------------------------

SAMPLE_DOCUMENTS: list[str] = [
    "LangGraph is a framework for building stateful, multi-actor applications "
    "with LLMs, built on top of LangChain. It uses a graph-based approach where "
    "nodes represent computation steps and edges represent transitions.",
    "LangGraph supports persistence through checkpointers, enabling long-running "
    "conversations and workflows. It provides both StateGraph and MessageGraph APIs "
    "for different use cases.",
    "The ReAct pattern in LangGraph combines reasoning and acting by allowing "
    "agents to think step by step and use tools to gather information before "
    "generating a final response.",
]

EVAL_QUERIES: list[dict[str, str]] = [
    {
        "input": "What is LangGraph and how does it work?",
        "expected_output": (
            "LangGraph is a framework for building stateful, multi-actor "
            "applications with LLMs. It uses a graph-based approach with nodes "
            "and edges."
        ),
    },
    {
        "input": "How does LangGraph handle persistence?",
        "expected_output": (
            "LangGraph supports persistence through checkpointers for "
            "long-running conversations and workflows."
        ),
    },
]


# ---------------------------------------------------------------------------
# Phase 2 — Ingest and retrieve
# ---------------------------------------------------------------------------


async def ingest_documents(documents: list[str]) -> None:
    """Ingest documents into Cognee knowledge graph."""
    from src.shared.cognee_toolkit import get_cognee_memory

    memory = get_cognee_memory()
    for doc in documents:
        await memory.add(doc)
    await memory.cognify()


async def retrieve_and_evaluate(
    queries: list[dict[str, str]] | None = None,
) -> list[dict[str, Any]]:
    """Retrieve context from Cognee and evaluate with DeepEval.

    Returns list of result dicts with metrics for each query.
    """
    from src.shared.deep_eval.llm_bridge import get_deepeval_model
    from src.shared.deep_eval.rag_evaluators import CogneeRAGEvaluator
    from src.shared.llm import get_llm

    if queries is None:
        queries = EVAL_QUERIES

    evaluator = CogneeRAGEvaluator()
    llm = get_llm(temperature=0.0)

    # Use the LiteLLMModel for display
    _model = get_deepeval_model()
    print(f"Using model: {_model.model}")
    print()

    results: list[dict[str, Any]] = []
    for query in queries:
        # Retrieve context from Cognee
        context = await evaluator.retrieve_context(query["input"])

        # Generate response using the LLM
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
    """Print a formatted summary of Cognee RAG evaluation."""
    print("=" * 80)
    print("COGNEE RAG EVALUATION — DeepEval Contextual Metrics")
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


async def main() -> None:
    print("Ingesting documents into Cognee...\n")
    await ingest_documents(SAMPLE_DOCUMENTS)

    print("Retrieving context and evaluating...\n")
    results = await retrieve_and_evaluate()
    display_results(results)


if __name__ == "__main__":
    asyncio.run(main())
