#!/usr/bin/env python3
"""의미 기반 구조화 2단계.

입력:
- *_step1-3_hierarchy.json

출력:
1. *_step2-1_normalized_titles.json
   - 제목 정규화 결과

2. *_step2-2_domain_matches.json
   - 도메인 매칭 결과

3. *_step2-3_domain_tagged.json
   - 도메인 태그를 추가한 원본 계층 결과
   - 아직 계층 재배치는 수행하지 않음

4. *_step2-4_hierarchy_conflicts.json
   - 부모/자식 도메인과 다음 Level 1을 비교한
     계층 오류 후보

5. *_step2-5_domain_repaired.json
   - 안전 조건을 만족하는 경우에 한해
     연속된 Section 묶음을 다음 Level 1 아래로 재배치한 결과

재배치 원칙:
- domain 하나만 보고 무조건 이동하지 않는다.
- 다음 Level 1이 비어 있어야 한다.
- 현재 부모의 자식 중 최소 2개 이상이
  '현재 부모와 domain 불일치 + 다음 부모와 domain 일치'
  조건을 만족해야 한다.
- 충돌 Section들이 현재 부모 children의 연속된 마지막 구간이어야 한다.
- 같은 원본 컨테이너(origin_path)에 속한 바로 앞 Section까지
  하나의 연속 묶음으로 판단한다.
- 원본 내용, source, section_id는 변경하지 않는다.
- 애매한 경우 자동 이동하지 않고 원래 계층을 유지한다.
"""

from __future__ import annotations

import copy
import json
import os
import re
from collections import defaultdict
from typing import Any, Iterator

from tkinter import Tk, messagebox
from tkinter.filedialog import askopenfilename


# ===========================================================================
# 도메인 규칙
# ===========================================================================

DOMAIN_RULES: list[dict[str, Any]] = [
    {
        "category": "supply",
        "topic": "supply_target",
        "priority": 100,
        "keywords": [
            "공급대상",
            "공급내역",
            "공급세대",
            "공급호수",
            "공급주택",
            "주택공급내역",
            "주택형별공급",
            "공급세대수",
        ],
    },
    {
        "category": "supply",
        "topic": "supply_scale",
        "priority": 99,
        "keywords": [
            "공급규모",
            "건설규모",
            "주택규모",
            "사업규모",
        ],
    },
    {
        "category": "price",
        "topic": "housing_price",
        "priority": 98,
        "keywords": [
            "주택분양가격",
            "분양가격",
            "공급금액",
            "분양금액",
            "주택가격",
            "분양대금",
            "공급가격",
        ],
    },
    {
        "category": "option",
        "topic": "balcony_extension",
        "priority": 97,
        "keywords": [
            "발코니확장",
            "발코니확장금액",
            "확장비용",
            "확장공사",
        ],
    },
    {
        "category": "option",
        "topic": "additional_options",
        "priority": 96,
        "keywords": [
            "추가선택품목",
            "선택품목",
            "유상옵션",
            "공간선택",
            "선택옵션",
            "마이너스옵션",
            "플러스옵션",
        ],
    },
    {
        "category": "eligibility",
        "topic": "application_eligibility",
        "priority": 95,
        "keywords": [
            "신청자격",
            "청약자격",
            "입주자격",
            "자격요건",
            "신청대상",
            "공급신청자격",
            "입주자격요건",
        ],
    },
    {
        "category": "schedule",
        "topic": "application_schedule",
        "priority": 94,
        "keywords": [
            "신청일정",
            "청약일정",
            "모집일정",
            "접수일정",
            "일정및장소",
            "신청및접수",
            "신청장소",
        ],
    },
    {
        "category": "schedule",
        "topic": "move_in_schedule",
        "priority": 93,
        "keywords": [
            "입주예정",
            "입주일정",
            "입주기간",
            "입주시기",
            "입주지정기간",
        ],
    },
    {
        "category": "contract",
        "topic": "contract_process",
        "priority": 92,
        "keywords": [
            "계약체결",
            "계약절차",
            "계약일정",
            "계약안내",
            "동호지정",
            "동호수지정",
            "계약장소",
        ],
    },
    {
        "category": "documents",
        "topic": "required_documents",
        "priority": 91,
        "keywords": [
            "구비서류",
            "제출서류",
            "신청서류",
            "계약서류",
            "서류제출",
            "필요서류",
            "증빙서류",
        ],
    },
    {
        "category": "payment",
        "topic": "payment_schedule",
        "priority": 90,
        "keywords": [
            "입주금납부",
            "대금납부",
            "납부일정",
            "납부방법",
            "계약금",
            "중도금",
            "잔금",
            "분양대금납부",
        ],
    },
    {
        "category": "restriction",
        "topic": "restrictions_and_penalties",
        "priority": 89,
        "keywords": [
            "재당첨제한",
            "전매제한",
            "거주의무",
            "벌칙",
            "부적격",
            "당첨취소",
            "제한사항",
        ],
    },
    {
        "category": "notice",
        "topic": "important_notices",
        "priority": 88,
        "keywords": [
            "유의사항",
            "주의사항",
            "확인사항",
            "안내사항",
            "기타사항",
        ],
    },
    {
        "category": "location",
        "topic": "complex_and_district",
        "priority": 87,
        "keywords": [
            "단지여건",
            "지구여건",
            "입지여건",
            "단지환경",
            "사업지구",
            "주택위치",
            "공급위치",
            "교통여건",
        ],
    },
    {
        "category": "management",
        "topic": "management_and_occupancy",
        "priority": 86,
        "keywords": [
            "주택관리",
            "관리사항",
            "입주관리",
            "관리비",
        ],
    },
    {
        "category": "organization",
        "topic": "project_parties",
        "priority": 85,
        "keywords": [
            "사업주체",
            "시공업체",
            "시공사",
            "감리회사",
            "사업시행자",
            "사업주체및시공업체",
        ],
    },
    {
        "category": "contact",
        "topic": "contact_information",
        "priority": 84,
        "keywords": [
            "문의처",
            "연락처",
            "전화번호",
            "홈페이지",
            "견본주택",
            "주택전시관",
            "사이버모델하우스",
        ],
    },
    {
        "category": "overview",
        "topic": "notice_overview",
        "priority": 50,
        "keywords": [
            "모집공고",
            "공고개요",
            "공고내용",
            "주요내용",
            "개요",
        ],
    },
]


