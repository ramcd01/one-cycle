import json
from typing import Any
from tkinter import Tk, messagebox
from tkinter.filedialog import askopenfilename


# ===========================================================================
# 공통 텍스트 처리
# ===========================================================================

def clean_text(value: Any) -> str:
    """텍스트 비교용 정규화.

    - None -> 빈 문자열
    - 줄바꿈 / 탭 / 연속 공백 -> 단일 공백
    """

    if value is None:
        return ""

    return " ".join(
        str(value)
        .replace("\r", "\n")
        .split()
    )


def normalize_header_path(
    path: Any,
) -> list[str]:
    """header_path 내부 문자열을 비교용으로 정규화한다."""

    if not isinstance(path, list):
        return []

    result: list[str] = []

    for item in path:
        text = clean_text(item)

        if text:
            result.append(text)

    return result


# ===========================================================================
# Source 좌표 처리
# ===========================================================================

def get_source_key(
    item: dict[str, Any],
) -> tuple[int, int] | None:
    """value 또는 merged_value의 source 좌표를 반환한다."""

    source = item.get("source")

    if not isinstance(source, dict):
        return None

    row = source.get("row")
    col = source.get("col")

    if row is None or col is None:
        return None

    try:
        return (
            int(row),
            int(col),
        )

    except (
        TypeError,
        ValueError,
    ):
        return None


# ===========================================================================
# 셀 범위 처리
# ===========================================================================

def cell_range(
    cell: dict[str, Any],
) -> tuple[int, int, int, int]:
    """셀의 시작 좌표와 병합 범위를 반환한다."""

    row = int(
        cell.get("row", 0)
        or 0
    )

    col = int(
        cell.get("col", 0)
        or 0
    )

    row_span = max(
        1,
        int(
            cell.get(
                "row_span",
                1,
            )
            or 1
        ),
    )

    col_span = max(
        1,
        int(
            cell.get(
                "col_span",
                1,
            )
            or 1
        ),
    )

    return (
        row,
        col,
        row_span,
        col_span,
    )


# ===========================================================================
# 표 Grid 복원
# ===========================================================================

def build_grid(
    table: dict[str, Any],
) -> tuple[
    list[
        list[
            dict[str, Any] | None
        ]
    ],
    list[str],
]:
    """원본 cells의 row/col/span 정보를 이용해 논리 Grid를 복원한다."""

    rows = int(
        table.get(
            "row_count",
            0,
        )
        or 0
    )

    cols = int(
        table.get(
            "col_count",
            0,
        )
        or 0
    )

    grid: list[
        list[
            dict[str, Any] | None
        ]
    ] = [
        [
            None
            for _ in range(cols)
        ]
        for _ in range(rows)
    ]

    errors: list[str] = []

    for cell in (
        table.get("cells")
        or []
    ):
        (
            row,
            col,
            row_span,
            col_span,
        ) = cell_range(cell)

        # ---------------------------------------------------------------
        # 시작 좌표 검사
        # ---------------------------------------------------------------

        if (
            row < 0
            or col < 0
            or row >= rows
            or col >= cols
        ):
            errors.append(
                f"셀 시작 좌표 초과: "
                f"row={row}, col={col}, "
                f"table={rows}x{cols}"
            )

            continue

        end_row = (
            row
            + row_span
        )

        end_col = (
            col
            + col_span
        )

        # ---------------------------------------------------------------
        # 병합 범위 검사
        # ---------------------------------------------------------------

        if (
            end_row > rows
            or end_col > cols
        ):
            errors.append(
                f"병합 범위 초과: "
                f"row={row}, col={col}, "
                f"row_span={row_span}, "
                f"col_span={col_span}, "
                f"table={rows}x{cols}"
            )

            continue

        # ---------------------------------------------------------------
        # 병합 셀 Grid 반영
        # ---------------------------------------------------------------

        for target_row in range(
            row,
            end_row,
        ):
            for target_col in range(
                col,
                end_col,
            ):
                if (
                    grid[
                        target_row
                    ][
                        target_col
                    ]
                    is not None
                ):
                    errors.append(
                        f"셀 범위 중복: "
                        f"row={target_row}, "
                        f"col={target_col}"
                    )

                grid[
                    target_row
                ][
                    target_col
                ] = cell

    return (
        grid,
        errors,
    )


# ===========================================================================
# 원본 Cell 좌표 Map
# ===========================================================================

def build_origin_cell_map(
    table: dict[str, Any],
) -> dict[
    tuple[int, int],
    dict[str, Any],
]:
    """원본 Cell을 (row, col) 좌표 기준으로 Map으로 만든다."""

    result: dict[
        tuple[int, int],
        dict[str, Any],
    ] = {}

    for cell in (
        table.get("cells")
        or []
    ):
        (
            row,
            col,
            _,
            _,
        ) = cell_range(cell)

        result[
            (
                row,
                col,
            )
        ] = cell

    return result


