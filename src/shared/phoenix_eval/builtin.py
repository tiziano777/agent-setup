"""Built-in Phoenix evaluator factories.

Each factory returns a ready-to-use Phoenix ``Evaluator`` backed by the
project's LiteLLM proxy.  Pass an explicit ``llm`` to override the default.

Categories:
    Response Quality  — conciseness, correctness, refusal
    RAG / Retrieval   — document relevance, faithfulness, hallucination
    Tool Use          — tool selection, invocation, response handling
    Deterministic     — regex match, precision/recall/f-score
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from src.shared.phoenix_eval.llm_bridge import _AVAILABLE, _check_available, get_eval_llm

if TYPE_CHECKING or _AVAILABLE:
    try:
        from phoenix.evals import (
            ConcisenessEvaluator,
            CorrectnessEvaluator,
            DocumentRelevanceEvaluator,
            FaithfulnessEvaluator,
            HallucinationEvaluator,
            MatchesRegex,
            PrecisionRecallFScore,
            RefusalEvaluator,
            ToolInvocationEvaluator,
            ToolResponseHandlingEvaluator,
            ToolSelectionEvaluator,
        )
    except ImportError:
        pass


# ── Response Quality ────────────────────────────────────────────────


def conciseness_evaluator(llm=None):
    """Evaluator: is the response concise? (1.0 = concise, 0.0 = verbose).

    Required fields: ``input``, ``output``.
    """
    _check_available()
    return ConcisenessEvaluator(llm=llm or get_eval_llm())


def correctness_evaluator(llm=None):
    """Evaluator: is the response correct? (1.0 = correct, 0.0 = incorrect).

    Required fields: ``input``, ``output``.
    """
    _check_available()
    return CorrectnessEvaluator(llm=llm or get_eval_llm())


def refusal_evaluator(llm=None):
    """Evaluator: did the LLM refuse to answer? (1.0 = refused, 0.0 = answered).

    Required fields: ``input``, ``output``.
    """
    _check_available()
    return RefusalEvaluator(llm=llm or get_eval_llm())


# ── RAG / Retrieval ─────────────────────────────────────────────────


def document_relevance_evaluator(llm=None):
    """Evaluator: is the retrieved document relevant? (1.0 = relevant, 0.0 = unrelated).

    Required fields: ``input``, ``document_text``.
    """
    _check_available()
    return DocumentRelevanceEvaluator(llm=llm or get_eval_llm())


def faithfulness_evaluator(llm=None):
    """Evaluator: is the response faithful to context? (1.0 = faithful, 0.0 = unfaithful).

    Required fields: ``input``, ``output``, ``context``.
    """
    _check_available()
    return FaithfulnessEvaluator(llm=llm or get_eval_llm())


def hallucination_evaluator(llm=None):
    """Evaluator: does the response hallucinate? (1.0 = hallucinated, 0.0 = factual).

    Required fields: ``input``, ``output``, ``context``.

    .. deprecated::
        Prefer :func:`faithfulness_evaluator` which inverts the score
        direction (1.0 = good).
    """
    _check_available()
    return HallucinationEvaluator(llm=llm or get_eval_llm())


# ── Tool Use ────────────────────────────────────────────────────────


def tool_selection_evaluator(llm=None):
    """Evaluator: did the agent pick the right tool? (1.0 = correct, 0.0 = incorrect).

    Required fields: ``input``, ``available_tools``, ``tool_selection``.
    """
    _check_available()
    return ToolSelectionEvaluator(llm=llm or get_eval_llm())


def tool_invocation_evaluator(llm=None):
    """Evaluator: were the tool parameters correct? (1.0 = correct, 0.0 = incorrect).

    Required fields: ``input``, ``available_tools``, ``tool_selection``.
    """
    _check_available()
    return ToolInvocationEvaluator(llm=llm or get_eval_llm())


def tool_response_evaluator(llm=None):
    """Evaluator: did the agent handle the tool output correctly? (1.0 = correct, 0.0 = incorrect).

    Required fields: ``input``, ``tool_call``, ``tool_result``, ``output``.
    """
    _check_available()
    return ToolResponseHandlingEvaluator(llm=llm or get_eval_llm())


# ── Deterministic (no LLM) ──────────────────────────────────────────


def regex_evaluator(pattern: str | re.Pattern, name: str | None = None):
    """Evaluator: does the output match a regex? (1.0 = match, 0.0 = no match).

    Args:
        pattern: Regex pattern (string or compiled).
        name: Optional evaluator name (defaults to ``"matches_regex"``).

    Required field: ``output``.
    """
    _check_available()
    return MatchesRegex(pattern=pattern, name=name)


def precision_recall_evaluator(
    beta: float = 1.0,
    average: str = "macro",
):
    """Evaluator: compute precision, recall, and F-beta score.

    Args:
        beta: Weight of recall vs precision (1.0 = F1).
        average: Averaging strategy (``"macro"``, ``"micro"``, ``"weighted"``).

    Required fields: ``expected``, ``output`` (label sequences).
    Returns three ``Score`` objects: precision, recall, f-score.
    """
    _check_available()
    return PrecisionRecallFScore(beta=beta, average=average)
