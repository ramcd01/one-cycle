"""선택한 공고에서 관련 청크를 검색하고 llama.cpp로 답변한다."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import requests
import torch
from sentence_transformers import SentenceTransformer


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = PROJECT_ROOT / "outputs"

EMBEDDING_MODEL = "Qwen/Qwen3-Embedding-0.6B"
LLAMA_URL = "http://127.0.0.1:8080"
LLAMA_MODEL = "local-rag"


def find_embedding_dir(document_id: str, document_format: str | None) -> Path:
    root = OUTPUT_ROOT / document_id / "05_embeddings"

    if not root.exists():
        raise FileNotFoundError(f"임베딩 폴더가 없습니다: {root}")

    candidates: list[Path] = []

    for directory in sorted(root.iterdir()):
        if not directory.is_dir():
            continue

        if document_format and directory.name != document_format:
            continue

        if (
            (directory / "embeddings.npy").exists()
            and (directory / "metadata.json").exists()
        ):
            candidates.append(directory)

    if not candidates:
        raise FileNotFoundError(
            f"{document_id}에서 사용할 임베딩 결과가 없습니다."
        )

    if len(candidates) > 1:
        formats = ", ".join(path.name for path in candidates)
        raise ValueError(
            f"임베딩 형식이 여러 개입니다: {formats}. "
            "--format으로 하나를 선택하세요."
        )

    return candidates[0]


def load_embedding_data(
    embedding_dir: Path,
) -> tuple[np.ndarray, list[dict[str, Any]]]:
    vectors = np.load(embedding_dir / "embeddings.npy")

    with (embedding_dir / "metadata.json").open(
        "r",
        encoding="utf-8",
    ) as file:
        metadata = json.load(file)

    chunks = metadata.get("chunks")

    if not isinstance(chunks, list):
        raise ValueError("metadata.json에 chunks 배열이 없습니다.")

    if vectors.ndim != 2:
        raise ValueError(f"잘못된 벡터 형태입니다: {vectors.shape}")

    if vectors.shape[0] != len(chunks):
        raise ValueError(
            "벡터 수와 메타데이터 수가 다릅니다: "
            f"{vectors.shape[0]} != {len(chunks)}"
        )

    return vectors, chunks


def load_query_model() -> SentenceTransformer:
    device = "cuda" if torch.cuda.is_available() else "cpu"

    print(f"질문 임베딩 장치: {device}")
    print(f"질문 임베딩 모델: {EMBEDDING_MODEL}")

    model = SentenceTransformer(
        EMBEDDING_MODEL,
        device=device,
    )
    model.eval()

    return model


def embed_question(
    model: SentenceTransformer,
    question: str,
) -> np.ndarray:
    vector = model.encode(
        [question],
        prompt_name="query",
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )

    return np.asarray(vector[0], dtype=np.float32)


def search_chunks(
    vectors: np.ndarray,
    chunks: list[dict[str, Any]],
    query_vector: np.ndarray,
    top_k: int,
) -> list[dict[str, Any]]:
    if vectors.shape[1] != query_vector.shape[0]:
        raise ValueError(
            "문서 벡터와 질문 벡터의 차원이 다릅니다: "
            f"{vectors.shape[1]} != {query_vector.shape[0]}"
        )

    scores = vectors @ query_vector
    indices = np.argsort(scores)[::-1][:top_k]

    results: list[dict[str, Any]] = []

    for rank, index in enumerate(indices, start=1):
        chunk = chunks[int(index)]

        results.append(
            {
                "rank": rank,
                "score": float(scores[int(index)]),
                "chunk_id": chunk.get("chunk_id"),
                "chunk_type": chunk.get("chunk_type"),
                "text": str(chunk.get("text") or "").strip(),
                "metadata": chunk.get("metadata") or {},
            }
        )

    return results


def print_results(results: list[dict[str, Any]]) -> None:
    print()
    print("=" * 80)
    print("Top-k 검색 결과")
    print("=" * 80)

    for result in results:
        print()
        print(
            f"[{result['rank']}] "
            f"유사도={result['score']:.4f} | "
            f"chunk_id={result['chunk_id']} | "
            f"type={result['chunk_type']}"
        )
        print("-" * 80)
        print(result["text"][:1200])

        if len(result["text"]) > 1200:
            print("...")

    print()
    print("=" * 80)


def build_context(results: list[dict[str, Any]]) -> str:
    parts: list[str] = []

    for result in results:
        parts.append(
            f"[근거 {result['rank']}]\n"
            f"chunk_id: {result['chunk_id']}\n"
            f"유사도: {result['score']:.4f}\n"
            f"{result['text']}"
        )

    return "\n\n".join(parts)


def ask_llama(
    question: str,
    results: list[dict[str, Any]],
) -> str:
    context = build_context(results)

    payload = {
        "model": LLAMA_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "당신은 LH 공고문을 정확하게 전달하는 질의응답 도우미입니다. "
                    "제공된 문서 근거만 사용하고 외부 지식이나 추측을 추가하지 마세요. "
                    "원문의 주어, 목적어, 조건, 예외, 부정 표현, 날짜, 금액, 수치를 "
                    "절대로 바꾸지 마세요. "
                    "특히 신청자격이나 법률 조건처럼 문장 관계가 중요한 내용은 "
                    "의미를 바꾸어 요약하지 말고 가능한 한 원문 표현을 유지하세요. "
                    "여러 조건이 있으면 각각 분리하여 답변하세요. "
                    "근거에서 확인할 수 없는 질문에는 정확히 "
                    "'제공된 문서 근거에서는 확인할 수 없습니다.'라고 답하세요. "
                    "답변에 사용한 근거 번호를 [근거 1]처럼 표시하세요."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"질문:\n{question}\n\n"
                    f"문서 근거:\n{context}\n\n"
                    "위 근거만 사용하여 한국어로 답변하세요. "
                    "복잡한 자격 조건은 축약하지 말고 원문의 행위 주체와 대상을 "
                    "그대로 보존하세요. 답변에 불필요한 해석이나 반복을 추가하지 마세요."
                ),
            },
        ],
        "temperature": 0.0,
        "max_tokens": 512,
        "stream": False,
    }

    response = requests.post(
        f"{LLAMA_URL}/v1/chat/completions",
        json=payload,
        timeout=180,
    )
    response.raise_for_status()

    data = response.json()
    return str(data["choices"][0]["message"]["content"]).strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--document",
        required=True,
        help="예: announcement_001",
    )
    parser.add_argument(
        "--format",
        choices=("hwp", "hwpx"),
        default=None,
    )
    parser.add_argument(
        "--question",
        default=None,
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
    )
    parser.add_argument(
        "--search-only",
        action="store_true",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    question = args.question or input("질문을 입력하세요: ").strip()

    if not question:
        raise ValueError("질문이 비어 있습니다.")

    embedding_dir = find_embedding_dir(
        args.document,
        args.format,
    )

    print(f"선택 공고: {args.document}")
    print(f"선택 형식: {embedding_dir.name}")
    print(f"임베딩 경로: {embedding_dir}")

    vectors, chunks = load_embedding_data(embedding_dir)

    print(f"벡터 수: {vectors.shape[0]}")
    print(f"벡터 차원: {vectors.shape[1]}")

    model = load_query_model()
    query_vector = embed_question(model, question)

    results = search_chunks(
        vectors,
        chunks,
        query_vector,
        args.top_k,
    )

    print_results(results)

    if args.search_only:
        print("검색 전용 모드: llama.cpp 호출 생략")
        return

    print()
    print("=" * 80)
    print("llama.cpp 답변")
    print("=" * 80)
    print(ask_llama(question, results))
    print("=" * 80)


if __name__ == "__main__":
    main()
