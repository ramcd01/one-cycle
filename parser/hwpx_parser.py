import argparse
import json
import os
import sys
from pathlib import Path

import jpype


# ============================================================
# Windows 콘솔 UTF-8 설정
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
    hwpx_jar_path: str,
) -> None:

    if jpype.isJVMStarted():
        return

    jar_path = os.path.abspath(
        hwpx_jar_path
    )

    if not os.path.exists(
        jar_path
    ):
        raise FileNotFoundError(
            f"hwpxlib JAR 파일을 찾을 수 없습니다: "
            f"{jar_path}"
        )

    jpype.startJVM(
        jpype.getDefaultJVMPath(),
        f"-Djava.class.path={jar_path}",
        convertStrings=True,
    )


# ============================================================
# T 객체 텍스트 추출
# ============================================================
def extract_text_from_t(
    t,
) -> str:
    """
    HWPX T 객체에서 텍스트를 추출합니다.
    """

    if t is None:
        return ""

    # --------------------------------------------------------
    # 단순 텍스트
    # --------------------------------------------------------
    try:
        if t.isOnlyText():

            text = t.onlyText()

            if text is not None:
                return str(text)

    except Exception:
        pass

    # --------------------------------------------------------
    # 복합 T 객체
    # --------------------------------------------------------
    parts = []

    try:
        item_count = (
            t.countOfItems()
        )

        for item_index in range(
            item_count
        ):

            item = t.getItem(
                item_index
            )

            if item is None:
                continue

            try:
                class_name = (
                    item
                    .getClass()
                    .getName()
                )

            except Exception:
                continue

            if class_name.endswith(
                ".NormalText"
            ):

                try:
                    text = (
                        item.text()
                    )

                    if text is not None:
                        parts.append(
                            str(text)
                        )

                except Exception:
                    continue

            elif class_name.endswith(
                ".FWSpace"
            ):
                parts.append(" ")

            elif class_name.endswith(
                ".LineBreak"
            ):
                parts.append("\n")

            elif class_name.endswith(
                ".Tab"
            ):
                parts.append("\t")

            else:
                continue

    except Exception:
        pass

    return "".join(
        parts
    )


# ============================================================
# HWPX Cell Paragraph 추출
# ============================================================
def extract_cell_paragraphs(
    tc,
) -> list:

    paragraphs_data = []

    try:
        sublist = (
            tc.subList()
        )

    except Exception:
        return paragraphs_data

    if sublist is None:
        return paragraphs_data

    try:
        paragraph_count = (
            sublist.countOfPara()
        )

    except Exception:
        return paragraphs_data

    for para_index in range(
        paragraph_count
    ):

        try:
            para = (
                sublist.getPara(
                    para_index
                )
            )

        except Exception:
            continue

        if para is None:
            continue

        para_parts = []

        try:
            run_count = (
                para.countOfRun()
            )

        except Exception:
            continue

        for run_index in range(
            run_count
        ):

            try:
                run = (
                    para.getRun(
                        run_index
                    )
                )

            except Exception:
                continue

            if run is None:
                continue

            try:
                item_count = (
                    run.countOfRunItem()
                )

            except Exception:
                continue

            for item_index in range(
                item_count
            ):

                try:
                    item = (
                        run.getRunItem(
                            item_index
                        )
                    )

                except Exception:
                    continue

                if item is None:
                    continue

                try:
                    class_name = (
                        item
                        .getClass()
                        .getName()
                    )

                except Exception:
                    continue

                if class_name.endswith(
                    ".paragraph.T"
                ):

                    text = (
                        extract_text_from_t(
                            item
                        )
                    )

                    if text:
                        para_parts.append(
                            text
                        )

        para_text = "".join(
            para_parts
        )

        if not para_text.strip():
            continue

        paragraphs_data.append(
            {
                "paragraph_index":
                    para_index,

                "text":
                    para_text,
            }
        )

    return paragraphs_data


# ============================================================
# Cell 전체 텍스트
# ============================================================
def extract_cell_text(
    tc,
) -> str:

    paragraphs = (
        extract_cell_paragraphs(
            tc
        )
    )

    return "\n".join(
        paragraph[
            "text"
        ]
        for paragraph
        in paragraphs
    ).strip()


