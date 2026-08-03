"""BGE reranker의 한국어 대화 관련성 테스트."""

from __future__ import annotations

import numpy as np
import torch
from sentence_transformers import CrossEncoder


MODEL_NAME = "BAAI/bge-reranker-v2-m3"


def main() -> None:
    device = "cuda" if torch.cuda.is_available() else "cpu"

    print(f"장치: {device}")
    print(f"모델: {MODEL_NAME}")

    model = CrossEncoder(
        MODEL_NAME,
        device=device,
        max_length=512,
    )

    pairs = [
        (
            "그럼 미성년자는요?",
            "이전 사용자 질문: 누가 신청할 수 있나요?",
        ),
        (
            "필요한 서류는요?",
            "이전 사용자 질문: 누가 신청할 수 있나요?",
        ),
        (
            "필요한 서류는요?",
            "이전 사용자 질문: 그럼 미성년자는요?",
        ),
        (
            "필요한 서류는요?",
            "이전 사용자 질문: 계약할 때 무엇을 준비해야 하나요?",
        ),
    ]

    scores = model.predict(
        pairs,
        batch_size=4,
        show_progress_bar=True,
        convert_to_numpy=True,
    )

    scores = np.asarray(scores).reshape(-1)

    print()
    print("=" * 80)
    print("대화 관련성 재평가 결과")
    print("=" * 80)

    for index, ((question, history), score) in enumerate(
        zip(pairs, scores),
        start=1,
    ):
        print(f"[{index}] 점수={float(score):.6f}")
        print(f"현재 질문: {question}")
        print(f"이전 대화: {history}")
        print("-" * 80)


if __name__ == "__main__":
    main()
