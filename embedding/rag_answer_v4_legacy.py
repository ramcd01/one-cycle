"""
Qwen3 임베딩 검색 + 동일 표 확장 + llama.cpp 답변 생성

개선 사항
1. Section 의미 재정렬 결과 사용
2. 조건·예외·부정 표현 누락 방지 Prompt
3. 1차 답변을 문서 근거와 다시 대조하는 검증 단계
4. 명백히 다른 Section의 직접 검색 노이즈 제거
5. 문서에 없는 개설·가입·발급 방법 질문 사전 차단
6. 청약통장 필요 여부·미성년자 예외·신청자격 개요의 고신뢰 규칙 답변
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any

import numpy as np

from search_embeddings import (
    TOP_K,
    build_expanded_context,
    calculate_similarity,
    encode_query,
    find_embedding_file,
    format_section_path,
    get_chunk_metadata,
    get_reranked_results,
    infer_query_topic,
    load_embeddings,
    load_metadata,
    load_model,
    select_metadata_json,
)


LLAMA_BASE_URL = os.getenv(
    "LLAMA_BASE_URL",
    "http://127.0.0.1:8080",
).rstrip("/")

LLAMA_MODEL = os.getenv(
    "LLAMA_MODEL",
    "",
).strip()

LLAMA_API_KEY = os.getenv(
    "LLAMA_API_KEY",
    "no-key",
).strip()

LLAMA_TIMEOUT_SECONDS = 600

TEMPERATURE = 0.1
MAX_OUTPUT_TOKENS = 768
MAX_CONTEXT_CHARS = 9000
MIN_TOP_SIMILARITY = 0.35

# 정확도 우선. CPU에서는 답변 시간이 늘어난다.
ENABLE_ANSWER_VERIFICATION = True


SYSTEM_PROMPT = """
당신은 LH 입주자모집공고문 전용 질의응답 도우미입니다.

반드시 제공된 [문서 근거]만 사용해 답하세요.
문서 근거에 없는 사실을 추측하거나 일반 상식으로 보완하지 마세요.

답변 원칙:
1. 질문에 대한 결론을 먼저 한국어 존댓말로 답하세요.
2. 날짜, 시간, 금액, 단위, 세대수, 주소, 연락처, 서류명을 원문대로 보존하세요.
3. [단위]가 있으면 숫자에 반드시 반영하세요.
4. 합계 또는 소계가 명시되어 있으면 개별 행을 임의로 더하지 말고 그 값을 우선 사용하세요.
5. 본인 계약과 대리 계약, 신청과 계약, 접수와 제출을 서로 혼동하지 마세요.
6. 일반 원칙과 예외 조건이 함께 있으면 둘 다 설명하세요.
7. '다만', '이 경우', '한하여', '만 가능', '예외', '불가' 같은 조건·제한 표현을 절대로 생략하지 마세요.
8. 가능 여부를 묻는 질문에서 조건이 있으면 단순히 '가능합니다' 또는 '불가능합니다'로 끝내지 마세요.
9. 문서 근거가 부족하면 "현재 문서 근거만으로는 확인할 수 없습니다."라고 답하세요.
10. 서로 다른 근거가 있으면 질문과 직접 관련된 Section의 구체적인 근거를 우선하세요.
11. 각 핵심 문장 끝에 사용한 근거 번호를 [근거 1]처럼 표시하세요.
12. 제공되지 않은 근거 번호를 만들지 마세요.
13. 답변 끝에 근거 원문 전체를 다시 복사하지 마세요.
14. 같은 문장이나 같은 내용을 반복하지 마세요.
15. '필요하다/필요하지 않다'를 판단할 때 현장접수 여부와 자격요건을 혼동하지 마세요.
16. 포괄적인 신청자격 질문에는 신청 대상, 예외, 제한을 받지 않는 조건, 선정 방식까지 근거에 있는 범위에서 빠짐없이 요약하세요.
""".strip()


VERIFIER_SYSTEM_PROMPT = """
당신은 문서 기반 답변 검증기입니다.

