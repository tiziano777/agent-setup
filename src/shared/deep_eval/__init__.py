"""DeepEval evaluation toolkit.

Provides extensible evaluators for LLM agent outputs, RAG pipelines,
and LangGraph workflows.  All LLM calls are routed through the project's
LiteLLM proxy.

Quick start::

    from src.shared.deep_eval import (
        answer_relevancy_metric,
        faithfulness_metric,
        evaluate,
        create_test_case,
    )

    tc = create_test_case(
        input="What is Python?",
        actual_output="A programming language.",
        retrieval_context=["Python is a programming language created by ..."],
    )
    evaluate([tc], metrics=[answer_relevancy_metric(), faithfulness_metric()])

Dependencies:
    Requires ``pip install -e '.[deepeval]'``.  All imports are lazy —
    ``ImportError`` is raised only when a function is actually called.
"""

from __future__ import annotations

from typing import Any

from src.shared.deep_eval.base import BaseDeepEvaluator
from src.shared.deep_eval.config import DeepEvalSettings

# ── Lazy re-exports ───────────────────────────────────────────────────
# DeepEval is a heavy dependency; we use lazy wrappers (cognee_toolkit style)
# so that importing this package never triggers the deepeval import itself.


# -- Config --


def get_settings():  # noqa: ANN201
    """Return the active ``DeepEvalSettings``."""
    from src.shared.deep_eval.config import get_settings as _fn

    return _fn()


def configure_deepeval(settings: Any | None = None):  # noqa: ANN201
    """Configure DeepEval (idempotent)."""
    from src.shared.deep_eval.config import configure_deepeval as _fn

    return _fn(settings=settings)


# -- LLM bridge --


def get_deepeval_model(model: str | None = None, temperature: float = 0.0):  # noqa: ANN201
    """Return a ``LiteLLMModel`` pointed at the LiteLLM proxy."""
    from src.shared.deep_eval.llm_bridge import get_deepeval_model as _fn

    return _fn(model=model, temperature=temperature)


# -- Metric factories --


def answer_relevancy_metric(model: Any | None = None, threshold: float = 0.5):  # noqa: ANN201
    from src.shared.deep_eval.metrics import answer_relevancy_metric as _fn

    return _fn(model=model, threshold=threshold)


def faithfulness_metric(model: Any | None = None, threshold: float = 0.5):  # noqa: ANN201
    from src.shared.deep_eval.metrics import faithfulness_metric as _fn

    return _fn(model=model, threshold=threshold)


def hallucination_metric(model: Any | None = None, threshold: float = 0.5):  # noqa: ANN201
    from src.shared.deep_eval.metrics import hallucination_metric as _fn

    return _fn(model=model, threshold=threshold)


def contextual_recall_metric(model: Any | None = None, threshold: float = 0.5):  # noqa: ANN201
    from src.shared.deep_eval.metrics import contextual_recall_metric as _fn

    return _fn(model=model, threshold=threshold)


def contextual_precision_metric(  # noqa: ANN201
    model: Any | None = None,
    threshold: float = 0.5,
):
    from src.shared.deep_eval.metrics import contextual_precision_metric as _fn

    return _fn(model=model, threshold=threshold)


def contextual_relevancy_metric(  # noqa: ANN201
    model: Any | None = None,
    threshold: float = 0.5,
):
    from src.shared.deep_eval.metrics import contextual_relevancy_metric as _fn

    return _fn(model=model, threshold=threshold)


def toxicity_metric(model: Any | None = None, threshold: float = 0.5):  # noqa: ANN201
    from src.shared.deep_eval.metrics import toxicity_metric as _fn

    return _fn(model=model, threshold=threshold)


def bias_metric(model: Any | None = None, threshold: float = 0.5):  # noqa: ANN201
    from src.shared.deep_eval.metrics import bias_metric as _fn

    return _fn(model=model, threshold=threshold)


def task_completion_metric(model: Any | None = None, threshold: float = 0.5):  # noqa: ANN201
    from src.shared.deep_eval.metrics import task_completion_metric as _fn

    return _fn(model=model, threshold=threshold)


def geval_metric(  # noqa: ANN201
    name: str,
    criteria: str,
    *,
    evaluation_steps: list[str] | None = None,
    model: Any | None = None,
    threshold: float = 0.5,
):
    from src.shared.deep_eval.metrics import geval_metric as _fn

    return _fn(
        name=name,
        criteria=criteria,
        evaluation_steps=evaluation_steps,
        model=model,
        threshold=threshold,
    )


# -- RAG evaluators --


def CogneeRAGEvaluator(  # noqa: N802, ANN201
    search_type: Any | None = None,
    model: Any | None = None,
    threshold: float = 0.5,
    **kwargs: Any,
):
    from src.shared.deep_eval.rag_evaluators import CogneeRAGEvaluator as _cls

    return _cls(search_type=search_type, model=model, threshold=threshold, **kwargs)


