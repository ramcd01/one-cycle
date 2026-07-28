import argparse
import copy
import json
import re
from pathlib import Path
from typing import Any


# ============================================================
# 검증된 Private Use Area 문자 매핑
# ============================================================
# 실제 원본 문서에서 기호가 확인된 경우에만 추가합니다.
#
# 예:
# VERIFIED_PRIVATE_USE_MAP = {
#     "\U000F02D6": "▶",
#     "\U000F021D": "○",
# }
#
# 주의:
# 현재는 실제 원문 기호가 검증되지 않았으므로
# 임의 매핑을 추가하지 않습니다.
VERIFIED_PRIVATE_USE_MAP: dict[str, str] = {}


# ============================================================
# JSON 로드
# ============================================================
def load_json(
    path: str,
) -> dict[str, Any]:

    file_path = Path(path)

    if not file_path.exists():
        raise FileNotFoundError(
            f"JSON 파일을 찾을 수 없습니다: {file_path}"
        )

    with file_path.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


# ============================================================
# JSON 저장
# ============================================================
def save_json(
    data: dict[str, Any],
    path: str,
) -> None:

    file_path = Path(path)

    file_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with file_path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=2,
        )


# ============================================================
# 기본 특수문자 정규화
# ============================================================
def normalize_special_characters(
    text: str,
) -> str:
    """
    안전하게 처리 가능한 특수문자만 정규화합니다.

    처리:
    - Non-breaking space → 일반 공백
    - Zero-width space 제거
    - BOM 제거

    주의:
    - HWP에서 깨진 문자 '�'는 임의 치환하지 않습니다.
    - PUA 문자는 별도의 검증된 매핑 함수에서 처리합니다.
    """

    if not text:
        return ""

    replacements = {
        "\u00A0": " ",
        "\u200B": "",
        "\uFEFF": "",
    }

    for source, target in replacements.items():
        text = text.replace(
            source,
            target,
        )

    return text


# ============================================================
# 검증된 Private Use Area 문자 정규화
# ============================================================
def normalize_verified_private_use_characters(
    text: str,
) -> str:
    """
    실제 원본 문서와 대조하여 의미가 검증된
    Private Use Area 문자만 치환합니다.

    VERIFIED_PRIVATE_USE_MAP에 등록되지 않은
    PUA 문자는 그대로 유지합니다.

    '�' replacement character도 임의로 변경하지 않습니다.
    """

    if not text:
        return ""

    for source, target in (
        VERIFIED_PRIVATE_USE_MAP.items()
    ):
        text = text.replace(
            source,
            target,
        )

    return text


# ============================================================
# 글머리표 공백 정규화
# ============================================================
def normalize_bullet_spacing(
    text: str,
) -> str:
    """
    각 줄 시작의 '■' 뒤 공백을
    정확히 한 칸으로 통일합니다.

    예:
        ■전화상담
        ■  전화상담
        ■   전화상담

    결과:
        ■ 전화상담

    문장 중간의 '■'는 변경하지 않습니다.
    """

    if not text:
        return ""

    normalized_lines = []

    for line in text.split(
        "\n"
    ):
        line = re.sub(
            r"^(\s*)■\s*",
            r"\1■ ",
            line,
        )

        # '■' 하나만 있는 줄은
        # 뒤쪽 공백 제거
        if line.strip() == "■":
            line = "■"

        normalized_lines.append(
            line
        )

    return "\n".join(
        normalized_lines
    )


