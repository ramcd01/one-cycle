"""대화 문맥을 반영해 근거를 검색하는 멀티턴 RAG 테스트."""

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

RRF_CONSTANT = 60


def find_embedding_dir(
    document_id: str,
    document_format: str | None,
) -> Path:
    root = OUTPUT_ROOT / document_id / "05_embeddings"

    if not root.exists():
        raise FileNotFoundError(f"임베딩 폴더가 없습니다: {root}")

    candidates: list[Path] = []

    for directory in sorted(root.iterdir()):
        if not directory.is_dir():
            continue

        if document_format and directory.name != document_format:
            continue

        embedding_path = directory / "embeddings.npy"
        metadata_path = directory / "metadata.json"

        if embedding_path.exists() and metadata_path.exists():
            candidates.append(directory)

    if not candidates:
        raise FileNotFoundError(
            f"{document_id}에서 사용할 임베딩 결과가 없습니다."
        )

    if len(candidates) > 1:
        formats = ", ".join(path.name for path in candidates)

        raise ValueError(
            f"임베딩 결과가 여러 개입니다: {formats}. "
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

    return np.asarray(vectors, dtype=np.float32), chunks


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


def build_contextual_query(
    current_question: str,
    previous_questions: list[str],
    max_history_turns: int,
) -> str:
    recent_questions = previous_questions[-max_history_turns:]

    if not recent_questions:
        return current_question

    history_text = "\n".join(
        f"{index}. {question}"
        for index, question in enumerate(recent_questions, start=1)
    )

    return (
        "이전 대화의 사용자 질문:\n"
        f"{history_text}\n\n"
        "현재 사용자 질문:\n"
        f"{current_question}"
    )


def encode_queries(
    model: SentenceTransformer,
    current_question: str,
    contextual_query: str,
) -> tuple[np.ndarray, np.ndarray]:
    query_texts = [current_question]

    context_is_different = contextual_query != current_question

    if context_is_different:
        query_texts.append(contextual_query)

    encoded = model.encode(
        query_texts,
        prompt_name="query",
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )

    vectors = np.asarray(encoded, dtype=np.float32)

    current_vector = vectors[0]

    if context_is_different:
        contextual_vector = vectors[1]
    else:
        contextual_vector = current_vector

    return current_vector, contextual_vector


def get_ranked_indices(
    scores: np.ndarray,
    candidate_k: int,
) -> list[int]:
    result_count = min(candidate_k, len(scores))

    indices = np.argsort(scores)[::-1][:result_count]

    return [int(index) for index in indices]


def reciprocal_rank_fusion(
    current_ranking: list[int],
    contextual_ranking: list[int],
) -> dict[int, float]:
    fused_scores: dict[int, float] = {}

    rankings = [current_ranking]

    if contextual_ranking != current_ranking:
        rankings.append(contextual_ranking)

    for ranking in rankings:
        for rank, vector_index in enumerate(ranking, start=1):
            score = 1.0 / (RRF_CONSTANT + rank)

            fused_scores[vector_index] = (
                fused_scores.get(vector_index, 0.0) + score
            )

    return fused_scores


def search_chunks(
    vectors: np.ndarray,
    chunks: list[dict[str, Any]],
    current_vector: np.ndarray,
    contextual_vector: np.ndarray,
    top_k: int,
    candidate_k: int,
) -> list[dict[str, Any]]:
    if vectors.shape[1] != current_vector.shape[0]:
        raise ValueError(
            "문서 벡터와 질문 벡터의 차원이 다릅니다: "
            f"{vectors.shape[1]} != {current_vector.shape[0]}"
        )

    current_scores = vectors @ current_vector
    contextual_scores = vectors @ contextual_vector

    current_ranking = get_ranked_indices(
        current_scores,
        candidate_k,
    )
    contextual_ranking = get_ranked_indices(
        contextual_scores,
        candidate_k,
    )

    fused_scores = reciprocal_rank_fusion(
        current_ranking,
        contextual_ranking,
    )

    final_indices = sorted(
        fused_scores,
        key=lambda index: (
            fused_scores[index],
            max(
                float(current_scores[index]),
                float(contextual_scores[index]),
            ),
        ),
        reverse=True,
    )[:top_k]

    results: list[dict[str, Any]] = []

    for rank, vector_index in enumerate(final_indices, start=1):
        chunk = chunks[vector_index]

        results.append(
            {
                "rank": rank,
                "vector_index": vector_index,
                "rrf_score": float(fused_scores[vector_index]),
                "current_score": float(current_scores[vector_index]),
                "context_score": float(contextual_scores[vector_index]),
                "chunk_id": chunk.get("chunk_id"),
                "chunk_type": chunk.get("chunk_type"),
                "text": str(chunk.get("text") or "").strip(),
                "metadata": chunk.get("metadata") or {},
            }
        )

    return results


def print_search_results(
    results: list[dict[str, Any]],
    contextual_query: str,
) -> None:
    print()
    print("=" * 80)
    print("문맥 기반 검색 질의")
    print("=" * 80)
    print(contextual_query)

    print()
    print("=" * 80)
    print("통합 Top-k 검색 결과")
    print("=" * 80)

    for result in results:
        print()
        print(
            f"[{result['rank']}] "
            f"RRF={result['rrf_score']:.6f} | "
            f"현재질문={result['current_score']:.4f} | "
            f"문맥질문={result['context_score']:.4f}"
        )
        print(
            f"chunk_id={result['chunk_id']} | "
            f"type={result['chunk_type']}"
        )
        print("-" * 80)
        print(result["text"][:1200])

        if len(result["text"]) > 1200:
            print("...")

    print()
    print("=" * 80)


def build_evidence_context(
    results: list[dict[str, Any]],
) -> str:
    parts: list[str] = []

    for result in results:
        parts.append(
            f"[근거 {result['rank']}]\n"
            f"chunk_id: {result['chunk_id']}\n"
            f"{result['text']}"
        )

    return "\n\n".join(parts)


def build_history_text(
    previous_questions: list[str],
    max_history_turns: int,
) -> str:
    recent_questions = previous_questions[-max_history_turns:]

    if not recent_questions:
        return "이전 질문 없음"

    return "\n".join(
        f"- {question}"
        for question in recent_questions
    )


def ask_llama(
    *,
    current_question: str,
    previous_questions: list[str],
    results: list[dict[str, Any]],
    max_history_turns: int,
) -> str:
    evidence = build_evidence_context(results)

    history_text = build_history_text(
        previous_questions,
        max_history_turns,
    )

    payload = {
        "model": LLAMA_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "당신은 LH 공고문 질의응답 도우미입니다. "
                    "제공된 문서 근거만 사용해 답변하세요. "
                    "근거에 없는 내용은 추측하지 마세요. "
                    "원문의 조건, 부정 표현, 수치와 날짜를 변경하지 마세요. "
                    "근거로 확인할 수 없으면 "
                    "'제공된 문서 근거에서는 확인할 수 없습니다.'라고 답하세요. "
                    "사용한 근거 번호를 표시하세요."
                ),
            },
            {
                "role": "user",
                "content": (
                    "이전 사용자 질문:\n"
                    f"{history_text}\n\n"
                    "현재 사용자 질문:\n"
                    f"{current_question}\n\n"
                    "검색된 문서 근거:\n"
                    f"{evidence}\n\n"
                    "대화 문맥과 문서 근거를 함께 고려하되, "
                    "답변 내용은 문서 근거에서 확인되는 내용으로만 작성하세요."
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

    try:
        answer = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as error:
        raise ValueError(
            "llama.cpp 응답에서 답변을 찾지 못했습니다."
        ) from error

    return str(answer).strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="대화 문맥 기반 멀티턴 RAG 테스트"
    )

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
        help="지정하면 한 번만 질문하고 종료합니다.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=3,
    )
    parser.add_argument(
        "--candidate-k",
        type=int,
        default=15,
        help="각 검색에서 가져올 후보 청크 수",
    )
    parser.add_argument(
        "--history-turns",
        type=int,
        default=3,
        help="검색에 사용할 이전 사용자 질문 수",
    )
    parser.add_argument(
        "--search-only",
        action="store_true",
    )

    return parser.parse_args()


