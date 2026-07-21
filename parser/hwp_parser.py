import argparse
import json
import os
import sys
from pathlib import Path

import jpype


# ============================================================
# 콘솔 UTF-8 설정
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
# JVM 시작
# ============================================================
def start_jvm(
    hwp_jar_path: str,
) -> None:

    if jpype.isJVMStarted():
        return

    jar_path = os.path.abspath(
        hwp_jar_path
    )

    if not os.path.exists(
        jar_path
    ):
        raise FileNotFoundError(
            f"hwplib JAR 파일을 찾을 수 없습니다: "
            f"{jar_path}"
        )

    jpype.startJVM(
        jpype.getDefaultJVMPath(),
        f"-Djava.class.path={jar_path}",
        convertStrings=True,
    )


# ============================================================
# Paragraph 텍스트 추출
# ============================================================
def extract_hwp_paragraph_text(
    paragraph,
) -> str:
    """
    HWP Paragraph에서 일반 텍스트를 추출합니다.
    """

    if paragraph is None:
        return ""

    try:
        text = (
            paragraph
            .getNormalString()
        )

        if text is None:
            return ""

        return str(text)

    except Exception:
        return ""


# ============================================================
# Cell 내부 Paragraph 추출
# ============================================================
def extract_cell_paragraphs(
    cell,
) -> list:
    """
    HWP Cell 내부 ParagraphList를 순회하여
    paragraph 단위 텍스트를 반환합니다.
    """

    paragraphs_data = []

    try:
        paragraph_list = (
            cell
            .getParagraphList()
        )

    except Exception:
        return paragraphs_data

    if paragraph_list is None:
        return paragraphs_data

    # --------------------------------------------------------
    # ParagraphList.getParagraphs()
    # --------------------------------------------------------
    try:
        paragraphs = (
            paragraph_list
            .getParagraphs()
        )

        for paragraph_index in range(
            len(paragraphs)
        ):
            paragraph = paragraphs[
                paragraph_index
            ]

            text = (
                extract_hwp_paragraph_text(
                    paragraph
                )
            )

            # 완전히 빈 문단 제외
            if not text.strip():
                continue

            paragraphs_data.append(
                {
                    "paragraph_index":
                        paragraph_index,

                    "text":
                        text,
                }
            )

        return paragraphs_data

    except Exception:
        pass

    # --------------------------------------------------------
    # fallback
    # --------------------------------------------------------
    try:
        text = (
            paragraph_list
            .getNormalString()
        )

        if (
            text is not None
            and str(text).strip()
        ):
            paragraphs_data.append(
                {
                    "paragraph_index": 0,
                    "text": str(text),
                }
            )

    except Exception:
        pass

    return paragraphs_data


# ============================================================
# Cell 전체 텍스트 추출
# ============================================================
def extract_cell_text(
    cell,
) -> str:
    """
    Cell 전체 텍스트를 반환합니다.
    """

    try:
        paragraph_list = (
            cell
            .getParagraphList()
        )

        if paragraph_list is None:
            return ""

        text = (
            paragraph_list
            .getNormalString()
        )

        if text is None:
            return ""

        return str(text)

    except Exception:
        return ""


# ============================================================
# HWP Cell 내부 Nested Table 탐색
# ============================================================
def find_nested_tables_in_hwp_cell(
    cell,
    table_counter: dict,
) -> list:
    """
    HWP Cell 내부 Paragraph의 ControlList를 순회하여
    중첩된 ControlTable을 재귀적으로 추출합니다.
    """

    nested_tables = []

    try:
        paragraph_list = (
            cell
            .getParagraphList()
        )

    except Exception:
        return nested_tables

    if paragraph_list is None:
        return nested_tables

    try:
        paragraphs = (
            paragraph_list
            .getParagraphs()
        )

    except Exception:
        return nested_tables

    for paragraph_index in range(
        len(paragraphs)
    ):

        paragraph = paragraphs[
            paragraph_index
        ]

        if paragraph is None:
            continue

        try:
            controls = (
                paragraph
                .getControlList()
            )

        except Exception:
            controls = None

        if controls is None:
            continue

        for control_index in range(
            len(controls)
        ):

            control = controls[
                control_index
            ]

            if control is None:
                continue

            try:
                class_name = (
                    control
                    .getClass()
                    .getName()
                )

            except Exception:
                continue

            if not class_name.endswith(
                ".ControlTable"
            ):
                continue

            current_table_index = (
                table_counter["value"]
            )

            table_counter["value"] += 1

            nested_table = (
                parse_table(
                    table=control,
                    table_index=current_table_index,
                    table_counter=table_counter,
                )
            )

            nested_table[
                "source"
            ] = {
                "paragraph_index":
                    paragraph_index,

                "control_index":
                    control_index,

                "location":
                    "nested_table",
            }

            nested_tables.append(
                nested_table
            )

    return nested_tables


