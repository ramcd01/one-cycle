from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any, Iterable


ACCESSIBILITY_KEYWORDS = (
    "장애인편의증진시설",
    "장애인편의시설",
    "편의증진시설",
)


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n+", "\n", text)
    return text.strip()


def compact_text(value: Any) -> str:
    return re.sub(r"\s+", "", clean_text(value))


def iter_sections(sections: Iterable[dict[str, Any]]) -> Iterable[dict[str, Any]]:
    for section in sections or []:
        if not isinstance(section, dict):
            continue
        yield section
        yield from iter_sections(section.get("children") or [])


def assign_accessibility_domain(document: dict[str, Any]) -> int:
    """Step 2에서 미분류된 접근성·장애인 편의시설 Section을 보완한다."""
    changed = 0
    resolved_ids: set[str] = set()

    for section in iter_sections(document.get("sections") or []):
        if section.get("domain"):
            continue

        title = compact_text(
            section.get("normalized_title")
            or section.get("title")
        )

        matched_keyword = next(
            (
                keyword
                for keyword in ACCESSIBILITY_KEYWORDS
                if compact_text(keyword) in title
            ),
            None,
        )

        if not matched_keyword:
            continue

        section["domain"] = {
            "category": "facility",
            "topic": "accessibility_facilities",
            "matched_keyword": matched_keyword,
        }
        section_id = str(section.get("section_id") or "")
        if section_id:
            resolved_ids.add(section_id)
        changed += 1

    unresolved = document.get("domain_unresolved")
    if isinstance(unresolved, list) and resolved_ids:
        document["domain_unresolved"] = [
            item
            for item in unresolved
            if str(item.get("section_id") or "") not in resolved_ids
        ]

    if changed:
        method = document.setdefault("domain_tagging_method", {})
        method["postprocessing"] = {
            "version": "accessibility-domain-v1",
            "resolved_count": changed,
            "rule": (
                "장애인 편의증진시설 관련 제목을 "
                "facility/accessibility_facilities로 보완"
            ),
        }

    return changed


def _cell_range(cell: dict[str, Any]) -> tuple[int, int, int, int]:
    return (
        int(cell.get("row", 0) or 0),
        int(cell.get("col", 0) or 0),
        max(1, int(cell.get("row_span", 1) or 1)),
        max(1, int(cell.get("col_span", 1) or 1)),
    )


def build_grid(
    table: dict[str, Any],
) -> tuple[list[list[dict[str, Any] | None]], list[str]]:
    rows = int(table.get("row_count", 0) or 0)
    cols = int(table.get("col_count", 0) or 0)

    grid: list[list[dict[str, Any] | None]] = [
        [None for _ in range(cols)]
        for _ in range(rows)
    ]
    errors: list[str] = []

    for cell in table.get("cells") or []:
        if not isinstance(cell, dict):
            continue

        row, col, row_span, col_span = _cell_range(cell)
        if (
            row < 0
            or col < 0
            or row + row_span > rows
            or col + col_span > cols
        ):
            errors.append(
                "병합 범위 초과: "
                f"row={row}, col={col}, "
                f"row_span={row_span}, col_span={col_span}"
            )
            continue

        ref = {
            "origin_row": row,
            "origin_col": col,
            "row_span": row_span,
            "col_span": col_span,
            "text": clean_text(cell.get("text")),
        }

        for target_row in range(row, row + row_span):
            for target_col in range(col, col + col_span):
                if grid[target_row][target_col] is not None:
                    existing = grid[target_row][target_col]
                    if (
                        existing.get("origin_row") != row
                        or existing.get("origin_col") != col
                    ):
                        errors.append(
                            "셀 범위 겹침: "
                            f"row={target_row}, col={target_col}"
                        )
                grid[target_row][target_col] = ref

    return grid, errors


def ref_source(ref: dict[str, Any] | None) -> dict[str, int] | None:
    if not ref:
        return None
    return {
        "row": int(ref.get("origin_row", 0)),
        "col": int(ref.get("origin_col", 0)),
    }


def grid_text(
    grid: list[list[dict[str, Any] | None]],
    row: int,
    col: int,
) -> str:
    if row < 0 or col < 0:
        return ""
    if row >= len(grid) or col >= len(grid[row]):
        return ""
    ref = grid[row][col]
    return clean_text(ref.get("text")) if ref else ""


