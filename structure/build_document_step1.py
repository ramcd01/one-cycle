#!/usr/bin/env python3
"""문서 계층 구조화 Step 1 — 2차 패치.

핵심 변경:
- 1행 표의 분리형 숫자 제목(`1` + 빈칸 + `모집지역...`) 결합
- 날짜와 긴 서술형 번호 문장을 제목 후보에서 제외
- `①`, `가.`, `(1)` 등을 전역 marker 종류가 아닌 지역적 형제 패턴과
  현재 부모 Section을 기준으로 승격
- 붙임/별첨/서식/개인정보 동의서 이후를 attachment 영역으로 분리
- 제목 level을 강한 anchor와 원문 위치를 기준으로 결정

기존 호출 규약:
    process(input_path, output_dir) -> (step1-1, step1-2, step1-3)
"""

from __future__ import annotations

import copy
import json
import os
import re
from collections import Counter, defaultdict
from tkinter import Tk, messagebox
from tkinter.filedialog import askopenfilename
from typing import Any, Iterable


ROMAN = "ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩⅪⅫ"
CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮"

MARKER_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("chapter", re.compile(r"^\s*(제\s*\d+\s*[장편부])\s*(.+)$")),
    ("roman", re.compile(rf"^\s*([{ROMAN}])(?:[.．])?\s*(.+)$")),
    ("decimal", re.compile(r"^\s*(\d+(?:\.\d+)+)(?:[.)])?\s+(.+)$")),
    ("arabic_dot", re.compile(r"^\s*(\d+)[.．]\s*(.+)$")),
    ("arabic_paren", re.compile(r"^\s*\((\d+)\)\s*(.+)$")),
    ("circled", re.compile(rf"^\s*([{CIRCLED}])\s*(.+)$")),
    ("korean_dot", re.compile(r"^\s*([가-하])[.．]\s*(.+)$")),
]

DATE_PATTERNS = [
    re.compile(r"^\s*\d{4}\s*[.]\s*\d{1,2}\s*[.]\s*\d{1,2}\s*[.]?\s*$"),
    re.compile(r"^\s*\d{4}\s*[-/]\s*\d{1,2}\s*[-/]\s*\d{1,2}\s*$"),
    re.compile(r"^\s*[’'‘]?\d{2}\s*[.]\s*\d{1,2}\s*[.]\s*\d{1,2}\s*[.]?\s*$"),
]

ATTACHMENT_KEYWORDS = (
    "붙임",
    "별첨",
    "서식",
    "개인정보 수집·이용 동의서",
    "개인정보 수집 이용 동의서",
    "개인정보 제공 동의서",
)

SENTENCE_END_PATTERNS = (
    r"(?:다|한다|됩니다|한다\.|됩니다\.|바랍니다|바랍니다\.|있음|없음|수 있음|수 없음)$",
    r"(?:하여야 함|해야 함|주의하시기 바랍니다|유의하시기 바랍니다)$",
)

STRONG_MAJOR_TYPES = {"chapter", "roman"}
ARABIC_TYPES = {"arabic_dot", "arabic_bare"}
LOCAL_CHILD_TYPES = {"decimal", "arabic_paren", "circled", "korean_dot"}


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).replace("\u00a0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\s*\n\s*", "\n", text)
    return text.strip()


def is_date_text(text: str) -> bool:
    value = clean_text(text)
    return any(pattern.fullmatch(value) for pattern in DATE_PATTERNS)


def looks_sentence_like(text: str) -> bool:
    value = clean_text(text)
    if not value:
        return False
    if "\n" in value:
        return True
    if len(value) >= 90:
        return True
    return any(re.search(pattern, value) for pattern in SENTENCE_END_PATTERNS)


def is_short_title(text: str, *, max_chars: int = 70) -> bool:
    value = clean_text(text)
    return bool(value) and len(value) <= max_chars and not looks_sentence_like(value)


def parse_marker(text: str) -> dict[str, Any] | None:
    """문자열 앞의 명시적 번호 marker를 파싱한다.

    숫자만 있는 marker(`1`)는 일반 문단에서는 허용하지 않는다. 분리형 표 제목
    판별 함수에서만 `arabic_bare`로 생성한다.
    """
    value = clean_text(text)
    if not value or is_date_text(value):
        return None

    for marker_type, pattern in MARKER_PATTERNS:
        match = pattern.match(value)
        if not match:
            continue
        marker = clean_text(match.group(1))
        title = clean_text(match.group(2))
        if not title:
            return None
        return {
            "marker": marker,
            "marker_type": marker_type,
            "title": title,
            "full_text": value,
        }
    return None


