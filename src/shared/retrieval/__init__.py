"""Retrieval infrastructure for the agent-setup project.

Provides factory functions that instantiate the right implementation
based on a provider name, following the same pattern used by
:func:`src.shared.llm.get_llm` and :func:`src.shared.memory.get_store`.

Quick-start example::

    from src.shared.retrieval import get_embedding, get_vectorstore

    emb = get_embedding("sentence-transformer")
    vs  = get_vectorstore("qdrant")
    vs.ensure_collection("docs", dims=emb.dimensions)

Or use :func:`get_retriever` for a ready-made hybrid pipeline::

    from src.shared.retrieval import get_retriever

    retriever = get_retriever()
    retriever.add_documents([{"id": "1", "content": "Hello world"}])
    results = retriever.search("hello", k=3)
"""

from __future__ import annotations

from src.shared.retrieval.chunking.base import BaseChunker
from src.shared.retrieval.config import RetrievalSettings
from src.shared.retrieval.contextual import ContextualEnricher
from src.shared.retrieval.embeddings.base import BaseEmbedding
from src.shared.retrieval.indexes.base import BaseIndex
from src.shared.retrieval.pipeline import RetrieverPipeline
from src.shared.retrieval.rerankers.base import BaseReranker
from src.shared.retrieval.vectorstores.base import BaseVectorStore, Document, SearchResult

__all__ = [
    # ABCs / data
    "BaseEmbedding",
    "BaseVectorStore",
    "BaseChunker",
    "BaseReranker",
    "BaseIndex",
    "Document",
    "SearchResult",
    # pipeline
    "RetrieverPipeline",
    "ContextualEnricher",
    # config
    "RetrievalSettings",
    # factories
    "get_embedding",
    "get_vectorstore",
    "get_chunker",
    "get_reranker",
    "get_retriever",
]


# ── Factory: Embedding ────────────────────────────────────────────────

def get_embedding(provider: str = "sentence-transformer", **kwargs) -> BaseEmbedding:
    """Return an embedding instance for the given provider.

    Supported providers:
        * ``"sentence-transformer"`` – local inference (default).
        * ``"openai"`` – OpenAI embeddings API.
    """
    if provider == "sentence-transformer":
        from src.shared.retrieval.embeddings.sentence_transformer import (
            SentenceTransformerEmbedding,
        )

        return SentenceTransformerEmbedding(**kwargs)

    if provider == "openai":
        from src.shared.retrieval.embeddings.openai import OpenAIEmbedding

        return OpenAIEmbedding(**kwargs)

    raise ValueError(f"Unknown embedding provider: {provider!r}")


# ── Factory: Vector Store ─────────────────────────────────────────────

def get_vectorstore(provider: str = "qdrant", **kwargs) -> BaseVectorStore:
    """Return a vector store instance for the given provider.

    Supported providers:
        * ``"qdrant"`` – Qdrant (default).
        * ``"pgvector"`` – PostgreSQL + pgvector.
    """
    if provider == "qdrant":
        from src.shared.retrieval.vectorstores.qdrant import QdrantVectorStore

        return QdrantVectorStore(**kwargs)

    if provider == "pgvector":
        from src.shared.retrieval.vectorstores.pgvector import PgVectorStore

        return PgVectorStore(**kwargs)

    raise ValueError(f"Unknown vectorstore provider: {provider!r}")


# ── Factory: Chunker ──────────────────────────────────────────────────

def get_chunker(strategy: str = "size", **kwargs) -> BaseChunker:
    """Return a chunker for the given strategy.

    Supported strategies:
        * ``"size"`` – character-based with overlap (default).
        * ``"sentence"`` – sentence-boundary splitting.
        * ``"structure"`` – heading/section splitting.
    """
    if strategy == "size":
        from src.shared.retrieval.chunking.size import SizeChunker

        return SizeChunker(**kwargs)

    if strategy == "sentence":
        from src.shared.retrieval.chunking.sentence import SentenceChunker

        return SentenceChunker(**kwargs)

    if strategy == "structure":
        from src.shared.retrieval.chunking.structure import StructureChunker

        return StructureChunker(**kwargs)

    raise ValueError(f"Unknown chunking strategy: {strategy!r}")


# ── Factory: Reranker ─────────────────────────────────────────────────

def get_reranker(provider: str = "cross-encoder", **kwargs) -> BaseReranker:
    """Return a reranker for the given provider.

    Supported providers:
        * ``"cross-encoder"`` – local CrossEncoder (default).
        * ``"llm"`` – LLM-based reranker via LiteLLM proxy.
    """
    if provider == "cross-encoder":
        from src.shared.retrieval.rerankers.cross_encoder import CrossEncoderReranker

        return CrossEncoderReranker(**kwargs)

    if provider == "llm":
        from src.shared.retrieval.rerankers.llm import LLMReranker

        return LLMReranker(**kwargs)

    raise ValueError(f"Unknown reranker provider: {provider!r}")


# ── Factory: Ready-made Retriever Pipeline ────────────────────────────

def get_retriever(
    settings: RetrievalSettings | None = None,
    **kwargs,
) -> RetrieverPipeline:
    """Build a hybrid retrieval pipeline from settings.

    By default creates a **BM25 + VectorIndex** pipeline with
    Reciprocal Rank Fusion merging.

    Args:
        settings: Configuration dataclass.  Uses defaults when *None*.
        **kwargs: Overrides forwarded to :class:`RetrieverPipeline`.
    """
    if settings is None:
        settings = RetrievalSettings()

    embedding = get_embedding(settings.embedding_provider, model_name=settings.embedding_model)

    from src.shared.retrieval.indexes.bm25 import BM25Index
    from src.shared.retrieval.indexes.vector import VectorIndex

    bm25 = BM25Index()
    vector = VectorIndex(embedding_fn=embedding.embed)

    indexes: list = [bm25, vector]

    reranker = None
    if settings.use_reranker:
        reranker = get_reranker(settings.reranker_provider)

    return RetrieverPipeline(
        indexes=indexes,
        reranker=reranker,
        k_rrf=settings.rrf_k,
        **kwargs,
    )
