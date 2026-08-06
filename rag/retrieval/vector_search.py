from __future__ import annotations

from typing import Any
import numpy as np
from embedding.model_loader import LoadedEmbeddingModel
from .models import LoadedCorpus, SearchResult

class VectorSearchError(RuntimeError):
    pass

def _extract_query_vector(output: Any) -> np.ndarray:
    if not isinstance(output, dict) or 'dense_vecs' not in output:
        raise VectorSearchError('BGE-M3 encode 결과에 dense_vecs가 없습니다.')
    vectors = np.asarray(output['dense_vecs'], dtype=np.float32)
    if vectors.ndim != 2 or vectors.shape[0] != 1:
        raise VectorSearchError(f"질문 임베딩 shape 오류: {vectors.shape}")
    vector = vectors[0]
    if not np.isfinite(vector).all():
        raise VectorSearchError('질문 임베딩에 NaN/Infinity가 있습니다.')
    return vector

def embed_query(loaded_model: LoadedEmbeddingModel, query: str, *, max_length: int, normalize: bool = True) -> np.ndarray:
    query = query.strip()
    if not query:
        raise VectorSearchError('검색 질문이 비어 있습니다.')
    try:
        output = loaded_model.model.encode([query], batch_size=1, max_length=max_length, return_dense=True, return_sparse=False, return_colbert_vecs=False)
    except Exception as exc:
        raise VectorSearchError(f"질문 임베딩 생성 실패: {exc}") from exc
    vector = _extract_query_vector(output)
    if normalize:
        norm = float(np.linalg.norm(vector))
        if norm == 0:
            raise VectorSearchError('질문 임베딩이 0 벡터입니다.')
        vector = vector / norm
    return vector.astype(np.float32, copy=False)

def vector_search(corpus: LoadedCorpus, query_vector: np.ndarray, *, top_k: int) -> list[SearchResult]:
    if top_k <= 0:
        raise VectorSearchError('top_k는 1 이상이어야 합니다.')
    query_vector = np.asarray(query_vector, dtype=np.float32)
    if query_vector.ndim != 1 or query_vector.shape[0] != corpus.embedding_dimension:
        raise VectorSearchError(f"질문 벡터 차원 오류: {query_vector.shape}, corpus={corpus.embedding_dimension}")
    if corpus.normalized:
        scores = corpus.embeddings @ query_vector
    else:
        cn = np.linalg.norm(corpus.embeddings, axis=1)
        qn = float(np.linalg.norm(query_vector))
        if qn == 0 or np.any(cn == 0):
            raise VectorSearchError('0 벡터 때문에 코사인 유사도를 계산할 수 없습니다.')
        scores = (corpus.embeddings @ query_vector)/(cn*qn)
    indexes = np.argsort(-scores, kind='stable')[:min(top_k, corpus.size)]
    results=[]
    for rank, idx in enumerate(indexes, start=1):
        i=int(idx); item=corpus.get_item(i)
        results.append(SearchResult(i, item.chunk_id, item, vector_score=float(scores[i]), vector_rank=rank, matched_by={'vector'}))
    return results
