"""LLM-based reranker (uses the project's LiteLLM proxy).

Adapted from the Anthropic course reranker pattern
(anthropic_course/rag/retriver/MultipleIndex.py).
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from src.shared.retrieval.rerankers.base import BaseReranker

if TYPE_CHECKING:
    from src.shared.retrieval.vectorstores.base import Document


class LLMReranker(BaseReranker):
    """Reranker that asks an LLM to select and order the most relevant documents.

    Uses :func:`src.shared.llm.get_llm` by default so it goes through
    the LiteLLM proxy and benefits from provider rotation.

    Args:
        llm: A LangChain-compatible chat model.  When *None*,
            :func:`get_llm` is called with ``temperature=0``.
    """

    def __init__(self, llm=None) -> None:
        self._llm = llm

    def _get_llm(self):
        if self._llm is not None:
            return self._llm
        from src.shared.llm import get_llm

        self._llm = get_llm(temperature=0.0)
        return self._llm

    def rerank(self, query: str, documents: list[Document], k: int) -> list[Document]:
        if len(documents) <= k:
            return list(documents)

        doc_xml = "\n".join(
            f"<document>\n"
            f"  <document_id>{doc.id}</document_id>\n"
            f"  <document_content>{doc.content}</document_content>\n"
            f"</document>"
            for doc in documents
        )

        prompt = (
            f"You are given a set of documents and a user question.\n"
            f"Select the {k} most relevant documents to answer the question "
            f"and return their IDs sorted by decreasing relevance.\n\n"
            f"<question>{query}</question>\n\n"
            f"<documents>\n{doc_xml}\n</documents>\n\n"
            f'Respond ONLY with JSON: {{"document_ids": ["id1", "id2", ...]}}'
        )

        llm = self._get_llm()
        response = llm.invoke([{"role": "user", "content": prompt}])

        text = response.content if hasattr(response, "content") else str(response)
        # Strip markdown fences if present.
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1]
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]

        try:
            ranked_ids = json.loads(text.strip())["document_ids"]
        except (json.JSONDecodeError, KeyError):
            # Fallback: return documents in original order.
            return documents[:k]

        lookup = {doc.id: doc for doc in documents}
        result = [lookup[did] for did in ranked_ids if did in lookup]

        # Pad with remaining documents if LLM returned fewer than k.
        if len(result) < k:
            seen = {doc.id for doc in result}
            for doc in documents:
                if doc.id not in seen:
                    result.append(doc)
                    if len(result) >= k:
                        break

        return result[:k]
