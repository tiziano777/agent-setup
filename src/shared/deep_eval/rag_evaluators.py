"""RAG evaluators for Cognee, Qdrant, and PGVector.

Each class extends ``BaseDeepEvaluator`` and pre-configures the contextual
RAG metrics (recall, precision, relevancy).  A ``retrieve_context()`` method
uses the corresponding vector database from the project infrastructure.

Usage::

    evaluator = QdrantRAGEvaluator(collection_name="my_docs")
    context = evaluator.retrieve_context("What is LangGraph?")
    results = evaluator.evaluate(
        input="What is LangGraph?",
        actual_output="LangGraph is a framework for...",
        retrieval_context=context,
    )
"""

from __future__ import annotations

import logging
from typing import Any

from src.shared.deep_eval.base import BaseDeepEvaluator
from src.shared.deep_eval.config import _check_available

logger = logging.getLogger(__name__)


# ── Cognee RAG evaluator ─────────────────────────────────────────────


class CogneeRAGEvaluator(BaseDeepEvaluator):
    """RAG evaluator using Cognee knowledge graph for retrieval.

    Cognee builds a semantic graph over ingested data and supports
    14 different search types.  This evaluator wraps the Cognee search
    interface and runs DeepEval contextual metrics on results.

    Args:
        search_type: ``CogneeSearchType`` enum value (defaults to INSIGHTS).
        model: LLM model for metrics.  Falls back to proxy default.
        threshold: Pass/fail threshold for metric scores.
    """

    def __init__(
        self,
        search_type: Any | None = None,
        model: Any | None = None,
        threshold: float = 0.5,
        **kwargs: Any,
    ) -> None:
        self._search_type = search_type
        super().__init__(model=model, threshold=threshold, **kwargs)

    def _setup_metrics(self, **kwargs: Any) -> None:
        _check_available()
        from deepeval.metrics import (
            ContextualPrecisionMetric,
            ContextualRecallMetric,
            ContextualRelevancyMetric,
        )

        self._metrics = [
            ContextualRecallMetric(model=self._model, threshold=self._threshold),
            ContextualPrecisionMetric(model=self._model, threshold=self._threshold),
            ContextualRelevancyMetric(model=self._model, threshold=self._threshold),
        ]

    async def retrieve_context(self, query: str) -> list[str]:
        """Retrieve context from Cognee knowledge graph.

        Args:
            query: The search query.

        Returns:
            List of context strings from the knowledge graph.
        """
        from src.shared.cognee_toolkit import get_cognee_memory

        memory = get_cognee_memory()
        if self._search_type is not None:
            results = await memory.search(query, search_type=self._search_type)
        else:
            results = await memory.search(query)
        return [str(r) for r in results]

    def create_test_case(self, **kwargs: Any) -> Any:
        _check_available()
        from deepeval.test_case import LLMTestCase

        return LLMTestCase(
            input=kwargs["input"],
            actual_output=kwargs["actual_output"],
            expected_output=kwargs.get("expected_output"),
            retrieval_context=kwargs.get("retrieval_context"),
        )


# ── Qdrant RAG evaluator ─────────────────────────────────────────────


class QdrantRAGEvaluator(BaseDeepEvaluator):
    """RAG evaluator using Qdrant for vector similarity search.

    Connects to the project's Qdrant instance and runs DeepEval
    contextual metrics on retrieval results.

    Args:
        collection_name: Qdrant collection to search.
        top_k: Number of results to retrieve.
        model: LLM model for metrics.  Falls back to proxy default.
        threshold: Pass/fail threshold for metric scores.
    """

    def __init__(
        self,
        collection_name: str = "documents",
        top_k: int = 3,
        model: Any | None = None,
        threshold: float = 0.5,
        **kwargs: Any,
    ) -> None:
        self._collection_name = collection_name
        self._top_k = top_k
        super().__init__(model=model, threshold=threshold, **kwargs)

    def _setup_metrics(self, **kwargs: Any) -> None:
        _check_available()
        from deepeval.metrics import (
            ContextualPrecisionMetric,
            ContextualRecallMetric,
            ContextualRelevancyMetric,
        )

        self._metrics = [
            ContextualRecallMetric(model=self._model, threshold=self._threshold),
            ContextualPrecisionMetric(model=self._model, threshold=self._threshold),
            ContextualRelevancyMetric(model=self._model, threshold=self._threshold),
        ]

    def retrieve_context(self, query: str, top_k: int | None = None) -> list[str]:
        """Retrieve context from Qdrant vector search.

        Args:
            query: The search query.
            top_k: Override the default number of results.

        Returns:
            List of context strings from Qdrant.
        """
        from src.shared.retrieval import get_vectorstore

        store = get_vectorstore(
            provider="qdrant",
            collection_name=self._collection_name,
        )
        return store.search(query, top_k=top_k or self._top_k)

    def create_test_case(self, **kwargs: Any) -> Any:
        _check_available()
        from deepeval.test_case import LLMTestCase

        return LLMTestCase(
            input=kwargs["input"],
            actual_output=kwargs["actual_output"],
            expected_output=kwargs.get("expected_output"),
            retrieval_context=kwargs.get("retrieval_context"),
        )


# ── PGVector RAG evaluator ───────────────────────────────────────────


class PGVectorRAGEvaluator(BaseDeepEvaluator):
    """RAG evaluator using PGVector for PostgreSQL-based vector search.

    Connects to the project's PGVector instance and runs DeepEval
    contextual metrics on retrieval results.

    Args:
        table_name: PostgreSQL table with vector embeddings.
        top_k: Number of results to retrieve.
        schema: PostgreSQL schema.  Defaults to ``PGVECTOR_SCHEMA_DEEPEVAL``
            env var, or ``"deepeval"``.
        model: LLM model for metrics.  Falls back to proxy default.
        threshold: Pass/fail threshold for metric scores.
    """

    def __init__(
        self,
        table_name: str = "documents",
        top_k: int = 3,
        schema: str | None = None,
        model: Any | None = None,
        threshold: float = 0.5,
        **kwargs: Any,
    ) -> None:
        self._table_name = table_name
        self._top_k = top_k
        self._schema = schema
        super().__init__(model=model, threshold=threshold, **kwargs)

    def _setup_metrics(self, **kwargs: Any) -> None:
        _check_available()
        from deepeval.metrics import (
            ContextualPrecisionMetric,
            ContextualRecallMetric,
            ContextualRelevancyMetric,
        )

        self._metrics = [
            ContextualRecallMetric(model=self._model, threshold=self._threshold),
            ContextualPrecisionMetric(model=self._model, threshold=self._threshold),
            ContextualRelevancyMetric(model=self._model, threshold=self._threshold),
        ]

    def retrieve_context(self, query: str, top_k: int | None = None) -> list[str]:
        """Retrieve context from PGVector.

        Args:
            query: The search query.
            top_k: Override the default number of results.

        Returns:
            List of context strings from PGVector.
        """
        from src.shared.retrieval import get_vectorstore

        kwargs: dict[str, Any] = {}
        if self._schema is not None:
            kwargs["schema"] = self._schema
        store = get_vectorstore(provider="pgvector", **kwargs)
        return store.search(query, top_k=top_k or self._top_k)

    def create_test_case(self, **kwargs: Any) -> Any:
        _check_available()
        from deepeval.test_case import LLMTestCase

        return LLMTestCase(
            input=kwargs["input"],
            actual_output=kwargs["actual_output"],
            expected_output=kwargs.get("expected_output"),
            retrieval_context=kwargs.get("retrieval_context"),
        )
