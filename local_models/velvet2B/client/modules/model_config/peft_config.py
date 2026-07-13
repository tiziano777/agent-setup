from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Literal


class PeftConfig(BaseModel):
    """Configuration for PEFT methods (e.g., LoRA)"""
    r: int = Field(..., gt=0, description="LoRA rank (intrinsic dimension of low-rank decomposition)")
    lora_alpha: int = Field(..., gt=0, description="LoRA alpha (scaling factor for LoRA weights)")
    lora_dropout: float = Field(0.0, ge=0.0, le=1.0, description="Dropout rate applied to LoRA layers")
    target_modules: list[str] = Field(
        ...,
        description="List of module names to apply LoRA to (e.g., ['q_proj', 'v_proj', 'k_proj', 'o_proj'])"
    )
