"""LangGraph agent evaluation with DeepEval.

Provides ``AgentEvaluator`` for end-to-end evaluation of compiled LangGraph
``StateGraph`` instances using DeepEval's ``CallbackHandler`` and metrics.

Supports both synchronous (``evaluate``) and asynchronous (``aevaluate``)
execution.

Usage::

    from src.shared.deep_eval import AgentEvaluator

    evaluator = AgentEvaluator(graph=my_compiled_graph)
    results = evaluator.evaluate(["What is the weather in Paris?"])
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from src.shared.deep_eval.config import _check_available, _ensure_configured
from src.shared.deep_eval.llm_bridge import get_deepeval_model

logger = logging.getLogger(__name__)


class AgentEvaluator:
    """End-to-end evaluator for compiled LangGraph agents.

    Wraps a compiled ``StateGraph`` and evaluates it using DeepEval's
    ``CallbackHandler`` which injects metrics into the LangGraph
    callback chain.

    Args:
        graph: A compiled LangGraph graph (``build_graph().compile()``).
        metrics: List of DeepEval metric instances.
                 Defaults to ``[TaskCompletionMetric()]``.
        model: LLM model for metrics.  Falls back to proxy default.
    """

    def __init__(
        self,
        graph: Any,
        metrics: list[Any] | None = None,
        model: Any | None = None,
    ) -> None:
        _check_available()
        _ensure_configured()
        self._graph = graph
        self._model = model or get_deepeval_model()

        if metrics is not None:
            self._metrics = metrics
        else:
            from deepeval.metrics import TaskCompletionMetric

            self._metrics = [TaskCompletionMetric(model=self._model)]

    def evaluate(self, inputs: list[str | dict[str, Any]]) -> list[dict[str, Any]]:
        """Evaluate the agent synchronously on a list of inputs.

        Each input is sent to the agent via ``graph.invoke()`` with a
        ``CallbackHandler`` that runs the configured metrics.

        Args:
            inputs: List of user queries (strings) or dicts with an
                    ``"input"`` key.

        Returns:
            List of result dicts::

                {"input": "...", "output": "...", "metrics": [...]}
        """
        from deepeval.dataset import EvaluationDataset, Golden
        from deepeval.integrations.langchain import CallbackHandler

        goldens = [
            Golden(input=i if isinstance(i, str) else i["input"]) for i in inputs
        ]
        dataset = EvaluationDataset(goldens=goldens)

        results: list[dict[str, Any]] = []
        for golden in dataset.evals_iterator():
            response = self._graph.invoke(
                {"messages": [{"role": "user", "content": golden.input}]},
                config={"callbacks": [CallbackHandler(metrics=list(self._metrics))]},
            )
            last_msg = response["messages"][-1]
            output = str(last_msg.content) if hasattr(last_msg, "content") else str(last_msg)
            results.append({
                "input": golden.input,
                "output": output,
                "metrics": [
                    {
                        "name": m.__class__.__name__,
                        "score": getattr(m, "score", None),
                        "reason": getattr(m, "reason", None),
                    }
                    for m in self._metrics
                ],
            })
        return results

    async def aevaluate(self, inputs: list[str | dict[str, Any]]) -> list[dict[str, Any]]:
        """Evaluate the agent asynchronously on a list of inputs.

        Uses ``graph.ainvoke()`` and ``asyncio.create_task()`` for
        concurrent evaluation as recommended by the DeepEval docs.

        Args:
            inputs: List of user queries (strings) or dicts with an
                    ``"input"`` key.

        Returns:
            List of result dicts (same shape as ``evaluate()``).
        """
        from deepeval.dataset import EvaluationDataset, Golden
        from deepeval.integrations.langchain import CallbackHandler

        goldens = [
            Golden(input=i if isinstance(i, str) else i["input"]) for i in inputs
        ]
        dataset = EvaluationDataset(goldens=goldens)

        results: list[dict[str, Any]] = []
        tasks: list[asyncio.Task[Any]] = []

        for golden in dataset.evals_iterator():
            task = asyncio.create_task(
                self._graph.ainvoke(
                    {"messages": [{"role": "user", "content": golden.input}]},
                    config={"callbacks": [CallbackHandler(metrics=list(self._metrics))]},
                )
            )
            dataset.evaluate(task)
            tasks.append(task)

        responses = await asyncio.gather(*tasks)

        for golden, response in zip(goldens, responses):
            last_msg = response["messages"][-1]
            output = str(last_msg.content) if hasattr(last_msg, "content") else str(last_msg)
            results.append({
                "input": golden.input,
                "output": output,
                "metrics": [
                    {
                        "name": m.__class__.__name__,
                        "score": getattr(m, "score", None),
                        "reason": getattr(m, "reason", None),
                    }
                    for m in self._metrics
                ],
            })
        return results

    @property
    def metrics(self) -> list[Any]:
        """Return the configured metrics."""
        return list(self._metrics)


# ── Convenience function ──────────────────────────────────────────────


def evaluate_langgraph_agent(
    graph: Any,
    inputs: list[str | dict[str, Any]],
    *,
    metrics: list[Any] | None = None,
    model: Any | None = None,
) -> list[dict[str, Any]]:
    """Convenience function for quick LangGraph agent evaluation.

    Creates an ``AgentEvaluator`` and runs synchronous evaluation.

    Args:
        graph: Compiled LangGraph graph.
        inputs: User queries to evaluate.
        metrics: DeepEval metrics (defaults to TaskCompletionMetric).
        model: LLM model for metrics.

    Returns:
        List of result dicts.
    """
    evaluator = AgentEvaluator(graph=graph, metrics=metrics, model=model)
    return evaluator.evaluate(inputs)


async def aevaluate_langgraph_agent(
    graph: Any,
    inputs: list[str | dict[str, Any]],
    *,
    metrics: list[Any] | None = None,
    model: Any | None = None,
) -> list[dict[str, Any]]:
    """Async convenience function for LangGraph agent evaluation.

    Args:
        graph: Compiled LangGraph graph.
        inputs: User queries to evaluate.
        metrics: DeepEval metrics (defaults to TaskCompletionMetric).
        model: LLM model for metrics.

    Returns:
        List of result dicts.
    """
    evaluator = AgentEvaluator(graph=graph, metrics=metrics, model=model)
    return await evaluator.aevaluate(inputs)
