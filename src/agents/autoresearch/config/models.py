"""Pydantic v2 configuration models for autoresearch sweeps.

Adapted from the original autoresearch config/models.py with LLMConfig
dependency removed (now uses src.shared.llm.get_llm() via proxy).
"""

from __future__ import annotations

import math
from enum import Enum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, model_validator

# ---------------------------------------------------------------------------
# Parameter specification
# ---------------------------------------------------------------------------

class ParamType(str, Enum):
    """Supported hyperparameter distribution types."""

    LOG_UNIFORM = "log_uniform"
    UNIFORM = "uniform"
    CHOICE = "choice"


class ParameterSpec(BaseModel):
    """A single hyperparameter's search specification."""

    type: ParamType
    min: float | None = None
    max: float | None = None
    values: list[Any] | None = None

    @model_validator(mode="after")
    def _validate_bounds(self) -> ParameterSpec:
        if self.type in (ParamType.LOG_UNIFORM, ParamType.UNIFORM):
            if self.min is None or self.max is None:
                raise ValueError(
                    f"Parameter type '{self.type.value}' requires 'min' and 'max'."
                )
            if self.min >= self.max:
                raise ValueError(
                    f"'min' ({self.min}) must be strictly less than 'max' ({self.max})."
                )
            if self.type is ParamType.LOG_UNIFORM and self.min <= 0:
                raise ValueError("log_uniform requires positive 'min'.")
        elif self.type is ParamType.CHOICE:
            if not self.values:
                raise ValueError(
                    "Parameter type 'choice' requires a non-empty 'values' list."
                )
        return self

    def sample_uniform(self, rng: Any | None = None) -> float | Any:
        """Draw a single sample from this parameter spec."""
        import random

        _rng = rng or random
        if self.type is ParamType.UNIFORM:
            return _rng.uniform(self.min, self.max)
        if self.type is ParamType.LOG_UNIFORM:
            log_val = _rng.uniform(math.log(self.min), math.log(self.max))
            return math.exp(log_val)
        return _rng.choice(self.values)


SearchSpace = dict[str, ParameterSpec]


# ---------------------------------------------------------------------------
# Agent rules
# ---------------------------------------------------------------------------

class ExplorationStrategy(str, Enum):
    CONSERVATIVE = "conservative"
    BALANCED = "balanced"
    AGGRESSIVE = "aggressive"


class AgentRules(BaseModel):
    """Constraints and preferences governing agent behaviour during a sweep."""

    rules_file: Path | None = Field(default=None)
    constraints: list[str] = Field(default_factory=list)
    preferences: list[str] = Field(default_factory=list)
    exploration_strategy: ExplorationStrategy = Field(
        default=ExplorationStrategy.BALANCED,
    )

    def load_rules_file(self) -> dict[str, Any]:
        if self.rules_file is None or not self.rules_file.exists():
            return {}
        return yaml.safe_load(self.rules_file.read_text()) or {}


# ---------------------------------------------------------------------------
# Metric / budget / strategy / hardware
# ---------------------------------------------------------------------------

class MetricGoal(str, Enum):
    MAXIMIZE = "maximize"
    MINIMIZE = "minimize"


class MetricConfig(BaseModel):
    name: str
    goal: MetricGoal = MetricGoal.MAXIMIZE


class CalibrationConfig(BaseModel):
    enabled: bool = False
    calibration_runs: int = Field(ge=1, default=3)
    timeout_multiplier: float = Field(gt=1.0, default=2.0)
    min_timeout_seconds: float = Field(ge=30, default=120)
    max_timeout_seconds: float | None = None


class BudgetConfig(BaseModel):
    max_experiments: int = Field(ge=1, default=100)
    max_wall_time_hours: float = Field(gt=0, default=8.0)
    max_run_time_seconds: float | None = Field(default=None, ge=60)
    calibration: CalibrationConfig = Field(default_factory=CalibrationConfig)


class StrategyType(str, Enum):
    AGENT = "agent"
    RANDOM = "random"
    GRID = "grid"