# ============================================================
# Table 파싱
# ============================================================
def parse_table(
    table,
    table_index: int,
    table_counter: dict,
) -> dict:
    """
    HWP Table을 공통 JSON으로 변환합니다.

    Cell 내부에 또 다른 Table이 있으면
    nested_tables에 재귀적으로 저장합니다.
    """

    cells = []

    try:
        row_list = (
            table
            .getRowList()
        )

    except Exception:
        row_list = None

    if row_list is None:
        return {
            "type": "table",
            "table_index": table_index,
            "row_count": 0,
            "col_count": 0,
            "cells": [],
        }

    for row_list_index in range(
        len(row_list)
    ):

        row = row_list[
            row_list_index
        ]

        try:
            cell_list = (
                row
                .getCellList()
            )

        except Exception:
            continue

        if cell_list is None:
            continue

        for cell_list_index in range(
            len(cell_list)
        ):

            cell = cell_list[
                cell_list_index
            ]

            if cell is None:
                continue

            try:
                header = (
                    cell
                    .getListHeader()
                )

            except Exception:
                continue

            if header is None:
                continue

            try:
                actual_row = int(
                    header
                    .getRowIndex()
                )

                actual_col = int(
                    header
                    .getColIndex()
                )

                row_span = int(
                    header
                    .getRowSpan()
                )

                col_span = int(
                    header
                    .getColSpan()
                )

            except Exception:
                continue

            # ------------------------------------------------
            # Cell 전체 텍스트
            # ------------------------------------------------
            full_text = (
                extract_cell_text(
                    cell
                )
            )

            # ------------------------------------------------
            # Cell 내부 Paragraph
            # ------------------------------------------------
            paragraphs = (
                extract_cell_paragraphs(
                    cell
                )
            )

            # ------------------------------------------------
            # Cell 내부 Nested Table
            # ------------------------------------------------
            nested_tables = (
                find_nested_tables_in_hwp_cell(
                    cell=cell,
                    table_counter=table_counter,
                )
            )

            cells.append(
                {
                    "row":
                        actual_row,

                    "col":
                        actual_col,

                    "row_span":
                        row_span,

                    "col_span":
                        col_span,

                    "text":
                        full_text,

                    "paragraphs":
                        paragraphs,

                    "nested_tables":
                        nested_tables,
                }
            )

    # ========================================================
    # Table 논리 크기 계산
    # ========================================================
    row_count = 0
    col_count = 0

    for cell in cells:

        row_count = max(
            row_count,
            cell["row"]
            + cell["row_span"],
        )

        col_count = max(
            col_count,
            cell["col"]
            + cell["col_span"],
        )

    return {
        "type":
            "table",

        "table_index":
            table_index,

        "row_count":
            row_count,

        "col_count":
            col_count,

        "cells":
            cells,
    }


