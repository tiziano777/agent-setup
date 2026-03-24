"""BM25 sparse index for lexical search.

Adapted from the Anthropic course implementation
(anthropic_course/rag/VectorDB/BM25Index.py) and conforms to the
:class:`BaseIndex` protocol.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any, Callable


class BM25Index:
    """In-memory BM25 index for keyword-based retrieval.

    Args:
        k1: Term frequency saturation parameter.
        b: Document length normalisation parameter.
        tokenizer: Custom tokenizer function. Defaults to lowercased
            whitespace/punctuation split.
    """

    def __init__(
        self,
        k1: float = 1.5,
        b: float = 0.75,
        tokenizer: Callable[[str], list[str]] | None = None,
    ) -> None:
        self.documents: list[dict[str, Any]] = []
        self._corpus_tokens: list[list[str]] = []
        self._doc_len: list[int] = []
        self._doc_freqs: dict[str, int] = {}
        self._avg_doc_len: float = 0.0
        self._idf: dict[str, float] = {}
        self._index_built: bool = False

        self.k1 = k1
        self.b = b
        self._tokenizer = tokenizer or self._default_tokenizer

    # -- tokenizer ---------------------------------------------------------

    @staticmethod
    def _default_tokenizer(text: str) -> list[str]:
        return [t for t in re.split(r"\W+", text.lower()) if t]

    # -- internal statistics -----------------------------------------------

    def _update_stats(self, doc_tokens: list[str]) -> None:
        self._doc_len.append(len(doc_tokens))
        seen: set[str] = set()
        for token in doc_tokens:
            if token not in seen:
                self._doc_freqs[token] = self._doc_freqs.get(token, 0) + 1
                seen.add(token)
        self._index_built = False

    def _build_index(self) -> None:
        if not self.documents:
            self._avg_doc_len = 0.0
            self._idf = {}
            self._index_built = True
            return
        n = len(self.documents)
        self._avg_doc_len = sum(self._doc_len) / n
        self._idf = {
            term: math.log(((n - freq + 0.5) / (freq + 0.5)) + 1)
            for term, freq in self._doc_freqs.items()
        }
        self._index_built = True

    def _score(self, query_tokens: list[str], doc_idx: int) -> float:
        counts = Counter(self._corpus_tokens[doc_idx])
        dl = self._doc_len[doc_idx]
        score = 0.0
        for token in query_tokens:
            idf = self._idf.get(token)
            if idf is None:
                continue
            tf = counts.get(token, 0)
            num = idf * tf * (self.k1 + 1)
            den = tf + self.k1 * (1 - self.b + self.b * (dl / self._avg_doc_len))
            score += num / (den + 1e-9)
        return score

    # -- BaseIndex protocol ------------------------------------------------

    def add_document(self, document: dict[str, Any]) -> None:
        content = document.get("content", "")
        if not isinstance(content, str):
            raise TypeError("Document 'content' must be a string.")
        tokens = self._tokenizer(content)
        self.documents.append(document)
        self._corpus_tokens.append(tokens)
        self._update_stats(tokens)

    def add_documents(self, documents: list[dict[str, Any]]) -> None:
        for doc in documents:
            self.add_document(doc)

    def search(
        self, query: Any, k: int = 5
    ) -> list[tuple[dict[str, Any], float]]:
        if not self.documents:
            return []
        if not isinstance(query, str):
            raise TypeError("BM25Index query must be a string.")
        if not self._index_built:
            self._build_index()
        if self._avg_doc_len == 0:
            return []

        tokens = self._tokenizer(query)
        if not tokens:
            return []

        scored = [
            (self._score(tokens, i), self.documents[i])
            for i in range(len(self.documents))
        ]
        scored = [(s, d) for s, d in scored if s > 1e-9]
        scored.sort(key=lambda x: x[0], reverse=True)

        return [(doc, score) for score, doc in scored[:k]]

    def __len__(self) -> int:
        return len(self.documents)
