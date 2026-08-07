from __future__ import annotations
from .models import SearchResult

class FusionError(RuntimeError):
    pass

def reciprocal_rank_fusion(vector_results: list[SearchResult], bm25_results: list[SearchResult], *, rrf_k: int = 60, top_k: int = 20) -> list[SearchResult]:
    if rrf_k <= 0 or top_k <= 0:
        raise FusionError('rrf_k와 top_k는 1 이상이어야 합니다.')
    merged={}
    def get(src):
        if src.vector_index not in merged:
            merged[src.vector_index]=SearchResult(src.vector_index, src.chunk_id, src.item)
        return merged[src.vector_index]
    for r in vector_results:
        m=get(r); m.vector_score=r.vector_score; m.vector_rank=r.vector_rank; m.matched_by.add('vector')
        if r.vector_rank is not None:
            m.fusion_score += 1.0/(rrf_k+r.vector_rank)
    for r in bm25_results:
        m=get(r); m.bm25_score=r.bm25_score; m.bm25_rank=r.bm25_rank; m.matched_by.add('bm25')
        if r.bm25_rank is not None:
            m.fusion_score += 1.0/(rrf_k+r.bm25_rank)
    ordered=sorted(merged.values(), key=lambda r:(-r.fusion_score, r.vector_rank or 10**9, r.bm25_rank or 10**9, r.vector_index))[:top_k]
    for rank, r in enumerate(ordered, start=1):
        r.fusion_rank=rank
    return ordered