def process_question(
    *,
    question: str,
    previous_questions: list[str],
    model: SentenceTransformer,
    vectors: np.ndarray,
    chunks: list[dict[str, Any]],
    args: argparse.Namespace,
) -> str | None:
    contextual_query = build_contextual_query(
        question,
        previous_questions,
        args.history_turns,
    )

    current_vector, contextual_vector = encode_queries(
        model,
        question,
        contextual_query,
    )

    results = search_chunks(
        vectors,
        chunks,
        current_vector,
        contextual_vector,
        args.top_k,
        args.candidate_k,
    )

    print_search_results(
        results,
        contextual_query,
    )

    if args.search_only:
        return None

    answer = ask_llama(
        current_question=question,
        previous_questions=previous_questions,
        results=results,
        max_history_turns=args.history_turns,
    )

    print()
    print("=" * 80)
    print("llama.cpp 답변")
    print("=" * 80)
    print(answer)
    print("=" * 80)

    return answer


def main() -> None:
    args = parse_args()

    if args.top_k < 1:
        raise ValueError("top-k는 1 이상이어야 합니다.")

    if args.candidate_k < args.top_k:
        raise ValueError(
            "candidate-k는 top-k 이상이어야 합니다."
        )

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

    previous_questions: list[str] = []

    if args.question:
        process_question(
            question=args.question,
            previous_questions=previous_questions,
            model=model,
            vectors=vectors,
            chunks=chunks,
            args=args,
        )
        return

    print()
    print("멀티턴 질문을 시작합니다.")
    print("종료: /exit")
    print("대화 문맥 초기화: /reset")

    while True:
        print()
        question = input("질문: ").strip()

        if not question:
            continue

        if question == "/exit":
            print("종료합니다.")
            break

        if question == "/reset":
            previous_questions.clear()
            print("대화 문맥을 초기화했습니다.")
            continue

        process_question(
            question=question,
            previous_questions=previous_questions,
            model=model,
            vectors=vectors,
            chunks=chunks,
            args=args,
        )

        previous_questions.append(question)


if __name__ == "__main__":
    main()
