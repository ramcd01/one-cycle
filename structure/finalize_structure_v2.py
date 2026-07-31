"""finalize_structure.py용 2차 재귀 중첩 표 패치.

기존 finalize_structure.py의 표 판별/후처리 함수를 그대로 재사용하고,
intro/Section/table cell blocks 전체를 재귀 순회하도록 최종 함수만 교체한다.
"""

from __future__ import annotations

import copy
from typing import Any, Iterable, Iterator


_SKIP_RECURSIVE_KEYS = {
    "structured_table",
    "source",
    "domain",
    "hierarchy_method",
    "table_structuring_method",
    "domain_tagging_method",
}


def _safe_int(value: Any, default: int = -1) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _table_key(table: dict[str, Any]) -> tuple[str, Any]:
    table_index = table.get("table_index")
    if table_index not in (None, ""):
        return ("table_index", str(table_index))
    return ("object", id(table))


def _iter_tables_in_value(
    value: Any,
    *,
    section_id: str,
    section_path: list[str],
    content_index: int,
    object_path: list[str],
    nested_depth: int,
    seen_objects: set[int],
) -> Iterator[dict[str, Any]]:
    if isinstance(value, list):
        for index, child in enumerate(value):
            yield from _iter_tables_in_value(
                child,
                section_id=section_id,
                section_path=section_path,
                content_index=content_index,
                object_path=[*object_path, f"list:{index}"],
                nested_depth=nested_depth,
                seen_objects=seen_objects,
            )
        return

    if not isinstance(value, dict):
        return

    object_id = id(value)
    if object_id in seen_objects:
        return
    seen_objects.add(object_id)

    is_table = value.get("type") == "table"
    current_depth = nested_depth

    if is_table:
        yield {
            "section_id": section_id,
            "section_path": copy.deepcopy(section_path),
            "content_index": content_index,
            "table": value,
            "object_path": copy.deepcopy(object_path),
            "nested_depth": nested_depth,
        }
        current_depth = nested_depth + 1

        # 중첩 표는 cell.blocks를 원문 행·열 순서로 우선 순회한다.
        cells = [
            cell
            for cell in value.get("cells") or []
            if isinstance(cell, dict)
        ]
        cells.sort(
            key=lambda cell: (
                _safe_int(cell.get("row"), 0),
                _safe_int(cell.get("col", cell.get("column")), 0),
            )
        )
        for cell in cells:
            row = _safe_int(cell.get("row"), 0)
            col = _safe_int(cell.get("col", cell.get("column")), 0)
            blocks = cell.get("blocks") or []
            yield from _iter_tables_in_value(
                blocks,
                section_id=section_id,
                section_path=section_path,
                content_index=content_index,
                object_path=[*object_path, f"cell:{row},{col}", "blocks"],
                nested_depth=current_depth,
                seen_objects=seen_objects,
            )
        return

    # table 이외 wrapper 안에 blocks/content가 들어 있는 경우도 보존적으로 탐색한다.
    for key, child in value.items():
        if key in _SKIP_RECURSIVE_KEYS:
            continue
        if isinstance(child, (dict, list)):
            yield from _iter_tables_in_value(
                child,
                section_id=section_id,
                section_path=section_path,
                content_index=content_index,
                object_path=[*object_path, str(key)],
                nested_depth=current_depth,
                seen_objects=seen_objects,
            )