# ===========================================================================
# Section 순회
# ===========================================================================

def walk_sections(
    sections: list[
        dict[str, Any]
    ],
    parent_path: list[str]
    | None = None,
):
    """sections / children을 재귀 순회한다."""

    path = (
        parent_path
        or []
    )

    for section in sections:
        title = clean_text(
            section.get("title")
        )

        current_path = (
            path
            + (
                [title]
                if title
                else []
            )
        )

        yield (
            section,
            current_path,
        )

        children = (
            section.get("children")
            or []
        )

        yield from walk_sections(
            children,
            current_path,
        )


# ===========================================================================
# 최종 구조화 JSON에서 표 수집
# ===========================================================================

def collect_final_tables(
    final_doc: dict[str, Any],
) -> list[
    dict[str, Any]
]:
    """모든 Section의 contents에서 table을 수집한다."""

    collected: list[
        dict[str, Any]
    ] = []

    for (
        section,
        path,
    ) in walk_sections(
        final_doc.get(
            "sections",
            [],
        )
    ):
        for content in (
            section.get(
                "contents"
            )
            or []
        ):
            if (
                isinstance(
                    content,
                    dict,
                )
                and content.get(
                    "type"
                )
                == "table"
            ):
                collected.append(
                    {
                        "table": content,
                        "section_id": (
                            section.get(
                                "section_id"
                            )
                        ),
                        "section_path": path,
                    }
                )

    return collected


# ===========================================================================
# 검증 결과 생성
# ===========================================================================

def validation_item(
    name: str,
    passed: bool,
    warning: bool,
    summary: str,
    details: list[str]
    | None = None,
) -> dict[str, Any]:
    """개별 검증 항목 결과를 생성한다."""

    if passed:
        status = "PASS"

    elif warning:
        status = "WARN"

    else:
        status = "FAIL"

    return {
        "name": name,
        "status": status,
        "summary": summary,
        "details": (
            details
            or []
        ),
    }


# ===========================================================================
# Step 3 전체 검증
# ===========================================================================

