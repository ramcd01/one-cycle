"""
로컬 임베딩 검색 + 메타데이터 재정렬 + 주제 필터 + 동일 표 Context 확장

개선 사항
1. 벡터 유사도 Top-N 후보를 만든 뒤 Section 제목과 질문 의도로 재정렬
2. 신청자격 질문에서 계약서류 청크가 상위에 오는 현상을 완화
3. 공급대상·공급정보 같은 표 개요 질문은 같은 표 전체를 확장
4. 기존 목록형·합계형·Key-Value 표 확장 유지
"""

from __future__ import annotations

import json
import os
import re
from tkinter import Tk, messagebox
from tkinter.filedialog import askopenfilename
from typing import Any

import numpy as np
import torch
from sentence_transformers import SentenceTransformer


MODEL_NAME = "Qwen/Qwen3-Embedding-0.6B"
TOP_K = 3
CANDIDATE_POOL_SIZE = 20

QUERY_INSTRUCTION = (
    "주어진 LH 입주자모집공고문에서 "
    "사용자 질문에 답할 수 있는 근거를 검색하세요."
)

LIST_QUERY_KEYWORDS = (
    "필요한서류",
    "필요서류",
    "구비서류",
    "제출서류",
    "어떤서류",
    "서류목록",
    "준비서류",
    "준비물",
    "증빙서류",
    "계약서류",
    "공통된서류",
)

AGGREGATE_QUERY_KEYWORDS = (
    "총",
    "전체",
    "합계",
    "소계",
    "전부",
    "모두몇",
    "총몇",
    "몇세대",
    "몇호",
    "몇개",
)

OVERVIEW_QUERY_KEYWORDS = (
    "공급대상",
    "공급정보",
    "공급주택",
    "주택유형",
    "주택종류",
    "대상정보",
)

TOTAL_TEXT_KEYWORDS = (
    "총계",
    "합계",
)

SUBTOTAL_TEXT_KEYWORDS = (
    "소계",
    "부분합계",
)


def select_metadata_json() -> str | None:
    root = Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    selected = askopenfilename(
        title="임베딩 메타데이터 JSON 선택",
        filetypes=[
            ("임베딩 메타데이터", "*_embedding_metadata.json"),
            ("JSON Files", "*.json"),
        ],
    )

    root.destroy()
    return selected or None


def load_metadata(metadata_path: str) -> dict[str, Any]:
    with open(metadata_path, "r", encoding="utf-8") as file:
        metadata = json.load(file)

    if not isinstance(metadata, dict):
        raise ValueError("메타데이터 JSON 최상위는 객체여야 합니다.")

    chunks = metadata.get("chunks")

    if not isinstance(chunks, list) or not chunks:
        raise ValueError("메타데이터 JSON에 유효한 chunks 배열이 없습니다.")

    return metadata


def find_embedding_file(
    metadata_path: str,
    metadata: dict[str, Any],
) -> str:
    vector_file = metadata.get("summary", {}).get("vector_file")

    if not vector_file:
        raise ValueError("메타데이터의 summary.vector_file 값이 없습니다.")

    embedding_path = os.path.join(
        os.path.dirname(metadata_path),
        vector_file,
    )

    if not os.path.exists(embedding_path):
        raise FileNotFoundError(
            "임베딩 벡터 파일을 찾을 수 없습니다.\n"
            f"예상 경로: {embedding_path}"
        )

    return embedding_path


def load_embeddings(
    embedding_path: str,
    metadata: dict[str, Any],
) -> np.ndarray:
    embeddings = np.load(embedding_path)

    if embeddings.ndim != 2:
        raise ValueError(
            f"임베딩 배열은 2차원이어야 합니다: {embeddings.shape}"
        )

    chunks = metadata["chunks"]

    if embeddings.shape[0] != len(chunks):
        raise ValueError(
            "벡터 개수와 메타데이터 청크 개수가 다릅니다: "
            f"{embeddings.shape[0]} != {len(chunks)}"
        )

    expected_dimension = int(
        metadata.get("embedding_model", {}).get(
            "dimension",
            embeddings.shape[1],
        )
    )

    if embeddings.shape[1] != expected_dimension:
        raise ValueError(
            "벡터 차원이 메타데이터와 다릅니다: "
            f"{embeddings.shape[1]} != {expected_dimension}"
        )

    return embeddings.astype(np.float32)


