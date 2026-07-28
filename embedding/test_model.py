'''
Qwen 모델이 다운로드·로딩되는가?
한국어 문장을 1024차원 벡터로 변환하는가?
'''
from __future__ import annotations

import torch
from sentence_transformers import SentenceTransformer

MODEL_NAME = "Qwen/Qwen3-Embedding-0.6B"


def main() -> None:
    device = "cuda" if torch.cuda.is_available() else "cpu"

    print(f"사용 장치: {device}")
    print(f"모델 로딩: {MODEL_NAME}")

    model = SentenceTransformer(
        MODEL_NAME,
        device=device,
    )

    texts = [
        "84A 주택형의 금회 공급호수는 101호입니다.",
        "계약체결일은 2026년 7월 22일입니다.",
    ]

    embeddings = model.encode(
        texts,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )

    print(f"벡터 배열 크기: {embeddings.shape}")
    print(f"첫 번째 벡터 일부: {embeddings[0][:10]}")


if __name__ == "__main__":
    main()