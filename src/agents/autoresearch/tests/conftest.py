"""Shared test fixtures for autoresearch tests."""

from __future__ import annotations

import pytest

from src.agents.autoresearch.config.models import (
    BudgetConfig,
    MetricConfig,
    MetricGoal,
    ParameterSpec,
    ParamType,
    StrategyConfig,
    StrategyType,
    SweepConfig,
)


@pytest.fixture
def minimal_sweep_config() -> dict:
    """A minimal sweep config dict for testing."""
    config = SweepConfig(
        name="test-sweep",
        base_setup=".",
        metric=MetricConfig(name="eval_accuracy", goal=MetricGoal.MAXIMIZE),
        budget=BudgetConfig(max_experiments=5, max_wall_time_hours=1.0),
        search_space={
            "learning_rate": ParameterSpec(
                type=ParamType.LOG_UNIFORM, min=1e-5, max=1e-3
            ),
            "batch_size": ParameterSpec(
                type=ParamType.CHOICE, values=[8, 16, 32]
            ),
        },
        strategy=StrategyConfig(type=StrategyType.RANDOM, waves_parallel=2),
    )
    return config.model_dump(mode="json")


@pytest.fixture
def sample_trajectory() -> list[dict]:
    """Sample experiment trajectory for node testing."""
    return [
        {
            "run_id": "exp_001",
            "wave_number": 1,
            "hyperparams": {"learning_rate": 1e-4, "batch_size": 16},
            "metrics": {"eval_accuracy": 0.82},
            "status": "completed",
            "wall_time_seconds": 120.0,
            "agent_reasoning": None,
        },
        {
            "run_id": "exp_002",
            "wave_number": 1,
            "hyperparams": {"learning_rate": 5e-4, "batch_size": 32},
            "metrics": {"eval_accuracy": 0.85},
            "status": "completed",
            "wall_time_seconds": 95.0,
            "agent_reasoning": None,
        },
        {
            "run_id": "exp_003",
            "wave_number": 2,
            "hyperparams": {"learning_rate": 2e-4, "batch_size": 8},
            "metrics": {},
            "status": "crashed",
            "wall_time_seconds": None,
            "agent_reasoning": None,
        },
    ]
