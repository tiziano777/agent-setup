"""Validate and sanitize proposed hyperparameter configurations."""

from __future__ import annotations

import random
from typing import Any

from langchain_core.messages import AIMessage

from src.agents.autoresearch.config.models import ParameterSpec, ParamType
from src.agents.autoresearch.states.state import AutoresearchState


def validate_proposals(state: AutoresearchState) -> dict[str, Any]:
    """Clamp proposals to search space bounds, deduplicate, fallback to random."""
    wave_configs = state.get("wave_configs", [])
    search_space_raw = state.get("active_search_space", {})
    trajectory = state.get("trajectory", [])
    sweep_config = state.get("sweep_config", {})
    waves_parallel = sweep_config.get("strategy", {}).get("waves_parallel", 4)

    # Parse search space
    search_space: dict[str, ParameterSpec] = {}
    for name, spec_data in search_space_raw.items():
        search_space[name] = ParameterSpec.model_validate(spec_data)

    # Existing hparam fingerprints for dedup
    existing_fps: set[str] = set()
    for entry in trajectory:
        hp = entry.get("hyperparams", {})
        existing_fps.add(_fingerprint(hp))

    validated: list[dict[str, Any]] = []
    for config in wave_configs:
        clamped = _clamp_config(config, search_space)
        fp = _fingerprint(clamped)
        if fp not in existing_fps:
            validated.append(clamped)
            existing_fps.add(fp)

    # Fallback: fill with random samples if not enough valid proposals
    while len(validated) < waves_parallel:
        sample = {
            name: spec.sample_uniform() for name, spec in search_space.items()
        }
        fp = _fingerprint(sample)
        if fp not in existing_fps:
            validated.append(sample)
            existing_fps.add(fp)

    final = validated[:waves_parallel]
    return {
        "wave_configs": final,
        "messages": [
            AIMessage(
                content=f"Validated {len(final)} configs "
                f"({len(wave_configs)} proposed, "
                f"{len(final) - min(len(wave_configs), len(final))} random fallback)."
            ),
        ],
    }


def _clamp_config(
    config: dict[str, Any], search_space: dict[str, ParameterSpec]
) -> dict[str, Any]:
    """Clamp values to search space bounds."""
    clamped: dict[str, Any] = {}
    for name, spec in search_space.items():
        val = config.get(name)
        if val is None:
            clamped[name] = spec.sample_uniform()
            continue
        if spec.type in (ParamType.UNIFORM, ParamType.LOG_UNIFORM):
            val = max(spec.min, min(spec.max, float(val)))
            clamped[name] = val
        elif spec.type is ParamType.CHOICE:
            if val not in spec.values:
                clamped[name] = random.choice(spec.values)
            else:
                clamped[name] = val
    return clamped


def _fingerprint(config: dict[str, Any]) -> str:
    """Create a hashable fingerprint for dedup."""
    parts: list[str] = []
    for k in sorted(config.keys()):
        v = config[k]
        if isinstance(v, float):
            parts.append(f"{k}={v:.6g}")
        else:
            parts.append(f"{k}={v}")
    return "|".join(parts)
