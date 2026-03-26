"""Adapter bridging BaseEmbedding to LightRAG's async EmbeddingFunc.

Wraps the project's synchronous :class:`BaseEmbedding.embed_batch` in
``run_in_executor`` and converts the output from ``list[list[float]]``
to ``np.ndarray`` as LightRAG expects.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)


def create_embedding_func(
    embedding_provider: str = "sentence-transformer",
    embedding_model: str = "paraphrase-multilingual-MiniLM-L12-v2",
    embedding_dims: int = 384,
    max_token_size: int = 8192,
    **kwargs: Any,
) -> Any:
    """Build a LightRAG ``EmbeddingFunc`` from the project's :class:`BaseEmbedding`.

    The returned object satisfies LightRAG's embedding interface::

        EmbeddingFunc(embedding_dim, max_token_size, func)

    where ``func`` is ``async (texts: list[str]) -> np.ndarray``.
    """
    from lightrag.utils import EmbeddingFunc

    from src.shared.retrieval import get_embedding

    embedding = get_embedding(provider=embedding_provider, model_name=embedding_model, **kwargs)

    actual_dims = embedding.dimensions
    if actual_dims != embedding_dims:
        logger.warning(
            "Configured embedding_dims=%d but model reports %d; using model value.",
            embedding_dims,
            actual_dims,
        )
        embedding_dims = actual_dims

    async def _embed_texts(texts: list[str], **_kw: Any) -> Any:
        import numpy as np

        loop = asyncio.get_running_loop()
        vectors = await loop.run_in_executor(None, embedding.embed_batch, texts)
        return np.array(vectors)

    return EmbeddingFunc(
        embedding_dim=embedding_dims,
        max_token_size=max_token_size,
        func=_embed_texts,
    )
