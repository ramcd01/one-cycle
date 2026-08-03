"""대화 문맥 선택, 질문 재작성, 의미 검색을 연결한 멀티턴 RAG."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

import numpy as np
import requests
import torch
from sentence_transformers import SentenceTransformer


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = PROJECT_ROOT / "outputs"

EMBEDDING_MODEL = "Qwen/Qwen3-Embedding-0.6B"
LLAMA_BASE_URL = "http://127.0.0.1:8080"
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


def load_embedding_model() -> SentenceTransformer:
    device = "cuda" if torch.cuda.is_available() else "cpu"

    print(f"임베딩 장치: {device}")
    print(f"임베딩 모델: {EMBEDDING_MODEL}")

    model = SentenceTransformer(
        EMBEDDING_MODEL,
        device=device,
    )
    model.eval()

    return model


def group_history(
    history: list[dict[str, str]],
) -> list[dict[str, str]]:
    """대화 메시지를 사용자 질문과 답변 단위로 묶는다."""

    exchanges: list[dict[str, str]] = []
    current_user: str | None = None

    for message in history:
        role = message.get("role")
        content = str(message.get("content") or "").strip()

        if not content:
            continue

        if role == "user":
            if current_user is not None:
                exchanges.append(
                    {
                        "user": current_user,
                        "assistant": "",
                    }
                )

            current_user = content

        elif role == "assistant" and current_user is not None:
            exchanges.append(
                {
                    "user": current_user,
                    "assistant": content,
                }
            )
            current_user = None

    if current_user is not None:
        exchanges.append(
            {
                "user": current_user,
                "assistant": "",
            }
        )

    return exchanges


def make_exchange_text(exchange: dict[str, str]) -> str:
    user_text = exchange["user"].strip()
    assistant_text = exchange["assistant"].strip()

    if assistant_text:
        return (
            f"이전 사용자 질문:\n{user_text}\n\n"
            f"이전 답변:\n{assistant_text}"
        )

    return f"이전 사용자 질문:\n{user_text}"


def select_relevant_history(
    *,
    model: SentenceTransformer,
    history: list[dict[str, str]],
    current_question: str,
    max_exchanges: int,
    minimum_score: float,
) -> list[dict[str, Any]]:
    """
    현재 질문과 의미적으로 가까운 이전 대화만 선택한다.

    특정 키워드나 질문 유형은 사용하지 않는다.
    """

    exchanges = group_history(history)

    if not exchanges or max_exchanges < 1:
        return []

    exchange_texts = [
        make_exchange_text(exchange)
        for exchange in exchanges
    ]

    query_vector = model.encode(
        [current_question],
        prompt_name="query",
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )[0]

    history_vectors = model.encode(
        exchange_texts,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )

    query_vector = np.asarray(query_vector, dtype=np.float32)
    history_vectors = np.asarray(history_vectors, dtype=np.float32)

    scores = history_vectors @ query_vector
    ranked_indices = np.argsort(scores)[::-1]

    selected: list[dict[str, Any]] = []

    for index in ranked_indices:
        score = float(scores[int(index)])

        if score < minimum_score:
            continue

        exchange = exchanges[int(index)]

        selected.append(
            {
                "exchange_index": int(index),
                "score": score,
                "user": exchange["user"],
                "assistant": exchange["assistant"],
            }
        )

        if len(selected) >= max_exchanges:
            break

    # 재작성 모델에는 시간 순서대로 전달한다.
    selected.sort(key=lambda item: item["exchange_index"])

    return selected


def build_selected_history_text(
    selected_history: list[dict[str, Any]],
) -> str:
    if not selected_history:
        return "관련 이전 대화 없음"

    parts: list[str] = []

    for item in selected_history:
        part = (
            f"[이전 대화, 관련도 {item['score']:.4f}]\n"
            f"사용자: {item['user']}"
        )

        assistant = str(item.get("assistant") or "").strip()

        if assistant:
            part += f"\n답변: {assistant}"

        parts.append(part)

    return "\n\n".join(parts)


def call_llama(
    *,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int,
) -> str:
    response = requests.post(
        f"{LLAMA_BASE_URL}/v1/chat/completions",
        json={
            "model": LLAMA_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],
            "temperature": 0.0,
            "max_tokens": max_tokens,
            "stream": False,
        },
        timeout=180,
    )

    response.raise_for_status()
    data = response.json()

    try:
        result = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as error:
        raise ValueError(
            "llama.cpp 응답에서 내용을 찾지 못했습니다."
        ) from error

    return str(result).strip()


def rewrite_question(
    *,
    current_question: str,
    selected_history: list[dict[str, Any]],
) -> str:
    """
    지시어나 생략된 대상을 복원해 독립 검색 질문을 만든다.

    질문 내용에 따라 분기하는 하드코딩은 하지 않는다.
    """

    if not selected_history:
        return current_question

    history_text = build_selected_history_text(selected_history)

    system_prompt = (
        "당신은 검색 질의 재작성기입니다. "
        "이전 대화와 현재 질문을 보고, 현재 질문을 대화 기록 없이도 "
        "이해할 수 있는 독립적인 검색 질문 한 문장으로 바꾸세요. "
        "질문에 답하지 마세요. "
        "대화에 없는 조건이나 사실을 추가하지 마세요. "
        "지시어와 생략된 대상만 필요한 범위에서 복원하세요. "
        "출력에는 재작성된 질문만 포함하세요."
    )

    user_prompt = (
        f"관련 이전 대화:\n{history_text}\n\n"
        f"현재 질문:\n{current_question}\n\n"
        "독립적인 검색 질문:"
    )

    rewritten = call_llama(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_tokens=128,
    )

    rewritten = rewritten.strip().strip('"').strip()

    return rewritten or current_question


def encode_search_queries(
    *,
    model: SentenceTransformer,
    current_question: str,
    rewritten_question: str,
) -> tuple[np.ndarray, np.ndarray]:
    texts = [current_question]

    rewrite_is_different = (
        rewritten_question.strip() != current_question.strip()
    )

    if rewrite_is_different:
        texts.append(rewritten_question)

    vectors = model.encode(
        texts,
        prompt_name="query",
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )

    vectors = np.asarray(vectors, dtype=np.float32)

    current_vector = vectors[0]

    if rewrite_is_different:
        rewritten_vector = vectors[1]
    else:
        rewritten_vector = current_vector

    return current_vector, rewritten_vector


def get_top_indices(
    scores: np.ndarray,
    candidate_k: int,
) -> list[int]:
    count = min(candidate_k, len(scores))

    return [
        int(index)
        for index in np.argsort(scores)[::-1][:count]
    ]


def reciprocal_rank_fusion(
    rankings: list[list[int]],
) -> dict[int, float]:
    fused_scores: dict[int, float] = {}

    for ranking in rankings:
        for rank, vector_index in enumerate(ranking, start=1):
            score = 1.0 / (RRF_CONSTANT + rank)

            fused_scores[vector_index] = (
                fused_scores.get(vector_index, 0.0) + score
            )

    return fused_scores


def search_chunks(
    *,
    document_vectors: np.ndarray,
    chunks: list[dict[str, Any]],
    current_vector: np.ndarray,
    rewritten_vector: np.ndarray,
    candidate_k: int,
    top_k: int,
) -> list[dict[str, Any]]:
    if document_vectors.shape[1] != current_vector.shape[0]:
        raise ValueError(
            "문서 벡터와 질문 벡터 차원이 다릅니다: "
            f"{document_vectors.shape[1]} != {current_vector.shape[0]}"
        )

    current_scores = document_vectors @ current_vector
    rewritten_scores = document_vectors @ rewritten_vector

    current_ranking = get_top_indices(
        current_scores,
        candidate_k,
    )
    rewritten_ranking = get_top_indices(
        rewritten_scores,
        candidate_k,
    )

    rankings = [current_ranking]

    if rewritten_ranking != current_ranking:
        rankings.append(rewritten_ranking)

    fused_scores = reciprocal_rank_fusion(rankings)

    final_indices = sorted(
        fused_scores,
        key=lambda index: (
            fused_scores[index],
            max(
                float(current_scores[index]),
                float(rewritten_scores[index]),
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
                "rewritten_score": float(
                    rewritten_scores[vector_index]
                ),
                "chunk_id": chunk.get("chunk_id"),
                "chunk_type": chunk.get("chunk_type"),
                "text": str(chunk.get("text") or "").strip(),
                "metadata": chunk.get("metadata") or {},
            }
        )

    return results


def print_retrieval_debug(
    *,
    selected_history: list[dict[str, Any]],
    current_question: str,
    rewritten_question: str,
    results: list[dict[str, Any]],
) -> None:
    print()
    print("=" * 80)
    print("선택된 이전 대화")
    print("=" * 80)

    if not selected_history:
        print("없음")
    else:
        for item in selected_history:
            print(
                f"- 관련도={item['score']:.4f} | "
                f"사용자: {item['user']}"
            )

    print()
    print("=" * 80)
    print("검색 질문")
    print("=" * 80)
    print(f"현재 질문: {current_question}")
    print(f"재작성 질문: {rewritten_question}")

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
            f"재작성질문={result['rewritten_score']:.4f}"
        )
        print(
            f"chunk_id={result['chunk_id']} | "
            f"type={result['chunk_type']}"
        )
        print("-" * 80)
        print(result["text"][:1200])

        if len(result["text"]) > 1200:
            print("...")

    print("=" * 80)


def build_evidence(
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


def generate_answer(
    *,
    current_question: str,
    rewritten_question: str,
    selected_history: list[dict[str, Any]],
    results: list[dict[str, Any]],
) -> str:
    history_text = build_selected_history_text(selected_history)
    evidence = build_evidence(results)

    system_prompt = (
        "당신은 LH 공고문 질의응답 도우미입니다. "
        "검색된 문서 근거만 사용해 답변하세요. "
        "근거에 없는 내용은 추측하지 마세요. "
        "원문의 조건, 부정 표현, 주체와 대상, 날짜와 수치를 "
        "변경하지 마세요. "
        "근거로 확인할 수 없으면 "
        "'제공된 문서 근거에서는 확인할 수 없습니다.'라고 답하세요. "
        "사용한 근거 번호를 표시하세요."
    )

    user_prompt = (
        f"관련 이전 대화:\n{history_text}\n\n"
        f"현재 사용자 질문:\n{current_question}\n\n"
        f"독립 검색 질문:\n{rewritten_question}\n\n"
        f"검색된 문서 근거:\n{evidence}\n\n"
        "현재 사용자 질문에 답하세요."
    )

    return call_llama(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_tokens=512,
    )


def process_question(
    *,
    question: str,
    history: list[dict[str, str]],
    model: SentenceTransformer,
    document_vectors: np.ndarray,
    chunks: list[dict[str, Any]],
    args: argparse.Namespace,
) -> str | None:
    started_at = time.perf_counter()

    selected_history = select_relevant_history(
        model=model,
        history=history,
        current_question=question,
        max_exchanges=args.history_exchanges,
        minimum_score=args.history_threshold,
    )

    history_selected_at = time.perf_counter()

    rewritten_question = rewrite_question(
        current_question=question,
        selected_history=selected_history,
    )

    rewritten_at = time.perf_counter()

    current_vector, rewritten_vector = encode_search_queries(
        model=model,
        current_question=question,
        rewritten_question=rewritten_question,
    )

    results = search_chunks(
        document_vectors=document_vectors,
        chunks=chunks,
        current_vector=current_vector,
        rewritten_vector=rewritten_vector,
        candidate_k=args.candidate_k,
        top_k=args.top_k,
    )

    retrieved_at = time.perf_counter()

    print_retrieval_debug(
        selected_history=selected_history,
        current_question=question,
        rewritten_question=rewritten_question,
        results=results,
    )

    print()
    print(
        "처리 시간 | "
        f"문맥선택={history_selected_at - started_at:.3f}s | "
        f"질문재작성={rewritten_at - history_selected_at:.3f}s | "
        f"검색={retrieved_at - rewritten_at:.3f}s"
    )

    if args.search_only:
        return None

    answer = generate_answer(
        current_question=question,
        rewritten_question=rewritten_question,
        selected_history=selected_history,
        results=results,
    )

    finished_at = time.perf_counter()

    print()
    print("=" * 80)
    print("llama.cpp 답변")
    print("=" * 80)
    print(answer)
    print("=" * 80)
    print(
        f"답변 생성 시간: {finished_at - retrieved_at:.3f}s | "
        f"전체: {finished_at - started_at:.3f}s"
    )

    return answer


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="대화 문맥 선택과 질문 재작성을 포함한 멀티턴 RAG"
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
        help="지정하면 단일 질문만 실행합니다.",
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
    )
    parser.add_argument(
        "--history-exchanges",
        type=int,
        default=3,
        help="현재 질문과 관련 있는 이전 대화 최대 개수",
    )
    parser.add_argument(
        "--history-threshold",
        type=float,
        default=0.25,
        help="이전 대화 선택 최소 유사도",
    )
    parser.add_argument(
        "--search-only",
        action="store_true",
    )

    return parser.parse_args()


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

    document_vectors, chunks = load_embedding_data(
        embedding_dir
    )

    print(f"벡터 수: {document_vectors.shape[0]}")
    print(f"벡터 차원: {document_vectors.shape[1]}")

    model = load_embedding_model()
    history: list[dict[str, str]] = []

    if args.question:
        process_question(
            question=args.question,
            history=history,
            model=model,
            document_vectors=document_vectors,
            chunks=chunks,
            args=args,
        )
        return

    print()
    print("멀티턴 질문을 시작합니다.")
    print("종료: /exit")
    print("대화 초기화: /reset")

    while True:
        print()
        question = input("질문: ").strip()

        if not question:
            continue

        if question == "/exit":
            print("종료합니다.")
            break

        if question == "/reset":
            history.clear()
            print("대화 기록을 초기화했습니다.")
            continue

        answer = process_question(
            question=question,
            history=history,
            model=model,
            document_vectors=document_vectors,
            chunks=chunks,
            args=args,
        )

        history.append(
            {
                "role": "user",
                "content": question,
            }
        )

        if answer:
            history.append(
                {
                    "role": "assistant",
                    "content": answer,
                }
            )


if __name__ == "__main__":
    main()