# 여러 의미가 함께 포함된 상위 제목용 규칙
COMPOSITE_RULES: list[dict[str, Any]] = [
    {
        "category": "supply",
        "topic": "supply_price_overview",
        "required_keywords": [
            "공급",
            "가격",
        ],
        "matched_keyword": "공급+가격",
    },
    {
        "category": "application",
        "topic": "eligibility_and_application_overview",
        "required_keywords": [
            "신청자격",
            "확인사항",
        ],
        "matched_keyword": "신청자격+확인사항",
    },
    {
        "category": "contract",
        "topic": "document_and_contract_overview",
        "required_keywords": [
            "서류",
            "계약",
        ],
        "matched_keyword": "서류+계약",
    },
]


# ===========================================================================
# 2-1 제목 정규화
# ===========================================================================

def normalize_title(title: Any) -> str:
    """도메인 매칭용 제목 문자열을 생성한다."""

    text = "" if title is None else str(title)

    text = (
        text.replace("\n", " ")
        .replace("\r", " ")
    )

    patterns = [
        r"^\s*제\s*\d+\s*[장절편부]\s*",
        r"^\s*[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩⅪⅫ]+[.．]?\s*",
        r"^\s*\d+(?:\.\d+)+[.)]?\s*",
        r"^\s*\d+[.．)]\s*",
        r"^\s*\(\d+\)\s*",
        r"^\s*[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮]\s*",
        r"^\s*[가-하][.．)]\s*",
    ]

    for pattern in patterns:
        new_text = re.sub(
            pattern,
            "",
            text,
        )

        if new_text != text:
            text = new_text
            break

    # 괄호 문자는 제거하고 내부 텍스트는 유지
    text = re.sub(
        r"[\[\]{}()<>〈〉《》「」『』【】]",
        " ",
        text,
    )

    text = (
        text.replace("․", " ")
        .replace("·", " ")
        .replace("ㆍ", " ")
    )

    text = re.sub(
        r"[,:;|/\\]+",
        " ",
        text,
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    ).strip()

    return text


def compact_text(text: str) -> str:
    """키워드 비교용 문자열."""

    return re.sub(
        r"[^0-9A-Za-z가-힣]",
        "",
        text,
    ).lower()


def walk_sections(
    sections: list[dict[str, Any]],
    path: list[str] | None = None,
) -> Iterator[
    tuple[
        dict[str, Any],
        list[str],
    ]
]:
    """모든 Section을 계층 순서대로 순회."""

    path = path or []

    for section in sections:
        title = str(
            section.get("title") or ""
        )

        current_path = path + [title]

        yield section, current_path

        children = section.get("children") or []

        if isinstance(children, list):
            yield from walk_sections(
                children,
                current_path,
            )


# ===========================================================================
# 2-2 도메인 매핑
# ===========================================================================

