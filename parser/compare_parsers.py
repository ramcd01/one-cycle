import argparse
import json
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any


# ============================================================
# Windows 콘솔 UTF-8 출력 설정
# ============================================================
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(
        encoding="utf-8",
        errors="replace",
    )

if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(
        encoding="utf-8",
        errors="replace",
    )


# ============================================================
# JSON 로드
# ============================================================
def load_json(
    path: str,
) -> dict[str, Any]:

    file_path = Path(
        path
    )

    if not file_path.exists():
        raise FileNotFoundError(
            f"JSON 파일을 찾을 수 없습니다: "
            f"{file_path}"
        )

    with file_path.open(
        "r",
        encoding="utf-8",
    ) as file:

        return json.load(
            file
        )


# ============================================================
# 텍스트 정규화
# ============================================================
def normalize_text(
    text: str,
) -> str:
    """
    비교용 텍스트 정규화.

    - 줄바꿈
    - 탭
    - 연속 공백

    을 하나의 공백으로 통일합니다.
    """

    if text is None:
        return ""

    text = str(
        text
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


# ============================================================
# Table 추출
# ============================================================
def get_tables(
    document: dict,
) -> list[dict]:
    """
    sections 내부의 table block을
    문서 순서대로 반환합니다.
    """

    tables = []

    for section in document.get(
        "sections",
        [],
    ):

        for block in section.get(
            "blocks",
            [],
        ):

            if block.get(
                "type"
            ) == "table":

                tables.append(
                    block
                )

    return tables


# ============================================================
# Cell 구조 키
# ============================================================
def cell_key(
    cell: dict,
) -> tuple:
    """
    Cell 구조 식별용 키.

    row
    col
    row_span
    col_span
    """

    return (
        cell.get(
            "row"
        ),
        cell.get(
            "col"
        ),
        cell.get(
            "row_span"
        ),
        cell.get(
            "col_span"
        ),
    )


# ============================================================
# 첫 불일치 위치 찾기
# ============================================================
def find_first_difference(
    text1: str,
    text2: str,
) -> int:
    """
    두 문자열이 처음 달라지는 위치를 반환합니다.

    완전히 동일하면 -1.
    """

    min_length = min(
        len(
            text1
        ),
        len(
            text2
        ),
    )

    for index in range(
        min_length
    ):

        if (
            text1[
                index
            ]
            !=
            text2[
                index
            ]
        ):

            return index

    if (
        len(
            text1
        )
        !=
        len(
            text2
        )
    ):

        return min_length

    return -1


# ============================================================
# 특정 위치 주변 문맥
# ============================================================
def get_context(
    text: str,
    position: int,
    context_size: int = 150,
) -> str:
    """
    특정 위치를 기준으로
    앞뒤 문맥을 반환합니다.
    """

    start = max(
        0,
        position
        -
        context_size,
    )

    end = min(
        len(
            text
        ),
        position
        +
        context_size,
    )

    return text[
        start:end
    ]


# ============================================================
# 상세 문자열 차이 분석
# ============================================================
def analyze_difference(
    hwp_text: str,
    hwpx_text: str,
) -> dict:
    """
    SequenceMatcher를 사용하여
    두 문자열의 차이 구간을 분석합니다.
    """

    matcher = SequenceMatcher(
        None,
        hwp_text,
        hwpx_text,
        autojunk=False,
    )

    differences = []

    for (
        tag,
        i1,
        i2,
        j1,
        j2,
    ) in matcher.get_opcodes():

        if tag == "equal":
            continue

        differences.append(
            {
                "type":
                    tag,

                "hwp_start":
                    i1,

                "hwp_end":
                    i2,

                "hwpx_start":
                    j1,

                "hwpx_end":
                    j2,

                "hwp_text":
                    hwp_text[
                        i1:i2
                    ],

                "hwpx_text":
                    hwpx_text[
                        j1:j2
                    ],
            }
        )

    return {
        "difference_count":
            len(
                differences
            ),

        "differences":
            differences,
    }


# ============================================================
# Cell 전체 텍스트 차이 출력
# ============================================================
def print_difference_detail(
    hwp_text: str,
    hwpx_text: str,
    max_differences: int = 5,
) -> None:
    """
    Cell 전체 텍스트의
    불일치 상세 내용을 출력합니다.
    """

    first_difference = (
        find_first_difference(
            hwp_text,
            hwpx_text,
        )
    )

    print(
        "첫 불일치 위치:",
        first_difference,
    )

    if first_difference >= 0:

        print()

        print(
            "[첫 불일치 주변 HWP]"
        )

        print(
            get_context(
                hwp_text,
                first_difference,
            )
        )

        print()

        print(
            "[첫 불일치 주변 HWPX]"
        )

        print(
            get_context(
                hwpx_text,
                first_difference,
            )
        )

    analysis = (
        analyze_difference(
            hwp_text,
            hwpx_text,
        )
    )

    print()

    print(
        "전체 차이 구간 수:",
        analysis[
            "difference_count"
        ],
    )

    print()

    for (
        index,
        difference,
    ) in enumerate(
        analysis[
            "differences"
        ][
            :max_differences
        ],
        start=1,
    ):

        print(
            f"[차이 구간 {index}]"
        )

        print(
            "유형:",
            difference[
                "type"
            ],
        )

        print(
            "HWP 위치:",
            f"{difference['hwp_start']}"
            f"~"
            f"{difference['hwp_end']}",
        )

        print(
            "HWPX 위치:",
            f"{difference['hwpx_start']}"
            f"~"
            f"{difference['hwpx_end']}",
        )

        hwp_diff = (
            difference[
                "hwp_text"
            ]
        )

        hwpx_diff = (
            difference[
                "hwpx_text"
            ]
        )

        print(
            "HWP 차이 텍스트:",
            repr(
                hwp_diff[
                    :500
                ]
            ),
        )

        print(
            "HWPX 차이 텍스트:",
            repr(
                hwpx_diff[
                    :500
                ]
            ),
        )

        print()


# ============================================================
# Cell Paragraph 텍스트 추출
# ============================================================
def get_cell_paragraph_texts(
    cell: dict,
) -> list[str]:
    """
    Cell의 paragraphs 배열에서
    실제 텍스트만 순서대로 추출합니다.

    paragraph_index 자체는 비교하지 않습니다.

    이유:
    HWP/HWPX에서 빈 Paragraph를
    서로 다르게 보존할 가능성이 있기 때문입니다.
    """

    paragraphs = cell.get(
        "paragraphs",
        [],
    )

    result = []

    for paragraph in paragraphs:

        text = normalize_text(
            paragraph.get(
                "text",
                "",
            )
        )

        if not text:
            continue

        result.append(
            text
        )

    return result


# ============================================================
# Cell Paragraph 비교
# ============================================================
def compare_paragraphs(
    hwp_cell: dict,
    hwpx_cell: dict,
) -> dict:
    """
    동일 Cell 내부의 Paragraph 배열을 비교합니다.

    비교 기준:

    1. Paragraph 개수
    2. 등장 순서
    3. 정규화된 Paragraph 텍스트

    paragraph_index 숫자는 직접 비교하지 않습니다.
    """

    hwp_paragraphs = (
        get_cell_paragraph_texts(
            hwp_cell
        )
    )

    hwpx_paragraphs = (
        get_cell_paragraph_texts(
            hwpx_cell
        )
    )

    hwp_count = len(
        hwp_paragraphs
    )

    hwpx_count = len(
        hwpx_paragraphs
    )

    max_count = max(
        hwp_count,
        hwpx_count,
    )

    matched = 0

    mismatches = []

    for index in range(
        max_count
    ):

        hwp_text = (
            hwp_paragraphs[
                index
            ]
            if index
            <
            hwp_count
            else None
        )

        hwpx_text = (
            hwpx_paragraphs[
                index
            ]
            if index
            <
            hwpx_count
            else None
        )

        if (
            hwp_text
            is not None
            and
            hwpx_text
            is not None
            and
            hwp_text
            ==
            hwpx_text
        ):

            matched += 1

            continue

        mismatches.append(
            {
                "paragraph_order":
                    index,

                "hwp_text":
                    hwp_text,

                "hwpx_text":
                    hwpx_text,
            }
        )

    return {
        "hwp_count":
            hwp_count,

        "hwpx_count":
            hwpx_count,

        "count_match":
            hwp_count
            ==
            hwpx_count,

        "matched":
            matched,

        "mismatch_count":
            len(
                mismatches
            ),

        "mismatches":
            mismatches,
    }


# ============================================================
# 전체 문서 비교
# ============================================================
def compare_documents(
    hwp: dict,
    hwpx: dict,
) -> None:

    hwp_tables = (
        get_tables(
            hwp
        )
    )

    hwpx_tables = (
        get_tables(
            hwpx
        )
    )

    print()

    print(
        "=" * 100
    )

    print(
        "HWP / HWPX 공통 JSON 비교"
    )

    print(
        "=" * 100
    )

    print(
        f"HWP Table 수  : "
        f"{len(hwp_tables)}"
    )

    print(
        f"HWPX Table 수 : "
        f"{len(hwpx_tables)}"
    )

    if (
        len(
            hwp_tables
        )
        !=
        len(
            hwpx_tables
        )
    ):

        print(
            "[WARN] Table 개수가 다릅니다."
        )

    # ========================================================
    # Cell 전체 통계
    # ========================================================
    total_cells = 0

    structure_match = 0

    exact_text_match = 0

    text_mismatch = 0

    mismatch_cells = []

    # ========================================================
    # Paragraph 통계
    # ========================================================
    paragraph_cells = 0

    paragraph_count_match = 0

    paragraph_full_match = 0

    paragraph_mismatch_cells = 0

    paragraph_mismatch_summary = []

    table_count = min(
        len(
            hwp_tables
        ),
        len(
            hwpx_tables
        ),
    )

    # ========================================================
    # Table 순회
    # ========================================================
    for table_index in range(
        table_count
    ):

        hwp_table = (
            hwp_tables[
                table_index
            ]
        )

        hwpx_table = (
            hwpx_tables[
                table_index
            ]
        )

        print()

        print(
            "-" * 100
        )

        print(
            f"TABLE {table_index}"
        )

        print(
            "HWP  : "
            f"{hwp_table.get('row_count')}"
            " × "
            f"{hwp_table.get('col_count')}"
        )

        print(
            "HWPX : "
            f"{hwpx_table.get('row_count')}"
            " × "
            f"{hwpx_table.get('col_count')}"
        )

        # ====================================================
        # Cell map 생성
        # ====================================================
        hwp_cells = {
            cell_key(
                cell
            ):
                cell

            for cell
            in hwp_table.get(
                "cells",
                [],
            )
        }

        hwpx_cells = {
            cell_key(
                cell
            ):
                cell

            for cell
            in hwpx_table.get(
                "cells",
                [],
            )
        }

        all_keys = sorted(
            set(
                hwp_cells.keys()
            )
            |
            set(
                hwpx_cells.keys()
            )
        )

        # ====================================================
        # Cell 순회
        # ====================================================
        for key in all_keys:

            total_cells += 1

            hwp_cell = (
                hwp_cells.get(
                    key
                )
            )

            hwpx_cell = (
                hwpx_cells.get(
                    key
                )
            )

            # =================================================
            # Cell 구조 불일치
            # =================================================
            if (
                hwp_cell
                is None
                or
                hwpx_cell
                is None
            ):

                print()

                print(
                    "[STRUCTURE MISMATCH]"
                )

                print(
                    "Table:",
                    table_index,
                )

                print(
                    "Cell:",
                    key,
                )

                if hwp_cell is None:

                    print(
                        "HWP에 없음"
                    )

                if hwpx_cell is None:

                    print(
                        "HWPX에 없음"
                    )

                continue

            structure_match += 1

            # =================================================
            # Cell 전체 Text 정규화
            # =================================================
            hwp_text = normalize_text(
                hwp_cell.get(
                    "text",
                    "",
                )
            )

            hwpx_text = normalize_text(
                hwpx_cell.get(
                    "text",
                    "",
                )
            )

            # =================================================
            # Paragraph 비교
            # =================================================
            paragraph_result = (
                compare_paragraphs(
                    hwp_cell,
                    hwpx_cell,
                )
            )

            paragraph_cells += 1

            if paragraph_result[
                "count_match"
            ]:

                paragraph_count_match += 1

            if (
                paragraph_result[
                    "mismatch_count"
                ]
                ==
                0
            ):

                paragraph_full_match += 1

            else:

                paragraph_mismatch_cells += 1

                paragraph_mismatch_summary.append(
                    {
                        "table_index":
                            table_index,

                        "cell":
                            key,

                        "hwp_count":
                            paragraph_result[
                                "hwp_count"
                            ],

                        "hwpx_count":
                            paragraph_result[
                                "hwpx_count"
                            ],

                        "mismatch_count":
                            paragraph_result[
                                "mismatch_count"
                            ],
                    }
                )

                print()

                print(
                    "=" * 100
                )

                print(
                    "[PARAGRAPH MISMATCH]"
                )

                print(
                    "Table:",
                    table_index,
                )

                print(
                    "Cell:",
                    key,
                )

                print(
                    "HWP Paragraph 수:",
                    paragraph_result[
                        "hwp_count"
                    ],
                )

                print(
                    "HWPX Paragraph 수:",
                    paragraph_result[
                        "hwpx_count"
                    ],
                )

                print(
                    "Paragraph 개수 일치:",
                    paragraph_result[
                        "count_match"
                    ],
                )

                print(
                    "일치 Paragraph:",
                    paragraph_result[
                        "matched"
                    ],
                )

                print(
                    "불일치 Paragraph:",
                    paragraph_result[
                        "mismatch_count"
                    ],
                )

                # 최대 10개만 출력
                for mismatch in (
                    paragraph_result[
                        "mismatches"
                    ][
                        :10
                    ]
                ):

                    print()

                    print(
                        "[Paragraph Order]",
                        mismatch[
                            "paragraph_order"
                        ],
                    )

                    hwp_para_text = (
                        mismatch[
                            "hwp_text"
                        ]
                        or
                        ""
                    )

                    hwpx_para_text = (
                        mismatch[
                            "hwpx_text"
                        ]
                        or
                        ""
                    )

                    print(
                        "HWP :",
                        repr(
                            hwp_para_text[
                                :300
                            ]
                        ),
                    )

                    print(
                        "HWPX:",
                        repr(
                            hwpx_para_text[
                                :300
                            ]
                        ),
                    )

            # =================================================
            # Cell 전체 Text 비교
            # =================================================
            if (
                hwp_text
                ==
                hwpx_text
            ):

                exact_text_match += 1

                continue

            text_mismatch += 1

            mismatch_cells.append(
                {
                    "table_index":
                        table_index,

                    "cell":
                        key,

                    "hwp_length":
                        len(
                            hwp_text
                        ),

                    "hwpx_length":
                        len(
                            hwpx_text
                        ),
                }
            )

            print()

            print(
                "=" * 100
            )

            print(
                "[TEXT MISMATCH]"
            )

            print(
                "Table:",
                table_index,
            )

            print(
                "Cell:",
                key,
            )

            print(
                "HWP 길이 :",
                len(
                    hwp_text
                ),
            )

            print(
                "HWPX 길이:",
                len(
                    hwpx_text
                ),
            )

            print(
                "길이 차이:",
                len(
                    hwp_text
                )
                -
                len(
                    hwpx_text
                ),
            )

            print()

            print_difference_detail(
                hwp_text,
                hwpx_text,
                max_differences=5,
            )

    # ========================================================
    # Cell 비교 결과
    # ========================================================
    print()

    print(
        "=" * 100
    )

    print(
        "비교 결과"
    )

    print(
        "=" * 100
    )

    print(
        "전체 비교 Cell:",
        total_cells,
    )

    print(
        "구조 일치 Cell:",
        structure_match,
    )

    print(
        "텍스트 완전 일치:",
        exact_text_match,
    )

    print(
        "텍스트 불일치:",
        text_mismatch,
    )

    if total_cells > 0:

        structure_ratio = (
            structure_match
            /
            total_cells
            *
            100
        )

        print(
            "구조 일치율:",
            f"{structure_ratio:.2f}%",
        )

    if structure_match > 0:

        text_ratio = (
            exact_text_match
            /
            structure_match
            *
            100
        )

        print(
            "텍스트 완전 일치율:",
            f"{text_ratio:.2f}%",
        )

    # ========================================================
    # Paragraph 비교 결과
    # ========================================================
    print()

    print(
        "=" * 100
    )

    print(
        "Paragraph 비교 결과"
    )

    print(
        "=" * 100
    )

    print(
        "Paragraph 비교 Cell:",
        paragraph_cells,
    )

    print(
        "Paragraph 개수 일치 Cell:",
        paragraph_count_match,
    )

    print(
        "Paragraph 완전 일치 Cell:",
        paragraph_full_match,
    )

    print(
        "Paragraph 불일치 Cell:",
        paragraph_mismatch_cells,
    )

    if paragraph_cells > 0:

        paragraph_count_ratio = (
            paragraph_count_match
            /
            paragraph_cells
            *
            100
        )

        paragraph_full_ratio = (
            paragraph_full_match
            /
            paragraph_cells
            *
            100
        )

        print(
            "Paragraph 개수 일치율:",
            f"{paragraph_count_ratio:.2f}%",
        )

        print(
            "Paragraph 완전 일치율:",
            f"{paragraph_full_ratio:.2f}%",
        )

    # ========================================================
    # Text 불일치 Cell 요약
    # ========================================================
    if mismatch_cells:

        print()

        print(
            "=" * 100
        )

        print(
            "텍스트 불일치 Cell 요약"
        )

        print(
            "=" * 100
        )

        for item in mismatch_cells:

            print(
                f"Table={item['table_index']} "
                f"Cell={item['cell']} "
                f"HWP={item['hwp_length']} "
                f"HWPX={item['hwpx_length']} "
                f"차이="
                f"{item['hwp_length'] - item['hwpx_length']}"
            )

    # ========================================================
    # Paragraph 불일치 Cell 요약
    # ========================================================
    if paragraph_mismatch_summary:

        print()

        print(
            "=" * 100
        )

        print(
            "Paragraph 불일치 Cell 요약"
        )

        print(
            "=" * 100
        )

        for item in paragraph_mismatch_summary:

            print(
                f"Table={item['table_index']} "
                f"Cell={item['cell']} "
                f"HWP Paragraph={item['hwp_count']} "
                f"HWPX Paragraph={item['hwpx_count']} "
                f"불일치={item['mismatch_count']}"
            )


# ============================================================
# CLI
# ============================================================
def main():

    parser = argparse.ArgumentParser(
        description=(
            "HWP와 HWPX에서 생성한 "
            "공통 JSON의 Table / Cell / Text / "
            "Paragraph 구조를 상세 비교합니다."
        )
    )

    parser.add_argument(
        "--hwp",
        required=True,
        help=(
            "HWP Common JSON 경로"
        ),
    )

    parser.add_argument(
        "--hwpx",
        required=True,
        help=(
            "HWPX Common JSON 경로"
        ),
    )

    args = parser.parse_args()

    hwp = load_json(
        args.hwp
    )

    hwpx = load_json(
        args.hwpx
    )

    compare_documents(
        hwp,
        hwpx,
    )


# ============================================================
# Entry Point
# ============================================================
if __name__ == "__main__":
    main()