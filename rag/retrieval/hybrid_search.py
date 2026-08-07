from __future__ import annotations

from pathlib import Path
from embedding.model_loader import LoadedEmbeddingModel, load_bge_m3_model
from .bm25_search import BM25Index, bm25_search
from .config import DEFAULT_RETRIEVAL_CONFIG, RetrievalConfig
from .corpus_loader import load_corpus
from .fusion import reciprocal_rank_fusion
from .models import LoadedCorpus, SearchResult
from .vector_search import embed_query, vector_search

class HybridSearchError(RuntimeError):
    pass

class HybridSearcher:
    def __init__(self, corpus: LoadedCorpus, loaded_model: LoadedEmbeddingModel, *, config: RetrievalConfig = DEFAULT_RETRIEVAL_CONFIG) -> None:
        config.validate()
        if corpus.model_name is not None and corpus.model_name != config.embedding_model_name:
            raise HybridSearchError(f"문서/질문 임베딩 모델 불일치: {corpus.model_name} != {config.embedding_model_name}")
        self.corpus=corpus
        self.loaded_model=loaded_model
        self.config=config
        self.bm25_index=BM25Index.from_corpus(corpus)

    @classmethod
    def from_files(cls, announcement_directory: str, *, document_format: str | None = None, outputs_root: str | Path | None = None, config: RetrievalConfig = DEFAULT_RETRIEVAL_CONFIG, loaded_model: LoadedEmbeddingModel | None = None) -> 'HybridSearcher':
        config.validate()
        corpus=load_corpus(announcement_directory, document_format=document_format, outputs_root=Path(outputs_root) if outputs_root is not None else config.outputs_root)
        if loaded_model is None:
            loaded_model=load_bge_m3_model(model_name=config.embedding_model_name, use_fp16=config.use_fp16, require_cuda=config.require_cuda, device_index=config.device_index)
        return cls(corpus, loaded_model, config=config)

    def search(self, query: str, *, vector_top_k: int | None = None, bm25_top_k: int | None = None, hybrid_top_k: int | None = None) -> list[SearchResult]:
        query=query.strip()
        if not query:
            raise HybridSearchError('검색 질문이 비어 있습니다.')
        query_vector=embed_query(self.loaded_model, query, max_length=self.config.query_max_length, normalize=True)
        v=vector_search(self.corpus, query_vector, top_k=vector_top_k or self.config.vector_top_k)
        b=bm25_search(self.corpus, self.bm25_index, query, top_k=bm25_top_k or self.config.bm25_top_k)
        return reciprocal_rank_fusion(v, b, rrf_k=self.config.rrf_k, top_k=hybrid_top_k or self.config.hybrid_top_k)