# ============================================================
# HWP 파싱
# ============================================================
def parse_hwp(
    hwp_jar_path: str,
    hwp_file_path: str,
) -> dict:

    start_jvm(
        hwp_jar_path
    )

    file_path = os.path.abspath(
        hwp_file_path
    )

    if not os.path.exists(
        file_path
    ):
        raise FileNotFoundError(
            f"HWP 파일을 찾을 수 없습니다: "
            f"{file_path}"
        )

    HWPReader = jpype.JClass(
        "kr.dogfoot.hwplib.reader.HWPReader"
    )

    hwp_file = (
        HWPReader.fromFile(
            file_path
        )
    )

    if hwp_file is None:
        raise RuntimeError(
            f"HWP 파일 파싱 실패: "
            f"{file_path}"
        )

    document = {
        "document": {
            "filename":
                os.path.basename(
                    file_path
                ),

            "format":
                "hwp",
        },

        "sections": [],
    }

    body_text = (
        hwp_file
        .getBodyText()
    )

    sections = (
        body_text
        .getSectionList()
    )

    # 모든 Table에 고유 index 부여
    table_counter = {
        "value": 0
    }

    # ========================================================
    # Section 순회
    # ========================================================
    for section_index in range(
        len(sections)
    ):

        section = sections[
            section_index
        ]

        section_data = {
            "section_index":
                section_index,

            "blocks":
                [],
        }

        paragraphs = (
            section
            .getParagraphs()
        )

        # ====================================================
        # Top-level Paragraph 순회
        # ====================================================
        for para_index in range(
            len(paragraphs)
        ):

            paragraph = paragraphs[
                para_index
            ]

            # ------------------------------------------------
            # 일반 Paragraph 텍스트
            # ------------------------------------------------
            paragraph_text = (
                extract_hwp_paragraph_text(
                    paragraph
                )
            )

            if paragraph_text.strip():

                section_data[
                    "blocks"
                ].append(
                    {
                        "type":
                            "paragraph",

                        "text":
                            paragraph_text,

                        "source": {
                            "section_index":
                                section_index,

                            "paragraph_index":
                                para_index,
                        },
                    }
                )

            # ------------------------------------------------
            # Control 순회
            # ------------------------------------------------
            try:
                controls = (
                    paragraph
                    .getControlList()
                )

            except Exception:
                controls = None

            if controls is None:
                continue

            for control_index in range(
                len(controls)
            ):

                control = controls[
                    control_index
                ]

                if control is None:
                    continue

                try:
                    class_name = (
                        control
                        .getClass()
                        .getName()
                    )

                except Exception:
                    continue

                # --------------------------------------------
                # Table만 처리
                # --------------------------------------------
                if not class_name.endswith(
                    ".ControlTable"
                ):
                    continue

                current_table_index = (
                    table_counter["value"]
                )

                table_counter["value"] += 1

                table_data = (
                    parse_table(
                        table=control,
                        table_index=current_table_index,
                        table_counter=table_counter,
                    )
                )

                table_data[
                    "source"
                ] = {
                    "section_index":
                        section_index,

                    "paragraph_index":
                        para_index,

                    "control_index":
                        control_index,

                    "location":
                        "top_level",
                }

                section_data[
                    "blocks"
                ].append(
                    table_data
                )

        document[
            "sections"
        ].append(
            section_data
        )

    # ========================================================
    # 통계
    # ========================================================
    document[
        "statistics"
    ] = {
        "section_count":
            len(
                document[
                    "sections"
                ]
            ),

        "table_count":
            table_counter[
                "value"
            ],
    }

    return document


# ============================================================
# JSON 저장
# ============================================================
def save_json(
    data: dict,
    output_path: str,
) -> None:

    output = Path(
        output_path
    )

    output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with output.open(
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
# CLI
# ============================================================
def main():

    parser = argparse.ArgumentParser(
        description=(
            "hwplib를 이용하여 HWP 문서를 "
            "중첩 표를 포함한 공통 JSON으로 변환합니다."
        )
    )

    parser.add_argument(
        "--hwp_jar_path",
        required=True,
    )

    parser.add_argument(
        "--file_path",
        required=True,
    )

    parser.add_argument(
        "--output_path",
        required=True,
    )

    args = parser.parse_args()

    result = parse_hwp(
        hwp_jar_path=
            args.hwp_jar_path,

        hwp_file_path=
            args.file_path,
    )

    save_json(
        result,
        args.output_path,
    )

    print()
    print("=" * 80)
    print("HWP 구조 변환 완료")
    print("=" * 80)

    print(
        "파일:",
        result[
            "document"
        ][
            "filename"
        ],
    )

    print(
        "Section 수:",
        result[
            "statistics"
        ][
            "section_count"
        ],
    )

    print(
        "전체 Table 수:",
        result[
            "statistics"
        ][
            "table_count"
        ],
    )

    print(
        "출력:",
        os.path.abspath(
            args.output_path
        ),
    )


if __name__ == "__main__":
    main()