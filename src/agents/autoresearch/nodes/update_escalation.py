"""Update escalation stage based on plateau detection."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage

from src.agents.autoresearch.config.models import SweepConfig
from src.agents.autoresearch.states.state import AutoresearchState


def update_escalation(state: AutoresearchState) -> dict[str, Any]:
    """Check for plateau and advance escalation stage if needed."""
    sweep_config_dict = state.get("sweep_config", {})
    escalation_stage = state.get("escalation_stage", 0)
    trajectory = state.get("trajectory", [])
    best_metric = state.get("best_metric_value")

    try:
        config = SweepConfig.model_validate(sweep_config_dict)
    except Exception:
        return {}

    if not config.escalation.enabled or not config.escalation.stages:
        return {}

    stages = config.escalation.stages
    if escalation_stage >= len(stages):
        return {}

    current_stage = stages[escalation_stage]

    # Check if we have enough experiments for this stage
    if len(trajectory) < current_stage.min_experiments:
        return {}

    # Check for plateau (no improvement in last N experiments)
    metric_name = config.metric.name
    goal = config.metric.goal.value
    recent = trajectory[-current_stage.plateau_patience :]

    if len(recent) < current_stage.plateau_patience:
        return {}

    # Find best metric in recent experiments
    recent_best = None
    for exp in recent:
        val = exp.get("metrics", {}).get(metric_name)
        if val is None:
            continue
        if recent_best is None:
            recent_best = val
        elif goal == "maximize" and val > recent_best:
            recent_best = val
        elif goal == "minimize" and val < recent_best:
            recent_best = val

    # Check if improvement exceeds threshold
    if best_metric is not None and recent_best is not None:
        if best_metric != 0:
            improvement = abs(recent_best - best_metric) / abs(best_metric)
        else:
            improvement = abs(recent_best - best_metric)

        if improvement < current_stage.plateau_threshold:
            # Plateau detected — advance stage
            new_stage = escalation_stage + 1
            new_search_space = state.get("active_search_space", {})

            # Add parameters from next stage
            if new_stage < len(stages):
                next_stage = stages[new_stage]
                for param_name in next_stage.parameters:
                    if param_name in sweep_config_dict.get("search_space", {}):
                        spec = sweep_config_dict["search_space"][param_name]
                        new_search_space[param_name] = spec

            return {
                "escalation_stage": new_stage,
                "active_search_space": new_search_space,
                "messages": [
                    AIMessage(
                        content=f"Escalation: advancing to stage {new_stage} "
                        f"(plateau detected, improvement {improvement:.4f} "
                        f"< threshold {current_stage.plateau_threshold})."
                    ),
                ],
            }

    return {}
