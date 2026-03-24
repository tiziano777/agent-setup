"""OpenAI embedding provider (API-based)."""

from __future__ import annotations

import os

from src.shared.retrieval.embeddings.base import BaseEmbedding

# OpenAI enforces a per-request input limit for embeddings.
_MAX_BATCH_SIZE = 2048

# Known dimensions for common models.
_MODEL_DIMS: dict[str, int] = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
}


class OpenAIEmbedding(BaseEmbedding):
    """Embedding provider that calls the OpenAI embeddings API.

    Args:
        model: OpenAI model identifier.
        api_key: Explicit API key.  Falls back to ``OPENAI_API_KEY`` env var.
        dims: Override output dimensionality (only supported by ``text-embedding-3-*``).
            When *None* the model's native dimensionality is used.
    """

    DEFAULT_MODEL = "text-embedding-3-small"

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        api_key: str | None = None,
        dims: int | None = None,
    ) -> None:
        self._model = model
        self._api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self._requested_dims = dims
        self._client = None  # lazy

    # -- lazy client -------------------------------------------------------

    def _get_client(self):
        if self._client is not None:
            return self._client
        from openai import OpenAI

        self._client = OpenAI(api_key=self._api_key)
        return self._client

    # -- helpers -----------------------------------------------------------

    def _call_api(self, texts: list[str]) -> list[list[float]]:
        client = self._get_client()
        kwargs: dict = {"model": self._model, "input": texts}
        if self._requested_dims is not None:
            kwargs["dimensions"] = self._requested_dims
        response = client.embeddings.create(**kwargs)
        # Response data is already sorted by index.
        return [item.embedding for item in response.data]

    # -- BaseEmbedding interface -------------------------------------------

    def embed(self, text: str) -> list[float]:
        return self._call_api([text])[0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        all_vectors: list[list[float]] = []
        for start in range(0, len(texts), _MAX_BATCH_SIZE):
            chunk = texts[start : start + _MAX_BATCH_SIZE]
            all_vectors.extend(self._call_api(chunk))
        return all_vectors

    @property
    def dimensions(self) -> int:
        if self._requested_dims is not None:
            return self._requested_dims
        dims = _MODEL_DIMS.get(self._model)
        if dims is not None:
            return dims
        # Fallback: make a single-token call to discover dimensionality.
        vec = self.embed("dim")
        return len(vec)