def sorted_cells(table: dict[str, Any]) -> list[dict[str, Any]]:
    def key(cell: dict[str, Any]) -> tuple[int, int]:
        return (
            int(cell.get("row", 0) or 0),
            int(cell.get("col", cell.get("column", 0)) or 0),
        )

    return sorted(
        [cell for cell in table.get("cells", []) if isinstance(cell, dict)],
        key=key,
    )


def cells_grouped_by_row(table: dict[str, Any]) -> dict[int, list[dict[str, Any]]]:
    rows: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for cell in sorted_cells(table):
        rows[int(cell.get("row", 0) or 0)].append(cell)
    return dict(rows)


def cell_text(cell: dict[str, Any]) -> str:
    direct = clean_text(cell.get("text"))
    if direct:
        return direct

    values: list[str] = []
    for block in cell.get("blocks") or []:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "paragraph":
            text = clean_text(block.get("text"))
            if text:
                values.append(text)
    return "\n".join(values)


def table_texts(table: dict[str, Any]) -> list[str]:
    return [text for cell in sorted_cells(table) if (text := cell_text(cell))]


def make_heading_item(
    candidate: dict[str, Any],
    origin_path: list[str],
    fallback_content: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "type": "heading_candidate",
        **candidate,
        "level": None,
        "resolved": False,
        "origin_path": copy.deepcopy(origin_path),
        "fallback_content": copy.deepcopy(fallback_content),
    }


def split_numeric_title_from_cells(
    cells: list[dict[str, Any]],
) -> tuple[str, str] | None:
    """같은 행의 숫자 셀과 짧은 제목 셀을 찾아 결합한다."""
    ordered = sorted(
        cells,
        key=lambda item: int(item.get("col", item.get("column", 0)) or 0),
    )
    values = [(cell, cell_text(cell)) for cell in ordered]
    number_positions = [
        index for index, (_, text) in enumerate(values) if re.fullmatch(r"\d{1,2}", text)
    ]
    if len(number_positions) != 1:
        return None

    number_index = number_positions[0]
    number = values[number_index][1]
    title_candidates = [
        text
        for index, (_, text) in enumerate(values)
        if index != number_index and text and is_short_title(text, max_chars=80)
    ]
    if len(title_candidates) != 1:
        return None

    title = title_candidates[0]
    if is_date_text(f"{number}.{title}"):
        return None
    return number, title


def table_heading_candidate(table: dict[str, Any]) -> dict[str, Any] | None:
    if table.get("type") != "table":
        return None
    if int(table.get("row_count", 0) or 0) != 1:
        return None
    if int(table.get("col_count", 999) or 999) > 5:
        return None

    cells = sorted_cells(table)
    split_title = split_numeric_title_from_cells(cells)
    if split_title:
        marker, title = split_title
        return {
            "marker": marker,
            "marker_type": "arabic_bare",
            "title": title,
            "full_text": f"{marker}. {title}",
            "display_title": f"{marker}. {title}",
            "source_kind": "table_split_heading",
            "source": copy.deepcopy(table.get("source", {})),
            "source_table_index": table.get("table_index"),
            "confidence": 1.0,
            "strong_anchor": True,
        }

    joined = clean_text(" ".join(table_texts(table)))
    parsed = parse_marker(joined)
    if not parsed or not is_short_title(parsed["title"], max_chars=80):
        return None

    parsed.update(
        {
            "display_title": parsed["full_text"],
            "source_kind": "table",
            "source": copy.deepcopy(table.get("source", {})),
            "source_table_index": table.get("table_index"),
            "confidence": 1.0,
            "strong_anchor": parsed["marker_type"] in STRONG_MAJOR_TYPES | {"arabic_dot"},
        }
    )
    return parsed


