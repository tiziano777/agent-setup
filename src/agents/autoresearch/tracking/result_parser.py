"""Parse structured experiment output lines from stdout.

The L1 training script communicates results back to L2 via specially
formatted lines printed to stdout:

    EXPERIMENT_STATUS=completed
    EXPERIMENT_RUN_ID=run_042
    EXPERIMENT_HYPERPARAMS={"learning_rate": 3e-5, "batch_size": 4}
    EXPERIMENT_RESULT={"eval_accuracy": 0.87, "eval_loss": 0.42}

This module extracts those lines from raw log output.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

# Regex that matches ``KEY=VALUE`` for our structured lines.
_LINE_RE = re.compile(
    r"^(EXPERIMENT_STATUS|EXPERIMENT_RUN_ID|EXPERIMENT_HYPERPARAMS"
    r"|EXPERIMENT_RESULT)=(.+)$"
)


@dataclass
class ParsedResult:
    """Collected structured fields from a single experiment's stdout."""
    status: str | None = None
    run_id: str | None = None
    hyperparams: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, float] = field(default_factory=dict)
    raw_lines: list[str] = field(default_factory=list)


def parse_experiment_output(log_text: str) -> ParsedResult:
    """Parse structured ``EXPERIMENT_*`` lines from raw log text.

    Every occurrence of a structured line overwrites the previous value
    (last-writer-wins), so the final state is captured.
    """
    result = ParsedResult()

    for line in log_text.splitlines():
        stripped = line.strip()
        m = _LINE_RE.match(stripped)
        if m is None:
            continue

        key, value = m.group(1), m.group(2)
        result.raw_lines.append(stripped)

        if key == "EXPERIMENT_STATUS":
            result.status = value.strip()
        elif key == "EXPERIMENT_RUN_ID":
            result.run_id = value.strip()
        elif key == "EXPERIMENT_HYPERPARAMS":
            try:
                result.hyperparams = json.loads(value)
            except json.JSONDecodeError:
                result.hyperparams = {"_raw": value}
        elif key == "EXPERIMENT_RESULT":
            try:
                parsed = json.loads(value)
                # Accept both flat dicts and nested {"metrics": {...}}
                if isinstance(parsed, dict):
                    result.metrics = {k: float(v) for k, v in parsed.items() if _is_numeric(v)}
            except (json.JSONDecodeError, ValueError):
                result.metrics = {"_raw_result": 0.0}

    return result


def extract_metric(log_text: str, metric_name: str) -> float | None:
    """Convenience: parse logs and return a single named metric, or None."""
    parsed = parse_experiment_output(log_text)
    return parsed.metrics.get(metric_name)


def _is_numeric(v: Any) -> bool:
    """Check whether a value can be losslessly converted to float."""
    if isinstance(v, (int, float)):
        return True
    if isinstance(v, str):
        try:
            float(v)
            return True
        except ValueError:
            return False
    return False
