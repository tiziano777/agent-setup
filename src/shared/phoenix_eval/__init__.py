"""Phoenix evaluation toolkit.

Provides ready-to-use evaluators for LLM agent outputs, backed by the
project's LiteLLM proxy.  All evaluators follow the Phoenix ``Evaluator``
protocol and can be used with :func:`evaluate_batch`.

Quick start::

    from src.shared.phoenix_eval import (
        correctness_evaluator,
        faithfulness_evaluator,
        evaluate_batch,
    )

    results = evaluate_batch(
        data=[
            {"input": "What is Python?", "output": "A programming language.", "context": "..."},
        ],
        evaluators=[correctness_evaluator(), faithfulness_evaluator()],
    )

Dependencies:
    Requires ``pip install -e '.[phoenix]'``.  All imports are lazy —
    ``ImportError`` is raised only when a function is actually called.
"""

from src.shared.phoenix_eval.annotations import to_phoenix_annotations
from src.shared.phoenix_eval.builtin import (
    conciseness_evaluator,
    correctness_evaluator,
    document_relevance_evaluator,
    faithfulness_evaluator,
    hallucination_evaluator,
    precision_recall_evaluator,
    refusal_evaluator,
    regex_evaluator,
    tool_invocation_evaluator,
    tool_response_evaluator,
    tool_selection_evaluator,
)
from src.shared.phoenix_eval.custom import create_code_evaluator, create_llm_judge
from src.shared.phoenix_eval.llm_bridge import get_eval_llm
from src.shared.phoenix_eval.runner import async_evaluate_batch, evaluate_batch

__all__ = [
    # LLM bridge
    "get_eval_llm",
    # Response quality
    "conciseness_evaluator",
    "correctness_evaluator",
    "refusal_evaluator",
    # RAG / Retrieval
    "document_relevance_evaluator",
    "faithfulness_evaluator",
    "hallucination_evaluator",
    # Tool use
    "tool_selection_evaluator",
    "tool_invocation_evaluator",
    "tool_response_evaluator",
    # Deterministic
    "regex_evaluator",
    "precision_recall_evaluator",
    # Custom factories
    "create_llm_judge",
    "create_code_evaluator",
    # Runner
    "evaluate_batch",
    "async_evaluate_batch",
    # Annotations
    "to_phoenix_annotations",
]
