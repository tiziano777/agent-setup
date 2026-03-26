"""Retrieval pipeline configuration."""

import os
from dataclasses import dataclass, field


@dataclass
class RetrievalSettings:
    """Central configuration for the retrieval infrastructure.

    Reads defaults from environment variables where appropriate.
    """

    # Embedding
    embedding_provider: str = "sentence-transformer"  # or "openai"
    embedding_model: str = "paraphrase-multilingual-MiniLM-L12-v2"
    embedding_dims: int = 384

    # Vector Store
    vectorstore_provider: str = "qdrant"  # or "pgvector"
    collection_name: str = "default"

    # Qdrant
    qdrant_url: str = field(
        default_factory=lambda: os.getenv("QDRANT_URL", "http://localhost:6333")
    )
    qdrant_api_key: str | None = field(
        default_factory=lambda: os.getenv("QDRANT_API_KEY")
    )

    # pgvector
    postgres_uri: str = field(
        default_factory=lambda: os.getenv(
            "PGVECTOR_URI", "postgresql://postgres:postgres@localhost:5433/vectors"
        )
    )
    pgvector_index_type: str = "hnsw"  # or "ivfflat"
    pgvector_schema: str = field(
        default_factory=lambda: os.getenv("PGVECTOR_SCHEMA", "public")
    )

    # Retrieval
    search_k: int = 5
    rrf_k: int = 60
    use_reranker: bool = False
    reranker_provider: str = "cross-encoder"  # or "llm"
