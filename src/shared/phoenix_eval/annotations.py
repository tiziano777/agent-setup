"""Phoenix trace annotation helpers.

Converts evaluation results into the format expected by Phoenix for
logging scores directly onto traces in the UI.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.shared.phoenix_eval.llm_bridge import _check_available

if TYPE_CHECKING:
    import pandas as pd


def to_phoenix_annotations(
    results: "pd.DataFrame",
    score_names: list[str] | None = None,
) -> "pd.DataFrame":
    """Convert evaluation results to Phoenix annotation format.

    Takes the output of :func:`evaluate_batch` and reformats it so
    that each evaluator's score, label, explanation, and metadata are
    in separate columns ready for Phoenix logging.

    Args:
        results: DataFrame returned by ``evaluate_batch`` or
                 ``async_evaluate_batch``.
        score_names: Subset of score columns to include.  Defaults to
                     all detected score columns.

    Returns:
        DataFrame in Phoenix annotation format with columns:
        ``score``, ``label``, ``explanation``, ``metadata``.
    """
    _check_available()
    from phoenix.evals import to_annotation_dataframe

    return to_annotation_dataframe(dataframe=results, score_names=score_names)
