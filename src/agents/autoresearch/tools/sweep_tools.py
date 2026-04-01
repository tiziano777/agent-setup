"""Tools for sweep configuration sampling and validation."""

from __future__ import annotations

import json
from typing import Any

from langchain_core.tools import tool

from src.agents.autoresearch.config.models import ParameterSpec


@tool
def sample_random_config(search_space_json: str) -> str:
    """Sample a random hyperparameter configuration from the search space.

    Args:
        search_space_json: JSON string of the search space definition.
    """
    raw = json.loads(search_space_json)
    config: dict[str, Any] = {}
    for name, spec_data in raw.items():
        spec = ParameterSpec.model_validate(spec_data)
        config[name] = spec.sample_uniform()
    return json.dumps(config, indent=2)


@tool
def validate_config(config_json: str, search_space_json: str) -> str:
    """Validate and clamp a proposed config to search space bounds.

    Args:
        config_json: JSON string of the proposed hyperparameter config.
        search_space_json: JSON string of the search space definition.
    """
    import random as _random

    config = json.loads(config_json)
    search_space = json.loads(search_space_json)
    issues: list[str] = []

    for name, spec_data in search_space.items():
        spec = ParameterSpec.model_validate(spec_data)
        val = config.get(name)
        if val is None:
            config[name] = spec.sample_uniform()
            issues.append(f"{name}: missing, sampled random value")
            continue
        if spec.min is not None and spec.max is not None:
            if val < spec.min or val > spec.max:
                clamped = max(spec.min, min(spec.max, float(val)))
                issues.append(f"{name}: {val} clamped to {clamped}")
                config[name] = clamped
        if spec.values is not None and val not in spec.values:
            new_val = _random.choice(spec.values)
            issues.append(f"{name}: {val} not in choices, replaced with {new_val}")
            config[name] = new_val

    return json.dumps({
        "config": config,
        "valid": len(issues) == 0,
        "issues": issues,
    }, indent=2)
