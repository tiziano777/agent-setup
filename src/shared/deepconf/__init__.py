"""RLM (Reasoning Language Model) module.

Exposes DeepConf class for deep thinking inference with confidence-based voting.
Built on facebookresearch/deepconf DeepThinkLLM with optional fallback strategies.
"""

from src.shared.deepconf.deep_conf import DeepConf, DeepConfOutput

__all__ = ["DeepConf", "DeepConfOutput"]
