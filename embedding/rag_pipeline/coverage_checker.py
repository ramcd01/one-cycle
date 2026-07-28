from __future__ import annotations

import re

from .schemas import CoverageResult, EvidenceItem, QueryPlan


PROCEDURE_MARKERS = (
    "1.", "2.", "①", "②", "단계", "절차", "방법", "접속", "선택",
    "입력", "방문하여", "지참", "준비물", "구비서류", "신청서 작성",
    "온라인", "홈페이지", "영업점", "창구", "계좌로 입금",
)

JUDGMENT_MARKERS = (
    "가능", "불가", "필수", "아님", "불문", "대상", "제외", "한하여",
    "경우에만", "제한", "요건", "자격",
)

TOTAL_MARKERS = ("총계", "합계", "소계", "총 ", "총:", "모집호수")


def _compact(value: str) -> str:
    return re.sub(r"\s+", "", value.lower())


def _target_tokens(target: str) -> list[str]:
    words = re.findall(r"[가-힣A-Za-z0-9]{2,}", target)
    stop = {
        "알려줘", "알려주세요", "무엇인가요", "어떻게", "되나요", "가능한가요",
        "필요한가요", "정보", "대한", "관련", "질문",
    }
    return [word for word in words if word not in stop][:8]


class CoverageChecker:
    def __init__(self, min_similarity: float = 0.35) -> None:
        self.min_similarity = min_similarity

    def check(
        self,
        query_plan: QueryPlan,
        evidence: list[EvidenceItem],
    ) -> CoverageResult:
        if not evidence:
            return CoverageResult(
                supported=False,
                reason="검색된 문서 근거가 없습니다.",
                missing_requirements=["evidence"],
            )

        max_similarity = max(item.similarity for item in evidence)
        if max_similarity < self.min_similarity:
            return CoverageResult(
                supported=False,
                reason=(
                    "질문과 직접 관련된 문서 근거의 유사도가 기준보다 낮습니다."
                ),
                missing_requirements=["relevant_evidence"],
            )

        combined = "\n".join(item.excerpt for item in evidence)
        compact = _compact(combined)
        tokens = _target_tokens(query_plan.target)
        target_matched = not tokens or any(_compact(token) in compact for token in tokens)

        if query_plan.answer_mode == "procedure_steps":
            target_tokens = _target_tokens(query_plan.target)
            same_evidence_support = False
            for item in evidence:
                item_compact = _compact(item.excerpt)
                item_has_target = (
                    not target_tokens
                    or any(_compact(token) in item_compact for token in target_tokens)
                )
                item_has_procedure = any(
                    marker in item.excerpt for marker in PROCEDURE_MARKERS
                )
                if item_has_target and item_has_procedure:
                    same_evidence_support = True
                    break

            if not same_evidence_support:
                return CoverageResult(
                    supported=False,
                    reason="대상은 언급될 수 있지만 요청한 방법·절차를 구성할 근거가 없습니다.",
                    missing_requirements=["procedure_steps"],
                )

        if query_plan.answer_mode == "boolean_with_conditions":
            direct_evidence = [
                item
                for item in evidence
                if "direct" in item.debug.get("selection_roles", [])
            ]
            if not direct_evidence:
                return CoverageResult(
                    supported=False,
                    reason="질문의 가능·필수 여부를 직접 뒷받침하는 근거를 선택하지 못했습니다.",
                    missing_requirements=["direct_judgment_evidence"],
                )
            direct_text = "\n".join(item.excerpt for item in direct_evidence)
            if not any(marker in direct_text for marker in JUDGMENT_MARKERS):
                return CoverageResult(
                    supported=False,
                    reason="가능·필수 여부를 판정할 명시적인 조건 근거가 부족합니다.",
                    missing_requirements=["judgment_or_conditions"],
                )

        if query_plan.answer_mode == "explicit_total":
            if not any(marker in combined for marker in TOTAL_MARKERS):
                return CoverageResult(
                    supported=False,
                    reason="문서에 명시된 합계·소계 근거를 찾지 못했습니다.",
                    missing_requirements=["explicit_total_or_subtotal"],
                )

        complete_modes = {
            "complete_list",
            "complete_grouped_list",
            "all_matching_items",
            "overview",
        }
        required_ids: list[str] = []
        if (
            query_plan.answer_mode in complete_modes
            and query_plan.completeness == "all"
        ):
            table_evidence = [
                item for item in evidence if item.location.table_index is not None
            ]
            if table_evidence:
                required_ids = [item.evidence_id for item in table_evidence]

        return CoverageResult(
            supported=True,
            reason="질문에 답할 문서 근거가 확보되었습니다.",
            required_evidence_ids=required_ids,
        )
