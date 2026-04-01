"""Generate random hyperparameter configurations for a wave."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage

from src.agents.autoresearch.config.models import ParameterSpec
from src.agents.autoresearch.states.state import AutoresearchState


def generate_random_wave(state: AutoresearchState) -> dict[str, Any]:
    """Sample random configs from the active search space."""
    search_space_raw = state.get("active_search_space", {})
    sweep_config = state.get("sweep_config", {})
    waves_parallel = sweep_config.get("strategy", {}).get("waves_parallel", 4)
    remaining = state.get("experiments_remaining", waves_parallel)
    wave_number = state.get("wave_number", 0) + 1

    n = min(waves_parallel, remaining)

    search_space: dict[str, ParameterSpec] = {}
    for name, spec_data in search_space_raw.items():
        search_space[name] = ParameterSpec.model_validate(spec_data)

    configs: list[dict[str, Any]] = []
    for _ in range(n):
        sample = {
            name: spec.sample_uniform() for name, spec in search_space.items()
        }
        configs.append(sample)

    return {
        "wave_configs": configs,
        "wave_number": wave_number,
        "messages": [
            AIMessage(
                content=f"Generated {len(configs)} random configs for wave {wave_number}."
            ),
        ],
    }