def iter_tables_recursive(document: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """intro와 모든 Section의 table/cell.blocks를 재귀 순회한다."""
    seen_objects: set[int] = set()

    for content_index, content in enumerate(document.get("intro") or []):
        yield from _iter_tables_in_value(
            content,
            section_id="intro",
            section_path=["문서 도입부"],
            content_index=content_index,
            object_path=["intro", str(content_index)],
            nested_depth=0,
            seen_objects=seen_objects,
        )

    def walk_sections(
        sections: Iterable[dict[str, Any]],
        parent_path: list[str],
    ) -> Iterator[dict[str, Any]]:
        for section in sections or []:
            if not isinstance(section, dict):
                continue

            title = str(
                section.get("normalized_title")
                or section.get("title")
                or ""
            ).strip()
            section_path = [*parent_path, *([title] if title else [])]
            section_id = str(section.get("section_id") or "")

            for content_index, content in enumerate(section.get("contents") or []):
                yield from _iter_tables_in_value(
                    content,
                    section_id=section_id,
                    section_path=section_path,
                    content_index=content_index,
                    object_path=[section_id or "section", "contents", str(content_index)],
                    nested_depth=0,
                    seen_objects=seen_objects,
                )

            yield from walk_sections(section.get("children") or [], section_path)

    yield from walk_sections(document.get("sections") or [], [])


def install_v2_overrides(namespace: dict[str, Any]) -> None:
    """기존 finalize_structure 모듈 namespace에 재귀 최종화 함수를 설치한다."""
    original_finalize = namespace.get("finalize_structured_document")
    structure_unresolved_table = namespace.get("structure_unresolved_table")

    if not callable(original_finalize):
        raise RuntimeError("기존 finalize_structured_document 함수를 찾을 수 없습니다.")
    if not callable(structure_unresolved_table):
        raise RuntimeError("기존 structure_unresolved_table 함수를 찾을 수 없습니다.")

    def iter_tables_compat(document: dict[str, Any]):
        for record in iter_tables_recursive(document):
            yield (
                record["section_id"],
                record["section_path"],
                record["content_index"],
                record["table"],
            )

    def finalize_structured_document_v2(document: dict[str, Any]) -> dict[str, Any]:
        # 기존 접근성 도메인/일반 표 후처리를 먼저 그대로 수행한다.
        original_finalize(document)

        method = document.setdefault("table_structuring_method", {})
        previous_post = method.get("postprocessing")
        if not isinstance(previous_post, dict):
            previous_post = {}

        previous_details = list(previous_post.get("details") or [])
        previous_resolved = {
            str(value)
            for value in previous_post.get("resolved_table_indexes") or []
        }
        previously_recorded = {
            str(item.get("table_index"))
            for item in previous_details
            if isinstance(item, dict) and item.get("table_index") is not None
        }

        resolved_indexes = set(previous_resolved)
        details = previous_details
        processed_keys: set[tuple[str, Any]] = set()
        nested_seen = 0
        nested_resolved = 0

        for record in iter_tables_recursive(document):
            table = record["table"]
            key = _table_key(table)
            if key in processed_keys:
                continue
            processed_keys.add(key)

            table_index = table.get("table_index")
            table_index_key = str(table_index) if table_index is not None else None
            nested_depth = int(record.get("nested_depth") or 0)

            # 기존 finalizer가 기록한 최상위 표는 중복 후처리하지 않는다.
            if nested_depth == 0 and table_index_key in previously_recorded:
                continue

            if nested_depth > 0:
                nested_seen += 1

            structured = table.get("structured_table") or {}
            if (
                isinstance(structured, dict)
                and structured.get("status") in {"structured", "partially_structured"}
                and structured.get("layout") in {"row_records", "key_value"}
            ):
                details.append(
                    {
                        "table_index": table_index,
                        "status": "already_structured",
                        "layout": structured.get("layout"),
                        "section_id": record["section_id"],
                        "nested_depth": nested_depth,
                        "object_path": record["object_path"],
                    }
                )
                continue

            replacement, reason = structure_unresolved_table(table)
            if replacement:
                replacement["postprocess_source"] = {
                    "section_id": record["section_id"],
                    "section_path": copy.deepcopy(record["section_path"]),
                    "content_index": record["content_index"],
                    "object_path": copy.deepcopy(record["object_path"]),
                    "nested_depth": nested_depth,
                }
                replacement["nested_table"] = nested_depth > 0
                table["structured_table"] = replacement

                if table_index_key is not None:
                    resolved_indexes.add(table_index_key)
                if nested_depth > 0:
                    nested_resolved += 1

                details.append(
                    {
                        "table_index": table_index,
                        "status": "structured",
                        "layout": replacement.get("layout"),
                        "orientation": replacement.get("orientation"),
                        "section_id": record["section_id"],
                        "nested_depth": nested_depth,
                        "object_path": record["object_path"],
                    }
                )
            else:
                details.append(
                    {
                        "table_index": table_index,
                        "status": "unchanged",
                        "reason": reason,
                        "section_id": record["section_id"],
                        "nested_depth": nested_depth,
                        "object_path": record["object_path"],
                    }
                )

        unresolved = document.get("table_unresolved")
        if isinstance(unresolved, list) and resolved_indexes:
            document["table_unresolved"] = [
                item
                for item in unresolved
                if str(item.get("table_index")) not in resolved_indexes
            ]

        resolved_values: list[Any] = []
        for value in sorted(resolved_indexes):
            try:
                resolved_values.append(int(value))
            except (TypeError, ValueError):
                resolved_values.append(value)

        method["postprocessing"] = {
            **previous_post,
            "version": "step3-postprocess-v2-recursive-nested-table",
            "resolved_table_count": len(resolved_values),
            "resolved_table_indexes": resolved_values,
            "nested_table_count": nested_seen,
            "nested_table_resolved_count": nested_resolved,
            "details": details,
            "rules": [
                *list(previous_post.get("rules") or []),
                "intro와 모든 Section의 table을 재귀 순회",
                "각 cell.blocks 내부 nested table을 독립적으로 구조화",
                "table_index 기준 중복 처리 방지",
                "부모 표가 fallback이어도 nested table 구조화 유지",
            ],
        }
        return document

    namespace["iter_tables"] = iter_tables_compat
    namespace["iter_tables_recursive"] = iter_tables_recursive
    namespace["finalize_structured_document"] = finalize_structured_document_v2
