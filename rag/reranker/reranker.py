from __future__ import annotations

from typing import Any

import numpy as np

from rag.retrieval.models import SearchResult

from .config import DEFAULT_RERANKER_CONFIG, RerankerConfig
from .model_loader import LoadedRerankerModel
from .models import RerankResult


class RerankerError(RuntimeError):
    """Reranker 점수 계산 또는 결과 검증 실패 시 발생한다."""


def _get_candidate_text(
    result: SearchResult,
    *,
    text_field: str,
) -> str:
    if text_field == "content":
        text = result.item.content
    elif text_field == "search_text":
        text = result.item.search_text
    else:
        raise RerankerError(
            f"지원하지 않는 Reranker 입력 필드입니다: {text_field}"
        )

    text = text.strip()

    if not text:
        raise RerankerError(
            f"Reranker 입력 텍스트가 비어 있습니다: {result.chunk_id}"
        )

    # 섹션 경로를 함께 넣어 문맥을 보존한다.
    section_path = " > ".join(result.item.section_path).strip()

    if section_path:
        return f"{section_path}\n\n{text}"

    return text


def _normalize_scores_output(
    raw_scores: Any,
    *,
    expected_count: int,
) -> np.ndarray:
    """
    FlagReranker.compute_score 반환값을 1차원 float32 배열로 변환한다.

    후보가 하나일 때 float 하나가 반환되는 버전도 지원한다.
    """
    scores = np.asarray(raw_scores, dtype=np.float32)

    if scores.ndim == 0:
        scores = scores.reshape(1)
    elif scores.ndim > 1:
        scores = scores.reshape(-1)

    if scores.shape[0] != expected_count:
        raise RerankerError(
            "후보 수와 Reranker 점수 수가 다릅니다: "
            f"candidates={expected_count}, scores={scores.shape[0]}"
        )

    if not np.isfinite(scores).all():
        raise RerankerError(
            "Reranker 점수에 NaN 또는 Infinity가 포함되어 있습니다."
        )

    return scores


def rerank_results(
    loaded_model: LoadedRerankerModel,
    query: str,
    candidates: list[SearchResult],
    *,
    config: RerankerConfig = DEFAULT_RERANKER_CONFIG,
    top_k: int | None = None,
) -> list[RerankResult]:
    """
    Hybrid Search 후보를 질문과 직접 비교하여 재정렬한다.
    """
    config.validate()

    query = query.strip()

    if not query:
        raise RerankerError("질문이 비어 있습니다.")

    if not candidates:
        raise RerankerError("재정렬할 Hybrid Search 후보가 없습니다.")

    candidate_limit = min(
        config.hybrid_candidate_top_k,
        len(candidates),
    )
    selected_candidates = candidates[:candidate_limit]

    pairs = [
        [
            query,
            _get_candidate_text(
                result,
                text_field=config.text_field,
            ),
        ]
        for result in selected_candidates
    ]

    print()
    print("=" * 70)
    print("Reranker 실행")
    print("=" * 70)
    print(f"질문              : {query}")
    print(f"Hybrid 후보 수    : {len(selected_candidates)}")
    print(f"배치 크기         : {config.batch_size}")
    print(f"최대 길이         : {config.max_length}")
    print(f"점수 정규화       : {config.normalize_scores}")
    print(f"입력 텍스트 필드  : {config.text_field}")

    try:
        raw_scores = loaded_model.model.compute_score(
            pairs,
            batch_size=config.batch_size,
            max_length=config.max_length,
            normalize=config.normalize_scores,
        )
    except TypeError:
        # 설치된 FlagEmbedding 버전이 batch_size 또는 normalize 인자를
        # 지원하지 않는 경우를 대비해 최소 인자로 다시 시도한다.
        try:
            raw_scores = loaded_model.model.compute_score(
                pairs,
                max_length=config.max_length,
                normalize=config.normalize_scores,
            )
        except Exception as exc:
            raise RerankerError(
                "Reranker 점수 계산에 실패했습니다.\n"
                f"실제 오류: {type(exc).__name__}: {exc}"
            ) from exc
    except RuntimeError as exc:
        if "out of memory" in str(exc).lower():
            raise RerankerError(
                "GPU 메모리가 부족합니다. "
                "rag/reranker/config.py의 batch_size를 줄이세요. "
                f"현재 batch_size={config.batch_size}"
            ) from exc

        raise RerankerError(
            "Reranker 추론 중 RuntimeError가 발생했습니다.\n"
            f"{exc}"
        ) from exc
    except Exception as exc:
        raise RerankerError(
            "Reranker 점수 계산에 실패했습니다.\n"
            f"실제 오류: {type(exc).__name__}: {exc}"
        ) from exc

    scores = _normalize_scores_output(
        raw_scores,
        expected_count=len(selected_candidates),
    )

    ordered_indexes = np.argsort(
        -scores,
        kind="stable",
    )

    result_limit = min(
        top_k if top_k is not None else config.rerank_top_k,
        len(selected_candidates),
    )

    results: list[RerankResult] = []

    for reranker_rank, index in enumerate(
        ordered_indexes[:result_limit],
        start=1,
    ):
        candidate = selected_candidates[int(index)]

        results.append(
            RerankResult(
                search_result=candidate,
                reranker_score=float(scores[index]),
                reranker_rank=reranker_rank,
            )
        )

    return results
