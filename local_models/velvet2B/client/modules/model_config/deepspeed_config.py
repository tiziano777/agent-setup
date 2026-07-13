from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Literal, Optional, Union

# Zero optimization configs

class OffloadOptimizerConfig(BaseModel):
    """Configuration for optimizer offloading"""
    device: Literal["cpu", "nvme"] = Field("cpu", description="Device to offload optimizer state to")
    pin_memory: bool = Field(True, description="Whether to pin memory for offloaded optimizer state")

class ActivationCheckpointingConfig(BaseModel):
    """Configuration for activation checkpointing to reduce memory usage"""
    partition_activations: bool = Field(True, description="Enable partitioning of activations across GPUs")
    cpu_checkpointing: bool = Field(True, description="Enable CPU offloading of checkpointed activations")
    contiguous_memory_optimization: bool = Field(True, description="Enable contiguous memory optimization for activations")
    synchronize_checkpoint_boundary: bool = Field(True, description="Synchronize checkpoint boundaries across GPUs")

class ZeroOptimizationConfig(BaseModel):
    """Configuration for ZeRO optimization"""
    stage: int = Field(2, ge=0, le=3, description="ZeRO stage (0=disabled, 1=param sharding, 2=grad+param sharding, 3=full sharding)")
    offload_optimizer: Optional[OffloadOptimizerConfig] = Field(None,description="Optimizer state offloading configuration")
    activation_checkpointing: Optional[ActivationCheckpointingConfig] = Field( None,description="Activation checkpointing configuration for memory optimization")

# Precision configs

class Fp16Config(BaseModel):
    """Configuration for FP16 precision"""
    enabled: bool = Field(False, description="Enable FP16 precision")

class Bf16Config(BaseModel):
    """Configuration for BF16 precision"""
    enabled: bool = Field(True, description="Enable BF16 precision")

# DEEPSPEED CONFIG

class DeepspeedConfig(BaseModel):
    """Configuration for DeepSpeed training"""
    fp16: Optional[Fp16Config] = Field(None, description="FP16 precision configuration")
    bf16: Optional[Bf16Config] = Field(None, description="BF16 precision configuration")
    
    zero_optimization: Optional[ZeroOptimizationConfig] = Field(None, description="ZeRO optimization configuration")

    gradient_accumulation_steps: Union[str, int] = Field("auto", description="Number of steps to accumulate gradients ('auto' to use training config value)")
    gradient_clipping: Union[str, float] = Field("auto", description="Maximum gradient norm ('auto' or float value)")
    train_batch_size: Union[str, int] = Field("auto", description="Global training batch size ('auto' to compute from per_device_train_batch_size)")
    train_micro_batch_size_per_gpu: Union[str, int] = Field("auto", description="Micro batch size per GPU ('auto' to use per_device_train_batch_size)")
