"""Cross-encoder reranker (local inference, no API calls)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.shared.retrieval.rerankers.base import BaseReranker

if TYPE_CHECKING:
    from src.shared.retrieval.vectorstores.base import Document


class CrossEncoderReranker(BaseReranker):
    """Reranker backed by a sentence-transformers CrossEncoder model.

    Cross-encoders jointly encode (query, document) pairs and produce a
    relevance score.  This is more accurate than bi-encoder cosine
    similarity but slower (O(n) inference per query).

    The model is loaded lazily on first call to :meth:`rerank`.

    Args:
        model_name: HuggingFace model identifier for the CrossEncoder.
        device: Torch device string.  *None* lets sentence-transformers choose.
    """

    DEFAULT_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        device: str | None = None,
    ) -> None:
        self._model_name = model_name
        self._device = device
        self._model = None  # lazy

    def _load_model(self):
        if self._model is not None:
            return
        from sentence_transformers import CrossEncoder

        kwargs = {}
        if self._device is not None:
            kwargs["device"] = self._device
        self._model = CrossEncoder(self._model_name, **kwargs)

    def rerank(self, query: str, documents: list[Document], k: int) -> list[Document]:
        if len(documents) <= k:
            return list(documents)

        self._load_model()

        pairs = [[query, doc.content] for doc in documents]
        scores = self._model.predict(pairs)

        scored = sorted(
            zip(scores, documents),
            key=lambda x: float(x[0]),
            reverse=True,
        )

        return [doc for _, doc in scored[:k]]
