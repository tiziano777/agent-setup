from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Literal, Optional


class DatasetConfig(BaseModel):
    """Configuration for dataset preparation and processing"""
    cache_dir: str = Field(..., description="Directory to cache processed dataset")
    filtered_samples: Optional[str] = Field(None, description="Path to JSONL file with long-context samples to filter out")
    templates_mapping: str = Field(..., description="Path to YAML file mapping chat types to template modules")

    prompt_strategy: Literal["random", "round_robin", "all"] = Field(
        "random",
        description="Strategy for pairing samples with system prompts: random (seeded), round_robin (cyclic), all (cartesian)"
    )
    rejected_temperature: float = Field(
        0.7,
        ge=0.0,
        le=1.0,
        description="Temperature for sampling negative examples during dataset preparation"
    )

    shuffle_strategy: Literal["random", "circular"] = Field(
        "random",
        description="Strategy for shuffling dataset: random (Fisher-Yates) or circular (block-based)"
    )
    shuffle_seed: int = Field(42, ge=0, description="Random seed for shuffle reproducibility")
    shuffle_block_size: int = Field(1000, gt=0, description="Block size for circular shuffle (rows per block)")

    # Hard Negative Filter
    hard_negative_enabled: bool = Field(True, description="Enable NLP-based hard negative selection")
    hard_negative_fallback: Literal["drop", "temperature"] = Field(
        "temperature",
        description="Fallback when no valid candidate survives filtering: drop sample or use temperature selection"
    )
    hard_negative_rouge_delta: float = Field(
        0.08, ge=0.0, le=0.5,
        description="Candidates with ROUGE-L > (1 - delta) vs gold are discarded as false negatives"
    )
    hard_negative_tau: float = Field(
        0.5, ge=0.0, le=1.0,
        description="Target ROUGE-L for ideal hard negative distance from gold"
    )
    hard_negative_entropy_min: float = Field(
        0.3, ge=0.0, le=1.0,
        description="Min normalized entropy; below this threshold = degenerate (loop/repetition)"
    )
    hard_negative_ttr_min: float = Field(
        0.2, ge=0.0, le=1.0,
        description="Min Type-Token Ratio; below this threshold = degenerate"
    )
    hard_negative_w1: float = Field(0.2, ge=0.0, le=1.0, description="Weight: entropy")
    hard_negative_w2: float = Field(0.2, ge=0.0, le=1.0, description="Weight: TTR")
    hard_negative_w3: float = Field(0.4, ge=0.0, le=1.0, description="Weight: ROUGE distance from tau")
    hard_negative_w4: float = Field(0.2, ge=0.0, le=1.0, description="Weight: length penalty")