class StrategyConfig(BaseModel):
    type: StrategyType = StrategyType.AGENT
    waves_parallel: int = Field(ge=1, default=4)


class HardwareBackend(str, Enum):
    LOCAL = "local"
    SSH = "ssh"
    SLURM = "slurm"
    SKYPILOT = "skypilot"


class SkyPilotConfig(BaseModel):
    accelerators: str = "A100:1"
    cloud: str | None = None
    region: str | None = None
    instance_type: str | None = None
    use_spot: bool = False
    num_nodes: int = Field(ge=1, default=1)


class HardwareConfig(BaseModel):
    backend: HardwareBackend = HardwareBackend.LOCAL
    max_concurrent_jobs: int = Field(ge=1, default=4)
    ssh_host: str | None = None
    ssh_user: str | None = None
    ssh_key_path: Path | None = None
    partition: str | None = None
    skypilot: SkyPilotConfig | None = None


# ---------------------------------------------------------------------------
# Agent mode and code-editing
# ---------------------------------------------------------------------------

class AgentMode(str, Enum):
    HPARAM_ONLY = "hparam_only"
    CODE_EDIT = "code_edit"


class CodeEditConfig(BaseModel):
    editable_files: list[str] = Field(default_factory=lambda: ["train.py"])
    protected_files: list[str] = Field(
        default_factory=lambda: ["prepare.py", "config.yaml", "requirements.txt"],
    )
    git_tracking: bool = True
    snapshot_per_experiment: bool = True


# ---------------------------------------------------------------------------
# Staged escalation
# ---------------------------------------------------------------------------

class EscalationStage(BaseModel):
    name: str
    parameters: list[str]
    min_experiments: int = Field(ge=1, default=5)
    plateau_patience: int = Field(ge=1, default=5)
    plateau_threshold: float = Field(ge=0, default=0.01)


class EscalationConfig(BaseModel):
    enabled: bool = False
    stages: list[EscalationStage] = Field(default_factory=list)
    auto_generate: bool = True


# ---------------------------------------------------------------------------
# LLM settings (simplified — proxy config comes from src.shared.llm)
# ---------------------------------------------------------------------------

class LLMSettings(BaseModel):
    """LLM settings for agent-driven and post-wave analysis.

    The actual proxy URL and model routing are handled by
    ``src.shared.llm.get_llm()``. These settings control behaviour.
    """

    enabled: bool = False
    temperature: float = 0.7
    max_tokens_per_call: int = 4096
    max_total_tokens: int = 500_000


# ---------------------------------------------------------------------------
# Top-level SweepConfig
# ---------------------------------------------------------------------------

class SweepConfig(BaseModel):
    """Complete specification for a hyperparameter sweep."""

    name: str
    base_setup: Path
    metric: MetricConfig
    budget: BudgetConfig = Field(default_factory=BudgetConfig)
    search_space: dict[str, ParameterSpec]
    agent_rules: AgentRules = Field(default_factory=AgentRules)
    strategy: StrategyConfig = Field(default_factory=StrategyConfig)
    hardware: HardwareConfig = Field(default_factory=HardwareConfig)
    agent_mode: AgentMode = AgentMode.HPARAM_ONLY
    code_edit: CodeEditConfig = Field(default_factory=CodeEditConfig)
    escalation: EscalationConfig = Field(default_factory=EscalationConfig)
    llm: LLMSettings = Field(default_factory=LLMSettings)

    @model_validator(mode="after")
    def _check_search_space_non_empty(self) -> SweepConfig:
        if not self.search_space:
            raise ValueError("search_space must contain at least one parameter.")
        return self

    @classmethod
    def from_yaml(cls, path: str | Path) -> SweepConfig:
        raw = yaml.safe_load(Path(path).read_text())
        sweep_data = raw.get("sweep", raw)
        return cls.model_validate(sweep_data)

    def to_yaml(self, path: str | Path) -> None:
        data = {"sweep": self.model_dump(mode="json")}
        Path(path).write_text(
            yaml.dump(data, default_flow_style=False, sort_keys=False)
        )