def QdrantRAGEvaluator(  # noqa: N802, ANN201
    collection_name: str = "documents",
    top_k: int = 3,
    model: Any | None = None,
    threshold: float = 0.5,
    **kwargs: Any,
):
    from src.shared.deep_eval.rag_evaluators import QdrantRAGEvaluator as _cls

    return _cls(
        collection_name=collection_name, top_k=top_k, model=model, threshold=threshold, **kwargs
    )


def PGVectorRAGEvaluator(  # noqa: N802, ANN201
    table_name: str = "documents",
    top_k: int = 3,
    model: Any | None = None,
    threshold: float = 0.5,
    **kwargs: Any,
):
    from src.shared.deep_eval.rag_evaluators import PGVectorRAGEvaluator as _cls

    return _cls(
        table_name=table_name, top_k=top_k, model=model, threshold=threshold, **kwargs
    )


# -- Agent evaluators --


def AgentEvaluator(  # noqa: N802, ANN201
    graph: Any,
    metrics: list[Any] | None = None,
    model: Any | None = None,
):
    from src.shared.deep_eval.agent_evaluators import AgentEvaluator as _cls

    return _cls(graph=graph, metrics=metrics, model=model)


def evaluate_langgraph_agent(  # noqa: ANN201
    graph: Any,
    inputs: list[str | dict[str, Any]],
    *,
    metrics: list[Any] | None = None,
    model: Any | None = None,
):
    from src.shared.deep_eval.agent_evaluators import evaluate_langgraph_agent as _fn

    return _fn(graph=graph, inputs=inputs, metrics=metrics, model=model)


async def aevaluate_langgraph_agent(  # noqa: ANN201
    graph: Any,
    inputs: list[str | dict[str, Any]],
    *,
    metrics: list[Any] | None = None,
    model: Any | None = None,
):
    from src.shared.deep_eval.agent_evaluators import aevaluate_langgraph_agent as _fn

    return await _fn(graph=graph, inputs=inputs, metrics=metrics, model=model)


# -- Runner --


def evaluate(  # noqa: ANN201
    test_cases: list[Any],
    metrics: list[Any],
    *,
    run_async: bool = True,
):
    from src.shared.deep_eval.runner import evaluate as _fn

    return _fn(test_cases=test_cases, metrics=metrics, run_async=run_async)


def evaluate_dataset(  # noqa: ANN201
    dataset: Any,
    metrics: list[Any],
    *,
    run_async: bool = True,
):
    from src.shared.deep_eval.runner import evaluate_dataset as _fn

    return _fn(dataset=dataset, metrics=metrics, run_async=run_async)


# -- Test case helpers --


def create_test_case(  # noqa: ANN201
    input: str,  # noqa: A002
    actual_output: str,
    **kwargs: Any,
):
    from src.shared.deep_eval.test_cases import create_test_case as _fn

    return _fn(input=input, actual_output=actual_output, **kwargs)


def create_rag_test_case(  # noqa: ANN201
    input: str,  # noqa: A002
    actual_output: str,
    retrieval_context: list[str],
    **kwargs: Any,
):
    from src.shared.deep_eval.test_cases import create_rag_test_case as _fn

    return _fn(
        input=input,
        actual_output=actual_output,
        retrieval_context=retrieval_context,
        **kwargs,
    )


def create_test_cases_from_dicts(data: list[dict[str, Any]]):  # noqa: ANN201
    from src.shared.deep_eval.test_cases import create_test_cases_from_dicts as _fn

    return _fn(data=data)


# ── Public API ────────────────────────────────────────────────────────

__all__ = [
    # Config
    "DeepEvalSettings",
    "configure_deepeval",
    "get_settings",
    # LLM bridge
    "get_deepeval_model",
    # Base class
    "BaseDeepEvaluator",
    # Response quality metrics
    "answer_relevancy_metric",
    "faithfulness_metric",
    "hallucination_metric",
    # RAG / Retrieval metrics
    "contextual_recall_metric",
    "contextual_precision_metric",
    "contextual_relevancy_metric",
    # Safety metrics
    "toxicity_metric",
    "bias_metric",
    # Agent metrics
    "task_completion_metric",
    # Custom metrics
    "geval_metric",
    # RAG evaluators
    "CogneeRAGEvaluator",
    "QdrantRAGEvaluator",
    "PGVectorRAGEvaluator",
    # Agent evaluators
    "AgentEvaluator",
    "evaluate_langgraph_agent",
    "aevaluate_langgraph_agent",
    # Runner
    "evaluate",
    "evaluate_dataset",
    # Test case helpers
    "create_test_case",
    "create_rag_test_case",
    "create_test_cases_from_dicts",
]
