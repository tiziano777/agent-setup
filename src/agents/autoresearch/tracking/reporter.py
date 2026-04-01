"""Generate markdown sweep reports.

Produces a human-readable report summarising the sweep's progress, including:
  - Best configuration found
  - Top-10 leaderboard table
  - Parameter importance / distributions
  - Suggestions for next steps
"""

from __future__ import annotations

import json
import statistics
from collections import defaultdict
from pathlib import Path

from src.agents.autoresearch.schemas.entities import (
    Experiment as HistoryEntry,
)
from src.agents.autoresearch.schemas.entities import (
    ExperimentStatus as RunStatusHistory,
)
from src.agents.autoresearch.tracking.aggregator import (
    best_config,
    parameter_importance,
    top_k_configs,
)


def generate_report(
    entries: list[HistoryEntry],
    metric_name: str,
    goal: str = "maximize",
    sweep_name: str = "",
    output_path: str | Path | None = None,
) -> str:
    """Generate a full markdown sweep report.

    Returns the report text and optionally writes it to *output_path*.
    """
    sections: list[str] = []

    # Header
    sections.append(f"# Sweep Report: {sweep_name or 'Unnamed'}\n")
    sections.append(f"**Metric:** `{metric_name}` (goal: {goal})  ")
    completed = [e for e in entries if e.status == RunStatusHistory.COMPLETED]
    total = len(entries)
    sections.append(f"**Total runs:** {total} | **Completed:** {len(completed)}\n")

    # Best config
    best = best_config(entries, metric_name, goal)
    sections.append("## Best Configuration\n")
    if best:
        val = best.metrics.get(metric_name, "N/A")
        sections.append(f"- **Run ID:** `{best.run_id}`")
        sections.append(f"- **{metric_name}:** `{val}`")
        sections.append("- **Hyperparameters:**")
        sections.append(f"  ```json\n  {json.dumps(best.hyperparams, indent=2)}\n  ```")
        if best.wall_time_seconds:
            sections.append(f"- **Wall time:** {best.wall_time_seconds:.1f}s")
        if best.agent_reasoning:
            sections.append(f"- **Agent reasoning:** {best.agent_reasoning}")
    else:
        sections.append("_No completed runs with this metric yet._")
    sections.append("")

    # Top-10 table
    top10 = top_k_configs(entries, metric_name, goal, k=10)
    sections.append("## Top-10 Configurations\n")
    if top10:
        # Build markdown table
        hp_keys = _collect_hp_keys(top10)
        header = "| Rank | Run ID | " + " | ".join(hp_keys) + f" | {metric_name} |"
        sep = "|" + "|".join(["---"] * (3 + len(hp_keys))) + "|"
        sections.append(header)
        sections.append(sep)
        for rank, e in enumerate(top10, 1):
            hp_vals = " | ".join(str(e.hyperparams.get(k, "-")) for k in hp_keys)
            metric_val = e.metrics.get(metric_name, "-")
            metric_str = f"{metric_val:.6f}" if isinstance(metric_val, float) else str(metric_val)
            sections.append(f"| {rank} | `{e.run_id}` | {hp_vals} | {metric_str} |")
    else:
        sections.append("_No completed runs yet._")
    sections.append("")

    # Parameter importance
    importance = parameter_importance(entries, metric_name)
    sections.append("## Parameter Importance\n")
    if importance:
        sections.append("| Parameter | Importance |")
        sections.append("|---|---|")
        for param, score in importance.items():
            bar = _bar_chart(score)
            sections.append(f"| `{param}` | {score:.3f} {bar} |")
    else:
        sections.append("_Not enough data to estimate parameter importance._")
    sections.append("")

    # Parameter distributions
    sections.append("## Parameter Distributions\n")
    if completed:
        for param in _collect_hp_keys(completed):
            values = [e.hyperparams.get(param) for e in completed if param in e.hyperparams]
            numeric = [v for v in values if isinstance(v, (int, float))]
            if numeric and len(numeric) >= 2:
                sections.append(f"### `{param}`")
                sections.append(f"- Range: [{min(numeric)}, {max(numeric)}]")
                sections.append(f"- Mean: {statistics.mean(numeric):.6g}")
                sections.append(f"- Std: {statistics.stdev(numeric):.6g}")
                sections.append("")
            else:
                counts: dict[str, int] = defaultdict(int)
                for v in values:
                    counts[str(v)] += 1
                sections.append(f"### `{param}`")
                for val, cnt in sorted(counts.items(), key=lambda t: t[1], reverse=True):
                    sections.append(f"- `{val}`: {cnt} runs")
                sections.append("")
    else:
        sections.append("_No completed runs yet._")

    # Suggestions
    sections.append("## Suggestions\n")
    suggestions = _generate_suggestions(entries, metric_name, goal, importance)
    for s in suggestions:
        sections.append(f"- {s}")
    sections.append("")

    report = "\n".join(sections)

    if output_path is not None:
        Path(output_path).write_text(report)

    return report


# ---- helpers ----

def _collect_hp_keys(entries: list[HistoryEntry]) -> list[str]:
    """Collect all hyperparameter keys across entries, in stable order."""
    seen: dict[str, None] = {}
    for e in entries:
        for k in e.hyperparams:
            seen.setdefault(k, None)
    return list(seen.keys())


def _bar_chart(score: float, width: int = 20) -> str:
    """Render a simple inline bar from 0..1."""
    filled = int(round(score * width))
    return "|" + "#" * filled + "-" * (width - filled) + "|"


def _generate_suggestions(
    entries: list[HistoryEntry],
    metric_name: str,
    goal: str,
    importance: dict[str, float],
) -> list[str]:
    """Generate actionable suggestions based on current results."""
    suggestions: list[str] = []
    completed = [e for e in entries if e.status == RunStatusHistory.COMPLETED]
    crashed = [e for e in entries if e.status == RunStatusHistory.CRASHED]

    if not completed:
        suggestions.append("No completed runs yet. Check that experiments are launching correctly.")
        return suggestions

    if len(completed) < 5:
        suggestions.append(
            "Fewer than 5 completed runs. "
            "Consider running more experiments for reliable conclusions."
        )

    if crashed and len(crashed) / max(len(entries), 1) > 0.3:
        suggestions.append(
            f"High crash rate ({len(crashed)}/{len(entries)}). "
            "Investigate common failure modes before launching more runs."
        )

    # Suggest focusing on high-importance parameters
    high_importance = [p for p, s in importance.items() if s > 0.5]
    if high_importance:
        suggestions.append(
            f"Parameters with highest impact: {', '.join(f'`{p}`' for p in high_importance)}. "
            "Consider narrowing the search space around the best values for these."
        )

    low_importance = [p for p, s in importance.items() if s < 0.1]
    if low_importance:
        suggestions.append(
            f"Parameters with low impact: {', '.join(f'`{p}`' for p in low_importance)}. "
            "Consider fixing these to reduce the search space."
        )

    return suggestions
