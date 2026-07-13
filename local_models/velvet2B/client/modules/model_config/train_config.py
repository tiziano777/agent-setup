from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Literal, Optional
from .peft_config import PeftConfig
from .deepspeed_config import DeepspeedConfig


class TrainingConfig(BaseModel):
    """Configuration for the training process"""
    learning_rate: float = Field(1e-5, gt=0.0, description="Learning rate for training")
    lr_scheduler_type: str = Field("linear", description="Learning rate scheduler type (e.g., linear, cosine)")
    optim: str = Field("paged_adamw_8bit", description="Optimizer (e.g., paged_adamw_8bit, adamw_torch)")
    beta: float = Field(0.1, ge=0.0, le=1.0, description="Beta parameter for DPO loss")
    weight_decay: float = Field(0.0, ge=0.0, description="Weight decay for regularization")
    warmup_steps: int = Field(1000, ge=0, description="Number of warmup steps")

    per_device_train_batch_size: int = Field(1, gt=0, description="Batch size per device during training")
    gradient_accumulation_steps: int = Field(16, gt=0, description="Number of steps to accumulate gradients before updating model")
    num_train_epochs: int = Field(3, gt=0, description="Number of training epochs")
    gradient_checkpointing: bool = Field(True, description="Enable gradient checkpointing to save memory")
    use_cache: bool = Field(False, description="Whether to use cached representations")
    ref_model: Optional[str] = Field(None, description="Path to reference model for DPO loss computation")
    precompute_ref_log_probs: bool = Field(False, description="Precompute reference model log probabilities")

    logging_steps: int = Field(10, gt=0, description="Log training metrics every N steps")
    eval_steps: int = Field(3000, gt=0, description="Run evaluation every N steps")
    save_steps: int = Field(3000, gt=0, description="Save checkpoint every N steps")
    max_steps: Optional[int] = Field(None, description="Maximum number of training steps (None = use num_train_epochs)")

    bf16: bool = Field(True, description="Use bfloat16 precision")
    torch_dtype: str = Field("bfloat16", description="Torch dtype (e.g., bfloat16, float16, float32)")
    remove_unused_columns: bool = Field(True, description="Remove unused columns from dataset")
    max_length: int = Field(8192, gt=0, description="Maximum total sequence length (prompt + response)")
    max_prompt_length: int = Field(2048, gt=0, description="Maximum prompt length")
    eval_size: float = Field(0.05, ge=0.0, le=1.0, description="Fraction of data to use for evaluation")

    deepspeed: Optional[DeepspeedConfig] = Field(None, description="DeepSpeed configuration")
    peft: Optional[PeftConfig] = Field(None, description="PEFT configuration (e.g., LoRA)")
