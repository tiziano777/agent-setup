"""Built-in DeepEval metric factories.

Each factory returns a configured DeepEval metric backed by the project's
LiteLLM proxy.  Pass an explicit ``model`` to override the default.

Categories:
    Response Quality  — answer relevancy, faithfulness, hallucination
    RAG / Retrieval   — contextual recall, precision, relevancy
    Safety            — toxicity, bias
    Agent             — task completion
    Custom            — GEval (custom criteria)
"""

from __future__ import annotations

from typing import Any

from src.shared.deep_eval.config import _check_available  # noqa: I001
from src.shared.deep_eval.llm_bridge import get_deepeval_model

# ── Response Quality ──────────────────────────────────────────────────


def answer_relevancy_metric(
    model: Any | None = None,
    threshold: float = 0.5,
):
    """Metric: is the response relevant to the input?

    Required ``LLMTestCase`` fields: ``input``, ``actual_output``.
    """
    _check_available()
    from deepeval.metrics import AnswerRelevancyMetric

    return AnswerRelevancyMetric(model=model or get_deepeval_model(), threshold=threshold)


def faithfulness_metric(
    model: Any | None = None,
    threshold: float = 0.5,
):
    """Metric: is the response faithful to the retrieval context?

    Required ``LLMTestCase`` fields: ``input``, ``actual_output``,
    ``retrieval_context``.
    """
    _check_available()
    from deepeval.metrics import FaithfulnessMetric

    return FaithfulnessMetric(model=model or get_deepeval_model(), threshold=threshold)


def hallucination_metric(
    model: Any | None = None,
    threshold: float = 0.5,
):
    """Metric: does the response contain hallucinated information?

    Required ``LLMTestCase`` fields: ``input``, ``actual_output``, ``context``.
    """
    _check_available()
    from deepeval.metrics import HallucinationMetric

    return HallucinationMetric(model=model or get_deepeval_model(), threshold=threshold)


# ── RAG / Retrieval ───────────────────────────────────────────────────


def contextual_recall_metric(
    model: Any | None = None,
    threshold: float = 0.5,
):
    """Metric: how much of the expected output is covered by retrieved context?

    Required ``LLMTestCase`` fields: ``input``, ``actual_output``,
    ``expected_output``, ``retrieval_context``.
    """
    _check_available()
    from deepeval.metrics import ContextualRecallMetric

    return ContextualRecallMetric(model=model or get_deepeval_model(), threshold=threshold)


def contextual_precision_metric(
    model: Any | None = None,
    threshold: float = 0.5,
):
    """Metric: how precise is the retrieved context relative to the query?

    Required ``LLMTestCase`` fields: ``input``, ``actual_output``,
    ``expected_output``, ``retrieval_context``.
    """
    _check_available()
    from deepeval.metrics import ContextualPrecisionMetric

    return ContextualPrecisionMetric(model=model or get_deepeval_model(), threshold=threshold)


def contextual_relevancy_metric(
    model: Any | None = None,
    threshold: float = 0.5,
):
    """Metric: is the retrieved context relevant to the input query?

    Required ``LLMTestCase`` fields: ``input``, ``actual_output``,
    ``retrieval_context``.
    """
    _check_available()
    from deepeval.metrics import ContextualRelevancyMetric

    return ContextualRelevancyMetric(model=model or get_deepeval_model(), threshold=threshold)


# ── Safety ────────────────────────────────────────────────────────────


def toxicity_metric(
    model: Any | None = None,
    threshold: float = 0.5,
):
    """Metric: does the response contain toxic content?

    Required ``LLMTestCase`` fields: ``input``, ``actual_output``.
    """
    _check_available()
    from deepeval.metrics import ToxicityMetric

    return ToxicityMetric(model=model or get_deepeval_model(), threshold=threshold)


def bias_metric(
    model: Any | None = None,
    threshold: float = 0.5,
):
    """Metric: does the response contain biased content?

    Required ``LLMTestCase`` fields: ``input``, ``actual_output``.
    """
    _check_available()
    from deepeval.metrics import BiasMetric

    return BiasMetric(model=model or get_deepeval_model(), threshold=threshold)


# ── Agent ─────────────────────────────────────────────────────────────


def task_completion_metric(
    model: Any | None = None,
    threshold: float = 0.5,
):
    """Metric: did the agent successfully complete the requested task?

    Used with ``CallbackHandler`` for LangGraph agent evaluation.
    """
    _check_available()
    from deepeval.metrics import TaskCompletionMetric

    return TaskCompletionMetric(model=model or get_deepeval_model(), threshold=threshold)


# ── Custom ────────────────────────────────────────────────────────────


def geval_metric(
    name: str,
    criteria: str,
    *,
    evaluation_steps: list[str] | None = None,
    model: Any | None = None,
    threshold: float = 0.5,
):
    """Create a custom GEval metric with user-defined criteria.

    GEval uses an LLM to evaluate outputs against arbitrary criteria
    specified in natural language.

    Args:
        name: Human-readable name for the metric.
        criteria: Natural language description of what to evaluate.
        evaluation_steps: Optional step-by-step evaluation instructions.
        model: LLM to use.  Defaults to the LiteLLM proxy model.
        threshold: Pass/fail threshold.

    Returns:
        A ``GEval`` metric instance.

    Example::

        metric = geval_metric(
            name="helpfulness",
            criteria="Is the response helpful and actionable?",
            evaluation_steps=[
                "Check if the response addresses the user's question",
                "Check if the response provides useful information",
            ],
        )
    """
    _check_available()
    from deepeval.metrics import GEval

    kwargs: dict[str, Any] = {
        "name": name,
        "criteria": criteria,
        "model": model or get_deepeval_model(),
        "threshold": threshold,
    }
    if evaluation_steps is not None:
        kwargs["evaluation_steps"] = evaluation_steps

    return GEval(**kwargs)