def detect_row_kind(values: list[str]) -> str:
    joined = compact_text(" ".join(values))
    if any(word in joined for word in ("총계", "합계", "계")):
        return "total"
    if any(word in joined for word in ("소계", "소계금액")):
        return "subtotal"
    return "data"


def make_columns(labels: list[str]) -> list[dict[str, Any]]:
    return [
        {
            "column": index,
            "header_path": [label],
        }
        for index, label in enumerate(labels)
    ]


def build_transposed_records(
    table: dict[str, Any],
    grid: list[list[dict[str, Any] | None]],
    *,
    label_start_row: int,
    orientation: str,
) -> dict[str, Any] | None:
    """첫 열이 필드명이고 나머지 열이 레코드인 가로형 표를 전치한다."""
    rows = int(table.get("row_count", 0) or 0)
    cols = int(table.get("col_count", 0) or 0)

    if rows - label_start_row < 2 or cols < 3:
        return None

    labels = [
        grid_text(grid, row, 0)
        for row in range(label_start_row, rows)
    ]

    if any(not label for label in labels):
        return None

    records: list[dict[str, Any]] = []

    for col in range(1, cols):
        values: list[dict[str, Any]] = []

        for relative_index, row in enumerate(
            range(label_start_row, rows)
        ):
            value = grid_text(grid, row, col)
            if not value:
                continue

            ref = grid[row][col]
            values.append(
                {
                    "column": relative_index,
                    "header_path": [labels[relative_index]],
                    "value": value,
                    "source": ref_source(ref),
                    "inherited_from_row_span": bool(
                        ref and int(ref.get("origin_row", row)) < row
                    ),
                }
            )

        if not values:
            continue

        records.append(
            {
                "row_index": col,
                "record_index": col - 1,
                "row_kind": detect_row_kind(
                    [str(item.get("value") or "") for item in values]
                ),
                "values": values,
                "merged_values": [],
            }
        )

    if not records:
        return None

    return {
        "status": "structured",
        "layout": "row_records",
        "orientation": orientation,
        "header_rows": list(range(label_start_row, rows)),
        "columns": make_columns(labels),
        "records": records,
        "postprocessed": True,
    }


def build_schedule_records(
    table: dict[str, Any],
    grid: list[list[dict[str, Any] | None]],
) -> dict[str, Any] | None:
    """도입부의 3행×2열 공고·계약 일정 표를 열 단위 레코드로 전환한다."""
    rows = int(table.get("row_count", 0) or 0)
    cols = int(table.get("col_count", 0) or 0)

    if rows != 3 or cols != 2:
        return None

    second_row = " ".join(
        grid_text(grid, 1, col)
        for col in range(cols)
    )
    if not re.search(r"\d{2,4}[.\-/]\d{1,2}", second_row):
        return None

    labels = ["구분", "일정", "장소"]
    records: list[dict[str, Any]] = []

    for col in range(cols):
        values: list[dict[str, Any]] = []
        for row, label in enumerate(labels):
            value = grid_text(grid, row, col)
            if not value:
                continue
            values.append(
                {
                    "column": row,
                    "header_path": [label],
                    "value": value,
                    "source": ref_source(grid[row][col]),
                    "inherited_from_row_span": False,
                }
            )

        if values:
            records.append(
                {
                    "row_index": col,
                    "record_index": col,
                    "row_kind": "data",
                    "values": values,
                    "merged_values": [],
                }
            )

    if not records:
        return None

    return {
        "status": "structured",
        "layout": "row_records",
        "orientation": "transposed_schedule",
        "header_rows": [],
        "columns": make_columns(labels),
        "records": records,
        "postprocessed": True,
    }