# ============================================================
# HWPX Cell 내부 Nested Table 탐색
# ============================================================
def find_nested_tables_in_hwpx_cell(
    tc,
    table_counter: dict,
) -> list:
    """
    Tc
    -> SubList
    -> Paragraph
    -> Run
    -> RunItem
    -> Table

    순서로 탐색하여 중첩 표를 재귀 파싱합니다.
    """

    nested_tables = []

    try:
        sublist = (
            tc.subList()
        )

    except Exception:
        return nested_tables

    if sublist is None:
        return nested_tables

    try:
        paragraph_count = (
            sublist.countOfPara()
        )

    except Exception:
        return nested_tables

    for para_index in range(
        paragraph_count
    ):

        try:
            para = (
                sublist.getPara(
                    para_index
                )
            )

        except Exception:
            continue

        if para is None:
            continue

        try:
            run_count = (
                para.countOfRun()
            )

        except Exception:
            continue

        for run_index in range(
            run_count
        ):

            try:
                run = (
                    para.getRun(
                        run_index
                    )
                )

            except Exception:
                continue

            if run is None:
                continue

            try:
                item_count = (
                    run.countOfRunItem()
                )

            except Exception:
                continue

            for item_index in range(
                item_count
            ):

                try:
                    item = (
                        run.getRunItem(
                            item_index
                        )
                    )

                except Exception:
                    continue

                if item is None:
                    continue

                try:
                    class_name = (
                        item
                        .getClass()
                        .getName()
                    )

                except Exception:
                    continue

                if not class_name.endswith(
                    ".Table"
                ):
                    continue

                current_table_index = (
                    table_counter[
                        "value"
                    ]
                )

                table_counter[
                    "value"
                ] += 1

                nested_table = (
                    parse_table(
                        table=item,
                        table_index=current_table_index,
                        table_counter=table_counter,
                    )
                )

                nested_table[
                    "source"
                ] = {
                    "paragraph_index":
                        para_index,

                    "run_index":
                        run_index,

                    "item_index":
                        item_index,

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
    HWPX Table 객체를 공통 JSON으로 변환합니다.

    Cell 내부 Nested Table도 재귀적으로 탐색합니다.
    """

    cells = []

    try:
        tr_count = (
            table.countOfTr()
        )

    except Exception:
        tr_count = 0

    for tr_index in range(
        tr_count
    ):

        try:
            tr = (
                table.getTr(
                    tr_index
                )
            )

        except Exception:
            continue

        if tr is None:
            continue

        try:
            tc_count = (
                tr.countOfTc()
            )

        except Exception:
            continue

        for tc_index in range(
            tc_count
        ):

            try:
                tc = (
                    tr.getTc(
                        tc_index
                    )
                )

            except Exception:
                continue

            if tc is None:
                continue

            try:
                addr = (
                    tc.cellAddr()
                )

                span = (
                    tc.cellSpan()
                )

            except Exception:
                continue

            if (
                addr is None
                or span is None
            ):
                continue

            try:
                row = int(
                    addr.rowAddr()
                )

                col = int(
                    addr.colAddr()
                )

                row_span = int(
                    span.rowSpan()
                )

                col_span = int(
                    span.colSpan()
                )

            except Exception:
                continue

            # ------------------------------------------------
            # Cell Paragraph
            # ------------------------------------------------
            paragraphs = (
                extract_cell_paragraphs(
                    tc
                )
            )

            # ------------------------------------------------
            # Nested Table
            # ------------------------------------------------
            nested_tables = (
                find_nested_tables_in_hwpx_cell(
                    tc=tc,
                    table_counter=table_counter,
                )
            )

            cell_data = {
                "row":
                    row,

                "col":
                    col,

                "row_span":
                    row_span,

                "col_span":
                    col_span,

                "text":
                    "\n".join(
                        paragraph[
                            "text"
                        ]
                        for paragraph
                        in paragraphs
                    ).strip(),

                "paragraphs":
                    paragraphs,

                "nested_tables":
                    nested_tables,
            }

            cells.append(
                cell_data
            )

    # ========================================================
    # Table 논리적 크기 계산
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
# HWPX 문서 파싱
# ============================================================
def parse_hwpx(
    hwpx_jar_path: str,
    hwpx_file_path: str,
) -> dict:

    start_jvm(
        hwpx_jar_path
    )

    file_path = os.path.abspath(
        hwpx_file_path
    )

    if not os.path.exists(
        file_path
    ):
        raise FileNotFoundError(
            f"HWPX 파일을 찾을 수 없습니다: "
            f"{file_path}"
        )

    # ========================================================
    # HWPXReader
    # ========================================================
    HWPXReader = jpype.JClass(
        "kr.dogfoot.hwpxlib.reader.HWPXReader"
    )

    hwpx_file = (
        HWPXReader.fromFilepath(
            file_path
        )
    )

    if hwpx_file is None:
        raise RuntimeError(
            f"HWPX 파일 파싱에 실패했습니다: "
            f"{file_path}"
        )

    # ========================================================
    # 공통 JSON
    # ========================================================
    document = {
        "document": {
            "filename":
                os.path.basename(
                    file_path
                ),

            "format":
                "hwpx",
        },

        "sections": [],
    }

    # ========================================================
    # Section
    # ========================================================
    sections = (
        hwpx_file
        .sectionXMLFileList()
    )

    table_counter = {
        "value": 0
    }

    # ========================================================
    # Section 순회
    # ========================================================
    for section_index in range(
        sections.count()
    ):

        section = sections.get(
            section_index
        )

        section_data = {
            "section_index":
                section_index,

            "blocks":
                [],
        }

        # ====================================================
        # Paragraph 순회
        # ====================================================
        for para_index in range(
            section.countOfPara()
        ):

            para = (
                section.getPara(
                    para_index
                )
            )

            if para is None:
                continue

            # =================================================
            # Run 순회
            # =================================================
            for run_index in range(
                para.countOfRun()
            ):

                run = (
                    para.getRun(
                        run_index
                    )
                )

                if run is None:
                    continue

                # =============================================
                # RunItem 순회
                # =============================================
                for item_index in range(
                    run.countOfRunItem()
                ):

                    item = (
                        run.getRunItem(
                            item_index
                        )
                    )

                    if item is None:
                        continue

                    try:
                        class_name = (
                            item
                            .getClass()
                            .getName()
                        )

                    except Exception:
                        continue

                    if not class_name.endswith(
                        ".Table"
                    ):
                        continue

                    current_table_index = (
                        table_counter[
                            "value"
                        ]
                    )

                    table_counter[
                        "value"
                    ] += 1

                    table_data = (
                        parse_table(
                            table=item,
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

                        "run_index":
                            run_index,

                        "item_index":
                            item_index,

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
            "hwpxlib를 이용하여 HWPX 문서를 "
            "중첩 표를 포함한 공통 JSON으로 변환합니다."
        )
    )

    parser.add_argument(
        "--hwpx_jar_path",
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

    result = parse_hwpx(
        hwpx_jar_path=
            args.hwpx_jar_path,

        hwpx_file_path=
            args.file_path,
    )

    save_json(
        result,
        args.output_path,
    )

    print()
    print("=" * 80)
    print("HWPX 구조 변환 완료")
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