# ============================================================
# 일반 텍스트 정규화
# ============================================================
def normalize_text(
    text: Any,
) -> str:
    """
    서비스용 일반 텍스트 정규화.

    처리:
    - None → ""
    - CRLF / CR → LF
    - 탭 → 공백
    - 줄 내부 연속 공백 축소
    - 각 줄 앞뒤 공백 제거
    - 빈 줄 제거

    Paragraph 간 의미 있는 줄바꿈은 유지합니다.
    """

    if text is None:
        return ""

    text = str(text)

    # --------------------------------------------------------
    # 줄바꿈 통일
    # --------------------------------------------------------
    text = text.replace(
        "\r\n",
        "\n",
    )

    text = text.replace(
        "\r",
        "\n",
    )

    # --------------------------------------------------------
    # 탭 → 공백
    # --------------------------------------------------------
    text = text.replace(
        "\t",
        " ",
    )

    normalized_lines = []

    for line in text.split(
        "\n"
    ):

        # ----------------------------------------------------
        # 연속된 일반 공백 축소
        # ----------------------------------------------------
        line = re.sub(
            r"[ ]+",
            " ",
            line,
        )

        # ----------------------------------------------------
        # 줄 앞뒤 공백 제거
        # ----------------------------------------------------
        line = line.strip()

        # ----------------------------------------------------
        # 빈 줄 제거
        # ----------------------------------------------------
        if not line:
            continue

        normalized_lines.append(
            line
        )

    return "\n".join(
        normalized_lines
    ).strip()


# ============================================================
# 최종 콘텐츠 텍스트 정규화
# ============================================================
def normalize_content_text(
    text: Any,
) -> str:
    """
    실제 콘텐츠에 적용되는 전체 텍스트 정규화 흐름.

    순서:
    1. 기본 특수문자 처리
    2. 검증된 PUA 문자 처리
    3. 글머리표 공백 처리
    4. 일반 공백 / 개행 처리
    """

    if text is None:
        text = ""

    text = str(
        text
    )

    # --------------------------------------------------------
    # 1. 기본 특수문자 처리
    # --------------------------------------------------------
    text = normalize_special_characters(
        text
    )

    # --------------------------------------------------------
    # 2. 검증된 PUA 문자 처리
    # --------------------------------------------------------
    text = (
        normalize_verified_private_use_characters(
            text
        )
    )

    # --------------------------------------------------------
    # 3. 글머리표 공백 통일
    # --------------------------------------------------------
    text = normalize_bullet_spacing(
        text
    )

    # --------------------------------------------------------
    # 4. 일반 텍스트 정규화
    # --------------------------------------------------------
    text = normalize_text(
        text
    )

    return text


# ============================================================
# Source Metadata 정규화
# ============================================================
def normalize_source(
    source: dict[str, Any] | None,
    document_format: str,
    section_index: int | None,
) -> dict[str, Any]:
    """
    HWP / HWPX 공통 위치 정보와
    포맷별 위치 정보를 분리합니다.

    중첩 표처럼 원본 source에
    section_index가 없는 경우
    현재 부모 Section의 값을 상속합니다.
    """

    if source is None:
        source = {}

    source_section_index = (
        source.get(
            "section_index"
        )
    )

    # --------------------------------------------------------
    # 중첩 표 section_index 상속
    # --------------------------------------------------------
    if source_section_index is None:
        source_section_index = (
            section_index
        )

    normalized = {
        "section_index":
            source_section_index,

        "paragraph_index":
            source.get(
                "paragraph_index"
            ),

        "location":
            source.get(
                "location"
            ),

        "format":
            document_format,

        "format_specific":
            {},
    }

    # --------------------------------------------------------
    # HWP 전용 정보
    # --------------------------------------------------------
    if "control_index" in source:
        normalized[
            "format_specific"
        ][
            "control_index"
        ] = source[
            "control_index"
        ]

    # --------------------------------------------------------
    # HWPX 전용 정보
    # --------------------------------------------------------
    if "run_index" in source:
        normalized[
            "format_specific"
        ][
            "run_index"
        ] = source[
            "run_index"
        ]

    if "item_index" in source:
        normalized[
            "format_specific"
        ][
            "item_index"
        ] = source[
            "item_index"
        ]

    # --------------------------------------------------------
    # 예상하지 못한 추가 source 정보 보존
    # --------------------------------------------------------
    common_keys = {
        "section_index",
        "paragraph_index",
        "location",
        "control_index",
        "run_index",
        "item_index",
    }

    extra = {
        key: value
        for key, value
        in source.items()
        if key not in common_keys
    }

    if extra:
        normalized[
            "format_specific"
        ].update(
            extra
        )

    return normalized


