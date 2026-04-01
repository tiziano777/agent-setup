"""Slice the next batch from a pre-computed grid."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage

from src.agents.autoresearch.states.state import AutoresearchState


def slice_next_wave(state: AutoresearchState) -> dict[str, Any]:
    """Take the next wave_size configs from the pre-computed grid."""
    grid_configs = state.get("grid_configs", [])
    offset = state.get("grid_offset", 0)
    sweep_config = state.get("sweep_config", {})
    waves_parallel = sweep_config.get("strategy", {}).get("waves_parallel", 4)
    remaining = state.get("experiments_remaining", waves_parallel)
    wave_number = state.get("wave_number", 0) + 1

    n = min(waves_parallel, remaining, len(grid_configs) - offset)
    wave_configs = grid_configs[offset : offset + n]
    new_offset = offset + n

    return {
        "wave_configs": wave_configs,
        "grid_offset": new_offset,
        "wave_number": wave_number,
        "messages": [
            AIMessage(
                content=f"Grid wave {wave_number}: configs [{offset}:{new_offset}] "
                f"of {len(grid_configs)} total."
            ),
        ],
    }
