from __future__ import annotations

from dataclasses import dataclass

from rag.generation.config import (
    DEFAULT_GENERATION_CONFIG,
    GenerationConfig,
)
from rag.generation.generator import generate_answer
from rag.generation.models import GeneratedAnswer
from rag.reranker.config import (
    DEFAULT_RERANKER_CONFIG,
    RerankerConfig,
)
from rag.reranker.model_loader import (
    LoadedRerankerModel,
    load_reranker_model,
)
from rag.reranker.reranker import rerank_results
from rag.retrieval.config import (
    DEFAULT_RETRIEVAL_CONFIG,
    RetrievalConfig,
)
from rag.retrieval.hybrid_search import HybridSearcher


@dataclass
class RAGPipeline:
    """
    Hybrid Search → Reranker → Qwen Generation을 연결한다.

    한 공고와 문서 형식별로 인스턴스를 만들어 재사용하는 구조다.
    """

    searcher: HybridSearcher
    reranker_model: LoadedRerankerModel
    reranker_config: RerankerConfig
    generation_config: GenerationConfig

    @classmethod
    def from_files(
        cls,
        announcement_directory: str,
        *,
        document_format: str | None = None,
        retrieval_config: RetrievalConfig = (
            DEFAULT_RETRIEVAL_CONFIG
        ),
        reranker_config: RerankerConfig = (
            DEFAULT_RERANKER_CONFIG
        ),
        generation_config: GenerationConfig = (
            DEFAULT_GENERATION_CONFIG
        ),
    ) -> "RAGPipeline":
        searcher = HybridSearcher.from_files(
            announcement_directory,
            document_format=document_format,
            config=retrieval_config,
        )

        loaded_reranker = load_reranker_model(
            model_name=reranker_config.model_name,
            use_fp16=reranker_config.use_fp16,
            require_cuda=reranker_config.require_cuda,
            device_index=reranker_config.device_index,
        )

        return cls(
            searcher=searcher,
            reranker_model=loaded_reranker,
            reranker_config=reranker_config,
            generation_config=generation_config,
        )

    def ask(self, query: str) -> GeneratedAnswer:
        hybrid_results = self.searcher.search(
            query,
            hybrid_top_k=(
                self.reranker_config.hybrid_candidate_top_k
            ),
        )

        reranked = rerank_results(
            self.reranker_model,
            query,
            hybrid_results,
            config=self.reranker_config,
        )

        return generate_answer(
            query=query,
            announcement_directory=(
                self.searcher.corpus.announcement_directory
            ),
            document_format=self.searcher.corpus.document_format,
            rerank_results=reranked,
            config=self.generation_config,
        )