# ============================================================
# Paragraph 정규화
# ============================================================
def normalize_paragraph(
    paragraph: dict[str, Any],
) -> dict[str, Any]:
    """
    Paragraph를 Common JSON 구조로 정규화합니다.
    """

    return {
        "type":
            "paragraph",

        "paragraph_index":
            paragraph.get(
                "paragraph_index"
            ),

        "text":
            normalize_content_text(
                paragraph.get(
                    "text",
                    "",
                )
            ),
    }


# ============================================================
# Cell 내부 Blocks 생성
# ============================================================
def build_cell_blocks(
    paragraphs: list[dict[str, Any]],
    nested_tables: list[dict[str, Any]],
    document_format: str,
    section_index: int | None,
) -> list[dict[str, Any]]:
    """
    기존 Cell 내부의

    paragraphs[]
    nested_tables[]

    를 하나의 blocks[] 배열로 병합합니다.

    paragraph_index 기준으로
    Paragraph와 Nested Table의 순서를 구성합니다.

    주의:
    현재 방식은 Paragraph 수준의 순서를 복원합니다.

    동일 Paragraph 내부에서
    text → table → text 같은 Run 수준의
    정확한 inline 순서는 완전히 보장하지 않습니다.
    """

    indexed_blocks = []

    # ========================================================
    # Paragraph
    # ========================================================
    for order, paragraph in enumerate(
        paragraphs
    ):

        paragraph_index = (
            paragraph.get(
                "paragraph_index"
            )
        )

        normalized_paragraph = (
            normalize_paragraph(
                paragraph
            )
        )

        indexed_blocks.append(
            {
                "paragraph_index":
                    paragraph_index,

                # 동일 paragraph_index에서
                # Paragraph를 Table보다 먼저 배치
                "type_priority":
                    0,

                "original_order":
                    order,

                "block":
                    normalized_paragraph,
            }
        )

    # ========================================================
    # Nested Table
    # ========================================================
    for order, table in enumerate(
        nested_tables
    ):

        source = table.get(
            "source",
            {},
        )

        paragraph_index = (
            source.get(
                "paragraph_index"
            )
        )

        normalized_table = (
            normalize_table(
                table,
                document_format,
                section_index,
            )
        )

        indexed_blocks.append(
            {
                "paragraph_index":
                    paragraph_index,

                "type_priority":
                    1,

                "original_order":
                    order,

                "block":
                    normalized_table,
            }
        )

    # ========================================================
    # Block 정렬
    # ========================================================
    def sort_key(
        item: dict[str, Any],
    ) -> tuple:

        paragraph_index = (
            item[
                "paragraph_index"
            ]
        )

        if paragraph_index is None:
            paragraph_index = float(
                "inf"
            )

        return (
            paragraph_index,
            item[
                "type_priority"
            ],
            item[
                "original_order"
            ],
        )

    indexed_blocks.sort(
        key=sort_key
    )

    return [
        item[
            "block"
        ]
        for item
        in indexed_blocks
    ]


# ============================================================
# Cell 정규화
# ============================================================
def normalize_cell(
    cell: dict[str, Any],
    document_format: str,
    section_index: int | None,
) -> dict[str, Any]:
    """
    Table Cell을 Common JSON 구조로 정규화합니다.

    기존:
        paragraphs[]
        nested_tables[]

    정규화:
        blocks[]
    """

    paragraphs = cell.get(
        "paragraphs",
        [],
    )

    nested_tables = cell.get(
        "nested_tables",
        [],
    )

    blocks = build_cell_blocks(
        paragraphs,
        nested_tables,
        document_format,
        section_index,
    )

    return {
        "row":
            cell.get(
                "row"
            ),

        "col":
            cell.get(
                "col"
            ),

        "row_span":
            cell.get(
                "row_span",
                1,
            ),

        "col_span":
            cell.get(
                "col_span",
                1,
            ),

        "text":
            normalize_content_text(
                cell.get(
                    "text",
                    "",
                )
            ),

        "blocks":
            blocks,
    }