def validate_step3(
    final_doc: dict[str, Any],
) -> dict[str, Any]:
    """Step 3 최종 구조화 결과를 검증한다."""

    table_entries = (
        collect_final_tables(
            final_doc
        )
    )

    total = len(
        table_entries
    )

    checks: list[
        dict[str, Any]
    ] = []

    # =======================================================================
    # 1. structured_table 생성 여부
    # =======================================================================

    missing_structured: list[
        str
    ] = []

    for entry in (
        table_entries
    ):
        table = (
            entry["table"]
        )

        if not isinstance(
            table.get(
                "structured_table"
            ),
            dict,
        ):
            missing_structured.append(
                f"table_index="
                f"{table.get('table_index')} / "
                f"{' > '.join(entry['section_path'])}"
            )

    checks.append(
        validation_item(
            "1. structured_table 생성 여부",
            passed=(
                total > 0
                and not missing_structured
            ),
            warning=(
                total == 0
            ),
            summary=(
                (
                    f"전체 표 {total}개 중 "
                    f"{total - len(missing_structured)}개에 "
                    f"structured_table 존재"
                )
                if total
                else "검증할 표가 없음"
            ),
            details=(
                missing_structured[
                    :30
                ]
            ),
        )
    )

    # =======================================================================
    # 2. Header ↔ Value 연결 여부
    #
    # 일반 values + merged_values 모두 검사한다.
    #
    # merged_values는 여러 Header에 중복 매핑하지 않고
    # 하나의 논리 값으로 계산한다.
    # =======================================================================

    mapped_values = 0
    nonempty_values = 0
    unresolved_header_values = 0

    mapping_issues: list[
        str
    ] = []

    for entry in (
        table_entries
    ):
        table = (
            entry["table"]
        )

        structured = (
            table.get(
                "structured_table"
            )
            or {}
        )

        if (
            structured.get(
                "status"
            )
            not in {
                "structured",
                "partially_structured",
            }
        ):
            continue

        layout = (
            structured.get(
                "layout"
            )
        )

        records = (
            structured.get(
                "records"
            )
            or []
        )

        # -------------------------------------------------------------------
        # key_value
        # -------------------------------------------------------------------

        if (
            layout
            == "key_value"
        ):
            for record in records:
                key = clean_text(
                    record.get(
                        "key"
                    )
                )

                value = clean_text(
                    record.get(
                        "value"
                    )
                )

                if (
                    key
                    or value
                ):
                    nonempty_values += 1

                    if (
                        key
                        and value
                    ):
                        mapped_values += 1

                    else:
                        unresolved_header_values += 1

                        mapping_issues.append(
                            f"table_index="
                            f"{table.get('table_index')} "
                            f"row="
                            f"{record.get('row_index')}: "
                            "key 또는 value가 비어 있음"
                        )

        # -------------------------------------------------------------------
        # row_records
        # -------------------------------------------------------------------

        elif (
            layout
            == "row_records"
        ):
            for record in records:

                # -----------------------------------------------------------
                # 일반 values
                # -----------------------------------------------------------

                for value_item in (
                    record.get(
                        "values"
                    )
                    or []
                ):
                    value = clean_text(
                        value_item.get(
                            "value"
                        )
                    )

                    if not value:
                        continue

                    nonempty_values += 1

                    header_path = (
                        normalize_header_path(
                            value_item.get(
                                "header_path"
                            )
                        )
                    )

                    if (
                        header_path
                        and value_item.get(
                            "status"
                        )
                        == "mapped"
                    ):
                        mapped_values += 1

                    else:
                        unresolved_header_values += 1

                        mapping_issues.append(
                            f"table_index="
                            f"{table.get('table_index')} "
                            f"row="
                            f"{record.get('row_index')} "
                            f"col="
                            f"{value_item.get('column')}: "
                            f"value={value!r}, "
                            "header_path 없음"
                        )

                # -----------------------------------------------------------
                # 가로 병합 merged_values
                # -----------------------------------------------------------

                for merged_item in (
                    record.get(
                        "merged_values"
                    )
                    or []
                ):
                    value = clean_text(
                        merged_item.get(
                            "value"
                        )
                    )

                    if not value:
                        continue

                    nonempty_values += 1

                    covered_columns = (
                        merged_item.get(
                            "covered_columns"
                        )
                        or []
                    )

                    covered_header_paths = (
                        merged_item.get(
                            "covered_header_paths"
                        )
                        or []
                    )

                    valid_header_paths = (
                        bool(
                            covered_header_paths
                        )
                        and all(
                            normalize_header_path(
                                item.get(
                                    "header_path"
                                )
                            )
                            for item
                            in covered_header_paths
                            if isinstance(
                                item,
                                dict,
                            )
                        )
                    )

                    if (
                        merged_item.get(
                            "status"
                        )
                        == "merged_data_span"
                        and covered_columns
                        and valid_header_paths
                    ):
                        mapped_values += 1

                    else:
                        unresolved_header_values += 1

                        mapping_issues.append(
                            f"table_index="
                            f"{table.get('table_index')} "
                            f"row="
                            f"{record.get('row_index')}: "
                            f"merged value={value!r}, "
                            "병합 Header 범위 정보 불완전"
                        )

    mapping_ratio = (
        mapped_values
        / nonempty_values
        if nonempty_values
        else 0.0
    )

    mapping_pass = (
        nonempty_values > 0
        and mapping_ratio
        == 1.0
    )

    mapping_warn = (
        nonempty_values == 0
        or mapping_ratio
        >= 0.9
    )

    checks.append(
        validation_item(
            "2. Header ↔ Value 연결 여부",
            passed=(
                mapping_pass
            ),
            warning=(
                not mapping_pass
                and mapping_warn
            ),
            summary=(
                f"비어 있지 않은 논리 값 "
                f"{nonempty_values}개 중 "
                f"{mapped_values}개 매핑 "
                f"({mapping_ratio:.1%}), "
                f"미해석 값 "
                f"{unresolved_header_values}개"
            ),
            details=(
                mapping_issues[
                    :30
                ]
            ),
        )
    )

    # =======================================================================
    # 3. Record 개수 검증
    # =======================================================================

    record_mismatches: list[
        str
    ] = []

    checked_record_tables = 0

    for entry in (
        table_entries
    ):
        table = (
            entry["table"]
        )

        structured = (
            table.get(
                "structured_table"
            )
            or {}
        )

        status = (
            structured.get(
                "status"
            )
        )

        layout = (
            structured.get(
                "layout"
            )
        )

        if (
            status
            not in {
                "structured",
                "partially_structured",
            }
        ):
            continue

        rows = int(
            table.get(
                "row_count",
                0,
            )
            or 0
        )

        records = (
            structured.get(
                "records"
            )
            or []
        )

        # -------------------------------------------------------------------
        # row_records
        # -------------------------------------------------------------------

        if (
            layout
            == "row_records"
        ):
            header_rows = (
                structured.get(
                    "header_rows"
                )
                or []
            )

            if not header_rows:
                continue

            expected_start = (
                max(
                    header_rows
                )
                + 1
            )

            (
                grid,
                errors,
            ) = build_grid(
                table
            )

            if errors:
                continue

            expected_nonempty_rows = 0

            cols = int(
                table.get(
                    "col_count",
                    0,
                )
                or 0
            )

            for row in range(
                expected_start,
                rows,
            ):
                has_value = False

                for col in range(
                    cols
                ):
                    ref = (
                        grid[
                            row
                        ][
                            col
                        ]
                    )

                    if (
                        ref
                        and clean_text(
                            ref.get(
                                "text"
                            )
                        )
                    ):
                        has_value = True
                        break

                if has_value:
                    expected_nonempty_rows += 1

            checked_record_tables += 1

            if (
                len(records)
                != expected_nonempty_rows
            ):
                record_mismatches.append(
                    f"table_index="
                    f"{table.get('table_index')}: "
                    f"예상 데이터 행 "
                    f"{expected_nonempty_rows}개, "
                    f"records "
                    f"{len(records)}개"
                )

        # -------------------------------------------------------------------
        # key_value
        # -------------------------------------------------------------------

        elif (
            layout
            == "key_value"
        ):
            checked_record_tables += 1

            if not records:
                record_mismatches.append(
                    f"table_index="
                    f"{table.get('table_index')}: "
                    "key_value records가 0개"
                )

    checks.append(
        validation_item(
            "3. Record 개수 검증",
            passed=(
                checked_record_tables > 0
                and not record_mismatches
            ),
            warning=(
                checked_record_tables
                == 0
            ),
            summary=(
                f"검증 대상 표 "
                f"{checked_record_tables}개, "
                f"불일치 "
                f"{len(record_mismatches)}개"
            ),
            details=(
                record_mismatches[
                    :30
                ]
            ),
        )
    )

    # =======================================================================
    # 4. 병합 셀 Header Path 복원
    # =======================================================================

    merged_header_tables = 0

    merged_header_issues: list[
        str
    ] = []

    for entry in (
        table_entries
    ):
        table = (
            entry["table"]
        )

        structured = (
            table.get(
                "structured_table"
            )
            or {}
        )

        if (
            structured.get(
                "layout"
            )
            != "row_records"
        ):
            continue

        header_rows = (
            structured.get(
                "header_rows"
            )
            or []
        )

        if not header_rows:
            continue

        merged_header_cells: list[
            dict[str, Any]
        ] = []

        for cell in (
            table.get(
                "cells"
            )
            or []
        ):
            (
                row,
                _col,
                row_span,
                col_span,
            ) = cell_range(
                cell
            )

            if (
                row
                in header_rows
                and (
                    row_span > 1
                    or col_span > 1
                )
                and clean_text(
                    cell.get(
                        "text"
                    )
                )
            ):
                merged_header_cells.append(
                    cell
                )

        if not merged_header_cells:
            continue

        merged_header_tables += 1

        columns = (
            structured.get(
                "columns"
            )
            or []
        )

        for cell in (
            merged_header_cells
        ):
            (
                _,
                col,
                _,
                col_span,
            ) = cell_range(
                cell
            )

            text_value = clean_text(
                cell.get(
                    "text"
                )
            )

            for target_col in range(
                col,
                col + col_span,
            ):
                column = next(
                    (
                        column_item
                        for column_item
                        in columns
                        if int(
                            column_item.get(
                                "column",
                                -1,
                            )
                        )
                        == target_col
                    ),
                    None,
                )

                path = (
                    column.get(
                        "header_path"
                    )
                    if column
                    else []
                )

                normalized_path = (
                    normalize_header_path(
                        path
                    )
                )

                if (
                    text_value
                    not in normalized_path
                ):
                    merged_header_issues.append(
                        f"table_index="
                        f"{table.get('table_index')} "
                        f"merged header="
                        f"{text_value!r}, "
                        f"적용 열="
                        f"{target_col}, "
                        f"실제 header_path="
                        f"{path}, "
                        f"정규화 header_path="
                        f"{normalized_path}"
                    )

    checks.append(
        validation_item(
            "4. 병합 셀 Header Path 복원",
            passed=(
                merged_header_tables > 0
                and not merged_header_issues
            ),
            warning=(
                merged_header_tables
                == 0
            ),
            summary=(
                f"병합 헤더 포함 표 "
                f"{merged_header_tables}개, "
                f"복원 문제 "
                f"{len(merged_header_issues)}개"
            ),
            details=(
                merged_header_issues[
                    :30
                ]
            ),
        )
    )

    # =======================================================================
    # 5. 원본 cells 보존 여부
    # =======================================================================

    original_missing: list[
        str
    ] = []

    empty_original: list[
        str
    ] = []

    for entry in (
        table_entries
    ):
        table = (
            entry["table"]
        )

        if (
            "cells"
            not in table
        ):
            original_missing.append(
                f"table_index="
                f"{table.get('table_index')}: "
                "cells 필드 없음"
            )

        elif not isinstance(
            table.get(
                "cells"
            ),
            list,
        ):
            original_missing.append(
                f"table_index="
                f"{table.get('table_index')}: "
                "cells가 배열이 아님"
            )

        elif (
            len(
                table.get(
                    "cells"
                )
                or []
            )
            == 0
        ):
            empty_original.append(
                f"table_index="
                f"{table.get('table_index')}: "
                "cells가 빈 배열"
            )

    checks.append(
        validation_item(
            "5. 원본 cells 보존 여부",
            passed=(
                total > 0
                and not original_missing
            ),
            warning=(
                total == 0
            ),
            summary=(
                f"전체 표 {total}개 중 "
                f"cells 누락 "
                f"{len(original_missing)}개, "
                f"빈 cells "
                f"{len(empty_original)}개"
            ),
            details=(
                (
                    original_missing
                    + empty_original
                )[
                    :30
                ]
            ),
        )
    )

    # =======================================================================
    # 6. 예외 표 처리 여부
    # =======================================================================

    exception_issues: list[
        str
    ] = []

    status_counts: dict[
        str,
        int,
    ] = {
        "structured": 0,
        "partially_structured": 0,
        "unresolved": 0,
        "skipped": 0,
        "missing": 0,
    }

    for entry in (
        table_entries
    ):
        table = (
            entry["table"]
        )

        structured = (
            table.get(
                "structured_table"
            )
            or {}
        )

        status = (
            structured.get(
                "status"
            )
            or "missing"
        )

        status_counts[
            status
        ] = (
            status_counts.get(
                status,
                0,
            )
            + 1
        )

        records = (
            structured.get(
                "records"
            )
            or []
        )

        if (
            status
            in {
                "skipped",
                "unresolved",
            }
            and records
        ):
            exception_issues.append(
                f"table_index="
                f"{table.get('table_index')}: "
                f"status={status}인데 "
                f"records "
                f"{len(records)}개 존재"
            )

        if (
            status
            == "skipped"
            and not structured.get(
                "reason"
            )
        ):
            exception_issues.append(
                f"table_index="
                f"{table.get('table_index')}: "
                "skipped 사유가 없음"
            )

        if (
            status
            in {
                "unresolved",
                "partially_structured",
            }
            and not (
                structured.get(
                    "reason"
                )
                or structured.get(
                    "unresolved_columns"
                )
            )
        ):
            exception_issues.append(
                f"table_index="
                f"{table.get('table_index')}: "
                f"status={status}인데 "
                "사유/미해석 열 기록 없음"
            )

    checks.append(
        validation_item(
            "6. 예외 표 처리 여부",
            passed=(
                not exception_issues
            ),
            warning=(
                total == 0
            ),
            summary=(
                "상태별 표 수: "
                + ", ".join(
                    f"{key}={value}"
                    for (
                        key,
                        value,
                    )
                    in status_counts.items()
                )
                + (
                    f" / 예외 처리 문제 "
                    f"{len(exception_issues)}개"
                )
            ),
            details=(
                exception_issues[
                    :30
                ]
            ),
        )
    )

    # =======================================================================
    # 7. 가로 병합 데이터 중복 매핑 여부
    #
    # 이전 문제:
    #
    # source=(4,1), value="소 계"
    # -> column 1
    # -> column 2
    # -> column 3
    # ...
    #
    # 같은 source가 한 record의 values에 여러 번 존재하면 FAIL.
    #
    # merged_values에 있는 source가 values에도 동시에 존재하면 FAIL.
    # =======================================================================

    duplicate_mapping_issues: list[
        str
    ] = []

    checked_row_records = 0

    for entry in (
        table_entries
    ):
        table = (
            entry["table"]
        )

        table_index = (
            table.get(
                "table_index"
            )
        )

        structured = (
            table.get(
                "structured_table"
            )
            or {}
        )

        if (
            structured.get(
                "layout"
            )
            != "row_records"
        ):
            continue

        for record in (
            structured.get(
                "records"
            )
            or []
        ):
            checked_row_records += 1

            row_index = (
                record.get(
                    "row_index"
                )
            )

            value_sources: dict[
                tuple[int, int],
                list[
                    dict[str, Any]
                ],
            ] = {}

            # ---------------------------------------------------------------
            # 일반 values source 수집
            # ---------------------------------------------------------------

            for value_item in (
                record.get(
                    "values"
                )
                or []
            ):
                source_key = (
                    get_source_key(
                        value_item
                    )
                )

                if source_key is None:
                    continue

                value_sources.setdefault(
                    source_key,
                    [],
                ).append(
                    value_item
                )

            # ---------------------------------------------------------------
            # 동일 source가 values 안에서 여러 Header에 매핑됐는지 검사
            # ---------------------------------------------------------------

            for (
                source_key,
                source_items,
            ) in value_sources.items():

                if (
                    len(
                        source_items
                    )
                    <= 1
                ):
                    continue

                columns = [
                    item.get(
                        "column"
                    )
                    for item
                    in source_items
                ]

                header_paths = [
                    normalize_header_path(
                        item.get(
                            "header_path"
                        )
                    )
                    for item
                    in source_items
                ]

                duplicate_mapping_issues.append(
                    f"table_index="
                    f"{table_index} "
                    f"row={row_index}: "
                    f"동일 source={source_key}가 "
                    f"values에 {len(source_items)}회 중복 매핑됨 / "
                    f"columns={columns}, "
                    f"header_paths={header_paths}"
                )

            # ---------------------------------------------------------------
            # merged_values 내부 중복 및 values와의 중복 검사
            # ---------------------------------------------------------------

            seen_merged_sources: set[
                tuple[int, int]
            ] = set()

            for merged_item in (
                record.get(
                    "merged_values"
                )
                or []
            ):
                source_key = (
                    get_source_key(
                        merged_item
                    )
                )

                if source_key is None:
                    continue

                if (
                    source_key
                    in seen_merged_sources
                ):
                    duplicate_mapping_issues.append(
                        f"table_index="
                        f"{table_index} "
                        f"row={row_index}: "
                        f"merged_values 내부에서 "
                        f"source={source_key} 중복"
                    )

                seen_merged_sources.add(
                    source_key
                )

                if (
                    source_key
                    in value_sources
                ):
                    duplicate_mapping_issues.append(
                        f"table_index="
                        f"{table_index} "
                        f"row={row_index}: "
                        f"source={source_key}가 "
                        "values와 merged_values에 동시에 존재"
                    )

    checks.append(
        validation_item(
            "7. 가로 병합 데이터 중복 매핑 여부",
            passed=(
                not duplicate_mapping_issues
            ),
            warning=False,
            summary=(
                f"row_records "
                f"{checked_row_records}개 검사, "
                f"중복 매핑 문제 "
                f"{len(duplicate_mapping_issues)}개"
            ),
            details=(
                duplicate_mapping_issues[
                    :30
                ]
            ),
        )
    )

    # =======================================================================
    # 8. merged_values 원본 및 범위 무결성
    #
    # 검사:
    # - 원본 source Cell 존재
    # - 원본 Cell이 실제 col_span > 1
    # - 원본 text와 merged value 동일
    # - col_span / row_span 일치
    # - covered_columns가 실제 병합 범위와 일치
    # - covered_header_paths의 column 범위가 일치
    # - 각 covered_header_path가 비어 있지 않음
    # =======================================================================

    merged_value_count = 0

    merged_value_issues: list[
        str
    ] = []

    for entry in (
        table_entries
    ):
        table = (
            entry["table"]
        )

        table_index = (
            table.get(
                "table_index"
            )
        )

        col_count = int(
            table.get(
                "col_count",
                0,
            )
            or 0
        )

        structured = (
            table.get(
                "structured_table"
            )
            or {}
        )

        if (
            structured.get(
                "layout"
            )
            != "row_records"
        ):
            continue

        origin_map = (
            build_origin_cell_map(
                table
            )
        )

        for record in (
            structured.get(
                "records"
            )
            or []
        ):
            row_index_raw = (
                record.get(
                    "row_index"
                )
            )

            try:
                row_index = int(
                    row_index_raw
                )

            except (
                TypeError,
                ValueError,
            ):
                row_index = -1

            for merged_item in (
                record.get(
                    "merged_values"
                )
                or []
            ):
                merged_value_count += 1

                source_key = (
                    get_source_key(
                        merged_item
                    )
                )

                value = clean_text(
                    merged_item.get(
                        "value"
                    )
                )

                # -----------------------------------------------------------
                # source 존재 여부
                # -----------------------------------------------------------

                if source_key is None:
                    merged_value_issues.append(
                        f"table_index="
                        f"{table_index} "
                        f"row={row_index}: "
                        f"merged value={value!r}, "
                        "source 좌표 없음"
                    )

                    continue

                origin_cell = (
                    origin_map.get(
                        source_key
                    )
                )

                if origin_cell is None:
                    merged_value_issues.append(
                        f"table_index="
                        f"{table_index} "
                        f"row={row_index}: "
                        f"source={source_key}에 "
                        "해당하는 원본 Cell 없음"
                    )

                    continue

                (
                    origin_row,
                    origin_col,
                    origin_row_span,
                    origin_col_span,
                ) = cell_range(
                    origin_cell
                )

                # -----------------------------------------------------------
                # 원본이 실제 가로 병합 Cell인지 확인
                # -----------------------------------------------------------

                if (
                    origin_col_span
                    <= 1
                ):
                    merged_value_issues.append(
                        f"table_index="
                        f"{table_index} "
                        f"row={row_index}: "
                        f"source={source_key}, "
                        f"원본 col_span="
                        f"{origin_col_span}인데 "
                        "merged_values에 저장됨"
                    )

                # -----------------------------------------------------------
                # 원본 Text 일치
                # -----------------------------------------------------------

                origin_text = clean_text(
                    origin_cell.get(
                        "text"
                    )
                )

                if (
                    origin_text
                    != value
                ):
                    merged_value_issues.append(
                        f"table_index="
                        f"{table_index} "
                        f"row={row_index}: "
                        f"source={source_key}, "
                        f"원본 value={origin_text!r}, "
                        f"merged value={value!r}"
                    )

                # -----------------------------------------------------------
                # row_span / col_span 일치
                # -----------------------------------------------------------

                merged_row_span = int(
                    merged_item.get(
                        "row_span",
                        1,
                    )
                    or 1
                )

                merged_col_span = int(
                    merged_item.get(
                        "col_span",
                        1,
                    )
                    or 1
                )

                if (
                    merged_row_span
                    != origin_row_span
                ):
                    merged_value_issues.append(
                        f"table_index="
                        f"{table_index} "
                        f"row={row_index}: "
                        f"source={source_key}, "
                        f"row_span 불일치 "
                        f"원본={origin_row_span}, "
                        f"merged={merged_row_span}"
                    )

                if (
                    merged_col_span
                    != origin_col_span
                ):
                    merged_value_issues.append(
                        f"table_index="
                        f"{table_index} "
                        f"row={row_index}: "
                        f"source={source_key}, "
                        f"col_span 불일치 "
                        f"원본={origin_col_span}, "
                        f"merged={merged_col_span}"
                    )

                # -----------------------------------------------------------
                # 현재 record row가 원본 병합 범위 안에 있는지 확인
                # -----------------------------------------------------------

                if not (
                    origin_row
                    <= row_index
                    < (
                        origin_row
                        + origin_row_span
                    )
                ):
                    merged_value_issues.append(
                        f"table_index="
                        f"{table_index} "
                        f"row={row_index}: "
                        f"source={source_key}, "
                        "record row가 원본 row_span 범위를 벗어남"
                    )

                # -----------------------------------------------------------
                # covered_columns 검증
                # -----------------------------------------------------------

                expected_columns = list(
                    range(
                        origin_col,
                        min(
                            origin_col
                            + origin_col_span,
                            col_count,
                        ),
                    )
                )

                covered_columns_raw = (
                    merged_item.get(
                        "covered_columns"
                    )
                    or []
                )

                covered_columns: list[
                    int
                ] = []

                try:
                    covered_columns = [
                        int(column)
                        for column
                        in covered_columns_raw
                    ]

                except (
                    TypeError,
                    ValueError,
                ):
                    covered_columns = []

                if (
                    covered_columns
                    != expected_columns
                ):
                    merged_value_issues.append(
                        f"table_index="
                        f"{table_index} "
                        f"row={row_index}: "
                        f"source={source_key}, "
                        f"covered_columns 불일치 "
                        f"예상={expected_columns}, "
                        f"실제={covered_columns}"
                    )

                # -----------------------------------------------------------
                # covered_header_paths 검증
                # -----------------------------------------------------------

                covered_header_paths = (
                    merged_item.get(
                        "covered_header_paths"
                    )
                    or []
                )

                header_path_columns: list[
                    int
                ] = []

                empty_header_columns: list[
                    int
                ] = []

                for header_info in (
                    covered_header_paths
                ):
                    if not isinstance(
                        header_info,
                        dict,
                    ):
                        continue

                    column_raw = (
                        header_info.get(
                            "column"
                        )
                    )

                    try:
                        column = int(
                            column_raw
                        )

                    except (
                        TypeError,
                        ValueError,
                    ):
                        continue

                    header_path_columns.append(
                        column
                    )

                    normalized_path = (
                        normalize_header_path(
                            header_info.get(
                                "header_path"
                            )
                        )
                    )

                    if not normalized_path:
                        empty_header_columns.append(
                            column
                        )

                if (
                    header_path_columns
                    != expected_columns
                ):
                    merged_value_issues.append(
                        f"table_index="
                        f"{table_index} "
                        f"row={row_index}: "
                        f"source={source_key}, "
                        "covered_header_paths 열 범위 불일치 "
                        f"예상={expected_columns}, "
                        f"실제={header_path_columns}"
                    )

                if (
                    empty_header_columns
                ):
                    merged_value_issues.append(
                        f"table_index="
                        f"{table_index} "
                        f"row={row_index}: "
                        f"source={source_key}, "
                        "빈 header_path가 존재하는 열="
                        f"{empty_header_columns}"
                    )

                # -----------------------------------------------------------
                # status 검증
                # -----------------------------------------------------------

                if (
                    merged_item.get(
                        "status"
                    )
                    != "merged_data_span"
                ):
                    merged_value_issues.append(
                        f"table_index="
                        f"{table_index} "
                        f"row={row_index}: "
                        f"source={source_key}, "
                        "merged_values status가 "
                        "merged_data_span이 아님"
                    )

    checks.append(
        validation_item(
            "8. merged_values 원본 및 범위 무결성",
            passed=(
                not merged_value_issues
            ),
            warning=False,
            summary=(
                f"merged_values "
                f"{merged_value_count}개 검사, "
                f"무결성 문제 "
                f"{len(merged_value_issues)}개"
            ),
            details=(
                merged_value_issues[
                    :30
                ]
            ),
        )
    )

    # =======================================================================
    # 전체 판정
    # =======================================================================

    pass_count = sum(
        check[
            "status"
        ]
        == "PASS"
        for check
        in checks
    )

    warn_count = sum(
        check[
            "status"
        ]
        == "WARN"
        for check
        in checks
    )

    fail_count = sum(
        check[
            "status"
        ]
        == "FAIL"
        for check
        in checks
    )

    if fail_count:
        overall = "FAIL"

    elif warn_count:
        overall = "WARN"

    else:
        overall = "PASS"

    return {
        "overall_status": overall,
        "summary": {
            "total_tables": total,
            "pass": pass_count,
            "warn": warn_count,
            "fail": fail_count,
        },
        "checks": checks,
        "note": (
            "자동 검증은 구조적 누락, Header-Value 연결, "
            "병합 셀 복원 및 가로 병합 데이터 중복을 확인합니다. "
            "대표 표는 원본 HWP/HWPX와 직접 대조해야 합니다."
        ),
    }


