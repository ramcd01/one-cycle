from __future__ import annotations

import re

from pydantic import ValidationError

from .llama_client import JsonResponseError, LlamaClient
from .schemas import AnswerPlan, CoverageResult, EvidenceItem, QueryPlan


SYSTEM_PROMPT = """
당신은 검증된 문서 근거만 사용하는 답변 계획기입니다.
제공된 Evidence는 이미 질문과 직접 관련된 원문만 골라낸 결과입니다.
외부 지식이나 상식을 사용하지 말고, Evidence가 직접 뒷받침하는 claim만 JSON으로 만드세요.

공통 규칙:
1. 각 claim은 반드시 실제 evidence_id를 하나 이상 인용해야 합니다.
2. Evidence에 없는 숫자, 날짜, 금액, 단위, 조건, 인과관계를 만들지 마세요.
3. 같은 결론이나 같은 내용을 표현만 바꾸어 반복하지 마세요.
4. 질문과 관계없는 배경 사실은 답변에 포함하지 마세요.
5. claim text에는 [근거] 표기를 넣지 마세요.
6. 문장은 짧고 직접적으로 작성하세요.
7. Evidence에 표시된 선택 역할(direct, condition, exception)을 반드시 지키세요.

answer_mode별 규칙:
- boolean_with_conditions:
  · conclusion claim은 정확히 1개만 만드세요.
  · conclusion은 질문 대상의 가능·필수·허용 여부를 직접 답하세요.
  · direct 역할 Evidence만 conclusion에 사용하세요.
  · condition 역할 Evidence가 있을 때만 condition claim을 만들 수 있습니다.
  · exception 역할 Evidence가 있을 때만 exception claim을 만들 수 있습니다.
  · direct 역할뿐이라면 conclusion 1개만 만들고 다른 claim은 만들지 마세요.
  · 원문에 있는 '불문' 자체를 예외로 분류하지 마세요. 질문의 직접 판정 근거입니다.
  · group은 null로 두세요.
- single_value:
  · 요청한 값 중심의 claim 1개를 우선하세요.
- explicit_total:
  · 문서에 명시된 합계·소계 claim 1개를 우선하세요.
- complete_list, complete_grouped_list, all_matching_items:
  · 서로 다른 항목을 빠짐없이 item claim으로 만드세요.
  · 실제 구분이 있을 때만 group을 사용하세요.
- overview:
  · 관련 표 행과 핵심 항목을 중복 없이 요약하세요.
- procedure_steps:
  · 문서에 실제로 존재하는 단계만 순서대로 작성하세요.

JSON 형식:
{
  "answer_mode": "입력 QueryPlan의 answer_mode와 동일",
  "claims": [
    {
      "text": "근거로 직접 뒷받침되는 한국어 문장 또는 항목",
      "evidence_ids": ["evidence_001"],
      "kind": "conclusion|condition|exception|item|total|step|explanation",
      "group": null
    }
  ]
}
""".strip()


def _format_evidence(evidence: list[EvidenceItem]) -> str:
    blocks: list[str] = []
    for item in evidence:
        location = " > ".join(item.location.section_path) or "문서 도입부"
        if item.location.table_index is not None:
            location += f" · 표 {item.location.table_index}"
        if item.location.row_index is not None:
            location += f" · 행 {item.location.row_index}"
        roles = ", ".join(item.debug.get("selection_roles", [])) or "item"
        blocks.append(
            f"[{item.evidence_id}]\n선택 역할: {roles}\n위치: {location}\n선택된 원문:\n{item.excerpt}"
        )
    return "\n\n".join(blocks)


def _numbers(text: str) -> set[str]:
    return set(re.findall(r"\d[\d,.:-]*", text))


def _normalize_claim(text: str) -> str:
    return re.sub(r"[^가-힣a-z0-9]", "", text.lower())


