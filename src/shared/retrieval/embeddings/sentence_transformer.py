"""Sentence-transformer embedding provider (local inference)."""

from __future__ import annotations

from src.shared.retrieval.embeddings.base import BaseEmbedding


class SentenceTransformerEmbedding(BaseEmbedding):
    """Embedding provider backed by a local sentence-transformers model.

    The model is loaded lazily on first call to :meth:`embed` or
    :meth:`embed_batch` so that importing the module is cheap.

    Args:
        model_name: HuggingFace model identifier.
        normalize: Whether to L2-normalize the output vectors.
        device: Torch device string (``"cpu"``, ``"cuda"``, ``"mps"``).
            When *None* sentence-transformers picks automatically.
    """

    DEFAULT_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    DEFAULT_DIMS = 384

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        normalize: bool = True,
        device: str | None = None,
    ) -> None:
        self._model_name = model_name
        self._normalize = normalize
        self._device = device
        self._model = None  # lazy
        self._dims: int | None = None

    # -- lazy model loading ------------------------------------------------

    def _load_model(self):
        if self._model is not None:
            return
        from sentence_transformers import SentenceTransformer

        kwargs = {}
        if self._device is not None:
            kwargs["device"] = self._device
        self._model = SentenceTransformer(self._model_name, **kwargs)
        self._dims = self._model.get_sentence_embedding_dimension()

    # -- BaseEmbedding interface -------------------------------------------

    def embed(self, text: str) -> list[float]:
        self._load_model()
        vector = self._model.encode(text, normalize_embeddings=self._normalize)
        return vector.tolist()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        self._load_model()
        vectors = self._model.encode(texts, normalize_embeddings=self._normalize)
        return [v.tolist() for v in vectors]

    @property
    def dimensions(self) -> int:
        if self._dims is None:
            self._load_model()
        return self._dims  # type: ignore[return-value]
