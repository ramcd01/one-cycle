from __future__ import annotations

import re
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Literal

import numpy as np
from pydantic import BaseModel, Field, ValidationError

from search_embeddings import encode_query

from .llama_client import JsonResponseError, LlamaClient
from .schemas import EvidenceItem, QueryPlan


SelectionRole = Literal["direct", "condition", "exception", "item", "context"]


class SelectedSpan(BaseModel):
    span_id: str = Field(min_length=1)
    role: SelectionRole = "direct"


class SelectionPayload(BaseModel):
    selected: list[SelectedSpan] = Field(default_factory=list)


@dataclass(frozen=True)
class EvidenceSpan:
    span_id: str
    evidence_id: str
    text: str
    order: int


@dataclass(frozen=True)
class RankedSpan:
    span: EvidenceSpan
    semantic_score: float
    hybrid_score: float
    token_hits: int
    marker_hits: int


SYSTEM_PROMPT = """
당신은 문서 근거 선택기입니다.
사용자 질문에 실제로 필요한 근거 조각의 span_id만 JSON으로 반환하세요.
답변을 만들거나 원문을 다시 쓰지 마세요.

핵심 규칙:
1. 반드시 아래 Evidence Spans에 실제로 제시된 span_id만 선택하세요.
2. 문장을 복사하거나 quote를 만들지 마세요. span_id만 반환하세요.
3. 질문의 핵심 대상과 직접 관계없는 근거는 선택하지 마세요.
4. 단순 배경, 다른 자격 조건, 접수 방식, 날짜, 법 조항은 질문 대상과 직접 관련되지 않으면 제외하세요.
5. 목록·문의처·개요 질문에서 completeness가 all이면 관련 항목을 빠짐없이 선택하세요.
6. 가격·날짜·합계·연락처 질문은 요청한 값과 단위·항목명을 포함한 조각만 선택하세요.
7. 질문 표현과 문서 용어가 달라도 의미가 같으면 관련 조각을 선택하세요.
8. 근거가 없으면 selected를 빈 배열로 반환하세요.
9. 같은 span_id를 중복 선택하지 마세요.

JSON 형식:
{
  "selected": [
    {
      "span_id": "evidence_001:s001",
      "role": "direct|condition|exception|item|context"
    }
  ]
}
""".strip()


_BULLET_BOUNDARY_RE = re.compile(r"(?<!^)(?=(?:■|※|[①②③④⑤⑥⑦⑧⑨⑩]))")
_PHONE_RE = re.compile(r"(?:\d{2,4}[-)]?\s*\d{3,4}[-]\d{4}|\d{3,4}-\d{4})")

JUDGMENT_MARKERS = (
    "가능", "불가", "필수", "아님", "불문", "대상", "제외", "한하여",
    "경우에만", "제한", "요건", "자격", "신청할 수", "신청 가능",
)

STRONG_REQUIREMENT_MARKERS = (
    "필수", "불문", "가입여부", "가입 여부", "없어도", "관계없이",
    "요건", "제한", "신청 가능", "신청할 수", "불가", "제외",
)

EXCEPTION_MARKERS = (
    "다만", "예외", "한하여", "경우에만", "이 경우", "미성년자",
    "단,", "제외",
)

CONDITION_MARKERS = (
    "경우", "조건", "요건", "기준", "현재", "이상", "이하", "등재",
)

PROCEDURE_MARKERS = (
    "1.", "2.", "①", "②", "단계", "절차", "방법", "접속", "선택",
    "입력", "방문하여", "지참", "준비물", "구비서류", "신청서 작성",
    "온라인", "홈페이지", "영업점", "창구", "계좌로 입금",
)

TOTAL_MARKERS = ("총계", "합계", "소계", "총 ", "총:", "모집호수")
CONTACT_MARKERS = ("문의", "연락", "전화", "콜센터", "사무실", "센터")
LIST_MARKERS = ("서류", "지참", "제출", "구비", "준비")

PROCEDURE_CONTEXT_MARKERS = (
    "현장접수", "현장(방문)", "인터넷", "모바일", "전화예약",
    "방문접수", "접수 및 계약", "선착순 동호지정",
)

CONTINUATION_PREFIXES = ("이 경우", "다만", "단,", "단 " )


def _location_text(item: EvidenceItem) -> str:
    location = " > ".join(item.location.section_path) or "문서 도입부"
    if item.location.table_index is not None:
        location += f" · 표 {item.location.table_index}"
    if item.location.row_index is not None:
        location += f" · 행 {item.location.row_index}"
    return location