사용자 질문, 문서 근거, 초안 답변을 비교하여 최종 답변을 다시 작성하세요.

반드시 확인할 사항:
1. 문서 근거에 없는 내용이 추가되지 않았는가
2. 일반 원칙과 예외 조건이 모두 반영되었는가
3. '다만', '이 경우', '한하여', '만 가능', '불가' 등의 조건이 누락되지 않았는가
4. 가능 여부 질문을 조건 없이 단정하지 않았는가
5. 금액 단위, 날짜, 시간, 세대수, 연락처가 정확한가
6. 근거 번호가 실제 제공된 번호와 일치하는가
7. 관련 없는 근거를 답변에 사용하지 않았는가
8. 청약통장 필요 여부를 현장접수 여부에서 잘못 추론하지 않았는가
9. 포괄적인 신청자격 질문에서 주요 조건을 한 문장만 답하고 나머지를 누락하지 않았는가

문제가 있으면 수정하고, 문제가 없어도 자연스럽게 다듬어 최종 답변만 출력하세요.
검토 과정이나 설명은 출력하지 마세요.
""".strip()


CONDITION_MARKERS = (
    "다만",
    "이 경우",
    "한하여",
    "만 신청 가능",
    "만 가능",
    "예외",
    "불가",
    "미성년",
    "세대주",
)


# 문서 밖 일반 사용법 질문을 판별한다.
# 예: "청약통장 만드는 법", "등본 발급 방법", "대출 신청 절차"
PROCEDURE_QUERY_PATTERNS = (
    r"(?P<subject>.+?)\s*만드는\s*법",
    r"(?P<subject>.+?)\s*만드는\s*방법",
    r"(?P<subject>.+?)\s*가입하는\s*법",
    r"(?P<subject>.+?)\s*가입\s*방법",
    r"(?P<subject>.+?)\s*개설\s*방법",
    r"(?P<subject>.+?)\s*발급\s*방법",
    r"(?P<subject>.+?)\s*신청\s*방법",
    r"(?P<subject>.+?)\s*이용\s*방법",
    r"(?P<subject>.+?)\s*처리\s*절차",
    r"(?P<subject>.+?)\s*신청\s*절차",
    r"(?P<subject>.+?)\s*가입\s*절차",
    r"(?P<subject>.+?)\s*개설\s*절차",
    r"(?P<subject>.+?)\s*어떻게\s*만들",
    r"(?P<subject>.+?)\s*어떻게\s*가입",
    r"(?P<subject>.+?)\s*어떻게\s*개설",
)

# 동일 대상을 표현하는 주요 용어 묶음
SUBJECT_ALIAS_GROUPS = (
    (
        "청약통장",
        (
            "청약통장",
            "입주자저축",
            "청약저축",
            "주택청약종합저축",
        ),
    ),
    (
        "주민등록표등본",
        (
            "주민등록표등본",
            "주민등록등본",
            "등본",
        ),
    ),
    (
        "인감증명서",
        (
            "인감증명서",
            "본인서명사실확인서",
        ),
    ),
)

# 실제 방법·절차 설명으로 볼 수 있는 구체적인 단서.
# 단순한 "가입 여부" 문구는 방법 설명으로 인정하지 않는다.
PROCEDURE_DETAIL_MARKERS = (
    "개설",
    "가입 방법",
    "가입방법",
    "가입 절차",
    "가입절차",
    "발급 방법",
    "발급방법",
    "발급 절차",
    "발급절차",
    "신청 방법",
    "신청방법",
    "신청 절차",
    "신청절차",
    "은행",
    "영업점",
    "창구",
    "온라인",
    "모바일",
    "준비물",
    "지참",
    "필요 서류",
    "필요서류",
    "구비 서류",
    "구비서류",
    "납입 금액",
    "납입금액",
    "예치금",
    "다운로드",
)


class LlamaServerError(RuntimeError):
    pass


def http_json(
    method: str,
    url: str,
    *,
    payload: dict[str, Any] | None = None,
    timeout: int = 30,
) -> dict[str, Any]:
    headers = {
        "Accept": "application/json",
    }

    data: bytes | None = None

    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(
            payload,
            ensure_ascii=False,
        ).encode("utf-8")

    if LLAMA_API_KEY:
        headers["Authorization"] = (
            f"Bearer {LLAMA_API_KEY}"
        )

    request = urllib.request.Request(
        url=url,
        data=data,
        headers=headers,
        method=method,
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=timeout,
        ) as response:
            response_text = response.read().decode("utf-8")

    except urllib.error.HTTPError as error:
        error_body = error.read().decode(
            "utf-8",
            errors="replace",
        )
        raise LlamaServerError(
            f"llama.cpp HTTP {error.code}: {error_body}"
        ) from error

    except urllib.error.URLError as error:
        raise LlamaServerError(
            "llama.cpp 서버에 연결할 수 없습니다.\n"
            f"서버 주소: {LLAMA_BASE_URL}\n"
            f"원인: {error.reason}"
        ) from error

    try:
        result = json.loads(response_text)

    except json.JSONDecodeError as error:
        raise LlamaServerError(
            "llama.cpp 서버가 JSON이 아닌 응답을 반환했습니다.\n"
            f"응답 일부: {response_text[:500]}"
        ) from error

    if not isinstance(result, dict):
        raise LlamaServerError(
            "llama.cpp 서버 응답 최상위 구조가 객체가 아닙니다."
        )

    return result


def check_llama_server() -> None:
    health = http_json(
        "GET",
        f"{LLAMA_BASE_URL}/health",
        timeout=10,
    )

    if str(health.get("status") or "").lower() != "ok":
        raise LlamaServerError(
            "llama.cpp 서버가 아직 준비되지 않았습니다.\n"
            f"health 응답: {health}"
        )


def get_llama_model_id() -> str:
    if LLAMA_MODEL:
        return LLAMA_MODEL

    response = http_json(
        "GET",
        f"{LLAMA_BASE_URL}/v1/models",
        timeout=30,
    )

    model_items = response.get("data")

    if not isinstance(model_items, list) or not model_items:
        raise LlamaServerError(
            "llama.cpp /v1/models 응답에서 모델을 찾지 못했습니다."
        )

    first_model = model_items[0]

    if not isinstance(first_model, dict):
        raise LlamaServerError(
            "llama.cpp 모델 정보 형식이 올바르지 않습니다."
        )

    model_id = str(
        first_model.get("id") or ""
    ).strip()

    if not model_id:
        raise LlamaServerError(
            "llama.cpp 모델 ID가 비어 있습니다."
        )

    return model_id


def call_chat(
    *,
    model_id: str,
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int,
) -> str:
    payload = {
        "model": model_id,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }

    response = http_json(
        "POST",
        f"{LLAMA_BASE_URL}/v1/chat/completions",
        payload=payload,
        timeout=LLAMA_TIMEOUT_SECONDS,
    )

    choices = response.get("choices")

    if not isinstance(choices, list) or not choices:
        raise LlamaServerError(
            "llama.cpp 응답에 choices가 없습니다."
        )

    message = choices[0].get("message")

    if not isinstance(message, dict):
        raise LlamaServerError(
            "llama.cpp choice.message 형식이 올바르지 않습니다."
        )

    answer = str(
        message.get("content") or ""
    ).strip()

    if not answer:
        raise LlamaServerError(
            "llama.cpp가 빈 답변을 반환했습니다."
        )

    return answer


def build_location_text(
    chunk: dict[str, Any],
) -> str:
    metadata = get_chunk_metadata(chunk)
    parts: list[str] = []

    section_path = format_section_path(metadata)

    if section_path:
        parts.append(section_path)

    table_index = metadata.get("table_index")
    row_index = metadata.get("row_index")

    if table_index is not None:
        parts.append(f"표 {table_index}")

    if row_index is not None:
        parts.append(f"행 {row_index}")

    return " · ".join(parts) or "위치 정보 없음"


def remove_topic_noise(
    question: str,
    context_results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    같은 표 확장 청크는 유지한다.
    직접 검색 결과 중 명백한 음수 보정을 받은 노이즈만 제거한다.
    """

    topic = infer_query_topic(question)

    if topic is None:
        return context_results

    positive_direct_count = sum(
        1
        for result in context_results
        if (
            result.get("direct_rank") is not None
            and float(result.get("topic_adjustment", 0.0)) > 0
        )
    )

    if positive_direct_count == 0:
        return context_results

    filtered: list[dict[str, Any]] = []

    for result in context_results:
        direct_rank = result.get("direct_rank")
        reasons = set(
            result.get("expansion_reasons") or []
        )
        adjustment = float(
            result.get("topic_adjustment", 0.0)
        )

        is_expanded_sibling = any(
            reason != "direct_top_k"
            for reason in reasons
        )

        if (
            direct_rank is not None
            and adjustment < 0
            and not is_expanded_sibling
        ):
            continue

        filtered.append(result)

    return filtered or context_results


