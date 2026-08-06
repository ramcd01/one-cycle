from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from rag.retrieval.models import SearchResult


@dataclass(frozen=True)
class RerankResult:
    """Hybrid Search 결과 하나에 Reranker 결과를 결합한 객체."""

    search_result: SearchResult
    reranker_score: float
    reranker_rank: int

    @property
    def chunk_id(self) -> str:
        return self.search_result.chunk_id

    @property
    def item(self):
        return self.search_result.item

    @property
    def hybrid_rank(self) -> int | None:
        return self.search_result.fusion_rank

    def to_dict(self) -> dict[str, Any]:
        payload = self.search_result.to_dict()
        payload.update(
            {
                "reranker_score": self.reranker_score,
                "reranker_rank": self.reranker_rank,
                "hybrid_rank": self.hybrid_rank,
            }
        )
        return payload