def match_domain(
    normalized_title: str,
) -> dict[str, Any] | None:
    """정규화 제목을 도메인 규칙과 비교."""

    compact = compact_text(
        normalized_title
    )

    if not compact:
        return None

    # -----------------------------------------------------------------------
    # 복합 규칙
    # -----------------------------------------------------------------------

    for rule in COMPOSITE_RULES:
        required_keywords = [
            compact_text(keyword)
            for keyword in rule[
                "required_keywords"
            ]
        ]

        if all(
            keyword in compact
            for keyword in required_keywords
        ):
            return {
                "category": rule["category"],
                "topic": rule["topic"],
                "matched_keyword": (
                    rule["matched_keyword"]
                ),
                "match_type": "composite",
            }

    # -----------------------------------------------------------------------
    # 일반 키워드
    # -----------------------------------------------------------------------

    candidates: list[
        tuple[
            int,
            int,
            dict[str, Any],
            str,
        ]
    ] = []

    for rule in DOMAIN_RULES:
        for keyword in rule["keywords"]:
            normalized_keyword = compact_text(
                keyword
            )

            if (
                normalized_keyword
                and normalized_keyword in compact
            ):
                candidates.append(
                    (
                        rule["priority"],
                        len(normalized_keyword),
                        rule,
                        keyword,
                    )
                )

    if not candidates:
        return None

    candidates.sort(
        key=lambda value: (
            value[0],
            value[1],
        ),
        reverse=True,
    )

    (
        _,
        _,
        selected_rule,
        selected_keyword,
    ) = candidates[0]

    return {
        "category": (
            selected_rule["category"]
        ),
        "topic": (
            selected_rule["topic"]
        ),
        "matched_keyword": (
            selected_keyword
        ),
        "match_type": "keyword",
    }


# ===========================================================================
# 공통 보조 함수
# ===========================================================================

def get_domain_category(
    section: dict[str, Any],
) -> str | None:
    """Section의 domain category 반환."""

    domain = section.get("domain")

    if not isinstance(
        domain,
        dict,
    ):
        return None

    category = domain.get("category")

    if not category:
        return None

    return str(category)


def get_origin_path(
    section: dict[str, Any],
) -> list[str]:
    """Section 제목의 원본 origin_path 반환."""

    source = section.get("source")

    if not isinstance(
        source,
        dict,
    ):
        return []

    origin_path = source.get(
        "origin_path"
    )

    if not isinstance(
        origin_path,
        list,
    ):
        return []

    return [
        str(value)
        for value in origin_path
    ]


def get_container_key(
    section: dict[str, Any],
) -> tuple[str, ...] | None:
    """같은 원본 레이아웃 컨테이너 여부를 판단할 key.

    예:
    [
        "block:7",
        "cell:0,0",
        "block:12"
    ]

    이 경우 마지막 block 번호는 컨테이너 내부 위치이므로 제거하고

    (
        "block:7",
        "cell:0,0"
    )

    를 같은 컨테이너 key로 사용한다.
    """

    origin_path = get_origin_path(
        section
    )

    if len(origin_path) < 2:
        return None

    return tuple(
        origin_path[:-1]
    )


def is_empty_section(
    section: dict[str, Any],
) -> bool:
    """Section 자체에 내용이나 자식이 없는지 검사."""

    contents = (
        section.get("contents")
        or []
    )

    children = (
        section.get("children")
        or []
    )

    return (
        len(contents) == 0
        and len(children) == 0
    )


# ===========================================================================
# 2-4 계층 충돌 검사
# ===========================================================================