def table_row_heading_candidate(
    table: dict[str, Any],
    row_index: int,
    cells: list[dict[str, Any]],
) -> dict[str, Any] | None:
    split_title = split_numeric_title_from_cells(cells)
    if split_title:
        marker, title = split_title
        return {
            "marker": marker,
            "marker_type": "arabic_bare",
            "title": title,
            "full_text": f"{marker}. {title}",
            "display_title": f"{marker}. {title}",
            "source_kind": "table_row_split_heading",
            "source": {
                **copy.deepcopy(table.get("source", {})),
                "row_index": row_index,
            },
            "source_table_index": table.get("table_index"),
            "confidence": 1.0,
            "strong_anchor": True,
        }

    texts = [cell_text(cell) for cell in cells if cell_text(cell)]
    joined = clean_text(" ".join(texts))
    if not joined or len(joined) > 100 or "\n" in joined:
        return None

    parsed = parse_marker(joined)
    if not parsed or not is_short_title(parsed["title"], max_chars=75):
        return None

    parsed.update(
        {
            "display_title": parsed["full_text"],
            "source_kind": "table_row",
            "source": {
                **copy.deepcopy(table.get("source", {})),
                "row_index": row_index,
            },
            "source_table_index": table.get("table_index"),
            "confidence": 1.0,
            "strong_anchor": parsed["marker_type"] in STRONG_MAJOR_TYPES | {"arabic_dot"},
        }
    )
    return parsed


def paragraph_heading_candidate(paragraph: dict[str, Any]) -> dict[str, Any] | None:
    text = clean_text(paragraph.get("text"))
    parsed = parse_marker(text)
    if not parsed:
        return None

    marker_type = parsed["marker_type"]
    title = parsed["title"]

    # 문장형 번호 항목은 Section이 아니라 본문 목록으로 남긴다.
    if looks_sentence_like(text) or not is_short_title(title, max_chars=75):
        return None

    parsed.update(
        {
            "display_title": parsed["full_text"],
            "source_kind": "paragraph",
            "source": copy.deepcopy(paragraph.get("source", {})),
            "paragraph_index": paragraph.get("paragraph_index"),
            "confidence": 0.98 if marker_type in STRONG_MAJOR_TYPES else 0.9,
            "strong_anchor": marker_type in STRONG_MAJOR_TYPES,
        }
    )
    return parsed


def table_row_heading_candidates(table: dict[str, Any]) -> dict[int, dict[str, Any]]:
    result: dict[int, dict[str, Any]] = {}
    for row_index, cells in cells_grouped_by_row(table).items():
        candidate = table_row_heading_candidate(table, row_index, cells)
        if candidate:
            result[row_index] = candidate
    return result


def is_single_cell_layout_container(table: dict[str, Any]) -> bool:
    nonempty_cells = [cell for cell in table.get("cells", []) if cell.get("blocks")]
    if len(nonempty_cells) != 1:
        return False
    blocks = nonempty_cells[0].get("blocks") or []
    return len(blocks) >= 3 and any(
        isinstance(block, dict) and block.get("type") == "table" for block in blocks
    )


def is_multi_cell_layout_container(table: dict[str, Any]) -> bool:
    if int(table.get("row_count", 0) or 0) < 3:
        return False
    candidates = table_row_heading_candidates(table)
    major_count = sum(
        candidate.get("marker_type") in STRONG_MAJOR_TYPES
        for candidate in candidates.values()
    )
    split_count = sum(
        candidate.get("source_kind") == "table_row_split_heading"
        for candidate in candidates.values()
    )
    return major_count >= 2 or split_count >= 2


def is_layout_container(table: dict[str, Any]) -> bool:
    return bool(
        table.get("type") == "table"
        and (is_single_cell_layout_container(table) or is_multi_cell_layout_container(table))
    )


