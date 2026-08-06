from __future__ import annotations

import sys
from pathlib import Path


if __package__ in (None, ""):
    PROJECT_ROOT = Path(__file__).resolve().parents[2]

    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))


import numpy as np

from rag.reranker.config import DEFAULT_RERANKER_CONFIG
from rag.reranker.model_loader import (
    clear_reranker_cuda_cache,
    load_reranker_model,
)


def main() -> int:
    config = DEFAULT_RERANKER_CONFIG

    try:
        loaded = load_reranker_model(
            model_name=config.model_name,
            use_fp16=config.use_fp16,
            require_cuda=config.require_cuda,
            device_index=config.device_index,
        )

        pairs = [
            [
                "계약금은 얼마야?",
                "계약금은 1,000만원 정액제입니다.",
            ],
            [
                "계약금은 얼마야?",
                "입주 예정 시기는 2028년 3월입니다.",
            ],
        ]

        scores = loaded.model.compute_score(
            pairs,
            batch_size=2,
            max_length=config.max_length,
            normalize=True,
        )

        scores_array = np.asarray(
            scores,
            dtype=np.float32,
        ).reshape(-1)

        print()
        print("=" * 70)
        print("Reranker 모델 테스트 완료")
        print("=" * 70)
        print(f"점수: {scores_array.tolist()}")

        if scores_array.shape[0] != 2:
            raise RuntimeError(
                f"점수 개수가 올바르지 않습니다: {scores_array.shape}"
            )

        if not np.isfinite(scores_array).all():
            raise RuntimeError(
                "점수에 NaN 또는 Infinity가 있습니다."
            )

        if scores_array[0] <= scores_array[1]:
            print(
                "경고: 관련 문장의 점수가 비관련 문장보다 "
                "높지 않습니다. 모델과 입력을 확인하세요."
            )

        return 0

    except Exception as exc:
        print()
        print("[Reranker 모델 테스트 실패]")
        print(f"{type(exc).__name__}: {exc}")
        return 1

    finally:
        clear_reranker_cuda_cache()


if __name__ == "__main__":
    sys.exit(main())
