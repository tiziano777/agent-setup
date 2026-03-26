"""Batch evaluation runner.

Wraps ``deepeval.evaluate()`` with auto-configuration of the LiteLLM proxy
so that metrics use the correct model endpoint.
"""

from __future__ import annotations

import logging
from typing import Any

from src.shared.deep_eval.config import _check_available, _ensure_configured

logger = logging.getLogger(__name__)


def evaluate(
    test_cases: list[Any],
    metrics: list[Any],
    *,
    run_async: bool = True,
) -> list[Any]:
    """Run DeepEval metrics on a list of test cases.

    Auto-configures the LiteLLM proxy before evaluation.

    Args:
        test_cases: List of ``LLMTestCase`` instances.
        metrics: List of DeepEval metric instances.
        run_async: Whether to run evaluations concurrently.

    Returns:
        The evaluation results from ``deepeval.evaluate()``.
    """
    _check_available()
    _ensure_configured()
    from deepeval import evaluate as _evaluate

    return _evaluate(test_cases, metrics=metrics, run_async=run_async)


def evaluate_dataset(
    dataset: Any,
    metrics: list[Any],
    *,
    run_async: bool = True,
) -> list[Any]:
    """Run DeepEval metrics on an ``EvaluationDataset``.

    Args:
        dataset: A ``deepeval.dataset.EvaluationDataset`` instance.
        metrics: List of DeepEval metric instances.
        run_async: Whether to run evaluations concurrently.

    Returns:
        The evaluation results from ``deepeval.evaluate()``.
    """
    _check_available()
    _ensure_configured()
    from deepeval import evaluate as _evaluate

    return _evaluate(dataset=dataset, metrics=metrics, run_async=run_async)
