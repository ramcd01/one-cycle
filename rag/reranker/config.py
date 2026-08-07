from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RerankerConfig:
    """BGE Reranker 실행 설정."""

    model_name: str = "BAAI/bge-reranker-v2-m3"

    # Hybrid Search에서 넘겨받을 최대 후보 수
    hybrid_candidate_top_k: int = 20

    # Reranker 재정렬 후 최종 반환 수
    rerank_top_k: int = 5

    batch_size: int = 4
    max_length: int = 1024

    use_fp16: bool = True
    require_cuda: bool = True
    device_index: int = 0

    # True이면 score를 sigmoid로 변환하여 0~1 범위로 반환
    normalize_scores: bool = True

    # 질문과 비교할 청크 텍스트 필드
    # 기본은 실제 LLM 근거로 사용되는 content
    text_field: str = "content"

    def validate(self) -> None:
        numeric_values = {
            "hybrid_candidate_top_k": self.hybrid_candidate_top_k,
            "rerank_top_k": self.rerank_top_k,
            "batch_size": self.batch_size,
            "max_length": self.max_length,
        }

        for name, value in numeric_values.items():
            if value <= 0:
                raise ValueError(f"{name}는 1 이상이어야 합니다.")

        if self.rerank_top_k > self.hybrid_candidate_top_k:
            raise ValueError(
                "rerank_top_k는 hybrid_candidate_top_k보다 "
                "클 수 없습니다."
            )

        if self.text_field not in {"content", "search_text"}:
            raise ValueError(
                "text_field는 'content' 또는 'search_text'여야 합니다."
            )


DEFAULT_RERANKER_CONFIG = RerankerConfig()