def compact_content(block: dict[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(block)


def row_fallback_content(
    table: dict[str, Any],
    row_index: int,
    cells: list[dict[str, Any]],
) -> dict[str, Any]:
    text = clean_text(" ".join(cell_text(cell) for cell in cells if cell_text(cell)))
    return {
        "type": "paragraph",
        "text": text,
        "source": {
            **copy.deepcopy(table.get("source", {})),
            "table_index": table.get("table_index"),
            "row_index": row_index,
        },
    }


def flatten_layout_table(
    table: dict[str, Any],
    table_path: list[str],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    rows = cells_grouped_by_row(table)
    row_candidates = table_row_heading_candidates(table)

    for row_index in sorted(rows):
        cells = rows[row_index]
        row_path = table_path + [f"row:{row_index}"]
        candidate = row_candidates.get(row_index)
        if candidate:
            items.append(
                make_heading_item(
                    candidate,
                    row_path,
                    fallback_content=row_fallback_content(table, row_index, cells),
                )
            )
            continue

        for cell in sorted(
            cells,
            key=lambda item: int(item.get("col", item.get("column", 0)) or 0),
        ):
            blocks = cell.get("blocks") or []
            if not blocks:
                continue
            cell_path = row_path + [
                f"cell:{cell.get('row', 0)},{cell.get('col', cell.get('column', 0))}"
            ]
            items.extend(flatten_blocks(blocks, cell_path))
    return items


def flatten_blocks(
    blocks: Iterable[dict[str, Any]],
    path: list[str] | None = None,
) -> list[dict[str, Any]]:
    path = path or []
    items: list[dict[str, Any]] = []

    for index, block in enumerate(blocks):
        if not isinstance(block, dict):
            continue
        block_path = path + [f"block:{index}"]
        block_type = block.get("type")

        if block_type == "table":
            candidate = table_heading_candidate(block)
            if candidate:
                items.append(
                    make_heading_item(
                        candidate,
                        block_path,
                        fallback_content=compact_content(block),
                    )
                )
                continue

            if is_layout_container(block):
                items.extend(flatten_layout_table(block, block_path))
                continue

            items.append(
                {
                    "type": "table",
                    "table_index": block.get("table_index"),
                    "row_count": block.get("row_count"),
                    "col_count": block.get("col_count"),
                    "data": compact_content(block),
                    "origin_path": block_path,
                }
            )
            continue

        if block_type == "paragraph":
            candidate = paragraph_heading_candidate(block)
            if candidate:
                items.append(
                    make_heading_item(
                        candidate,
                        block_path,
                        fallback_content=compact_content(block),
                    )
                )
            else:
                items.append(
                    {
                        "type": "paragraph",
                        "text": clean_text(block.get("text")),
                        "data": compact_content(block),
                        "heading_candidate": False,
                        "origin_path": block_path,
                    }
                )
            continue

        items.append(
            {
                "type": block_type or "unknown",
                "data": compact_content(block),
                "origin_path": block_path,
            }
        )
    return items


def item_text(item: dict[str, Any]) -> str:
    if item.get("type") == "heading_candidate":
        return clean_text(item.get("full_text"))
    if item.get("type") == "paragraph":
        return clean_text(item.get("text"))
    data = item.get("data")
    if isinstance(data, dict):
        return clean_text(data.get("text"))
    return ""


def is_attachment_start(text: str) -> bool:
    value = clean_text(text)
    compact = re.sub(r"\s+", "", value)
    if not compact:
        return False

    for keyword in ATTACHMENT_KEYWORDS:
        key = re.sub(r"\s+", "", keyword)
        if compact.startswith(key):
            return True
        if "개인정보" in key and key in compact:
            return True
    return False


def mark_document_regions(items: list[dict[str, Any]]) -> None:
    region = "body"
    for item in items:
        text = item_text(item)
        if region == "body" and is_attachment_start(text):
            region = "attachment"
        item["document_region"] = region


def marker_number(item: dict[str, Any]) -> int | None:
    marker_type = item.get("marker_type")
    marker = clean_text(item.get("marker"))
    if marker_type in {"arabic_dot", "arabic_bare", "arabic_paren"} and marker.isdigit():
        return int(marker)
    if marker_type == "decimal":
        try:
            return int(marker.split(".")[-1])
        except ValueError:
            return None
    if marker_type == "roman" and marker in ROMAN:
        return ROMAN.index(marker) + 1
    if marker_type == "circled" and marker in CIRCLED:
        return CIRCLED.index(marker) + 1
    if marker_type == "korean_dot" and marker:
        return ord(marker[0]) - ord("가") + 1
    chapter_match = re.search(r"\d+", marker)
    if marker_type == "chapter" and chapter_match:
        return int(chapter_match.group())
    return None


def container_key(item: dict[str, Any]) -> tuple[str, ...]:
    path = [str(value) for value in item.get("origin_path") or []]
    trimmed: list[str] = []
    for value in path:
        if value.startswith("block:"):
            continue
        trimmed.append(value)
    # 같은 표/셀 내부의 연속 번호는 동일 컨테이너로 간주한다.
    if item.get("source_table_index") is not None:
        return (
            f"table:{item.get('source_table_index')}",
            *[value for value in trimmed if value.startswith("cell:")][:1],
        )
    return tuple(trimmed[:-1] if trimmed else ["document"])


def sequence_supported(
    candidates: list[dict[str, Any]],
    target_index: int,
) -> bool:
    target = candidates[target_index]
    marker_type = target.get("marker_type")
    key = container_key(target)
    region = target.get("document_region")

    peers: list[tuple[int, int]] = []
    for index, item in enumerate(candidates):
        if item.get("marker_type") != marker_type:
            continue
        if item.get("document_region") != region:
            continue
        if container_key(item) != key:
            continue
        number = marker_number(item)
        if number is not None:
            peers.append((index, number))

    if len(peers) < 2:
        return False

    peer_numbers = [number for _, number in peers]
    for left, right in zip(peer_numbers, peer_numbers[1:]):
        if right == left + 1:
            return True
    return len(set(peer_numbers)) >= 2 and min(peer_numbers) == 1


def nearest_resolved_before(
    headings: list[dict[str, Any]],
    index: int,
    *,
    maximum_level: int | None = None,
) -> dict[str, Any] | None:
    for previous in reversed(headings[:index]):
        if not previous.get("resolved") or previous.get("level") is None:
            continue
        level = int(previous["level"])
        if maximum_level is None or level <= maximum_level:
            return previous
    return None


def resolve_heading_levels(items: list[dict[str, Any]]) -> None:
    headings = [item for item in items if item.get("type") == "heading_candidate"]
    body_headings = [item for item in headings if item.get("document_region") == "body"]
    has_major = any(item.get("marker_type") in STRONG_MAJOR_TYPES for item in body_headings)

    # 1차: 강한 anchor
    for index, item in enumerate(headings):
        item["level"] = None
        item["resolved"] = False
        item["level_reason"] = ""

        if item.get("document_region") == "attachment":
            item["level_reason"] = "attachment 영역의 번호는 본문 Section으로 승격하지 않음"
            continue

        marker_type = item.get("marker_type")
        if marker_type in STRONG_MAJOR_TYPES:
            item["level"] = 1
            item["resolved"] = True
            item["level_reason"] = "로마 숫자/장·편·부 강한 anchor"
            continue

        if marker_type in ARABIC_TYPES:
            # 표 분리형 제목은 독립 anchor로 강하게 인정한다.
            strong_table = item.get("source_kind") in {
                "table",
                "table_row",
                "table_split_heading",
                "table_row_split_heading",
            }
            supported = sequence_supported(headings, index)
            if strong_table or supported:
                item["level"] = 2 if has_major and nearest_resolved_before(headings, index, maximum_level=1) else 1
                item["resolved"] = True
                item["level_reason"] = (
                    "강한 대제목 아래의 숫자형 지역 anchor"
                    if item["level"] == 2
                    else "문서 최상위 숫자형 anchor"
                )

    # 2차: 지역별 하위 번호. marker 자체가 아니라 현재 부모와 형제 패턴을 본다.
    for index, item in enumerate(headings):
        if item.get("resolved") or item.get("document_region") == "attachment":
            continue
        marker_type = item.get("marker_type")
        if marker_type not in LOCAL_CHILD_TYPES:
            continue
        if not sequence_supported(headings, index):
            item["level_reason"] = "같은 컨테이너의 연속 형제 번호가 없어 목록으로 유지"
            continue

        parent = nearest_resolved_before(headings, index)
        if not parent:
            item["level_reason"] = "현재 부모 Section이 없어 목록으로 유지"
            continue

        parent_level = int(parent.get("level") or 1)
        # ①/가./(1) 같은 일반 문단 marker는 로마 대제목 바로 아래에서는
        # 목록일 가능성이 높다. 평문 marker를 Section으로 승격하려면
        # 적어도 숫자형 중간 부모(level 2)가 이미 확인되어야 한다.
        if item.get("source_kind") == "paragraph" and parent_level < 2:
            item["level_reason"] = "평문 하위 번호가 최상위 대제목 바로 아래에 있어 목록으로 유지"
            continue

        item["level"] = min(parent_level + 1, 4)
        item["resolved"] = True
        item["level_reason"] = "현재 부모와 같은 컨테이너의 연속 형제 패턴 확인"

    # 3차: decimal은 직전 arabic anchor의 자식으로 우선 배치한다.
    last_resolved: dict[int, dict[str, Any]] = {}
    for item in headings:
        if item.get("resolved"):
            level = int(item.get("level") or 1)
            last_resolved[level] = item
            for stale in [value for value in last_resolved if value > level]:
                last_resolved.pop(stale, None)
            continue

        if item.get("marker_type") != "decimal" or item.get("document_region") == "attachment":
            continue
        parent = last_resolved.get(2) or last_resolved.get(1)
        if parent and is_short_title(item.get("title", ""), max_chars=70):
            item["level"] = min(int(parent.get("level") or 1) + 1, 4)
            item["resolved"] = True
            item["level_reason"] = "직전 숫자형/대제목 anchor 아래 decimal 구조"


def infer_heading_scheme(items: list[dict[str, Any]]) -> dict[str, Any]:
    """호환용 요약. Level 결정은 item별 지역 판단으로 이미 수행한다."""
    headings = [item for item in items if item.get("type") == "heading_candidate"]
    counts = Counter(item.get("marker_type") for item in headings)
    resolved_counts: Counter[tuple[str, int]] = Counter()
    for item in headings:
        if item.get("resolved") and item.get("level") is not None:
            resolved_counts[(str(item.get("marker_type")), int(item["level"]))] += 1

    scheme: dict[str, Any] = {}
    for marker_type, count in counts.items():
        levels = {
            level: resolved_counts[(str(marker_type), level)]
            for level in range(1, 5)
            if resolved_counts[(str(marker_type), level)]
        }
        scheme[str(marker_type)] = {
            "count": count,
            "resolved_levels": levels,
            "policy": "global marker mapping disabled; local anchor/context based",
        }

    return {
        "scheme": scheme,
        "heading_count": len(headings),
        "resolved_heading_count": sum(bool(item.get("resolved")) for item in headings),
        "evidence": [
            {
                "item_id": item.get("item_id"),
                "marker_type": item.get("marker_type"),
                "full_text": item.get("full_text"),
                "level": item.get("level"),
                "resolved": item.get("resolved"),
                "reason": item.get("level_reason"),
                "document_region": item.get("document_region"),
            }
            for item in headings
        ],
    }


def assign_levels(items: list[dict[str, Any]], inference: dict[str, Any] | None = None) -> None:
    resolve_heading_levels(items)
    if inference is not None:
        refreshed = infer_heading_scheme(items)
        inference.clear()
        inference.update(refreshed)


def make_section(item: dict[str, Any], section_id: str) -> dict[str, Any]:
    return {
        "section_id": section_id,
        "level": item["level"],
        "marker": item.get("marker"),
        "marker_type": item.get("marker_type"),
        "title": item.get("title"),
        "display_title": item.get("display_title") or item.get("full_text"),
        "contents": [],
        "children": [],
        "source": {
            "source_kind": item.get("source_kind"),
            "table_index": item.get("source_table_index"),
            "paragraph_index": item.get("paragraph_index"),
            "origin_path": copy.deepcopy(item.get("origin_path")),
            "document_region": item.get("document_region"),
            "level_reason": item.get("level_reason"),
            **copy.deepcopy(item.get("source", {})),
        },
    }


def content_from_item(item: dict[str, Any]) -> dict[str, Any]:
    if item.get("type") == "heading_candidate":
        fallback = item.get("fallback_content")
        if isinstance(fallback, dict):
            result = copy.deepcopy(fallback)
            result.setdefault("type", "paragraph")
            result.setdefault("text", item.get("full_text", ""))
        else:
            result = {
                "type": "paragraph",
                "text": item.get("full_text", ""),
            }
        result["heading_candidate"] = True
        result["marker"] = item.get("marker")
        result["marker_type"] = item.get("marker_type")
        result["document_region"] = item.get("document_region")
        result["origin_path"] = copy.deepcopy(item.get("origin_path"))
        return result

    if item.get("type") == "paragraph":
        result = copy.deepcopy(item.get("data", {}))
        result["type"] = "paragraph"
        result["text"] = item.get("text", "")
        result["origin_path"] = copy.deepcopy(item.get("origin_path"))
        result["document_region"] = item.get("document_region")
        return result

    if item.get("type") == "table":
        result = copy.deepcopy(item.get("data", {}))
        result["origin_path"] = copy.deepcopy(item.get("origin_path"))
        result["document_region"] = item.get("document_region")
        return result

    result = copy.deepcopy(item.get("data", item))
    if isinstance(result, dict):
        result.setdefault("document_region", item.get("document_region"))
    return result


def build_hierarchy(
    document: dict[str, Any],
    items: list[dict[str, Any]],
    inference: dict[str, Any],
) -> dict[str, Any]:
    intro: list[dict[str, Any]] = []
    sections: list[dict[str, Any]] = []
    unresolved_items: list[dict[str, Any]] = []
    stack: list[dict[str, Any]] = []
    section_counter = 0

    for item in items:
        if item.get("type") == "heading_candidate" and item.get("resolved"):
            section_counter += 1
            node = make_section(item, f"sec_{section_counter:04d}")
            level = int(item["level"])
            while stack and int(stack[-1]["level"]) >= level:
                stack.pop()
            if stack:
                stack[-1]["children"].append(node)
            else:
                sections.append(node)
            stack.append(node)
            continue

        if item.get("type") == "heading_candidate":
            unresolved = copy.deepcopy(item)
            unresolved["reason"] = item.get("level_reason") or "지역 계층 근거 부족"
            unresolved_items.append(unresolved)

        content = content_from_item(item)
        if stack:
            stack[-1]["contents"].append(content)
        else:
            intro.append(content)

    return {
        "document": copy.deepcopy(document),
        "hierarchy_method": {
            "version": "step1-v3-local-anchor-attachment",
            "stages": [
                "1-1 ordered_items_and_heading_candidates",
                "1-2 body_attachment_region_detection",
                "1-3 local_anchor_and_sibling_sequence_level_resolution",
                "1-4 hierarchy_building",
            ],
            "heading_scheme": copy.deepcopy(inference),
            "rules": [
                "1행 표의 숫자 셀과 짧은 제목 셀을 결합",
                "날짜와 긴 문장형 번호 항목 제외",
                "marker 종류 전역 매핑 금지",
                "circled/korean/paren은 현재 부모와 연속 형제 패턴이 있을 때만 승격",
                "attachment 영역 번호는 본문 최상위 Section으로 승격하지 않음",
            ],
        },
        "intro": intro,
        "sections": sections,
        "unresolved_items": unresolved_items,
    }


def process(input_path: str, output_dir: str) -> tuple[str, str, str]:
    with open(input_path, "r", encoding="utf-8") as file:
        source = json.load(file)

    all_blocks: list[dict[str, Any]] = []
    for section in source.get("sections", []):
        if isinstance(section, dict):
            all_blocks.extend(section.get("blocks", []))

    items = flatten_blocks(all_blocks)
    for index, item in enumerate(items, start=1):
        item["item_id"] = f"item_{index:04d}"
        item["order"] = index

    mark_document_regions(items)
    resolve_heading_levels(items)
    inference = infer_heading_scheme(items)
    hierarchy = build_hierarchy(source.get("document", {}), items, inference)

    os.makedirs(output_dir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(input_path))[0]
    step1_items_path = os.path.join(output_dir, f"{stem}_step1-1_items.json")
    heading_scheme_path = os.path.join(output_dir, f"{stem}_step1-2_heading_scheme.json")
    hierarchy_path = os.path.join(output_dir, f"{stem}_step1-3_hierarchy.json")

    with open(step1_items_path, "w", encoding="utf-8") as file:
        json.dump(
            {"document": source.get("document", {}), "items": items},
            file,
            ensure_ascii=False,
            indent=2,
        )

    with open(heading_scheme_path, "w", encoding="utf-8") as file:
        json.dump(
            {"document": source.get("document", {}), **inference},
            file,
            ensure_ascii=False,
            indent=2,
        )

    with open(hierarchy_path, "w", encoding="utf-8") as file:
        json.dump(hierarchy, file, ensure_ascii=False, indent=2)

    return step1_items_path, heading_scheme_path, hierarchy_path


def select_input_json() -> str | None:
    root = Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    selected = askopenfilename(
        parent=root,
        title="정규화 JSON 파일 선택",
        filetypes=[("JSON 파일", "*.json"), ("모든 파일", "*.*")],
    )
    root.destroy()
    return selected or None


def main() -> None:
    input_path = select_input_json()
    if not input_path:
        print("JSON 파일을 선택하지 않아 실행을 종료합니다.")
        return

    structure_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(structure_dir, "output")

    try:
        paths = process(input_path, output_dir)
        messagebox.showinfo(
            "구조화 1단계 완료",
            "\n".join(["구조화 결과를 생성했습니다.", "", *paths]),
        )
    except (OSError, json.JSONDecodeError, ValueError, TypeError) as error:
        messagebox.showerror("구조화 1단계 실패", str(error))
        raise


if __name__ == "__main__":
    main()
