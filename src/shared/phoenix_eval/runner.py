"""Batch evaluation runner.

Wraps ``phoenix.evals.evaluate_dataframe`` /
``phoenix.evals.async_evaluate_dataframe`` with convenience conversion
from ``list[dict]`` and project defaults.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from src.shared.phoenix_eval.llm_bridge import _check_available

if TYPE_CHECKING:
    import pandas as pd


def evaluate_batch(
    data: list[dict[str, Any]] | "pd.DataFrame",
    evaluators: list[Any],
    *,
    max_retries: int = 3,
    exit_on_error: bool = False,
) -> "pd.DataFrame":
    """Run evaluators on a batch of data (sync).

    Args:
        data: Evaluation inputs as a list of dicts or a pandas DataFrame.
              Each dict/row must contain the fields expected by the evaluators
              (e.g. ``input``, ``output``, ``context``).
        evaluators: List of Phoenix evaluator instances (from ``builtin``
                    or ``custom`` factories).
        max_retries: Max retries per LLM call on transient failures.
        exit_on_error: If ``True``, raise on first error instead of
                       recording it.

    Returns:
        DataFrame with original columns plus score/label/explanation
        columns for each evaluator.
    """
    _check_available()
    import pandas as pd
    from phoenix.evals import evaluate_dataframe

    if isinstance(data, list):
        data = pd.DataFrame(data)

    return evaluate_dataframe(
        dataframe=data,
        evaluators=evaluators,
        max_retries=max_retries,
        exit_on_error=exit_on_error,
    )


async def async_evaluate_batch(
    data: list[dict[str, Any]] | "pd.DataFrame",
    evaluators: list[Any],
    *,
    concurrency: int = 10,
    max_retries: int = 3,
    exit_on_error: bool = False,
) -> "pd.DataFrame":
    """Run evaluators on a batch of data (async with concurrency).

    Args:
        data: Evaluation inputs as a list of dicts or a pandas DataFrame.
        evaluators: List of Phoenix evaluator instances.
        concurrency: Max concurrent LLM calls.
        max_retries: Max retries per LLM call on transient failures.
        exit_on_error: If ``True``, raise on first error.

    Returns:
        DataFrame with original columns plus score/label/explanation
        columns for each evaluator.
    """
    _check_available()
    import pandas as pd
    from phoenix.evals import async_evaluate_dataframe

    if isinstance(data, list):
        data = pd.DataFrame(data)

    return await async_evaluate_dataframe(
        dataframe=data,
        evaluators=evaluators,
        concurrency=concurrency,
        max_retries=max_retries,
        exit_on_error=exit_on_error,
    )