def limit_context_results(
    context_results: list[dict[str, Any]],
    max_chars: int = MAX_CONTEXT_CHARS,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    used_chars = 0

    for result in context_results:
        chunk = result.get("chunk")

        if not isinstance(chunk, dict):
            continue

        text = str(
            chunk.get("text")
            or chunk.get("content")
            or ""
        ).strip()

        if not text:
            continue

        additional_chars = len(text)

        if (
            selected
            and used_chars + additional_chars > max_chars
        ):
            continue

        selected.append(result)
        used_chars += additional_chars

    return selected


def format_evidence_for_prompt(
    context_results: list[dict[str, Any]],
) -> str:
    blocks: list[str] = []

    for evidence_number, result in enumerate(
        context_results,
        start=1,
    ):
        chunk = result["chunk"]
        location = build_location_text(chunk)
        chunk_text = str(
            chunk.get("text")
            or chunk.get("content")
            or ""
        ).strip()

        blocks.append(
            f"[근거 {evidence_number}]\n"
            f"위치: {location}\n"
            f"청크 유형: {chunk.get('chunk_type')}\n"
            f"원문:\n{chunk_text}"
        )

    return "\n\n".join(blocks)



def compact_for_match(value: Any) -> str:
    """공백과 일부 문장부호를 제거해 비교용 문자열을 만든다."""

    return re.sub(
        r"[\s\[\]\(\){}<>·ㆍ,.:;!?\"'`]+",
        "",
        str(value or "").lower(),
    )


def extract_procedure_subject(
    question: str,
) -> str | None:
    """방법·절차 질문에서 대상 표현을 추출한다."""

    cleaned_question = str(question or "").strip()

    for pattern in PROCEDURE_QUERY_PATTERNS:
        match = re.search(
            pattern,
            cleaned_question,
            flags=re.IGNORECASE,
        )

        if not match:
            continue

        subject = str(
            match.groupdict().get("subject")
            or ""
        ).strip()

        subject = re.sub(
            r"^(?:그럼|그러면|혹시|저기|이거|그거)\s*",
            "",
            subject,
        ).strip()

        subject = re.sub(
            r"(?:은|는|이|가|을|를|의)$",
            "",
            subject,
        ).strip()

        return subject or None

    return None


def get_subject_aliases(
    subject: str,
) -> tuple[str, ...]:
    """질문 대상을 문서에서 찾기 위한 동의 표현을 반환한다."""

    compact_subject = compact_for_match(subject)

    for canonical, aliases in SUBJECT_ALIAS_GROUPS:
        alias_values = (
            canonical,
            *aliases,
        )

        if any(
            compact_for_match(alias) in compact_subject
            or compact_subject in compact_for_match(alias)
            for alias in alias_values
            if compact_for_match(alias)
        ):
            return tuple(
                dict.fromkeys(alias_values)
            )

    return (subject,)


def evaluate_document_support(
    question: str,
    context_results: list[dict[str, Any]],
) -> tuple[bool, str | None]:
    """
    문서가 방법·절차 질문에 실제로 답할 수 있는지 확인한다.

    벡터 유사도가 높아도 다음 조건을 만족하지 않으면 차단한다.
    1. 질문 대상이 근거에 실제로 등장
    2. 같은 근거 안에 구체적인 방법·절차 단서가 존재
    """

    subject = extract_procedure_subject(question)

    if not subject:
        return True, None

    aliases = get_subject_aliases(subject)
    compact_aliases = tuple(
        compact_for_match(alias)
        for alias in aliases
        if compact_for_match(alias)
    )

    subject_mentioned = False
    procedure_supported = False

    for result in context_results:
        chunk = result.get("chunk")

        if not isinstance(chunk, dict):
            continue

        chunk_text = str(
            chunk.get("text")
            or chunk.get("content")
            or ""
        )

        compact_chunk = compact_for_match(chunk_text)

        has_subject = any(
            alias in compact_chunk
            for alias in compact_aliases
        )

        if not has_subject:
            continue

        subject_mentioned = True

        if any(
            compact_for_match(marker) in compact_chunk
            for marker in PROCEDURE_DETAIL_MARKERS
        ):
            procedure_supported = True
            break

    if procedure_supported:
        return True, None

    if subject_mentioned:
        reason = (
            f"현재 문서에는 '{subject}'에 대한 언급은 있지만, "
            "만드는 방법이나 개설·가입 절차는 안내되어 있지 않습니다."
        )
    else:
        reason = (
            f"현재 문서에는 '{subject}'을(를) 만드는 방법이나 "
            "개설·가입 절차에 대한 근거가 없습니다."
        )

    return False, reason



def get_context_chunk_text(
    result: dict[str, Any],
) -> str:
    chunk = result.get("chunk")

    if not isinstance(chunk, dict):
        return ""

    return str(
        chunk.get("text")
        or chunk.get("content")
        or ""
    ).strip()


def find_evidence_with_terms(
    context_results: list[dict[str, Any]],
    required_terms: tuple[str, ...],
) -> tuple[int, str] | None:
    """모든 필수 표현이 들어 있는 첫 근거를 찾는다."""

    compact_terms = tuple(
        compact_for_match(term)
        for term in required_terms
    )

    for evidence_number, result in enumerate(
        context_results,
        start=1,
    ):
        text = get_context_chunk_text(result)
        compact_text_value = compact_for_match(text)

        if all(
            term in compact_text_value
            for term in compact_terms
        ):
            return evidence_number, text

    return None


def is_subscription_savings_necessity_question(
    question: str,
) -> bool:
    compact_question = compact_for_match(question)

    has_subject = any(
        compact_for_match(keyword) in compact_question
        for keyword in (
            "청약통장",
            "입주자저축",
            "청약저축",
            "주택청약종합저축",
        )
    )

    has_necessity_intent = any(
        compact_for_match(keyword) in compact_question
        for keyword in (
            "필요",
            "필수",
            "있어야",
            "없어도",
            "가입해야",
            "가입되어야",
        )
    )

    return has_subject and has_necessity_intent


def is_broad_eligibility_question(
    question: str,
) -> bool:
    compact_question = compact_for_match(question)

    has_general_eligibility = any(
        compact_for_match(keyword) in compact_question
        for keyword in (
            "신청자격",
            "신청조건",
            "지원자격",
            "자격을알려",
            "자격이어떻게",
        )
    )

    has_specific_subtopic = any(
        compact_for_match(keyword) in compact_question
        for keyword in (
            "미성년",
            "청약통장",
            "입주자저축",
            "법인",
            "주택소유",
            "무주택",
            "소득",
            "자산",
            "당첨",
            "거주지역",
            "세대주",
        )
    )

    return has_general_eligibility and not has_specific_subtopic


def build_high_confidence_grounded_answer(
    question: str,
    context_results: list[dict[str, Any]],
) -> str | None:
    """
    근거 문구가 명확한 고위험 질문은 생성 모델의 추론에 맡기지 않고,
    문서 표현을 바탕으로 보수적으로 답한다.
    """

    compact_question = compact_for_match(question)

    if is_subscription_savings_necessity_question(question):
        evidence = find_evidence_with_terms(
            context_results,
            (
                "입주자저축 가입여부",
                "불문",
            ),
        )

        if evidence is not None:
            evidence_number, _ = evidence

            return (
                "아니요. 이 공고에서는 신청자의 입주자저축 가입 여부를 "
                "불문하므로, 청약통장 가입은 신청 필수 조건이 아닙니다. "
                f"[근거 {evidence_number}]"
            )

    if "미성년" in compact_question:
        evidence = find_evidence_with_terms(
            context_results,
            (
                "미성년자",
                "직계존속의 사망",
                "실종선고",
                "행방불명",
                "세대주",
                "같은 세대별 주민등록표",
            ),
        )

        if evidence is not None:
            evidence_number, _ = evidence

            return (
                "원칙적으로 이 공고의 신청 대상은 성년자입니다. "
                "다만, 「민법」상 미성년자는 직계존속의 사망, 실종선고 및 "
                "행방불명 등으로 형제자매 또는 자녀를 부양해야 하는 "
                "세대주인 경우에만 신청할 수 있습니다. "
                "이 경우 형제자매 및 자녀는 미성년자와 같은 세대별 "
                "주민등록표에 등재되어 있어야 합니다. "
                f"[근거 {evidence_number}]"
            )

    if is_broad_eligibility_question(question):
        evidence = find_evidence_with_terms(
            context_results,
            (
                "대한민국 거주 성년자",
                "국내에 주소를 둔 법인",
                "입주자저축 가입여부",
                "소득 및 자산요건",
                "선착순",
            ),
        )

        if evidence is not None:
            evidence_number, evidence_text = evidence
            compact_evidence = compact_for_match(
                evidence_text
            )

            lines: list[str] = [
                "신청 자격과 주요 확인사항은 다음과 같습니다.",
                (
                    "- 입주자모집공고일 기준 대한민국에 거주하는 "
                    "성년자와 국내에 주소를 둔 법인이 신청할 수 있습니다. "
                    f"[근거 {evidence_number}]"
                ),
            ]

            if "1세대2주택이상도가능" in compact_evidence:
                lines.append(
                    "- 1세대 2주택 이상도 신청할 수 있습니다. "
                    f"[근거 {evidence_number}]"
                )

            if (
                "미성년자" in compact_evidence
                and "직계존속의사망" in compact_evidence
                and "세대주" in compact_evidence
            ):
                lines.append(
                    "- 미성년자는 직계존속의 사망, 실종선고 및 행방불명 "
                    "등으로 형제자매 또는 자녀를 부양해야 하는 세대주인 "
                    "경우에만 신청할 수 있으며, 해당 가족은 같은 세대별 "
                    "주민등록표에 등재되어 있어야 합니다. "
                    f"[근거 {evidence_number}]"
                )

            if (
                "거주지역" in compact_evidence
                and "주택소유여부" in compact_evidence
                and "입주자저축가입여부" in compact_evidence
                and "과거당첨사실여부" in compact_evidence
                and "소득및자산요건" in compact_evidence
                and "불문" in compact_evidence
            ):
                lines.append(
                    "- 거주지역, 주택 소유 여부, 입주자저축 가입 여부, "
                    "과거 당첨 사실, 소득 및 자산요건과 관계없이 "
                    "신청할 수 있습니다. "
                    f"[근거 {evidence_number}]"
                )

            if (
                "재당첨제한" in compact_evidence
                and "당첨자관리" in compact_evidence
                and "적용되지않습니다" in compact_evidence
            ):
                lines.append(
                    "- 당첨 및 계약 체결 시 재당첨 제한과 당첨자 관리가 "
                    "적용되지 않습니다. "
                    f"[근거 {evidence_number}]"
                )

            if "선착순" in compact_evidence:
                lines.append(
                    "- 입주자는 선착순 방식으로 선정합니다. "
                    f"[근거 {evidence_number}]"
                )

            return "\n".join(lines)

    return None


def build_condition_warning(
    question: str,
    evidence_text: str,
) -> str:
    q = "".join(question.lower().split())
    is_yes_no_question = any(
        marker in q
        for marker in (
            "수있",
            "가능",
            "되나요",
            "돼",
            "인가요",
            "맞아",
        )
    )

    evidence_has_condition = any(
        marker in evidence_text
        for marker in CONDITION_MARKERS
    )

    if is_yes_no_question and evidence_has_condition:
        return (
            "\n\n[중요 검증 지시]\n"
            "이 질문은 가능 여부를 묻고 문서 근거에 조건 또는 예외가 있습니다. "
            "원칙과 예외 조건을 모두 포함해 답하고, 단순히 가능 또는 불가능하다고 단정하지 마세요."
        )

    return ""


def create_draft_answer(
    *,
    model_id: str,
    question: str,
    evidence_text: str,
) -> str:
    user_prompt = (
        "[사용자 질문]\n"
        f"{question}\n\n"
        "[문서 근거]\n"
        f"{evidence_text}"
        f"{build_condition_warning(question, evidence_text)}"
    )

    return call_chat(
        model_id=model_id,
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ],
        temperature=TEMPERATURE,
        max_tokens=MAX_OUTPUT_TOKENS,
    )