def detect_hierarchy_conflicts(
    sections: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Level 1 간 계층 충돌 후보 탐지.

    조건:
    - child domain != current parent domain
    - child domain == next Level 1 domain

    자동 이동은 하지 않는다.
    """

    conflicts: list[
        dict[str, Any]
    ] = []

    if len(sections) < 2:
        return conflicts

    for parent_index in range(
        len(sections) - 1
    ):
        current_parent = (
            sections[parent_index]
        )

        next_parent = (
            sections[
                parent_index + 1
            ]
        )

        current_category = (
            get_domain_category(
                current_parent
            )
        )

        next_category = (
            get_domain_category(
                next_parent
            )
        )

        if (
            current_category is None
            or next_category is None
        ):
            continue

        children = (
            current_parent.get(
                "children"
            )
            or []
        )

        if not isinstance(
            children,
            list,
        ):
            continue

        for (
            child_index,
            child,
        ) in enumerate(children):
            if not isinstance(
                child,
                dict,
            ):
                continue

            child_category = (
                get_domain_category(
                    child
                )
            )

            if child_category is None:
                continue

            if (
                child_category
                != current_category
                and child_category
                == next_category
            ):
                conflicts.append(
                    {
                        "type": (
                            "possible_wrong_parent"
                        ),
                        "severity": (
                            "warning"
                        ),
                        "parent_index": (
                            parent_index
                        ),
                        "child_index": (
                            child_index
                        ),
                        "child_section_id": (
                            child.get(
                                "section_id"
                            )
                        ),
                        "child_title": (
                            child.get(
                                "title"
                            )
                        ),
                        "child_domain": (
                            copy.deepcopy(
                                child.get(
                                    "domain"
                                )
                            )
                        ),
                        "child_origin_path": (
                            get_origin_path(
                                child
                            )
                        ),
                        "current_parent": {
                            "section_id": (
                                current_parent.get(
                                    "section_id"
                                )
                            ),
                            "title": (
                                current_parent.get(
                                    "title"
                                )
                            ),
                            "domain": (
                                copy.deepcopy(
                                    current_parent.get(
                                        "domain"
                                    )
                                )
                            ),
                        },
                        "suggested_parent": {
                            "section_id": (
                                next_parent.get(
                                    "section_id"
                                )
                            ),
                            "title": (
                                next_parent.get(
                                    "title"
                                )
                            ),
                            "domain": (
                                copy.deepcopy(
                                    next_parent.get(
                                        "domain"
                                    )
                                )
                            ),
                            "empty_before_repair": (
                                is_empty_section(
                                    next_parent
                                )
                            ),
                        },
                        "reason": (
                            "자식 Section의 domain "
                            "category가 현재 부모와 "
                            "다르고 바로 다음 Level 1 "
                            "Section의 category와 일치함"
                        ),
                        "action": (
                            "2-4에서는 자동 이동하지 않음. "
                            "2-5 안전 재배치 조건을 추가로 "
                            "검사함."
                        ),
                    }
                )

    return conflicts


def build_hierarchy_conflict_result(
    tagged: dict[str, Any],
) -> dict[str, Any]:
    """2-4 결과 JSON."""

    sections = tagged.get(
        "sections"
    )

    if not isinstance(
        sections,
        list,
    ):
        raise ValueError(
            "도메인 태깅 결과에 "
            "sections 배열이 없습니다."
        )

    conflicts = (
        detect_hierarchy_conflicts(
            sections
        )
    )

    return {
        "document": copy.deepcopy(
            tagged.get(
                "document",
                {},
            )
        ),
        "step": "2-4",
        "description": (
            "도메인 기반 부모-자식 "
            "계층 정합성 검사 결과"
        ),
        "policy": {
            "automatic_repair": False,
            "rule": (
                "child domain != "
                "current parent domain AND "
                "child domain == "
                "next top-level section domain"
            ),
            "note": (
                "2-4 결과는 오류 후보이며, "
                "2-5 단계에서 추가 안전 조건을 "
                "통과한 경우에만 자동 재배치한다."
            ),
        },
        "summary": {
            "conflict_count": (
                len(conflicts)
            ),
        },
        "conflicts": conflicts,
    }


# ===========================================================================
# 2-5 안전한 연속 Section 묶음 재배치
# ===========================================================================

def group_conflicts_by_parent_pair(
    conflicts: list[dict[str, Any]],
) -> dict[
    tuple[str, str],
    list[dict[str, Any]],
]:
    """현재 부모/추천 부모 조합별 충돌 그룹."""

    grouped: dict[
        tuple[str, str],
        list[dict[str, Any]],
    ] = defaultdict(list)

    for conflict in conflicts:
        current_parent = (
            conflict.get(
                "current_parent"
            )
            or {}
        )

        suggested_parent = (
            conflict.get(
                "suggested_parent"
            )
            or {}
        )

        current_id = str(
            current_parent.get(
                "section_id"
            )
            or ""
        )

        suggested_id = str(
            suggested_parent.get(
                "section_id"
            )
            or ""
        )

        if (
            current_id
            and suggested_id
        ):
            grouped[
                (
                    current_id,
                    suggested_id,
                )
            ].append(
                conflict
            )

    return grouped


def repair_contiguous_section_groups(
    tagged: dict[str, Any],
    conflicts: list[dict[str, Any]],
    min_strong_conflicts: int = 2,
) -> tuple[
    dict[str, Any],
    list[dict[str, Any]],
]:
    """안전 조건을 만족하는 연속 Section 묶음 재배치.

    현재 익산평화 케이스 예:

    Ⅱ 신청자격 및 확인사항
    ├─ 일정 및 장소
    ├─ 동호지정 세부일정 및 유의사항   <- strong conflict
    └─ 계약 시 구비서류               <- strong conflict

    Ⅲ 서류제출, 동호지정 및 계약체결 등
    └─ 비어 있음

    세 자식이 동일한 원본 컨테이너에 있고,
    충돌 2개가 마지막 연속 구간에 존재하며,
    다음 Level 1이 비어 있다면:

    Ⅱ 신청자격 및 확인사항

    Ⅲ 서류제출, 동호지정 및 계약체결 등
    ├─ 일정 및 장소
    ├─ 동호지정 세부일정 및 유의사항
    └─ 계약 시 구비서류

    로 보정한다.

    애매한 경우에는 이동하지 않는다.
    """

    repaired = copy.deepcopy(
        tagged
    )

    sections = repaired.get(
        "sections"
    )

    if not isinstance(
        sections,
        list,
    ):
        raise ValueError(
            "2-5 재배치 대상에 "
            "sections 배열이 없습니다."
        )

    repairs: list[
        dict[str, Any]
    ] = []

    grouped = (
        group_conflicts_by_parent_pair(
            conflicts
        )
    )

    # 인접 Level 1 쌍만 검사
    for parent_index in range(
        len(sections) - 1
    ):
        current_parent = (
            sections[parent_index]
        )

        next_parent = (
            sections[
                parent_index + 1
            ]
        )

        current_id = str(
            current_parent.get(
                "section_id"
            )
            or ""
        )

        next_id = str(
            next_parent.get(
                "section_id"
            )
            or ""
        )

        pair_conflicts = (
            grouped.get(
                (
                    current_id,
                    next_id,
                ),
                [],
            )
        )

        # ---------------------------------------------------------------
        # 조건 1
        # 최소 2개 이상의 명확한 충돌이 있어야 함
        # ---------------------------------------------------------------

        if (
            len(pair_conflicts)
            < min_strong_conflicts
        ):
            continue

        # ---------------------------------------------------------------
        # 조건 2
        # 다음 Level 1이 완전히 비어 있어야 함
        # ---------------------------------------------------------------

        if not is_empty_section(
            next_parent
        ):
            continue

        children = (
            current_parent.get(
                "children"
            )
            or []
        )

        if not isinstance(
            children,
            list,
        ):
            continue

        if not children:
            continue

        conflict_indices = sorted(
            {
                int(
                    conflict[
                        "child_index"
                    ]
                )
                for conflict
                in pair_conflicts
                if isinstance(
                    conflict.get(
                        "child_index"
                    ),
                    int,
                )
            }
        )

        if (
            len(conflict_indices)
            < min_strong_conflicts
        ):
            continue

        # ---------------------------------------------------------------
        # 조건 3
        # 강한 충돌들이 children 마지막 구간까지 이어져야 함
        #
        # 예:
        # idx 1, 2
        # children 길이 3
        #
        # 마지막 충돌 idx == 2 == len(children)-1
        # ---------------------------------------------------------------

        last_conflict_index = (
            conflict_indices[-1]
        )

        if (
            last_conflict_index
            != len(children) - 1
        ):
            continue

        first_conflict_index = (
            conflict_indices[0]
        )

        first_conflict_child = (
            children[
                first_conflict_index
            ]
        )

        common_container = (
            get_container_key(
                first_conflict_child
            )
        )

        if common_container is None:
            continue

        # ---------------------------------------------------------------
        # 조건 4
        # 강한 충돌들이 동일 원본 컨테이너에 있어야 함
        # ---------------------------------------------------------------

        all_conflicts_same_container = (
            all(
                get_container_key(
                    children[index]
                )
                == common_container
                for index in conflict_indices
            )
        )

        if not all_conflicts_same_container:
            continue

        # ---------------------------------------------------------------
        # 같은 컨테이너에 속한 바로 앞 Section까지 확장
        #
        # 익산평화에서는
        #
        # idx 0 일정 및 장소
        # idx 1 동호지정...
        # idx 2 계약 시 구비서류
        #
        # 모두 같은 block:7 내부이므로
        # idx 0까지 이동 범위 확장
        # ---------------------------------------------------------------

        move_start_index = (
            first_conflict_index
        )

        while (
            move_start_index > 0
        ):
            previous_child = (
                children[
                    move_start_index - 1
                ]
            )

            previous_container = (
                get_container_key(
                    previous_child
                )
            )

            if (
                previous_container
                != common_container
            ):
                break

            move_start_index -= 1

        move_candidates = (
            children[
                move_start_index:
            ]
        )

        # ---------------------------------------------------------------
        # 조건 5
        # 이동될 마지막 연속 구간 전체가 같은 컨테이너인지 확인
        # ---------------------------------------------------------------

        if not all(
            get_container_key(child)
            == common_container
            for child in move_candidates
        ):
            continue

        # ---------------------------------------------------------------
        # 안전 조건 통과
        # 실제 이동
        # ---------------------------------------------------------------

        remaining_children = (
            children[
                :move_start_index
            ]
        )

        moved_children = (
            move_candidates
        )

        current_parent[
            "children"
        ] = remaining_children

        next_parent[
            "children"
        ] = (
            moved_children
            + (
                next_parent.get(
                    "children"
                )
                or []
            )
        )

        repairs.append(
            {
                "type": (
                    "contiguous_section_group_repair"
                ),
                "current_parent": {
                    "section_id": (
                        current_parent.get(
                            "section_id"
                        )
                    ),
                    "title": (
                        current_parent.get(
                            "title"
                        )
                    ),
                    "domain": (
                        copy.deepcopy(
                            current_parent.get(
                                "domain"
                            )
                        )
                    ),
                },
                "new_parent": {
                    "section_id": (
                        next_parent.get(
                            "section_id"
                        )
                    ),
                    "title": (
                        next_parent.get(
                            "title"
                        )
                    ),
                    "domain": (
                        copy.deepcopy(
                            next_parent.get(
                                "domain"
                            )
                        )
                    ),
                },
                "strong_conflict_count": (
                    len(pair_conflicts)
                ),
                "move_start_index": (
                    move_start_index
                ),
                "source_container": list(
                    common_container
                ),
                "moved_sections": [
                    {
                        "section_id": (
                            child.get(
                                "section_id"
                            )
                        ),
                        "title": (
                            child.get(
                                "title"
                            )
                        ),
                        "domain": (
                            copy.deepcopy(
                                child.get(
                                    "domain"
                                )
                            )
                        ),
                        "origin_path": (
                            get_origin_path(
                                child
                            )
                        ),
                    }
                    for child
                    in moved_children
                ],
                "reason": (
                    "다음 Level 1이 비어 있고, "
                    "현재 부모의 마지막 연속 자식 구간에서 "
                    "최소 2개의 강한 domain 충돌이 발견되었으며, "
                    "해당 자식들이 동일한 원본 컨테이너에 "
                    "속해 있어 하나의 Section 묶음으로 재배치함"
                ),
            }
        )

    # ---------------------------------------------------------------
    # 재배치 후 다시 충돌 검사
    # ---------------------------------------------------------------

    remaining_conflicts = (
        detect_hierarchy_conflicts(
            sections
        )
    )

    repaired[
        "hierarchy_repair"
    ] = {
        "step": "2-5",
        "automatic_repair": True,
        "strategy": (
            "contiguous_tail_group_with_"
            "multiple_domain_conflicts"
        ),
        "safety_conditions": [
            (
                "현재 부모와 다음 Level 1이 "
                "문서상 인접해야 함"
            ),
            (
                "다음 Level 1의 contents와 "
                "children이 모두 비어 있어야 함"
            ),
            (
                "최소 2개의 자식이 현재 부모와 "
                "domain이 다르고 다음 부모와 "
                "domain이 일치해야 함"
            ),
            (
                "충돌 자식이 현재 children의 "
                "마지막 연속 구간에 있어야 함"
            ),
            (
                "이동 자식들이 동일 원본 "
                "origin_path 컨테이너에 속해야 함"
            ),
        ],
        "repair_count": (
            len(repairs)
        ),
        "repairs": repairs,
        "remaining_conflict_count": (
            len(
                remaining_conflicts
            )
        ),
        "remaining_conflicts": (
            remaining_conflicts
        ),
    }

    return (
        repaired,
        repairs,
    )


# ===========================================================================
# Step 2 전체 처리
# ===========================================================================

def build_step2_results(
    source: dict[str, Any],
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
]:
    """Step 2-1 ~ Step 2-5 결과 생성."""

    if not isinstance(
        source.get("sections"),
        list,
    ):
        raise ValueError(
            "1단계 계층 JSON이 아닙니다. "
            "최상위 sections 배열을 "
            "찾을 수 없습니다."
        )

    tagged = copy.deepcopy(
        source
    )

    title_records: list[
        dict[str, Any]
    ] = []

    match_records: list[
        dict[str, Any]
    ] = []

    unmatched_records: list[
        dict[str, Any]
    ] = []

    original_sections = list(
        walk_sections(
            source["sections"]
        )
    )

    tagged_sections = list(
        walk_sections(
            tagged["sections"]
        )
    )

    if (
        len(original_sections)
        != len(tagged_sections)
    ):
        raise ValueError(
            "원본 Section 수와 복사본 "
            "Section 수가 일치하지 않습니다."
        )

    # -----------------------------------------------------------------------
    # 2-1 / 2-2 / 2-3
    # -----------------------------------------------------------------------

    for (
        (
            original_section,
            section_path,
        ),
        (
            tagged_section,
            _,
        ),
    ) in zip(
        original_sections,
        tagged_sections,
    ):
        title = str(
            original_section.get(
                "title"
            )
            or ""
        )

        normalized = (
            normalize_title(
                title
            )
        )

        domain = (
            match_domain(
                normalized
            )
        )

        title_record = {
            "section_id": (
                original_section.get(
                    "section_id"
                )
            ),
            "level": (
                original_section.get(
                    "level"
                )
            ),
            "section_path": (
                section_path
            ),
            "original_title": (
                title
            ),
            "normalized_title": (
                normalized
            ),
        }

        title_records.append(
            title_record
        )

        tagged_section[
            "normalized_title"
        ] = normalized

        tagged_section[
            "domain"
        ] = None

        if domain is not None:
            final_domain = {
                "category": (
                    domain["category"]
                ),
                "topic": (
                    domain["topic"]
                ),
                "matched_keyword": (
                    domain[
                        "matched_keyword"
                    ]
                ),
            }

            tagged_section[
                "domain"
            ] = final_domain

            match_records.append(
                {
                    **title_record,
                    "domain": (
                        final_domain
                    ),
                    "match_type": (
                        domain[
                            "match_type"
                        ]
                    ),
                }
            )

        else:
            unmatched_records.append(
                {
                    **title_record,
                    "reason": (
                        "등록된 도메인 "
                        "키워드와 일치하지 않음"
                    ),
                }
            )

    # -----------------------------------------------------------------------
    # Step 2-1
    # -----------------------------------------------------------------------

    step2_1 = {
        "document": copy.deepcopy(
            source.get(
                "document",
                {},
            )
        ),
        "step": "2-1",
        "description": (
            "계층 제목 정규화 결과"
        ),
        "titles": title_records,
    }

    # -----------------------------------------------------------------------
    # Step 2-2
    # -----------------------------------------------------------------------

    step2_2 = {
        "document": copy.deepcopy(
            source.get(
                "document",
                {},
            )
        ),
        "step": "2-2",
        "description": (
            "도메인 규칙 매칭 결과"
        ),
        "summary": {
            "total_sections": (
                len(title_records)
            ),
            "matched_sections": (
                len(match_records)
            ),
            "unmatched_sections": (
                len(
                    unmatched_records
                )
            ),
        },
        "matches": match_records,
        "unmatched": (
            unmatched_records
        ),
    }

    # -----------------------------------------------------------------------
    # Step 2-3
    # -----------------------------------------------------------------------

    tagged[
        "domain_tagging_method"
    ] = {
        "step": "2-3",
        "target": (
            "section_title_only"
        ),
        "method": (
            "normalized_title_"
            "keyword_mapping"
        ),
        "content_inheritance": (
            "contents는 부모 section의 "
            "domain을 이후 chunk 생성 시 상속"
        ),
        "unmatched_policy": (
            "domain=null로 유지하고 "
            "domain_unresolved에 기록"
        ),
    }

    tagged[
        "domain_unresolved"
    ] = unmatched_records

    # -----------------------------------------------------------------------
    # Step 2-4
    # -----------------------------------------------------------------------

    step2_4 = (
        build_hierarchy_conflict_result(
            tagged
        )
    )

    tagged[
        "hierarchy_validation"
    ] = {
        "step": "2-4",
        "checked": True,
        "automatic_repair": False,
        "conflict_count": (
            step2_4[
                "summary"
            ][
                "conflict_count"
            ]
        ),
        "conflicts": copy.deepcopy(
            step2_4[
                "conflicts"
            ]
        ),
    }

    # -----------------------------------------------------------------------
    # Step 2-5
    # -----------------------------------------------------------------------

    (
        repaired,
        _repairs,
    ) = repair_contiguous_section_groups(
        tagged,
        step2_4[
            "conflicts"
        ],
        min_strong_conflicts=2,
    )

    return (
        step2_1,
        step2_2,
        tagged,
        step2_4,
        repaired,
    )


# ===========================================================================
# 파일 저장
# ===========================================================================

def save_json(
    path: str,
    data: dict[str, Any],
) -> None:
    """JSON 저장."""

    with open(
        path,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=2,
        )


def process(
    input_path: str,
    output_dir: str,
) -> tuple[
    str,
    str,
    str,
    str,
    str,
]:
    """Step 2 실행 및 저장."""

    with open(
        input_path,
        "r",
        encoding="utf-8",
    ) as file:
        source = json.load(
            file
        )

    (
        step2_1,
        step2_2,
        step2_3,
        step2_4,
        step2_5,
    ) = build_step2_results(
        source
    )

    os.makedirs(
        output_dir,
        exist_ok=True,
    )

    stem = os.path.splitext(
        os.path.basename(
            input_path
        )
    )[0]

    stem = re.sub(
        r"_step1-3_hierarchy$",
        "",
        stem,
    )

    path_21 = os.path.join(
        output_dir,
        (
            f"{stem}_step2-1_"
            "normalized_titles.json"
        ),
    )

    path_22 = os.path.join(
        output_dir,
        (
            f"{stem}_step2-2_"
            "domain_matches.json"
        ),
    )

    path_23 = os.path.join(
        output_dir,
        (
            f"{stem}_step2-3_"
            "domain_tagged.json"
        ),
    )

    path_24 = os.path.join(
        output_dir,
        (
            f"{stem}_step2-4_"
            "hierarchy_conflicts.json"
        ),
    )

    path_25 = os.path.join(
        output_dir,
        (
            f"{stem}_step2-5_"
            "domain_repaired.json"
        ),
    )

    save_json(
        path_21,
        step2_1,
    )

    save_json(
        path_22,
        step2_2,
    )

    save_json(
        path_23,
        step2_3,
    )

    save_json(
        path_24,
        step2_4,
    )

    save_json(
        path_25,
        step2_5,
    )

    return (
        path_21,
        path_22,
        path_23,
        path_24,
        path_25,
    )


# ===========================================================================
# 입력 파일 선택
# ===========================================================================

def select_input_json() -> str | None:
    """Step 1 최종 hierarchy JSON 선택."""

    root = Tk()

    root.withdraw()

    root.attributes(
        "-topmost",
        True,
    )

    selected = (
        askopenfilename(
            title=(
                "1단계 최종 계층 "
                "JSON 선택"
            ),
            filetypes=[
                (
                    "Step1 hierarchy JSON",
                    (
                        "*_step1-3_"
                        "hierarchy.json"
                    ),
                ),
                (
                    "JSON Files",
                    "*.json",
                ),
            ],
        )
    )

    root.destroy()

    return (
        selected
        or None
    )


# ===========================================================================
# 콘솔 출력
# ===========================================================================

def print_conflict_summary(
    step2_4_path: str,
) -> None:
    """2-4 충돌 결과 출력."""

    with open(
        step2_4_path,
        "r",
        encoding="utf-8",
    ) as file:
        result = json.load(
            file
        )

    conflicts = (
        result.get(
            "conflicts",
            [],
        )
    )

    print()
    print("-" * 72)
    print(
        f"계층 충돌 후보: "
        f"{len(conflicts)}개"
    )
    print("-" * 72)

    if not conflicts:
        print(
            "계층 충돌 후보가 "
            "발견되지 않았습니다."
        )

        return

    for (
        index,
        conflict,
    ) in enumerate(
        conflicts,
        start=1,
    ):
        current_parent = (
            conflict.get(
                "current_parent",
                {},
            )
        )

        suggested_parent = (
            conflict.get(
                "suggested_parent",
                {},
            )
        )

        print(
            f"[{index}] "
            f"{conflict.get('child_title')}"
        )

        print(
            "  현재 부모 : "
            f"{current_parent.get('title')}"
        )

        print(
            "  추천 후보 : "
            f"{suggested_parent.get('title')}"
        )

        print(
            "  자식 domain : "
            f"{conflict.get('child_domain')}"
        )

        print()


def print_repair_summary(
    step2_5_path: str,
) -> None:
    """2-5 자동 재배치 결과 출력."""

    with open(
        step2_5_path,
        "r",
        encoding="utf-8",
    ) as file:
        result = json.load(
            file
        )

    repair_info = (
        result.get(
            "hierarchy_repair",
            {},
        )
    )

    repairs = (
        repair_info.get(
            "repairs",
            [],
        )
    )

    print()
    print("-" * 72)
    print(
        f"계층 자동 재배치: "
        f"{len(repairs)}건"
    )
    print("-" * 72)

    if not repairs:
        print(
            "안전 조건을 만족하는 "
            "자동 재배치 대상이 없습니다."
        )

        return

    for (
        index,
        repair,
    ) in enumerate(
        repairs,
        start=1,
    ):
        current_parent = (
            repair.get(
                "current_parent",
                {},
            )
        )

        new_parent = (
            repair.get(
                "new_parent",
                {},
            )
        )

        moved_sections = (
            repair.get(
                "moved_sections",
                [],
            )
        )

        print(
            f"[{index}] "
            f"{current_parent.get('title')}"
            " → "
            f"{new_parent.get('title')}"
        )

        print(
            "  이동 Section:"
        )

        for section in moved_sections:
            print(
                "   - "
                f"{section.get('title')}"
            )

        print()


# ===========================================================================
# 실행
# ===========================================================================

def main() -> None:
    input_path = (
        select_input_json()
    )

    if not input_path:
        print(
            "JSON 파일을 "
            "선택하지 않았습니다."
        )
        return

    script_dir = (
        os.path.dirname(
            os.path.abspath(
                __file__
            )
        )
    )

    output_dir = (
        os.path.join(
            script_dir,
            "output",
        )
    )

    try:
        outputs = process(
            input_path,
            output_dir,
        )

    except (
        OSError,
        json.JSONDecodeError,
        ValueError,
        TypeError,
        KeyError,
        IndexError,
    ) as error:
        messagebox.showerror(
            "2단계 구조화 실패",
            str(error),
        )

        raise

    print()
    print("=" * 72)
    print(
        "2단계 도메인 태깅, "
        "계층 검사 및 재배치 완료"
    )
    print("=" * 72)

    for output in outputs:
        print(
            output
        )

    # 2-4
    print_conflict_summary(
        outputs[3]
    )

    # 2-5
    print_repair_summary(
        outputs[4]
    )

    messagebox.showinfo(
        "2단계 구조화 완료",
        (
            "2-1 ~ 2-5 결과를 "
            "생성했습니다.\n\n"
            + "\n".join(
                outputs
            )
            + "\n\n"
            + "다음 단계에서는 "
            "*_step2-5_domain_repaired.json을 "
            "사용하세요."
        ),
    )


if __name__ == "__main__":
    main()