def load_model(
    metadata: dict[str, Any],
) -> tuple[SentenceTransformer, str]:
    model_name = (
        metadata.get("embedding_model", {}).get("model_name")
        or MODEL_NAME
    )
    device = "cuda" if torch.cuda.is_available() else "cpu"

    print(f"사용 장치: {device}")
    print(f"검색 모델 로딩: {model_name}")

    model = SentenceTransformer(
        model_name,
        device=device,
    )

    return model, device


def normalize_vector(vector: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(vector)

    if norm == 0:
        raise ValueError("질문 임베딩 벡터의 길이가 0입니다.")

    return vector / norm


def encode_query(
    model: SentenceTransformer,
    question: str,
) -> np.ndarray:
    question = question.strip()

    if not question:
        raise ValueError("질문이 비어 있습니다.")

    try:
        query_embedding = model.encode(
            question,
            prompt_name="query",
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )

    except (KeyError, ValueError):
        query_text = (
            f"Instruct: {QUERY_INSTRUCTION}\n"
            f"Query: {question}"
        )
        query_embedding = model.encode(
            query_text,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )

    query_embedding = np.asarray(
        query_embedding,
        dtype=np.float32,
    )

    if query_embedding.ndim != 1:
        query_embedding = query_embedding.reshape(-1)

    return normalize_vector(query_embedding)


def calculate_similarity(
    embeddings: np.ndarray,
    query_embedding: np.ndarray,
) -> np.ndarray:
    if embeddings.shape[1] != query_embedding.shape[0]:
        raise ValueError(
            "청크 벡터와 질문 벡터의 차원이 다릅니다: "
            f"{embeddings.shape[1]} != {query_embedding.shape[0]}"
        )

    return embeddings @ query_embedding


def compact_text(value: Any) -> str:
    return "".join(str(value or "").lower().split())


def get_chunk_metadata(
    chunk: dict[str, Any],
) -> dict[str, Any]:
    metadata = chunk.get("metadata")
    return metadata if isinstance(metadata, dict) else {}


def format_section_path(
    metadata: dict[str, Any],
) -> str:
    path = metadata.get("section_path") or []

    if isinstance(path, list):
        return " > ".join(str(value) for value in path)

    return str(path)


def get_section_text(
    chunk: dict[str, Any],
) -> str:
    metadata = get_chunk_metadata(chunk)
    return compact_text(
        " ".join(
            [
                str(metadata.get("section_title") or ""),
                format_section_path(metadata),
            ]
        )
    )


def get_domain_text(
    chunk: dict[str, Any],
) -> str:
    metadata = get_chunk_metadata(chunk)
    domain = metadata.get("domain")

    if isinstance(domain, dict):
        return compact_text(
            " ".join(str(value) for value in domain.values())
        )

    return compact_text(domain)


def infer_query_topic(question: str) -> str | None:
    q = compact_text(question)

    if any(
        keyword in q
        for keyword in (
            "신청자격",
            "자격",
            "미성년",
            "성년",
            "주택소유",
            "입주자저축",
            "소득",
            "자산요건",
        )
    ):
        return "eligibility"

    if any(
        keyword in q
        for keyword in (
            "청약통장",
            "입주자저축",
            "청약저축",
            "주택청약종합저축",
        )
    ):
        return "subscription_savings"

    if (
        "서류" in q
        or "준비물" in q
    ):
        return "documents"

    if any(
        keyword in q
        for keyword in (
            "일정",
            "장소",
            "언제",
            "어디",
            "시간",
        )
    ):
        return "schedule"

    if any(
        keyword in q
        for keyword in (
            "분양가격",
            "주택가격",
            "가격",
            "얼마",
        )
    ):
        return "price"

    if any(
        keyword in q
        for keyword in (
            "공급대상",
            "공급정보",
            "공급주택",
            "몇세대",
            "모집호수",
        )
    ):
        return "supply"

    if any(
        keyword in q
        for keyword in (
            "연락처",
            "문의",
            "전화번호",
            "콜센터",
        )
    ):
        return "contact"

    return None


def get_topic_adjustment(
    question: str,
    chunk: dict[str, Any],
) -> float:
    """
    벡터 점수에 더할 Section 기반 보정값.

    이 값은 정답을 강제로 결정하지 않고,
    관련 Section이 근소한 점수 차이로 밀리는 현상을 줄이는 용도다.
    """

    topic = infer_query_topic(question)

    if topic is None:
        return 0.0

    section = get_section_text(chunk)
    domain = get_domain_text(chunk)
    chunk_text = compact_text(
        chunk.get("text")
        or chunk.get("content")
        or ""
    )

    adjustment = 0.0

    if topic == "eligibility":
        if (
            "신청자격" in section
            or "eligibility" in domain
            or "applicationeligibility" in domain
        ):
            adjustment += 0.16

        if (
            "미성년" in compact_text(question)
            and "미성년" in chunk_text
        ):
            adjustment += 0.06

        if (
            "계약시구비서류" in section
            or "계약서류" in section
        ):
            adjustment -= 0.14

    elif topic == "subscription_savings":
        if (
            "신청자격" in section
            or "eligibility" in domain
            or "applicationeligibility" in domain
        ):
            adjustment += 0.14

        if any(
            keyword in chunk_text
            for keyword in (
                "청약통장",
                "입주자저축",
                "청약저축",
                "주택청약종합저축",
            )
        ):
            adjustment += 0.14

        if (
            "계약시구비서류" in section
            or "계약서류" in section
        ):
            adjustment -= 0.12

    elif topic == "documents":
        if (
            "구비서류" in section
            or "제출서류" in section
            or "requireddocuments" in domain
        ):
            adjustment += 0.16

    elif topic == "schedule":
        if "일정및장소" in section:
            adjustment += 0.16
        elif "세부일정" in section:
            adjustment += 0.09

    elif topic == "price":
        if (
            "분양가격" in section
            or "주택가격" in section
            or "housingprice" in domain
        ):
            adjustment += 0.16

    elif topic == "supply":
        if (
            "공급대상" in section
            or "supplytarget" in domain
            or "supplyscale" in domain
        ):
            adjustment += 0.16

    elif topic == "contact":
        if (
            "연락처" in section
            or "contact" in domain
        ):
            adjustment += 0.16

    return adjustment



def is_chunk_relevant_to_topic(
    question: str,
    chunk: dict[str, Any],
) -> bool:
    """
    질문 주제가 명확할 때 해당 주제와 직접 관련된 청크인지 판별한다.

    벡터 점수만 높고 Section이 다른 청크가 LLM Context에 섞이는 것을
    줄이기 위한 보수적인 필터다.
    """

    topic = infer_query_topic(question)

    if topic is None:
        return True

    section = get_section_text(chunk)
    domain = get_domain_text(chunk)
    chunk_text = compact_text(
        chunk.get("text")
        or chunk.get("content")
        or ""
    )
    combined = " ".join(
        [
            section,
            domain,
            chunk_text,
        ]
    )

    if topic == "eligibility":
        return any(
            keyword in combined
            for keyword in (
                "신청자격",
                "eligibility",
                "applicationeligibility",
                "성년자",
                "미성년자",
                "입주자저축",
                "주택소유여부",
                "과거당첨",
                "소득및자산요건",
                "대한민국거주",
                "국내에주소를둔법인",
            )
        )

    if topic == "subscription_savings":
        return any(
            keyword in combined
            for keyword in (
                "청약통장",
                "입주자저축",
                "청약저축",
                "주택청약종합저축",
            )
        )

    if topic == "documents":
        return any(
            keyword in combined
            for keyword in (
                "구비서류",
                "제출서류",
                "계약서류",
                "준비서류",
                "requireddocuments",
            )
        )

    if topic == "schedule":
        return any(
            keyword in combined
            for keyword in (
                "일정및장소",
                "세부일정",
                "일정",
                "장소",
                "시간",
            )
        )

    if topic == "price":
        return any(
            keyword in combined
            for keyword in (
                "분양가격",
                "주택가격",
                "계약금",
                "잔금",
                "housingprice",
            )
        )

    if topic == "supply":
        return any(
            keyword in combined
            for keyword in (
                "공급대상",
                "공급세대수",
                "모집호수",
                "supplytarget",
                "supplyscale",
            )
        )

    if topic == "contact":
        return any(
            keyword in combined
            for keyword in (
                "연락처",
                "분양문의",
                "콜센터",
                "전화",
                "contact",
            )
        )

    return True


def get_top_results(
    scores: np.ndarray,
    chunks: list[dict[str, Any]],
    top_k: int,
) -> list[dict[str, Any]]:
    """기존 호환용 순수 벡터 Top-K."""

    actual_top_k = min(top_k, len(chunks))
    top_indices = np.argsort(scores)[::-1][:actual_top_k]

    return [
        {
            "rank": rank,
            "vector_index": int(vector_index),
            "similarity": float(scores[vector_index]),
            "rerank_score": float(scores[vector_index]),
            "topic_adjustment": 0.0,
            "chunk": chunks[int(vector_index)],
        }
        for rank, vector_index in enumerate(top_indices, start=1)
    ]


def get_reranked_results(
    question: str,
    scores: np.ndarray,
    chunks: list[dict[str, Any]],
    top_k: int,
    candidate_pool_size: int = CANDIDATE_POOL_SIZE,
) -> list[dict[str, Any]]:
    """벡터 후보를 Section 의미로 재정렬한다."""

    pool_size = min(
        candidate_pool_size,
        len(chunks),
    )

    candidate_indices = np.argsort(scores)[::-1][:pool_size]
    candidates: list[dict[str, Any]] = []

    for vector_index_value in candidate_indices:
        vector_index = int(vector_index_value)
        chunk = chunks[vector_index]
        vector_score = float(scores[vector_index])
        adjustment = get_topic_adjustment(
            question,
            chunk,
        )

        candidates.append(
            {
                "vector_index": vector_index,
                "similarity": vector_score,
                "topic_adjustment": adjustment,
                "rerank_score": vector_score + adjustment,
                "chunk": chunk,
            }
        )

    candidates.sort(
        key=lambda item: (
            item["rerank_score"],
            item["similarity"],
        ),
        reverse=True,
    )

    selected = candidates[: min(top_k, len(candidates))]

    for rank, result in enumerate(selected, start=1):
        result["rank"] = rank

    return selected


def detect_query_intent(
    question: str,
) -> dict[str, bool]:
    compact_question = compact_text(question)

    is_list_query = any(
        keyword in compact_question
        for keyword in LIST_QUERY_KEYWORDS
    )

    is_aggregate_query = any(
        keyword in compact_question
        for keyword in AGGREGATE_QUERY_KEYWORDS
    )

    has_specific_housing_type = bool(
        re.search(
            r"\d{2,3}[a-z]{1,3}",
            compact_question,
            flags=re.IGNORECASE,
        )
    )

    is_overview_query = (
        any(
            keyword in compact_question
            for keyword in OVERVIEW_QUERY_KEYWORDS
        )
        and not has_specific_housing_type
        and not is_aggregate_query
    )

    return {
        "list_query": is_list_query,
        "aggregate_query": is_aggregate_query,
        "overview_query": is_overview_query,
    }


def get_table_index(chunk: dict[str, Any]) -> Any:
    return get_chunk_metadata(chunk).get("table_index")


def get_row_index(chunk: dict[str, Any]) -> int:
    row_index = get_chunk_metadata(chunk).get("row_index")

    try:
        return int(row_index)

    except (TypeError, ValueError):
        return 10**9


def get_row_kind(chunk: dict[str, Any]) -> str:
    return compact_text(
        get_chunk_metadata(chunk).get("row_kind")
    )


def is_table_chunk(chunk: dict[str, Any]) -> bool:
    return str(
        chunk.get("chunk_type") or ""
    ).startswith("table_")


def get_aggregate_priority(chunk: dict[str, Any]) -> int:
    row_kind = get_row_kind(chunk)
    chunk_text = compact_text(
        chunk.get("text")
        or chunk.get("content")
        or ""
    )

    if row_kind == "total":
        return 0

    if any(
        keyword in chunk_text
        for keyword in TOTAL_TEXT_KEYWORDS
    ):
        return 0

    if row_kind == "subtotal":
        return 1

    if any(
        keyword in chunk_text
        for keyword in SUBTOTAL_TEXT_KEYWORDS
    ):
        return 1

    return 2


def find_table_chunk_indices(
    chunks: list[dict[str, Any]],
    table_index: Any,
) -> list[int]:
    return [
        vector_index
        for vector_index, chunk in enumerate(chunks)
        if (
            is_table_chunk(chunk)
            and get_table_index(chunk) == table_index
        )
    ]


def get_expansion_reason_label(reason: str) -> str:
    labels = {
        "direct_top_k": "재정렬 검색 Top-K",
        "key_value_table": "Key-Value 표 전체 확장",
        "list_table": "목록형 질문 표 전체 확장",
        "aggregate_table": "합계형 질문 표 전체 확장",
        "overview_table": "표 개요 질문 전체 확장",
    }

    return labels.get(reason, reason)


def build_expanded_context(
    question: str,
    raw_results: list[dict[str, Any]],
    scores: np.ndarray,
    chunks: list[dict[str, Any]],
) -> dict[str, Any]:
    intent = detect_query_intent(question)

    topic_relevant_results = [
        result
        for result in raw_results
        if is_chunk_relevant_to_topic(
            question,
            result["chunk"],
        )
    ]

    selected_direct_results = (
        topic_relevant_results
        if topic_relevant_results
        else raw_results
    )

    direct_result_by_index = {
        int(result["vector_index"]): result
        for result in selected_direct_results
    }

    direct_rank_by_index = {
        vector_index: int(result["rank"])
        for vector_index, result in direct_result_by_index.items()
    }

    selected_indices = set(direct_rank_by_index.keys())

    reasons_by_index: dict[int, set[str]] = {
        vector_index: {"direct_top_k"}
        for vector_index in selected_indices
    }

    table_reasons: dict[Any, set[str]] = {}
    table_seed_rank: dict[Any, int] = {}
    dominant_table_index: Any = None

    for result in selected_direct_results:
        chunk = result["chunk"]
        table_index = get_table_index(chunk)

        if table_index is None:
            continue

        table_seed_rank.setdefault(
            table_index,
            int(result["rank"]),
        )

        if dominant_table_index is None:
            dominant_table_index = table_index

    for result in selected_direct_results:
        chunk = result["chunk"]

        if chunk.get("chunk_type") != "table_key_value":
            continue

        table_index = get_table_index(chunk)

        if table_index is not None:
            table_reasons.setdefault(
                table_index,
                set(),
            ).add("key_value_table")

    if (
        intent["list_query"]
        and dominant_table_index is not None
    ):
        table_reasons.setdefault(
            dominant_table_index,
            set(),
        ).add("list_table")

    if (
        intent["aggregate_query"]
        and dominant_table_index is not None
    ):
        table_reasons.setdefault(
            dominant_table_index,
            set(),
        ).add("aggregate_table")

    if (
        intent["overview_query"]
        and dominant_table_index is not None
    ):
        table_reasons.setdefault(
            dominant_table_index,
            set(),
        ).add("overview_table")

    expanded_tables: list[dict[str, Any]] = []

    for table_index, reasons in table_reasons.items():
        table_chunk_indices = find_table_chunk_indices(
            chunks,
            table_index,
        )

        for vector_index in table_chunk_indices:
            selected_indices.add(vector_index)
            reasons_by_index.setdefault(
                vector_index,
                set(),
            ).update(reasons)

        expanded_tables.append(
            {
                "table_index": table_index,
                "reasons": sorted(reasons),
                "chunk_count": len(table_chunk_indices),
                "seed_rank": table_seed_rank.get(table_index),
            }
        )

    def context_sort_key(
        vector_index: int,
    ) -> tuple[int, int, int, int]:
        chunk = chunks[vector_index]
        table_index = get_table_index(chunk)

        if (
            table_index == dominant_table_index
            and table_index in table_reasons
        ):
            aggregate_priority = (
                get_aggregate_priority(chunk)
                if intent["aggregate_query"]
                else 0
            )

            return (
                0,
                aggregate_priority,
                get_row_index(chunk),
                vector_index,
            )

        direct_rank = direct_rank_by_index.get(vector_index)

        if direct_rank is not None:
            return (
                1,
                direct_rank,
                0,
                vector_index,
            )

        if table_index in table_reasons:
            return (
                2,
                table_seed_rank.get(table_index, 10**9),
                get_row_index(chunk),
                vector_index,
            )

        return (
            3,
            10**9,
            get_row_index(chunk),
            vector_index,
        )

    ordered_indices = sorted(
        selected_indices,
        key=context_sort_key,
    )

    context_results: list[dict[str, Any]] = []

    for context_order, vector_index in enumerate(
        ordered_indices,
        start=1,
    ):
        direct_result = direct_result_by_index.get(vector_index)

        context_results.append(
            {
                "context_order": context_order,
                "vector_index": vector_index,
                "similarity": float(scores[vector_index]),
                "rerank_score": (
                    float(direct_result["rerank_score"])
                    if direct_result
                    else float(scores[vector_index])
                ),
                "topic_adjustment": (
                    float(direct_result["topic_adjustment"])
                    if direct_result
                    else 0.0
                ),
                "direct_rank": direct_rank_by_index.get(vector_index),
                "expansion_reasons": sorted(
                    reasons_by_index.get(vector_index, set())
                ),
                "chunk": chunks[vector_index],
            }
        )

    return {
        "intent": intent,
        "query_topic": infer_query_topic(question),
        "direct_result_count": len(selected_direct_results),
        "filtered_direct_count": (
            len(raw_results) - len(selected_direct_results)
        ),
        "dominant_table_index": dominant_table_index,
        "expanded_tables": expanded_tables,
        "context_results": context_results,
    }


def print_chunk_result(
    title: str,
    result: dict[str, Any],
) -> None:
    chunk = result["chunk"]
    metadata = get_chunk_metadata(chunk)

    print(
        f"\n{title} "
        f"similarity={result['similarity']:.4f} "
        f"rerank={result.get('rerank_score', result['similarity']):.4f}"
    )
    print(
        f"topic_adjustment="
        f"{result.get('topic_adjustment', 0.0):+.4f}"
    )
    print(f"vector_index: {result['vector_index']}")
    print(f"chunk_id: {chunk.get('chunk_id')}")
    print(f"chunk_type: {chunk.get('chunk_type')}")
    print(
        "section: "
        f"{format_section_path(metadata) or '-'}"
    )

    if metadata.get("table_index") is not None:
        print(f"table_index: {metadata.get('table_index')}")

    if metadata.get("row_index") is not None:
        print(f"row_index: {metadata.get('row_index')}")

    if metadata.get("row_kind"):
        print(f"row_kind: {metadata.get('row_kind')}")

    print("-" * 80)
    print(
        chunk.get("text")
        or chunk.get("content")
        or ""
    )
    print("-" * 80)


def print_search_results(
    question: str,
    raw_results: list[dict[str, Any]],
    expanded_context: dict[str, Any],
) -> None:
    line = "=" * 80

    print("\n" + line)
    print(f"질문: {question}")
    print(line)
    print("\n[1] 벡터 후보 + Section 재정렬 Top-K")

    for result in raw_results:
        print_chunk_result(
            f"[{result['rank']}위]",
            result,
        )

    intent = expanded_context["intent"]

    print("\n" + line)
    print("[2] 검색 후 동일 표 Context 확장")
    print(line)
    print(
        "질문 의도: "
        f"목록형={intent['list_query']}, "
        f"합계형={intent['aggregate_query']}, "
        f"개요형={intent['overview_query']}"
    )

    expanded_tables = expanded_context["expanded_tables"]

    if not expanded_tables:
        print("동일 표 확장 조건에 해당하지 않습니다.")

    else:
        for table_info in expanded_tables:
            reason_text = ", ".join(
                get_expansion_reason_label(reason)
                for reason in table_info["reasons"]
            )
            print(
                f"- table_index={table_info['table_index']} "
                f"/ 표 청크 {table_info['chunk_count']}개 "
                f"/ 사유: {reason_text}"
            )

    context_results = expanded_context["context_results"]
    added_results = [
        result
        for result in context_results
        if result["direct_rank"] is None
    ]

    print(
        f"\n최종 LLM Context: {len(context_results)}개 "
        f"(직접 검색 {len(raw_results)}개 "
        f"+ 추가 확장 {len(added_results)}개)"
    )
    print(line + "\n")


def print_loaded_summary(
    metadata_path: str,
    embedding_path: str,
    embeddings: np.ndarray,
    metadata: dict[str, Any],
) -> None:
    print("\n" + "=" * 80)
    print("로컬 임베딩 검색 준비 완료")
    print("=" * 80)
    print(f"메타데이터: {metadata_path}")
    print(f"벡터 파일: {embedding_path}")
    print(f"전체 청크: {len(metadata['chunks'])}개")
    print(f"임베딩 배열: {embeddings.shape}")
    print(f"기본 Top-K: {TOP_K}")
    print(f"후보 Pool: {CANDIDATE_POOL_SIZE}")
    print("Section 재정렬: 활성화")
    print("동일 표 Context 확장: 활성화")
    print("=" * 80)
    print(
        "질문을 입력하세요. "
        "종료하려면 exit, quit 또는 q를 입력하세요.\n"
    )


def main() -> None:
    metadata_path = select_metadata_json()

    if not metadata_path:
        print("메타데이터 JSON을 선택하지 않았습니다.")
        return

    try:
        metadata = load_metadata(metadata_path)
        embedding_path = find_embedding_file(
            metadata_path,
            metadata,
        )
        embeddings = load_embeddings(
            embedding_path,
            metadata,
        )
        model, _ = load_model(metadata)

        print_loaded_summary(
            metadata_path,
            embedding_path,
            embeddings,
            metadata,
        )

        while True:
            question = input("질문> ").strip()

            if question.lower() in {
                "exit",
                "quit",
                "q",
            }:
                print("검색 테스트를 종료합니다.")
                break

            if not question:
                print("질문을 입력해주세요.")
                continue

            query_embedding = encode_query(
                model,
                question,
            )
            scores = calculate_similarity(
                embeddings,
                query_embedding,
            )
            raw_results = get_reranked_results(
                question,
                scores,
                metadata["chunks"],
                TOP_K,
            )
            expanded_context = build_expanded_context(
                question,
                raw_results,
                scores,
                metadata["chunks"],
            )
            print_search_results(
                question,
                raw_results,
                expanded_context,
            )

    except (
        OSError,
        json.JSONDecodeError,
        ValueError,
        TypeError,
        RuntimeError,
    ) as error:
        messagebox.showerror(
            "검색 테스트 실패",
            str(error),
        )
        raise


if __name__ == "__main__":
    main()
