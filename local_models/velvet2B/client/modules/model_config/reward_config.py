from __future__ import annotations
from pydantic import BaseModel, Field


class RewardFunction(BaseModel):
    """Configuration for a single reward function"""
    name: str = Field(..., min_length=1, description="Name identifier for the reward function")
    module_path: str = Field(..., min_length=1, description="Module import path (e.g., modules.rewards.accuracy_example)")


class RewardConfig(BaseModel):
    """Configuration for reward model and functions"""
    type: str = Field("verifiable", description="Type of reward (e.g., verifiable, learned)")
    functions: list[RewardFunction] = Field(
        default_factory=list,
        description="List of reward functions to apply during training evaluation"
    )
