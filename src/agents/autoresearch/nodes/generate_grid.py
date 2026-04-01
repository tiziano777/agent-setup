"""Generate full Cartesian product grid of configurations."""

from __future__ import annotations

import itertools
import math
from typing import Any

from langchain_core.messages import AIMessage

from src.agents.autoresearch.config.models import ParameterSpec, ParamType
from src.agents.autoresearch.states.state import AutoresearchState


def generate_grid(state: AutoresearchState) -> dict[str, Any]:
    """Compute the full grid of hyperparameter combinations."""
    search_space_raw = state.get("active_search_space", {})

    search_space: dict[str, ParameterSpec] = {}
    for name, spec_data in search_space_raw.items():
        search_space[name] = ParameterSpec.model_validate(spec_data)

    # Build discrete values per parameter
    n_points = 5
    param_names = sorted(search_space.keys())
    param_values: list[list[Any]] = []

    for name in param_names:
        spec = search_space[name]
        if spec.type is ParamType.CHOICE:
            param_values.append(list(spec.values))
        elif spec.type is ParamType.UNIFORM:
            step = (spec.max - spec.min) / (n_points - 1) if n_points > 1 else 0
            vals = [spec.min + i * step for i in range(n_points)]
            param_values.append(vals)
        elif spec.type is ParamType.LOG_UNIFORM:
            log_min = math.log(spec.min)
            log_max = math.log(spec.max)
            step = (log_max - log_min) / (n_points - 1) if n_points > 1 else 0
            vals = [math.exp(log_min + i * step) for i in range(n_points)]
            param_values.append(vals)

    # Cartesian product
    grid_configs: list[dict[str, Any]] = []
    for combo in itertools.product(*param_values):
        config = dict(zip(param_names, combo))
        grid_configs.append(config)

    return {
        "grid_configs": grid_configs,
        "grid_offset": 0,
        "messages": [
            AIMessage(
                content=f"Generated grid with {len(grid_configs)} total configurations."
            ),
        ],
    }
