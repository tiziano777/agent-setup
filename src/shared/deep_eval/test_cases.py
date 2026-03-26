"""LLMTestCase helper factories.

Convenience functions for creating ``deepeval.test_case.LLMTestCase``
instances from common input shapes.
"""

from __future__ import annotations

from typing import Any

from src.shared.deep_eval.config import _check_available


def create_test_case(
    input: str,  # noqa: A002
    actual_output: str,
    *,
    expected_output: str | None = None,
    context: list[str] | None = None,
    retrieval_context: list[str] | None = None,
) -> Any:
    """Create a basic ``LLMTestCase``.

    Args:
        input: The user query / prompt.
        actual_output: The LLM's response.
        expected_output: Ground-truth expected response (optional).
        context: Gold-standard context strings (optional).
        retrieval_context: Retrieved context strings (optional).

    Returns:
        A ``deepeval.test_case.LLMTestCase`` instance.
    """
    _check_available()
    from deepeval.test_case import LLMTestCase

    kwargs: dict[str, Any] = {
        "input": input,
        "actual_output": actual_output,
    }
    if expected_output is not None:
        kwargs["expected_output"] = expected_output
    if context is not None:
        kwargs["context"] = context
    if retrieval_context is not None:
        kwargs["retrieval_context"] = retrieval_context

    return LLMTestCase(**kwargs)


def create_rag_test_case(
    input: str,  # noqa: A002
    actual_output: str,
    retrieval_context: list[str],
    *,
    expected_output: str | None = None,
    context: list[str] | None = None,
) -> Any:
    """Create an ``LLMTestCase`` pre-configured for RAG evaluation.

    Ensures ``retrieval_context`` is always present (required by
    contextual recall/precision/relevancy metrics).

    Args:
        input: The user query.
        actual_output: The RAG pipeline's response.
        retrieval_context: Retrieved context strings from the vector DB.
        expected_output: Ground-truth expected response (optional).
        context: Gold-standard context strings (optional).
    """
    _check_available()
    return create_test_case(
        input=input,
        actual_output=actual_output,
        expected_output=expected_output,
        context=context,
        retrieval_context=retrieval_context,
    )


def create_test_cases_from_dicts(data: list[dict[str, Any]]) -> list[Any]:
    """Convert a list of dicts to ``LLMTestCase`` instances.

    Each dict must contain at least ``input`` and ``actual_output`` keys.
    Additional keys (``expected_output``, ``context``, ``retrieval_context``)
    are passed through if present.

    Args:
        data: List of dicts with test case data.

    Returns:
        List of ``LLMTestCase`` instances.
    """
    _check_available()
    cases = []
    for item in data:
        cases.append(
            create_test_case(
                input=item["input"],
                actual_output=item["actual_output"],
                expected_output=item.get("expected_output"),
                context=item.get("context"),
                retrieval_context=item.get("retrieval_context"),
            )
        )
    return cases