# ===========================================================================
# 검증 결과 출력
# ===========================================================================

def print_validation_report(
    report: dict[str, Any],
) -> None:
    """터미널에 검증 결과를 출력한다."""

    line = (
        "="
        * 76
    )

    print(
        "\n"
        + line
    )

    print(
        "3단계 최종 구조화 검증 결과"
    )

    print(
        line
    )

    for check in (
        report.get(
            "checks",
            [],
        )
    ):
        print(
            f"[{check['status']}] "
            f"{check['name']}"
        )

        print(
            f"  "
            f"{check['summary']}"
        )

        details = (
            check.get(
                "details"
            )
            or []
        )

        for detail in (
            details[
                :10
            ]
        ):
            print(
                f"   - "
                f"{detail}"
            )

        if (
            len(details)
            > 10
        ):
            print(
                f"   - ... 외 "
                f"{len(details) - 10}건"
            )

        print()

    summary = (
        report.get(
            "summary",
            {},
        )
    )

    print(
        line
    )

    print(
        f"최종 판정: "
        f"{report.get('overall_status')} | "
        f"PASS "
        f"{summary.get('pass', 0)} / "
        f"WARN "
        f"{summary.get('warn', 0)} / "
        f"FAIL "
        f"{summary.get('fail', 0)}"
    )

    print(
        f"검증한 표: "
        f"{summary.get('total_tables', 0)}개"
    )

    print(
        report.get(
            "note",
            "",
        )
    )

    print(
        line
        + "\n"
    )


