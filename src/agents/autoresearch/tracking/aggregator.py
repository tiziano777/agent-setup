"""Aggregate results across multiple experiment runs.

Provides utilities to identify the best configuration, rank top-k results,
and estimate parameter importance via basic variance analysis.
"""

from __future__ import annotations

import statistics
from collections import defaultdict

from src.agents.autoresearch.schemas.entities import (
    Experiment as HistoryEntry,
)
from src.agents.autoresearch.schemas.entities import (
    ExperimentStatus as RunStatusHistory,
)


def best_config(
    entries: list[HistoryEntry],
    metric_name: str,
    goal: str = "maximize",
) -> HistoryEntry | None:
    """Return the single best completed entry for *metric_name*."""
    scored = _score_entries(entries, metric_name)
    if not scored:
        return None
    reverse = goal == "maximize"
    scored.sort(key=lambda t: t[0], reverse=reverse)
    return scored[0][1]


def top_k_configs(
    entries: list[HistoryEntry],
    metric_name: str,
    goal: str = "maximize",
    k: int = 10,
) -> list[HistoryEntry]:
    """Return the top *k* completed entries for *metric_name*."""
    scored = _score_entries(entries, metric_name)
    reverse = goal == "maximize"
    scored.sort(key=lambda t: t[0], reverse=reverse)
    return [entry for _, entry in scored[:k]]


def parameter_importance(
    entries: list[HistoryEntry],
    metric_name: str,
) -> dict[str, float]:
    """Estimate parameter importance via per-parameter variance contribution.

    For each hyperparameter, we group runs by their value for that parameter
    and compute the variance of mean-metric across groups. A higher variance
    indicates the parameter has more influence on the metric.

    Returns a dict mapping parameter names to their importance score
    (normalised so that the maximum is 1.0).
    """
    completed = [
        e for e in entries
        if e.status == RunStatusHistory.COMPLETED and metric_name in e.metrics
    ]
    if len(completed) < 2:
        return {}

    # Collect all hyperparameter names
    param_names: set[str] = set()
    for e in completed:
        param_names.update(e.hyperparams.keys())

    importance: dict[str, float] = {}

    for param in param_names:
        groups: dict[str, list[float]] = defaultdict(list)
        for e in completed:
            val = e.hyperparams.get(param)
            if val is None:
                continue
            group_key = str(val)
            groups[group_key].append(e.metrics[metric_name])

        if len(groups) < 2:
            importance[param] = 0.0
            continue

        # Variance of group means
        group_means = [statistics.mean(vals) for vals in groups.values() if vals]
        if len(group_means) < 2:
            importance[param] = 0.0
            continue

        importance[param] = statistics.variance(group_means)

    # Normalise to [0, 1]
    max_imp = max(importance.values()) if importance else 1.0
    if max_imp > 0:
        importance = {k: v / max_imp for k, v in importance.items()}

    return dict(sorted(importance.items(), key=lambda t: t[1], reverse=True))


# ---- internal ----

def _score_entries(
    entries: list[HistoryEntry],
    metric_name: str,
) -> list[tuple[float, HistoryEntry]]:
    """Filter to completed entries that have the requested metric."""
    scored: list[tuple[float, HistoryEntry]] = []
    for e in entries:
        if e.status != RunStatusHistory.COMPLETED:
            continue
        val = e.metrics.get(metric_name)
        if val is not None:
            scored.append((val, e))
    return scored