class AnswerPlanner:
    def __init__(self, client: LlamaClient) -> None:
        self.client = client

    def create(
        self,
        *,
        question: str,
        query_plan: QueryPlan,
        coverage: CoverageResult,
        evidence: list[EvidenceItem],
    ) -> AnswerPlan:
        evidence_map = {item.evidence_id: item for item in evidence}
        prompt = (
            f"사용자 질문:\n{question}\n\n"
            f"QueryPlan:\n{query_plan.model_dump_json(indent=2)}\n\n"
            f"완전성 검사:\n{coverage.model_dump_json(indent=2)}\n\n"
            f"Evidence:\n{_format_evidence(evidence)}\n\n"
            "JSON만 출력하세요."
        )

        last_error: Exception | None = None
        for attempt in range(2):
            retry_note = ""
            if attempt == 1:
                retry_note = (
                    "\n이전 출력이 검증에 실패했습니다. 중복 claim을 제거하세요. "
                    "boolean_with_conditions에서 direct 역할만 제공되었다면 "
                    "conclusion 1개만 작성하고 condition·exception·explanation을 만들지 마세요."
                )
            try:
                payload = self.client.chat_json(
                    system_prompt=SYSTEM_PROMPT,
                    user_prompt=prompt + retry_note,
                    temperature=0.0,
                    max_tokens=1200,
                )
                plan = AnswerPlan.model_validate(payload)
                self._validate_plan(
                    plan=plan,
                    query_plan=query_plan,
                    coverage=coverage,
                    evidence_map=evidence_map,
                )
                return plan
            except (JsonResponseError, ValidationError, ValueError, RuntimeError) as error:
                last_error = error

        raise RuntimeError(f"답변 계획 생성 실패: {last_error}")

    def _validate_plan(
        self,
        *,
        plan: AnswerPlan,
        query_plan: QueryPlan,
        coverage: CoverageResult,
        evidence_map: dict[str, EvidenceItem],
    ) -> None:
        if plan.answer_mode != query_plan.answer_mode:
            raise ValueError("AnswerPlan의 answer_mode가 QueryPlan과 다릅니다.")

        normalized_claims: set[str] = set()
        used_ids: set[str] = set()

        for claim in plan.claims:
            normalized = _normalize_claim(claim.text)
            if normalized in normalized_claims:
                raise ValueError("동일한 claim이 중복되었습니다.")
            normalized_claims.add(normalized)

            cited_texts: list[str] = []
            for evidence_id in claim.evidence_ids:
                if evidence_id not in evidence_map:
                    raise ValueError(f"존재하지 않는 evidence_id: {evidence_id}")
                used_ids.add(evidence_id)
                cited_texts.append(evidence_map[evidence_id].excerpt)

            cited_numbers = _numbers("\n".join(cited_texts))
            unsupported_numbers = _numbers(claim.text) - cited_numbers
            if unsupported_numbers:
                raise ValueError(
                    "근거에 없는 숫자가 claim에 포함됨: "
                    + ", ".join(sorted(unsupported_numbers))
                )

        if query_plan.answer_mode == "boolean_with_conditions":
            conclusions = [claim for claim in plan.claims if claim.kind == "conclusion"]
            if len(conclusions) != 1:
                raise ValueError(
                    "boolean_with_conditions는 conclusion claim이 정확히 1개여야 합니다."
                )
            if conclusions[0].group is not None:
                raise ValueError("boolean 결론에는 group을 사용할 수 없습니다.")

            roles_by_id = {
                evidence_id: set(item.debug.get("selection_roles", []))
                for evidence_id, item in evidence_map.items()
            }
            direct_ids = {
                evidence_id
                for evidence_id, roles in roles_by_id.items()
                if "direct" in roles
            }
            condition_ids = {
                evidence_id
                for evidence_id, roles in roles_by_id.items()
                if "condition" in roles
            }
            exception_ids = {
                evidence_id
                for evidence_id, roles in roles_by_id.items()
                if "exception" in roles
            }

            if not (set(conclusions[0].evidence_ids) & direct_ids):
                raise ValueError(
                    "boolean 결론은 direct 역할 Evidence를 인용해야 합니다."
                )
            if len(conclusions[0].text) > 240:
                raise ValueError("boolean 결론이 지나치게 깁니다.")

            invalid_kinds = {
                claim.kind
                for claim in plan.claims
                if claim.kind not in {"conclusion", "condition", "exception"}
            }
            if invalid_kinds:
                raise ValueError(
                    "boolean 답변에 허용되지 않은 claim kind: "
                    + ", ".join(sorted(invalid_kinds))
                )
            if any(claim.group is not None for claim in plan.claims):
                raise ValueError("boolean 답변에는 group을 사용할 수 없습니다.")

            for claim in plan.claims:
                cited = set(claim.evidence_ids)
                if claim.kind == "condition" and not (cited & condition_ids):
                    raise ValueError(
                        "condition claim은 condition 역할 Evidence가 있을 때만 만들 수 있습니다."
                    )
                if claim.kind == "exception" and not (cited & exception_ids):
                    raise ValueError(
                        "exception claim은 exception 역할 Evidence가 있을 때만 만들 수 있습니다."
                    )

            if not condition_ids and any(
                claim.kind == "condition" for claim in plan.claims
            ):
                raise ValueError("선택된 조건 근거가 없으므로 condition claim을 만들 수 없습니다.")
            if not exception_ids and any(
                claim.kind == "exception" for claim in plan.claims
            ):
                raise ValueError("선택된 예외 근거가 없으므로 exception claim을 만들 수 없습니다.")

            if not condition_ids and not exception_ids and len(plan.claims) != 1:
                raise ValueError(
                    "direct 역할 근거만 있는 boolean 답변은 conclusion 1개만 허용됩니다."
                )

        if query_plan.answer_mode == "explicit_total":
            total_claims = [
                claim for claim in plan.claims
                if claim.kind in {"total", "conclusion"}
            ]
            if not total_claims:
                raise ValueError("explicit_total 답변에 total claim이 없습니다.")

        missing_required = set(coverage.required_evidence_ids) - used_ids
        if missing_required:
            raise ValueError(
                "완전성 모드에서 누락된 Evidence: "
                + ", ".join(sorted(missing_required))
            )