def _split_excerpt(excerpt: str) -> list[str]:
    """원문을 바꾸지 않고 줄바꿈·글머리표 경계로만 나눈다."""
    normalized = excerpt.replace("\r\n", "\n").replace("\r", "\n")
    output: list[str] = []

    for raw_line in normalized.split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        parts = [part.strip() for part in _BULLET_BOUNDARY_RE.split(line) if part.strip()]
        output.extend(parts)

    if not output and normalized.strip():
        output.append(normalized.strip())

    return output


def _span_key(text: str) -> str:
    return re.sub(r"[^가-힣a-z0-9]", "", text.lower())


def _build_spans(evidence: list[EvidenceItem]) -> tuple[list[EvidenceSpan], dict[str, EvidenceSpan]]:
    spans: list[EvidenceSpan] = []
    span_map: dict[str, EvidenceSpan] = {}
    seen_texts: set[str] = set()
    order = 0

    for item in evidence:
        for index, text in enumerate(_split_excerpt(item.excerpt), start=1):
            key = _span_key(text)
            if key and key in seen_texts:
                continue
            if key:
                seen_texts.add(key)

            span_id = f"{item.evidence_id}:s{index:03d}"
            span = EvidenceSpan(
                span_id=span_id,
                evidence_id=item.evidence_id,
                text=text,
                order=order,
            )
            spans.append(span)
            span_map[span_id] = span
            order += 1

    return spans, span_map


def _format_ranked_spans(
    evidence: list[EvidenceItem],
    ranked_spans: list[RankedSpan],
) -> str:
    evidence_map = {item.evidence_id: item for item in evidence}
    grouped: OrderedDict[str, list[RankedSpan]] = OrderedDict()
    for ranked in ranked_spans:
        grouped.setdefault(ranked.span.evidence_id, []).append(ranked)

    blocks: list[str] = []
    for evidence_id, group in grouped.items():
        item = evidence_map[evidence_id]
        lines = [
            f"[{evidence_id}]",
            f"위치: {_location_text(item)}",
            "선택 가능한 span:",
        ]
        for ranked in group:
            lines.append(f"- [{ranked.span.span_id}] {ranked.span.text}")
        blocks.append("\n".join(lines))

    return "\n\n".join(blocks)


def _compact(value: str) -> str:
    return re.sub(r"\s+", "", value.lower())


def _target_tokens(question: str, query_plan: QueryPlan) -> list[str]:
    combined = f"{question} {query_plan.target} {query_plan.scope or ''}"
    tokens = re.findall(r"[가-힣A-Za-z0-9]{2,}", combined)
    stopwords = {
        "알려줘", "알려주세요", "무엇인가요", "어떻게", "되나요", "가능한가요",
        "필요한가요", "정보", "관련", "질문", "대한", "해주세요", "인가요",
        "있나요", "있어요", "주세요",
    }
    unique: list[str] = []
    for token in tokens:
        if token in stopwords or token in unique:
            continue
        unique.append(token)
    return unique[:16]


def _mode_markers(query_plan: QueryPlan) -> tuple[str, ...]:
    if query_plan.answer_mode == "boolean_with_conditions":
        return JUDGMENT_MARKERS
    if query_plan.answer_mode == "procedure_steps":
        return PROCEDURE_MARKERS
    if query_plan.answer_mode == "explicit_total":
        return TOTAL_MARKERS
    if query_plan.answer_mode == "all_matching_items":
        return CONTACT_MARKERS
    if query_plan.answer_mode in {"complete_list", "complete_grouped_list"}:
        return LIST_MARKERS
    return ()


