from __future__ import annotations

import re

from pydantic import ValidationError

from .llama_client import JsonResponseError, LlamaClient
from .schemas import QueryPlan


SYSTEM_PROMPT = """
당신은 문서 기반 질의응답 시스템의 질문 계획기입니다.
질문의 정답을 작성하지 말고, 질문이 요구하는 검색·답변 형태만 JSON으로 분류하세요.
특정 문장 표현이 아니라 의미를 기준으로 판단하세요.

허용 intent:
fact_lookup, requirement_check, list_lookup, aggregate,
procedure, contact_lookup, overview, explanation

허용 answer_mode:
single_value, boolean_with_conditions, complete_list,
complete_grouped_list, explicit_total, procedure_steps,
all_matching_items, overview, grounded_explanation

규칙:
- 가능/필수/허용 여부와 조건을 묻는 질문은 requirement_check + boolean_with_conditions
- 여러 서류·항목·종류를 묻는 질문은 list_lookup
- 총합·몇 세대·합계를 묻는 질문은 aggregate + explicit_total
- 만드는 법·절차·방법을 묻는 질문은 procedure + procedure_steps
- 전화번호·문의처·연락처는 contact_lookup + all_matching_items
- 전체 정보·개요·무엇이 있는지를 묻는 질문은 overview
- 특정 금액·날짜·장소·값 하나는 fact_lookup + single_value
- 쉽게 설명·의미 해석은 explanation + grounded_explanation
- 목록·문의처·개요는 completeness를 all로 설정
- 하나의 대상에 대한 가능·필수 여부 질문은 completeness를 relevant로 설정

아래 키만 포함한 JSON 객체를 출력하세요.
{
  "intent": "...",
  "target": "질문의 핵심 대상",
  "answer_mode": "...",
  "scope": "관련 문서 영역 또는 null",
  "completeness": "single|relevant|all",
  "requested_fields": []
}
""".strip()


_BROAD_ELIGIBILITY_PATTERNS = (
    r"신청\s*자격(?:을|이|은|는)?\s*(?:알려|정리|설명|뭐|무엇)",
    r"지원\s*자격(?:을|이|은|는)?\s*(?:알려|정리|설명|뭐|무엇)",
    r"자격\s*조건(?:을|이|은|는)?\s*(?:알려|정리|설명|뭐|무엇)",
    r"누가\s*(?:신청|지원)(?:할\s*수\s*)?있",
    r"신청\s*대상(?:을|이|은|는)?\s*(?:알려|정리|설명|뭐|무엇)",
)


def _is_broad_eligibility_question(question: str) -> bool:
    compact = re.sub(r"\s+", " ", question.strip().lower())
    return any(re.search(pattern, compact) for pattern in _BROAD_ELIGIBILITY_PATTERNS)


def _normalize_plan(question: str, plan: QueryPlan) -> QueryPlan:
    """LLM 분류 결과를 서비스 정책에 맞게 보정한다.

    특정 질문의 정답을 넣는 것이 아니라, 답변 범위만 안정화한다.
    - 단일 대상의 예/아니오 질문: 관련 근거만 사용
    - 신청자격 전체를 묻는 질문: 전체 개요로 처리
    """
    if _is_broad_eligibility_question(question):
        return QueryPlan(
            intent="overview",
            target="신청 자격",
            answer_mode="overview",
            scope="신청자격",
            completeness="all",
            requested_fields=plan.requested_fields,
        )

    if plan.answer_mode == "boolean_with_conditions":
        return plan.model_copy(update={"completeness": "relevant"})

    return plan


def _fallback_plan(question: str) -> QueryPlan:
    q = "".join(question.lower().split())

    if re.search(r"(방법|절차|만드는법|어떻게.*(만들|가입|발급|신청|제출))", q):
        return QueryPlan(
            intent="procedure",
            target=question.strip(),
            answer_mode="procedure_steps",
            scope=None,
            completeness="all",
        )

    if any(token in q for token in ("연락처", "전화번호", "문의처", "문의전화")):
        return QueryPlan(
            intent="contact_lookup",
            target=question.strip(),
            answer_mode="all_matching_items",
            scope="연락처",
            completeness="all",
        )

    if any(token in q for token in ("총", "합계", "소계", "몇세대", "몇호")):
        return QueryPlan(
            intent="aggregate",
            target=question.strip(),
            answer_mode="explicit_total",
            scope=None,
            completeness="all",
        )

    if any(token in q for token in ("필요한서류", "구비서류", "제출서류", "준비물", "목록")):
        return QueryPlan(
            intent="list_lookup",
            target=question.strip(),
            answer_mode="complete_grouped_list",
            scope=None,
            completeness="all",
        )

    if _is_broad_eligibility_question(question):
        return QueryPlan(
            intent="overview",
            target="신청 자격",
            answer_mode="overview",
            scope="신청자격",
            completeness="all",
        )

    if re.search(r"(가능|할수있|필요|필수|없어도|되어야|자격)", q):
        return QueryPlan(
            intent="requirement_check",
            target=question.strip(),
            answer_mode="boolean_with_conditions",
            scope="신청자격",
            completeness="relevant",
        )

    if any(token in q for token in ("정보", "알려줘", "어떤", "무엇이")) and not re.search(r"(얼마|언제|어디)", q):
        return QueryPlan(
            intent="overview",
            target=question.strip(),
            answer_mode="overview",
            scope=None,
            completeness="all",
        )

    return QueryPlan(
        intent="fact_lookup",
        target=question.strip(),
        answer_mode="single_value",
        scope=None,
        completeness="single",
    )


class QueryPlanner:
    def __init__(self, client: LlamaClient) -> None:
        self.client = client

    def plan(self, question: str) -> QueryPlan:
        prompt = f"사용자 질문:\n{question}\n\nJSON만 출력하세요."
        try:
            payload = self.client.chat_json(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=prompt,
                temperature=0.0,
                max_tokens=500,
            )
            plan = QueryPlan.model_validate(payload)
        except (JsonResponseError, ValidationError, RuntimeError):
            plan = _fallback_plan(question)

        return _normalize_plan(question, plan)
