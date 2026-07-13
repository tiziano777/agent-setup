from __future__ import annotations
import logging
from typing import Any, Optional

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import LoraConfig, get_peft_model, TaskType

logger = logging.getLogger(__name__)


class ModelLoader:
    """Load, configure and optionally wrap models with PEFT adapters.

    Usage:
        loader = ModelLoader(hf_token=os.getenv('HF_TOKEN'))
        model, tokenizer = loader.load_model(
            model_id='velvet-2b',
            model_uri='/path/to/checkpoint',
            peft_cfg={'r': 16, 'lora_alpha': 32, ...},
        )
    """

    def __init__(self, hf_token: Optional[str] = None) -> None:
        self.hf_token = hf_token
        self.model = None
        self.tokenizer = None
        self.peft_config = None

        if self.hf_token:
            try:
                from huggingface_hub import login
                login(token=self.hf_token)
                logger.info('Logged into Hugging Face hub via HF_TOKEN')
            except Exception as e:
                logger.warning('Could not login to huggingface_hub: %s', e)

    # ------------------------------------------------------------------
    # High-level entry point
    # ------------------------------------------------------------------

    def load_model(
        self,
        model_id: str,
        model_uri: str | None = None,
        torch_dtype: str = "bfloat16",
        device_map: str | None = None,
        peft_cfg: dict | None = None
    ) -> tuple[AutoModelForCausalLM, AutoTokenizer]:
        """Load base model + tokenizer; optionally apply LoRA on last N% layers.

        Args:
            model_id: HF model id (fallback if model_uri is None).
            model_uri: Local path or URI (takes precedence over model_id).
            torch_dtype: Dtype string (e.g. 'bfloat16', 'float16').
            device_map: Device map passed to from_pretrained.
            peft_cfg: Dict from config.yml 'peft' section. If present, LoRA is applied.
    
        Returns:
            (model, tokenizer) tuple ready for training.
        """
        dtype = getattr(torch, torch_dtype) if isinstance(torch_dtype, str) and hasattr(torch, torch_dtype) else torch.float16
        model_kwargs: dict[str, Any] = {'torch_dtype': dtype, 'device_map': device_map}

        # Resolve source
        source = model_uri or model_id
        if model_uri:
            model = self._load_from_uri(model_uri, trust_remote_code=True, **model_kwargs)
        else:
            model = self._load_from_hf(model_id, **model_kwargs)

        # PEFT / LoRA
        if peft_cfg:
            model = self._apply_peft(model, peft_cfg)

        # Tokenizer
        tokenizer = AutoTokenizer.from_pretrained(source, trust_remote_code=True)
        
        # Configura il tokenizer
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token
            tokenizer.pad_token_id = tokenizer.eos_token_id
        tokenizer.padding_side = "right"
        if hasattr(model, 'config'):
            model.config.pad_token_id = tokenizer.pad_token_id
            model.config.eos_token_id = tokenizer.eos_token_id

        self.model = model
        self.tokenizer = tokenizer
        return model, tokenizer

    # ------------------------------------------------------------------
    # PEFT helpers
    # ------------------------------------------------------------------

    def _apply_peft(self, model, peft_cfg: dict):
        """Apply LoRA adapter filtered to last `trainable_ratio` of layers."""
        target_modules = peft_cfg.get('target_modules', [])
        peft_trainable_ratio = peft_cfg.get('peft_trainable_ratio', 0.4)

        if target_modules and hasattr(model, 'config'):
            n_layers = getattr(model.config, 'num_hidden_layers', None)
            if n_layers:
                first_layer = int(n_layers * (1 - float(peft_trainable_ratio)))
                filtered = []
                for mod in target_modules:
                    for idx in range(first_layer, n_layers):
                        filtered.append(f"model.layers.{idx}.self_attn.{mod}")
                        filtered.append(f"model.layers.{idx}.mlp.{mod}")
                target_modules = filtered
                logger.info("LoRA on last %d%% layers (%d-%d of %d): %d modules",
                            int(float(peft_trainable_ratio) * 100), first_layer, n_layers - 1, n_layers, len(target_modules))

        lora_cfg = LoraConfig(
            r=peft_cfg.get('r', 16),
            lora_alpha=peft_cfg.get('lora_alpha', 32),
            lora_dropout=peft_cfg.get('lora_dropout', 0.05),
            bias=peft_cfg.get('bias', 'none'),
            task_type=TaskType.CAUSAL_LM,
            init_lora_weights=peft_cfg.get('init_lora_weights', True),
            inference_mode=peft_cfg.get('inference_mode', False),
            use_dora=peft_cfg.get('use_dora', False),
            target_modules=target_modules,
        )
        self.peft_config = lora_cfg

        model = get_peft_model(model, lora_cfg)
        try:
            model.print_trainable_parameters()
        except Exception:
            pass
        return model

    # ------------------------------------------------------------------
    # Low-level loaders (kept for direct use)
    # ------------------------------------------------------------------

    def _load_from_hf(self, model_id: str, **kwargs: Any) -> AutoModelForCausalLM:
        """Load a model from Hugging Face hub."""
        if self.hf_token:
            kwargs.setdefault('token', self.hf_token)
        return AutoModelForCausalLM.from_pretrained(model_id, **kwargs)

    def _load_from_uri(self, uri: str, **kwargs: Any) -> AutoModelForCausalLM:
        """Load a model from an arbitrary URI or local path."""
        if self.hf_token:
            kwargs.setdefault('token', self.hf_token)
        return AutoModelForCausalLM.from_pretrained(uri, **kwargs)