# ============================================================
# Table 정규화
# ============================================================
def normalize_table(
    table: dict[str, Any],
    document_format: str,
    section_index: int | None,
) -> dict[str, Any]:
    """
    Table을 Common JSON 구조로 정규화합니다.

    Nested Table도 동일한 함수를
    재귀적으로 사용합니다.
    """

    normalized_cells = []

    for cell in table.get(
        "cells",
        [],
    ):
        normalized_cells.append(
            normalize_cell(
                cell,
                document_format,
                section_index,
            )
        )

    return {
        "type":
            "table",

        "table_index":
            table.get(
                "table_index"
            ),

        "row_count":
            table.get(
                "row_count"
            ),

        "col_count":
            table.get(
                "col_count"
            ),

        "cells":
            normalized_cells,

        "source":
            normalize_source(
                table.get(
                    "source",
                    {},
                ),
                document_format,
                section_index,
            ),
    }


# ============================================================
# Section Block 정규화
# ============================================================
def normalize_block(
    block: dict[str, Any],
    document_format: str,
    section_index: int | None,
) -> dict[str, Any] | None:
    """
    Section 내부 Block을 유형별로 정규화합니다.
    """

    block_type = block.get(
        "type"
    )

    # --------------------------------------------------------
    # Table
    # --------------------------------------------------------
    if block_type == "table":
        return normalize_table(
            block,
            document_format,
            section_index,
        )

    # --------------------------------------------------------
    # Paragraph
    # --------------------------------------------------------
    if block_type == "paragraph":
        return normalize_paragraph(
            block
        )

    # --------------------------------------------------------
    # 아직 정의하지 않은 Block은
    # 데이터 손실 방지를 위해 그대로 보존
    # --------------------------------------------------------
    return copy.deepcopy(
        block
    )


# ============================================================
# Document 전체 정규화
# ============================================================
def normalize_document(
    document: dict[str, Any],
) -> dict[str, Any]:
    """
    HWP / HWPX Parser가 생성한 Raw JSON을
    Common JSON 구조로 정규화합니다.
    """

    document_info = document.get(
        "document",
        {},
    )

    document_format = (
        str(
            document_info.get(
                "format",
                "",
            )
        )
        .lower()
        .strip()
    )

    normalized = {
        "document": {
            "filename":
                document_info.get(
                    "filename"
                ),

            "format":
                document_format,
        },

        "sections":
            [],
    }

    # ========================================================
    # Section 순회
    # ========================================================
    for section in document.get(
        "sections",
        [],
    ):

        section_index = (
            section.get(
                "section_index"
            )
        )

        normalized_section = {
            "section_index":
                section_index,

            "blocks":
                [],
        }

        # ====================================================
        # Section 내부 Block 순회
        # ====================================================
        for block in section.get(
            "blocks",
            [],
        ):

            normalized_block = (
                normalize_block(
                    block,
                    document_format,
                    section_index,
                )
            )

            if normalized_block is not None:
                normalized_section[
                    "blocks"
                ].append(
                    normalized_block
                )

        normalized[
            "sections"
        ].append(
            normalized_section
        )

    return normalized


# ============================================================
# CLI
# ============================================================
def main() -> None:

    parser = argparse.ArgumentParser(
        description=(
            "HWP / HWPX Parser JSON을 "
            "Common JSON 구조로 정규화합니다."
        )
    )

    parser.add_argument(
        "--input",
        required=True,
        help="입력 Parser JSON 경로",
    )

    parser.add_argument(
        "--output",
        required=True,
        help="출력 Normalized JSON 경로",
    )

    args = parser.parse_args()

    # ========================================================
    # Raw JSON 로드
    # ========================================================
    raw_document = load_json(
        args.input
    )

    # ========================================================
    # Document 정규화
    # ========================================================
    normalized_document = (
        normalize_document(
            raw_document
        )
    )

    # ========================================================
    # 결과 저장
    # ========================================================
    save_json(
        normalized_document,
        args.output,
    )

    print(
        "정규화 완료"
    )

    print(
        f"입력: {args.input}"
    )

    print(
        f"출력: {args.output}"
    )


# ============================================================
# Entry Point
# ============================================================
if __name__ == "__main__":
    main()