def verify_answer(
    *,
    model_id: str,
    question: str,
    evidence_text: str,
    draft_answer: str,
) -> str:
    if not ENABLE_ANSWER_VERIFICATION:
        return draft_answer

    verifier_prompt = (
        "[사용자 질문]\n"
        f"{question}\n\n"
        "[문서 근거]\n"
        f"{evidence_text}\n\n"
        "[초안 답변]\n"
        f"{draft_answer}"
    )

    return call_chat(
        model_id=model_id,
        messages=[
            {
                "role": "system",
                "content": VERIFIER_SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": verifier_prompt,
            },
        ],
        temperature=0.0,
        max_tokens=MAX_OUTPUT_TOKENS,
    )


def print_retrieval_summary(
    *,
    question: str,
    raw_results: list[dict[str, Any]],
    context_results: list[dict[str, Any]],
) -> None:
    line = "=" * 80

    print("\n" + line)
    print(f"질문: {question}")
    print(line)

    print(
        f"재정렬 Top-{len(raw_results)}: "
        + ", ".join(
            (
                f"{result['chunk'].get('chunk_id')}"
                f"(vector={result['similarity']:.4f}, "
                f"rerank={result['rerank_score']:.4f})"
            )
            for result in raw_results
        )
    )

    print(
        f"최종 LLM Context: {len(context_results)}개"
    )

    for evidence_number, result in enumerate(
        context_results,
        start=1,
    ):
        chunk = result["chunk"]

        print(
            f"  [근거 {evidence_number}] "
            f"{chunk.get('chunk_id')} · "
            f"{build_location_text(chunk)}"
        )


