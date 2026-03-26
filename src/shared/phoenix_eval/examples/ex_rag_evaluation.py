"""RAG (Retrieval-Augmented Generation) evaluation example.

Demonstrates the **RAG / Retrieval** evaluators provided by the Phoenix
evaluation toolkit:

* ``faithfulness_evaluator``         — Is the response faithful to the
                                       retrieved context?  (1.0 = faithful)
* ``hallucination_evaluator``        — Does the response contain info NOT
                                       in the context?  (1.0 = hallucinated)
                                       **Deprecated** — prefer faithfulness.
* ``document_relevance_evaluator``   — Is the retrieved document relevant
                                       to the user query?  (1.0 = relevant)

Two distinct input schemas are used:

    Faithfulness / Hallucination
        ``{"input": str, "output": str, "context": str}``

    Document Relevance
        ``{"input": str, "document_text": str}``

The example follows four phases:
    1. Define reusable sample data (separate per schema)
    2. Instantiate evaluators
    3. Run batch evaluations
    4. Inspect and compare results

Prerequisites:
    - Infrastructure running (``make build``)
    - ``pip install -e '.[phoenix]'``

Run::

    python -m src.shared.evals.examples.ex_rag_evaluation
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd

# ---------------------------------------------------------------------------
# Phase 1 — Sample data
# ---------------------------------------------------------------------------
# Two separate datasets are needed because the evaluators expect different
# schemas.  Mixing schemas in one dataset would cause KeyError at eval time.
# ---------------------------------------------------------------------------

# --- 1a. Faithfulness / Hallucination samples ---
# Required keys: "input", "output", "context"
#
# "context" represents the retrieved passages the agent was grounded on.
# A faithful response only uses information present in the context.
# A hallucinated response introduces facts NOT in the context.

RAG_FAITHFULNESS_SAMPLES: list[dict[str, str]] = [
    {
        # Faithful answer — everything in the output comes from context
        "input": "When was the Eiffel Tower built?",
        "output": "The Eiffel Tower was built between 1887 and 1889.",
        "context": (
            "The Eiffel Tower is a wrought-iron lattice tower in Paris. "
            "Construction began in January 1887 and was completed on "
            "March 31, 1889. It was built as the entrance arch for the "
            "1889 World's Fair."
        ),
    },
    {
        # Hallucinated answer — the output claims 300m, but context says 330m
        "input": "How tall is the Eiffel Tower?",
        "output": "The Eiffel Tower is exactly 300 meters tall and was painted red.",
        "context": (
            "The Eiffel Tower stands 330 metres (1,083 ft) tall and is "
            "painted in three shades of brown, with the lightest at the top."
        ),
    },
    {
        # Partially faithful — some info from context, some fabricated
        "input": "Who designed the Eiffel Tower?",
        "output": (
            "The Eiffel Tower was designed by Gustave Eiffel's company. "
            "It took exactly 200 workers to build it."
        ),
        "context": (
            "The tower was designed by Gustave Eiffel's engineering company. "
            "About 300 workers joined 18,038 pieces of iron using 2.5 million "
            "rivets during construction."
        ),
    },
]

# --- 1b. Document relevance samples ---
# Required keys: "input", "document_text"
#
# "document_text" is the content of a single retrieved document/chunk.
# The evaluator judges whether this document is relevant to the query.

RAG_RELEVANCE_SAMPLES: list[dict[str, str]] = [
    {
        # Relevant document
        "input": "What are the visiting hours of the Eiffel Tower?",
        "document_text": (
            "The Eiffel Tower is open daily. Summer hours (June 15 to "
            "September 1) are 9:00 AM to 12:45 AM. The rest of the year, "
            "hours are 9:30 AM to 11:45 PM. Last admission is 45 minutes "
            "before closing."
        ),
    },
    {
        # Irrelevant document — talks about a completely different topic
        "input": "What are the visiting hours of the Eiffel Tower?",
        "document_text": (
            "Python is a high-level, general-purpose programming language. "
            "Its design philosophy emphasizes code readability with the use "
            "of significant indentation."
        ),
    },
    {
        # Marginally relevant — same topic but doesn't answer the question
        "input": "What are the visiting hours of the Eiffel Tower?",
        "document_text": (
            "The Eiffel Tower was originally intended to be a temporary "
            "structure, built for the 1889 World's Fair. It was almost "
            "demolished in 1909 but was saved because of its usefulness "
            "as a radio transmission tower."
        ),
    },
]


# ---------------------------------------------------------------------------
# Phase 2 — Evaluator instantiation
# ---------------------------------------------------------------------------


def build_faithfulness_evaluators() -> list:
    """Return faithfulness + hallucination evaluators for comparison.

    Both evaluate the same data schema but score in opposite directions:
        - faithfulness: 1.0 = faithful (good)
        - hallucination: 1.0 = hallucinated (bad)

    faithfulness_evaluator is the recommended one; hallucination_evaluator
    is included here for educational comparison only.
    """
    from src.shared.phoenix_eval import faithfulness_evaluator, hallucination_evaluator

    return [
        faithfulness_evaluator(),    # 1.0 = faithful (GOOD)
        hallucination_evaluator(),   # 1.0 = hallucinated (BAD)  [deprecated]
    ]


def build_relevance_evaluators() -> list:
    """Return the document-relevance evaluator."""
    from src.shared.phoenix_eval import document_relevance_evaluator

    return [
        document_relevance_evaluator(),  # 1.0 = relevant, 0.0 = unrelated
    ]


# ---------------------------------------------------------------------------
# Phase 3 — Batch evaluation
# ---------------------------------------------------------------------------
# We run TWO separate evaluations because the schemas differ.
# Trying to run document_relevance on faithfulness data (or vice versa)
# would fail due to missing columns.
# ---------------------------------------------------------------------------


def run_faithfulness_evaluation(
    samples: list[dict[str, str]] | None = None,
) -> "pd.DataFrame":
    """Evaluate faithfulness and hallucination on RAG samples.

    Parameters
    ----------
    samples:
        Dicts with ``"input"``, ``"output"``, ``"context"`` keys.
        Defaults to ``RAG_FAITHFULNESS_SAMPLES``.

    Returns
    -------
    pd.DataFrame
        Columns: input, output, context, faithfulness, hallucination, ...
    """
    from src.shared.phoenix_eval import evaluate_batch

    if samples is None:
        samples = RAG_FAITHFULNESS_SAMPLES

    return evaluate_batch(
        data=samples,
        evaluators=build_faithfulness_evaluators(),
        max_retries=3,
        exit_on_error=False,
    )


def run_relevance_evaluation(
    samples: list[dict[str, str]] | None = None,
) -> "pd.DataFrame":
    """Evaluate document relevance on retrieval samples.

    Parameters
    ----------
    samples:
        Dicts with ``"input"`` and ``"document_text"`` keys.
        Defaults to ``RAG_RELEVANCE_SAMPLES``.

    Returns
    -------
    pd.DataFrame
        Columns: input, document_text, document_relevance, ...
    """
    from src.shared.phoenix_eval import evaluate_batch

    if samples is None:
        samples = RAG_RELEVANCE_SAMPLES

    return evaluate_batch(
        data=samples,
        evaluators=build_relevance_evaluators(),
        max_retries=3,
        exit_on_error=False,
    )


# ---------------------------------------------------------------------------
# Phase 4 — Display & compare results
# ---------------------------------------------------------------------------


def display_faithfulness_results(results: "pd.DataFrame") -> None:
    """Print faithfulness vs hallucination comparison."""
    print("=" * 80)
    print("RAG FAITHFULNESS / HALLUCINATION EVALUATION")
    print("=" * 80)
    print()
    print("NOTE: faithfulness (1.0 = good) and hallucination (1.0 = bad)")
    print("      are conceptual inverses. A perfect answer scores")
    print("      faithfulness=1.0 AND hallucination=0.0.")
    print()

    for idx, row in results.iterrows():
        print(f"--- Sample {idx} ---")
        print(f"  Input  : {str(row['input'])[:70]}")
        print(f"  Output : {str(row['output'])[:70]}")
        print(f"  Context: {str(row['context'])[:70]}...")

        faith = row.get("faithfulness", "N/A")
        halluc = row.get("hallucination", "N/A")
        print(f"  faithfulness  = {faith}")
        print(f"  hallucination = {halluc}")
        print()


def display_relevance_results(results: "pd.DataFrame") -> None:
    """Print document-relevance scores."""
    print("=" * 80)
    print("DOCUMENT RELEVANCE EVALUATION")
    print("=" * 80)
    print()

    for idx, row in results.iterrows():
        print(f"--- Sample {idx} ---")
        print(f"  Query   : {str(row['input'])[:70]}")
        print(f"  Document: {str(row['document_text'])[:70]}...")

        score = row.get("document_relevance", "N/A")
        label = row.get("document_relevance_label", "")
        print(f"  relevance = {score}  ({label})")
        print()


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Run both evaluation pipelines
    faith_results = run_faithfulness_evaluation()
    display_faithfulness_results(faith_results)

    rel_results = run_relevance_evaluation()
    display_relevance_results(rel_results)