# ===========================================================================
# 입력 파일 선택
# ===========================================================================

def select_step3_json() -> str | None:
    """Step 3 최종 JSON 파일을 선택한다."""

    root = Tk()

    root.withdraw()

    root.attributes(
        "-topmost",
        True,
    )

    selected = askopenfilename(
        title=(
            "3단계 최종 JSON 선택"
        ),
        filetypes=[
            (
                "3단계 최종 JSON",
                "*_step3-3_structured_tables.json",
            ),
            (
                "JSON Files",
                "*.json",
            ),
        ],
    )

    root.destroy()

    return (
        selected
        or None
    )


# ===========================================================================
# 실행
# ===========================================================================

def main() -> None:
    input_path = (
        select_step3_json()
    )

    if not input_path:
        print(
            "JSON 파일을 선택하지 않았습니다."
        )

        return

    try:
        with open(
            input_path,
            "r",
            encoding="utf-8",
        ) as file:
            final_doc = (
                json.load(
                    file
                )
            )

    except (
        OSError,
        json.JSONDecodeError,
    ) as error:
        messagebox.showerror(
            "검증 실패",
            str(error),
        )

        raise

    report = (
        validate_step3(
            final_doc
        )
    )

    print(
        f"\n검증 파일: "
        f"{input_path}"
    )

    print_validation_report(
        report
    )

    messagebox.showinfo(
        "검증 완료",
        (
            "터미널에 검증 결과를 출력했습니다.\n\n"
            f"최종 판정: "
            f"{report.get('overall_status')}"
        ),
    )


if __name__ == "__main__":
    main()