def print_answer_and_sources(
    answer: str,
    context_results: list[dict[str, Any]],
) -> None:
    line = "=" * 80

    print("\n" + line)
    print("AI 최종 답변")
    print(line)
    print(answer)

    print("\n" + line)
    print("답변에 전달된 근거")
    print(line)

    for evidence_number, result in enumerate(
        context_results,
        start=1,
    ):
        chunk = result["chunk"]

        print(
            f"[근거 {evidence_number}] "
            f"{build_location_text(chunk)}"
        )
        print(
            f"  chunk_id={chunk.get('chunk_id')} "
            f"/ type={chunk.get('chunk_type')} "
            f"/ similarity={result.get('similarity', 0.0):.4f}"
        )

    print(line + "\n")


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
        embedding_model, _ = load_model(metadata)

        print("llama.cpp 서버 확인 중...")
        check_llama_server()
        llama_model_id = get_llama_model_id()

        print("\n" + "=" * 80)
        print("RAG 답변 생성 준비 완료")
        print("=" * 80)
        print(f"임베딩 배열: {embeddings.shape}")
        print(f"검색 Top-K: {TOP_K}")
        print(f"llama.cpp 서버: {LLAMA_BASE_URL}")
        print(f"생성 모델: {llama_model_id}")
        print(
            "답변 검증 단계: "
            f"{'활성화' if ENABLE_ANSWER_VERIFICATION else '비활성화'}"
        )
        print("=" * 80)
        print(
            "질문을 입력하세요. "
            "종료하려면 exit, quit 또는 q를 입력하세요.\n"
        )

        while True:
            question = input("질문> ").strip()

            if question.lower() in {
                "exit",
                "quit",
                "q",
            }:
                print("RAG 답변 테스트를 종료합니다.")
                break

            if not question:
                print("질문을 입력해주세요.")
                continue

            query_embedding = encode_query(
                embedding_model,
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

            if not raw_results:
                print(
                    "\n현재 문서에서 관련 근거를 찾지 못했습니다.\n"
                )
                continue

            top_vector_similarity = max(
                float(result["similarity"])
                for result in raw_results
            )

            if top_vector_similarity < MIN_TOP_SIMILARITY:
                print(
                    "\n현재 문서 근거만으로는 확인할 수 없습니다.\n"
                    f"최고 벡터 유사도: {top_vector_similarity:.4f} "
                    f"(기준: {MIN_TOP_SIMILARITY:.2f})\n"
                )
                continue

            expanded_context = build_expanded_context(
                question,
                raw_results,
                scores,
                metadata["chunks"],
            )

            context_results = remove_topic_noise(
                question,
                expanded_context["context_results"],
            )

            context_results = limit_context_results(
                context_results,
                MAX_CONTEXT_CHARS,
            )

            if not context_results:
                print(
                    "\n답변 생성에 사용할 근거가 없습니다.\n"
                )
                continue

            best_context_similarity = max(
                float(result.get("similarity", 0.0))
                for result in context_results
            )

            if best_context_similarity < MIN_TOP_SIMILARITY:
                print(
                    "\n현재 문서 근거만으로는 확인할 수 없습니다.\n"
                    f"주제 필터 후 최고 유사도: "
                    f"{best_context_similarity:.4f} "
                    f"(기준: {MIN_TOP_SIMILARITY:.2f})\n"
                )
                continue

            is_supported, unsupported_reason = (
                evaluate_document_support(
                    question,
                    context_results,
                )
            )

            if not is_supported:
                print(
                    "\n현재 문서 근거만으로는 요청한 방법을 "
                    "안내할 수 없습니다."
                )
                print(
                    unsupported_reason
                    or "구체적인 방법·절차 근거가 없습니다."
                )
                print()
                continue

            print_retrieval_summary(
                question=question,
                raw_results=raw_results,
                context_results=context_results,
            )

            guarded_answer = (
                build_high_confidence_grounded_answer(
                    question,
                    context_results,
                )
            )

            if guarded_answer is not None:
                print(
                    "\n고신뢰 문서 규칙 답변 적용"
                )
                print_answer_and_sources(
                    guarded_answer,
                    context_results,
                )
                continue

            evidence_text = format_evidence_for_prompt(
                context_results
            )

            print("\n1차 답변 생성 중...")

            draft_answer = create_draft_answer(
                model_id=llama_model_id,
                question=question,
                evidence_text=evidence_text,
            )

            if ENABLE_ANSWER_VERIFICATION:
                print("문서 근거 대조 및 조건 검증 중...")

            final_answer = verify_answer(
                model_id=llama_model_id,
                question=question,
                evidence_text=evidence_text,
                draft_answer=draft_answer,
            )

            print_answer_and_sources(
                final_answer,
                context_results,
            )

    except (
        OSError,
        json.JSONDecodeError,
        ValueError,
        TypeError,
        RuntimeError,
        MemoryError,
    ) as error:
        print("\nRAG 답변 테스트 실패")
        print(str(error))
        raise


if __name__ == "__main__":
    main()