def _encode_documents(embedding_model: Any, texts: list[str]) -> np.ndarray:
    try:
        vectors = embedding_model.encode(
            texts,
            prompt_name="document",
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
    except (KeyError, ValueError, TypeError):
        vectors = embedding_model.encode(
            texts,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )

    array = np.asarray(vectors, dtype=np.float32)
    if array.ndim == 1:
        array = array.reshape(1, -1)
    return array


def _rank_spans(
    *,
    embedding_model: Any,
    question: str,
    query_plan: QueryPlan,
    spans: list[EvidenceSpan],
) -> list[RankedSpan]:
    if not spans:
        return []

    query_vector = encode_query(embedding_model, question)
    document_vectors = _encode_documents(
        embedding_model,
        [span.text for span in spans],
    )
    semantic_scores = document_vectors @ query_vector

    tokens = _target_tokens(question, query_plan)
    markers = _mode_markers(query_plan)

    ranked: list[RankedSpan] = []
    for span, semantic in zip(spans, semantic_scores, strict=True):
        compact = _compact(span.text)
        token_hits = sum(1 for token in tokens if _compact(token) in compact)
        marker_hits = sum(1 for marker in markers if marker in span.text)

        lexical_bonus = min(0.10, token_hits * 0.025)
        marker_bonus = min(0.08, marker_hits * 0.02)

        if query_plan.answer_mode == "boolean_with_conditions" and any(
            marker in span.text for marker in STRONG_REQUIREMENT_MARKERS
        ):
            marker_bonus += 0.08

        off_topic_penalty = 0.0
        if query_plan.answer_mode == "boolean_with_conditions":
            question_scope = f"{question} {query_plan.target}"
            mentions_procedure = any(
                marker in question_scope for marker in PROCEDURE_CONTEXT_MARKERS
            )
            if not mentions_procedure and any(
                marker in span.text for marker in PROCEDURE_CONTEXT_MARKERS
            ):
                off_topic_penalty = 0.08

        if query_plan.answer_mode == "all_matching_items" and _PHONE_RE.search(span.text):
            marker_bonus += 0.06

        ranked.append(
            RankedSpan(
                span=span,
                semantic_score=float(semantic),
                hybrid_score=float(semantic + lexical_bonus + marker_bonus - off_topic_penalty),
                token_hits=token_hits,
                marker_hits=marker_hits,
            )
        )

    ranked.sort(key=lambda item: (-item.hybrid_score, item.span.order))
    return ranked


def _materialize_ranked(
    *,
    selected: list[tuple[RankedSpan, SelectionRole]],
    evidence_map: dict[str, EvidenceItem],
    method: str,
) -> list[EvidenceItem]:
    grouped: OrderedDict[str, list[tuple[RankedSpan, SelectionRole]]] = OrderedDict()
    seen: set[str] = set()

    for ranked, role in selected:
        if ranked.span.span_id in seen:
            continue
        seen.add(ranked.span.span_id)
        grouped.setdefault(ranked.span.evidence_id, []).append((ranked, role))

    output: list[EvidenceItem] = []
    for evidence_id, items in grouped.items():
        items.sort(key=lambda pair: pair[0].span.order)
        source_item = evidence_map[evidence_id]
        output.append(
            source_item.model_copy(
                deep=True,
                update={
                    "excerpt": "\n".join(pair[0].span.text for pair in items),
                    "debug": {
                        **source_item.debug,
                        "selection_method": method,
                        "selection_roles": [pair[1] for pair in items],
                        "selected_span_ids": [pair[0].span.span_id for pair in items],
                        "selected_span_scores": {
                            pair[0].span.span_id: {
                                "semantic": round(pair[0].semantic_score, 6),
                                "hybrid": round(pair[0].hybrid_score, 6),
                            }
                            for pair in items
                        },
                        "original_excerpt": source_item.excerpt,
                    },
                },
            )
        )
    return output


def _select_boolean_semantically(
    *,
    query_plan: QueryPlan,
    ranked_spans: list[RankedSpan],
    evidence_map: dict[str, EvidenceItem],
) -> list[EvidenceItem]:
    """가능·필수 여부 질문에서 직접 판정 근거만 선택한다.

    하나의 대상에 대한 예/아니오 질문은 가장 직접적인 원문 1개를 기본으로
    사용한다. 조건·예외는 같은 근거 안에서 바로 이어지는 문장이 명시적인
    연결 표현으로 시작할 때만 보완한다. 다른 표·다른 문단의 일반 안내는
    자동으로 섞지 않는다.
    """
    judgment_candidates = [
        ranked
        for ranked in ranked_spans
        if any(marker in ranked.span.text for marker in JUDGMENT_MARKERS)
    ]
    if not judgment_candidates:
        return []

    best = judgment_candidates[0]
    selected: list[tuple[RankedSpan, SelectionRole]] = [(best, "direct")]

    same_evidence = sorted(
        [
            ranked
            for ranked in ranked_spans
            if ranked.span.evidence_id == best.span.evidence_id
        ],
        key=lambda item: item.span.order,
    )
    by_order = {item.span.order: item for item in same_evidence}

    # 직접 근거 뒤에 "이 경우", "다만" 등으로 이어지는 조건만 추가한다.
    next_ranked = by_order.get(best.span.order + 1)
    if (
        next_ranked is not None
        and next_ranked.span.text.startswith(CONTINUATION_PREFIXES)
        and next_ranked.semantic_score >= best.semantic_score - 0.12
    ):
        role: SelectionRole = (
            "exception"
            if next_ranked.span.text.startswith(("다만", "단,"))
            else "condition"
        )
        selected.append((next_ranked, role))

    # 선택된 문장이 "이 경우"로 시작하면 바로 앞 원칙 문장도 함께 보존한다.
    if best.span.text.startswith("이 경우"):
        previous = by_order.get(best.span.order - 1)
        if previous is not None and previous.semantic_score >= best.semantic_score - 0.12:
            selected.insert(0, (previous, "direct"))
            selected[1] = (best, "condition")

    return _materialize_ranked(
        selected=selected,
        evidence_map=evidence_map,
        method="single_direct_boolean",
    )


def _fallback_select(
    *,
    query_plan: QueryPlan,
    ranked_spans: list[RankedSpan],
    evidence_map: dict[str, EvidenceItem],
) -> list[EvidenceItem]:
    if not ranked_spans:
        return []

    if query_plan.completeness == "all":
        limit = 12
        floor = ranked_spans[0].hybrid_score - 0.12
        chosen = [item for item in ranked_spans[:limit] if item.hybrid_score >= floor]
    else:
        chosen = ranked_spans[:3]

    return _materialize_ranked(
        selected=[(item, "item") for item in chosen],
        evidence_map=evidence_map,
        method="hybrid_semantic_fallback",
    )


class EvidenceSelector:
    def __init__(self, client: LlamaClient, embedding_model: Any) -> None:
        self.client = client
        self.embedding_model = embedding_model

    def select(
        self,
        *,
        question: str,
        query_plan: QueryPlan,
        evidence: list[EvidenceItem],
    ) -> list[EvidenceItem]:
        if not evidence:
            return []

        spans, span_map = _build_spans(evidence)
        evidence_map = {item.evidence_id: item for item in evidence}
        if not spans:
            return []

        ranked_spans = _rank_spans(
            embedding_model=self.embedding_model,
            question=question,
            query_plan=query_plan,
            spans=spans,
        )

        # 가능·필수·허용 여부는 의미적으로 가장 직접적인 문장을 시스템이 고른다.
        if query_plan.answer_mode == "boolean_with_conditions":
            return _select_boolean_semantically(
                query_plan=query_plan,
                ranked_spans=ranked_spans,
                evidence_map=evidence_map,
            )

        # LLM에는 전체 원문이 아니라 의미 점수 상위 후보만 제공한다.
        candidate_limit = 16 if query_plan.completeness == "all" else 8
        candidates = ranked_spans[:candidate_limit]
        candidate_map = {item.span.span_id: item for item in candidates}

        prompt = (
            f"사용자 질문:\n{question}\n\n"
            f"QueryPlan:\n{query_plan.model_dump_json(indent=2)}\n\n"
            f"Evidence Spans:\n{_format_ranked_spans(evidence, candidates)}\n\n"
            "JSON만 출력하세요."
        )

        last_error: Exception | None = None
        for attempt in range(2):
            retry_note = ""
            if attempt == 1:
                retry_note = (
                    "\n이전 결과가 검증에 실패했습니다. 위 후보 목록에 표시된 "
                    "span_id만 그대로 선택하세요."
                )
            try:
                payload = self.client.chat_json(
                    system_prompt=SYSTEM_PROMPT,
                    user_prompt=prompt + retry_note,
                    temperature=0.0,
                    max_tokens=1000,
                )
                selection = SelectionPayload.model_validate(payload)

                selected_ranked: list[tuple[RankedSpan, SelectionRole]] = []
                for selected in selection.selected:
                    ranked = candidate_map.get(selected.span_id)
                    if ranked is None or selected.span_id not in span_map:
                        raise ValueError(f"후보에 없는 span_id 선택: {selected.span_id}")
                    selected_ranked.append((ranked, selected.role))

                if not selected_ranked:
                    return []

                return _materialize_ranked(
                    selected=selected_ranked,
                    evidence_map=evidence_map,
                    method="llm_from_semantic_candidates",
                )
            except (JsonResponseError, ValidationError, ValueError, RuntimeError) as error:
                last_error = error

        fallback = _fallback_select(
            query_plan=query_plan,
            ranked_spans=ranked_spans,
            evidence_map=evidence_map,
        )
        if fallback:
            return fallback

        raise RuntimeError(f"근거 선택 실패: {last_error}")
