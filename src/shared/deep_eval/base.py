"""Extensible base class for DeepEval evaluators.

Subclasses implement ``_setup_metrics()`` to configure which DeepEval metrics
to run and ``create_test_case()`` to build an ``LLMTestCase`` from raw data.
The base class provides ``evaluate()`` and ``evaluate_batch()`` for free.

Example::

    class MyEvaluator(BaseDeepEvaluator):
        def _setup_metrics(self, **kwargs):
            from deepeval.metrics import AnswerRelevancyMetric
            self._metrics = [AnswerRelevancyMetric(model=self._model)]

        def create_test_case(self, *, input, actual_output, **kwargs):
            from deepeval.test_case import LLMTestCase
            return LLMTestCase(input=input, actual_output=actual_output)
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

from src.shared.deep_eval.config import _check_available
from src.shared.deep_eval.llm_bridge import get_deepeval_model

logger = logging.getLogger(__name__)


class BaseDeepEvaluator(ABC):
    """Abstract base class for DeepEval evaluators.

    Provides a consistent interface for evaluating LLM outputs with
    configurable metrics.  Concrete subclasses must implement:

    * ``_setup_metrics(**kwargs)`` — populate ``self._metrics``
    * ``create_test_case(**kwargs)`` — return an ``LLMTestCase``
    """

    def __init__(
        self,
        model: Any | None = None,
        threshold: float = 0.5,
        **kwargs: Any,
    ) -> None:
        _check_available()
        self._model = model or get_deepeval_model()
        self._threshold = threshold
        self._metrics: list[Any] = []
        self._setup_metrics(**kwargs)

    # ── Abstract interface ────────────────────────────────────────────

    @abstractmethod
    def _setup_metrics(self, **kwargs: Any) -> None:
        """Configure the metrics to run.

        Populate ``self._metrics`` with DeepEval metric instances.
        Use ``self._model`` as the LLM for metrics that require one.
        """
        ...

    @abstractmethod
    def create_test_case(self, **kwargs: Any) -> Any:
        """Build an ``LLMTestCase`` from the provided keyword arguments.

        Returns:
            A ``deepeval.test_case.LLMTestCase`` instance.
        """
        ...

    # ── Evaluation ────────────────────────────────────────────────────

    def evaluate(self, **kwargs: Any) -> list[dict[str, Any]]:
        """Evaluate a single test case against all configured metrics.

        Keyword arguments are forwarded to :meth:`create_test_case`.

        Returns:
            List of result dicts, one per metric::

                {"metric": "AnswerRelevancyMetric", "score": 0.85,
                 "reason": "...", "passed": True}
        """
        test_case = self.create_test_case(**kwargs)
        results: list[dict[str, Any]] = []
        for metric in self._metrics:
            metric.measure(test_case)
            results.append({
                "metric": metric.__class__.__name__,
                "score": metric.score,
                "reason": getattr(metric, "reason", None),
                "passed": metric.score >= self._threshold,
            })
        return results

    def evaluate_batch(self, data: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
        """Evaluate multiple test cases sequentially.

        Args:
            data: List of keyword-argument dicts, each forwarded to
                  :meth:`evaluate`.

        Returns:
            List of per-item result lists.
        """
        return [self.evaluate(**item) for item in data]

    # ── Introspection ─────────────────────────────────────────────────

    @property
    def metrics(self) -> list[Any]:
        """Return a copy of the configured metrics list."""
        return list(self._metrics)

    @property
    def threshold(self) -> float:
        """The pass/fail threshold for metric scores."""
        return self._threshold