def looks_like_standard_header_row(
    table: dict[str, Any],
    grid: list[list[dict[str, Any] | None]],
) -> bool:
    rows = int(table.get("row_count", 0) or 0)
    cols = int(table.get("col_count", 0) or 0)
    if rows < 2 or cols < 2:
        return False

    first_row_cells = [
        cell
        for cell in table.get("cells") or []
        if int(cell.get("row", 0) or 0) == 0
    ]
    if len(first_row_cells) < max(2, cols // 2):
        return False

    labels = [grid_text(grid, 0, col) for col in range(cols)]
    nonempty = [label for label in labels if label]
    if len(nonempty) < max(2, cols // 2):
        return False

    numeric_like = sum(
        bool(re.search(r"\d", label))
        for label in nonempty
    )
    long_count = sum(len(label) > 30 for label in nonempty)

    return (
        numeric_like <= max(1, len(nonempty) // 3)
        and long_count == 0
    )


def build_standard_row_records(
    table: dict[str, Any],
    grid: list[list[dict[str, Any] | None]],
) -> dict[str, Any] | None:
    """첫 행을 Header로 사용하고 row_span 값을 각 데이터 행에 상속한다."""
    rows = int(table.get("row_count", 0) or 0)
    cols = int(table.get("col_count", 0) or 0)

    if rows < 2 or cols < 2:
        return None

    labels = [
        grid_text(grid, 0, col)
        for col in range(cols)
    ]
    if sum(bool(label) for label in labels) < max(2, cols // 2):
        return None

    records: list[dict[str, Any]] = []

    for row in range(1, rows):
        values: list[dict[str, Any]] = []
        merged_values: list[dict[str, Any]] = []
        seen_merged: set[tuple[int, int]] = set()

        for col in range(cols):
            ref = grid[row][col]
            value = clean_text(ref.get("text")) if ref else ""
            if not value:
                continue

            origin_row = int(ref.get("origin_row", row))
            origin_col = int(ref.get("origin_col", col))
            col_span = int(ref.get("col_span", 1) or 1)
            row_span = int(ref.get("row_span", 1) or 1)

            if col_span > 1:
                source_key = (origin_row, origin_col)
                if source_key in seen_merged:
                    continue
                seen_merged.add(source_key)

                covered_columns = list(
                    range(origin_col, min(cols, origin_col + col_span))
                )
                merged_values.append(
                    {
                        "value": value,
                        "source": {
                            "row": origin_row,
                            "col": origin_col,
                        },
                        "row_span": row_span,
                        "col_span": col_span,
                        "covered_columns": covered_columns,
                        "covered_header_paths": [
                            {
                                "column": covered_col,
                                "header_path": [
                                    labels[covered_col]
                                    or f"열 {covered_col}"
                                ],
                            }
                            for covered_col in covered_columns
                        ],
                        "inherited_from_row_span": origin_row < row,
                    }
                )
                continue

            label = labels[col] or f"열 {col}"
            values.append(
                {
                    "column": col,
                    "header_path": [label],
                    "value": value,
                    "source": {
                        "row": origin_row,
                        "col": origin_col,
                    },
                    "inherited_from_row_span": origin_row < row,
                }
            )

        if not values and not merged_values:
            continue

        all_values = [
            str(item.get("value") or "")
            for item in [*values, *merged_values]
        ]
        records.append(
            {
                "row_index": row,
                "row_kind": detect_row_kind(all_values),
                "values": values,
                "merged_values": merged_values,
            }
        )

    if not records:
        return None

    return {
        "status": "structured",
        "layout": "row_records",
        "orientation": "standard_rows_with_rowspan_inheritance",
        "header_rows": [0],
        "columns": make_columns(
            [
                label or f"열 {index}"
                for index, label in enumerate(labels)
            ]
        ),
        "records": records,
        "postprocessed": True,
    }


def structure_unresolved_table(
    table: dict[str, Any],
) -> tuple[dict[str, Any] | None, str | None]:
    rows = int(table.get("row_count", 0) or 0)
    cols = int(table.get("col_count", 0) or 0)

    if rows <= 0 or cols <= 0:
        return None, "행·열 수가 없어 후처리할 수 없음"

    grid, errors = build_grid(table)
    if errors:
        return None, "; ".join(errors)

    # 문서 제목처럼 단일 셀뿐인 표는 의도적으로 fallback 유지.
    if rows == 1 and cols == 1:
        return None, "단일 셀 제목·레이아웃 표는 fallback 유지"

    schedule = build_schedule_records(table, grid)
    if schedule:
        return schedule, None

    # 첫 행 전체 병합 제목이 있는 가로형 표
    first_row_cells = [
        cell
        for cell in table.get("cells") or []
        if int(cell.get("row", 0) or 0) == 0
    ]
    title_row = (
        len(first_row_cells) == 1
        and int(first_row_cells[0].get("col_span", 1) or 1) >= cols
    )

    if title_row:
        transposed = build_transposed_records(
            table,
            grid,
            label_start_row=1,
            orientation="transposed_columns_with_title",
        )
        if transposed:
            transposed["table_title"] = clean_text(
                first_row_cells[0].get("text")
            )
            return transposed, None

    if looks_like_standard_header_row(table, grid):
        standard = build_standard_row_records(table, grid)
        if standard:
            return standard, None

    transposed = build_transposed_records(
        table,
        grid,
        label_start_row=0,
        orientation="transposed_columns",
    )
    if transposed:
        return transposed, None

    return None, "지원 가능한 후처리 표 패턴과 일치하지 않음"


def iter_tables(
    document: dict[str, Any],
) -> Iterable[tuple[str, list[str], int, dict[str, Any]]]:
    for index, content in enumerate(document.get("intro") or []):
        if isinstance(content, dict) and content.get("type") == "table":
            yield "intro", ["문서 도입부"], index, content

    def walk(
        sections: Iterable[dict[str, Any]],
        path: list[str],
    ) -> Iterable[tuple[str, list[str], int, dict[str, Any]]]:
        for section in sections or []:
            if not isinstance(section, dict):
                continue
            title = clean_text(
                section.get("normalized_title")
                or section.get("title")
            )
            section_path = [*path, title] if title else list(path)

            for index, content in enumerate(section.get("contents") or []):
                if (
                    isinstance(content, dict)
                    and content.get("type") == "table"
                ):
                    yield (
                        str(section.get("section_id") or ""),
                        section_path,
                        index,
                        content,
                    )

            yield from walk(
                section.get("children") or [],
                section_path,
            )

    yield from walk(document.get("sections") or [], [])


def finalize_structured_document(
    document: dict[str, Any],
) -> dict[str, Any]:
    """Step 3 최종 JSON의 도메인·intro 표·unresolved 표를 보완한다."""
    assign_accessibility_domain(document)
    resolved_table_indexes: set[int] = set()
    details: list[dict[str, Any]] = []

    for section_id, section_path, content_index, table in iter_tables(document):
        structured = table.get("structured_table") or {}
        if (
            structured.get("status") == "structured"
            and structured.get("layout") in {"row_records", "key_value"}
        ):
            continue

        replacement, reason = structure_unresolved_table(table)
        table_index = int(table.get("table_index", -1))

        if replacement:
            replacement["postprocess_source"] = {
                "section_id": section_id,
                "section_path": copy.deepcopy(section_path),
                "content_index": content_index,
            }
            table["structured_table"] = replacement
            resolved_table_indexes.add(table_index)
            details.append(
                {
                    "table_index": table_index,
                    "status": "structured",
                    "layout": replacement.get("layout"),
                    "orientation": replacement.get("orientation"),
                    "section_id": section_id,
                }
            )
        else:
            details.append(
                {
                    "table_index": table_index,
                    "status": "unchanged",
                    "reason": reason,
                    "section_id": section_id,
                }
            )

    unresolved = document.get("table_unresolved")
    if isinstance(unresolved, list) and resolved_table_indexes:
        document["table_unresolved"] = [
            item
            for item in unresolved
            if int(item.get("table_index", -1)) not in resolved_table_indexes
        ]

    method = document.setdefault("table_structuring_method", {})
    method["postprocessing"] = {
        "version": "step3-postprocess-v1",
        "resolved_table_count": len(resolved_table_indexes),
        "resolved_table_indexes": sorted(resolved_table_indexes),
        "details": details,
        "rules": [
            "intro 표도 Step 3 최종 결과에서 검사",
            "첫 열이 필드명인 가로형 표를 열 단위 레코드로 전치",
            "3행×2열 일정표를 구분·일정·장소 레코드로 전치",
            "첫 행 Header 표에서 row_span 값을 데이터 행에 상속",
            "단일 셀 제목 표는 fallback으로 유지",
        ],
    }

    return document


def update_json_file(
    path: str | Path,
    transform,
) -> dict[str, Any]:
    target = Path(path)
    with target.open("r", encoding="utf-8") as file:
        data = json.load(file)

    transform(data)

    with target.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)

    return data


def finalize_step2_file(path: str | Path) -> dict[str, Any]:
    return update_json_file(path, assign_accessibility_domain)


def finalize_step3_file(path: str | Path) -> dict[str, Any]:
    return update_json_file(path, finalize_structured_document)

# >>> HANCOM_V2_RECURSIVE_TABLE_PATCH >>>
try:
    from .finalize_structure_v2 import install_v2_overrides
except ImportError:
    from finalize_structure_v2 import install_v2_overrides

install_v2_overrides(globals())
# <<< HANCOM_V2_RECURSIVE_TABLE_PATCH <<<
