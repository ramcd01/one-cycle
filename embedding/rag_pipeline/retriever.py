from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from search_embeddings import (
    TOP_K,
    build_expanded_context,
    calculate_similarity,
    encode_query,
    get_reranked_results,
)


@dataclass(slots=True)
class RetrievalOutput:
    raw_results: list[dict[str, Any]]
    context_results: list[dict[str, Any]]
    expansion: dict[str, Any]
    max_raw_similarity: float
    max_context_similarity: float


class Retriever:
    def __init__(
        self,
        *,
        embedding_model: Any,
        embeddings: np.ndarray,
        chunks: list[dict[str, Any]],
        top_k: int = TOP_K,
    ) -> None:
        self.embedding_model = embedding_model
        self.embeddings = embeddings
        self.chunks = chunks
        self.top_k = top_k

    def retrieve(self, question: str) -> RetrievalOutput:
        query_embedding = encode_query(self.embedding_model, question)
        scores = calculate_similarity(self.embeddings, query_embedding)
        raw_results = get_reranked_results(
            question,
            scores,
            self.chunks,
            self.top_k,
        )
        expansion = build_expanded_context(
            question,
            raw_results,
            scores,
            self.chunks,
        )
        context_results = expansion.get("context_results", [])

        max_raw = max(
            (float(item.get("similarity", 0.0)) for item in raw_results),
            default=0.0,
        )
        max_context = max(
            (float(item.get("similarity", 0.0)) for item in context_results),
            default=0.0,
        )

        return RetrievalOutput(
            raw_results=raw_results,
            context_results=context_results,
            expansion=expansion,
            max_raw_similarity=max_raw,
            max_context_similarity=max_context,
        )
