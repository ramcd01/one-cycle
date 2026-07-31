"""Step 4 Chunking runner — 2차 패치.

변경 사항:
- 완전한 문단/목록/문장만 overlap으로 사용
- overlap 단위가 제한보다 길면 잘라 쓰지 않고 overlap 생략
- table cell.blocks의 nested table을 재귀적으로 별도 Chunk 생성
- table_index 기준 중복 생성 방지
- 부모 fallback 표에서는 nested table 텍스트를 제외해 중복을 줄임
"""

from __future__ import annotations

import argparse
import copy
import inspect
import json
import re
from pathlib import Path
from typing import Any, Iterator

try:
    from . import build_chunks as build_chunks_module
except ImportError:
    import build_chunks as build_chunks_module


MAX_CHARS = int(build_chunks_module.MAX_CHARS)
OVERLAP_CHARS = int(build_chunks_module.OVERLAP_CHARS)

LIST_PREFIX_RE = re.compile(
    r"^\s*(?:\d+[.)]|\(\d+\)|[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮]|[가-하][.．]|[-•▪])\s*"
)
SENTENCE_END_RE = re.compile(
    r"(?:[.!?。！？]|(?:입니다|합니다|됩니다|바랍니다|있습니다|없습니다|하여야 합니다|해야 합니다|수 있습니다|수 없습니다|있음|없음|하여야 함|해야 함))\s*$"
)


def normalize_for_split(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)

    lines = [line.strip() for line in text.split("\n")]
    normalized: list[str] = []
    for line in lines:
        if line:
            normalized.append(line)
        elif normalized and normalized[-1] != "":
            normalized.append("")
    while normalized and normalized[-1] == "":
        normalized.pop()
    return "\n".join(normalized).strip()


def split_sentences(text: str) -> list[str]:
    value = text.strip()
    if not value:
        return []
    parts = re.split(r"(?<=[.!?。！？])\s+", value)
    return [part.strip() for part in parts if part.strip()]


def split_oversize_unit(unit: str, max_chars: int) -> list[str]:
    """Chunk 상한을 맞추기 위한 최후 분할.

    문장 경계를 우선하며, 문장 하나가 max_chars보다 긴 경우에만 공백/하드
    경계를 사용한다. 이 하드 분할 조각은 overlap 선별 단계에서 짧은 꼬리로
    재사용되지 않도록 별도 overlap 함수가 보수적으로 판단한다.
    """
    sentences = split_sentences(unit)
    if len(sentences) > 1:
        pieces: list[str] = []
        current: list[str] = []
        current_len = 0
        for sentence in sentences:
            additional = len(sentence) + (1 if current else 0)
            if current and current_len + additional > max_chars:
                pieces.append(" ".join(current).strip())
                current = [sentence]
                current_len = len(sentence)
            elif len(sentence) > max_chars:
                if current:
                    pieces.append(" ".join(current).strip())
                    current = []
                    current_len = 0
                pieces.extend(split_oversize_unit(sentence, max_chars))
            else:
                current.append(sentence)
                current_len += additional
        if current:
            pieces.append(" ".join(current).strip())
        return pieces

    remaining = unit.strip()
    pieces: list[str] = []
    while len(remaining) > max_chars:
        window = remaining[: max_chars + 1]
        search_start = max(1, int(max_chars * 0.6))
        whitespace = [
            match.start()
            for match in re.finditer(r"\s+", window)
            if match.start() >= search_start
        ]
        split_at = max(whitespace) if whitespace else max_chars
        piece = remaining[:split_at].strip()
        if not piece:
            piece = remaining[:max_chars].strip()
            split_at = max_chars
        pieces.append(piece)
        remaining = remaining[split_at:].strip()
    if remaining:
        pieces.append(remaining)
    return pieces


def semantic_units(text: str, max_chars: int) -> list[str]:
    """문단 → 목록/줄 → 문장 순으로 의미 단위를 만든다."""
    normalized = normalize_for_split(text)
    if not normalized:
        return []

    raw_units = [
        unit.strip()
        for unit in re.split(r"\n{2,}|\n+", normalized)
        if unit.strip()
    ]
    units: list[str] = []
    for unit in raw_units:
        if len(unit) <= max_chars:
            units.append(unit)
        else:
            units.extend(split_oversize_unit(unit, max_chars))
    return units


def is_complete_overlap_unit(unit: str) -> bool:
    """짧은 문장 꼬리나 하드 분할 조각을 overlap에서 제외한다."""
    value = unit.strip()
    if not value:
        return False
    if LIST_PREFIX_RE.match(value):
        return True
    if len(value) < 12:
        return False
    if SENTENCE_END_RE.search(value):
        return True
    # 줄/문단 단위로 보존된 충분히 긴 정보 단위는 완전 문단으로 인정한다.
    return len(value) >= 25


def overlap_atomic_units(text: str) -> list[str]:
    """overlap 후보를 자르지 않은 원래 줄/문장 단위로 반환한다."""
    normalized = normalize_for_split(text)
    if not normalized:
        return []

    units: list[str] = []
    for paragraph in [part for part in re.split(r"\n{2,}|\n+", normalized) if part.strip()]:
        paragraph = paragraph.strip()
        sentences = split_sentences(paragraph)
        if len(sentences) > 1:
            units.extend(sentences)
        else:
            units.append(paragraph)
    return [unit.strip() for unit in units if unit.strip()]


def trailing_whole_units(text: str, overlap_chars: int) -> list[str]:
    if overlap_chars <= 0:
        return []

    units = overlap_atomic_units(text)
    if not units:
        return []

    last = units[-1]
    # 마지막 완전 단위가 제한보다 길거나 불완전하면 이전 단위를 끌어오지 않는다.
    if len(last) > overlap_chars or not is_complete_overlap_unit(last):
        return []

    selected = [last]
    total = len(last)
    for unit in reversed(units[:-1]):
        if not is_complete_overlap_unit(unit):
            break
        additional = len(unit) + 1
        if total + additional > overlap_chars:
            break
        selected.append(unit)
        total += additional
    return list(reversed(selected))


def smart_split_text(
    text: str,
    max_chars: int = MAX_CHARS,
    overlap_chars: int = OVERLAP_CHARS,
) -> list[str]:
    text = normalize_for_split(text)
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    units = semantic_units(text, max_chars)
    if not units:
        return [text[:max_chars]]

    base_chunks: list[str] = []
    current_units: list[str] = []
    current_length = 0

    for unit in units:
        additional = len(unit) + (1 if current_units else 0)
        if current_units and current_length + additional > max_chars:
            base_chunks.append("\n".join(current_units).strip())
            current_units = [unit]
            current_length = len(unit)
        else:
            current_units.append(unit)
            current_length += additional
    if current_units:
        base_chunks.append("\n".join(current_units).strip())

    if overlap_chars <= 0 or len(base_chunks) <= 1:
        return base_chunks

    result = [base_chunks[0]]
    for index in range(1, len(base_chunks)):
        current = base_chunks[index]
        overlap_units = trailing_whole_units(base_chunks[index - 1], overlap_chars)
        if overlap_units:
            candidate = "\n".join([*overlap_units, current]).strip()
            if len(candidate) <= max_chars:
                current = candidate
        result.append(current)
    return result


def patch_chunking_splitter() -> None:
    build_chunks_module.split_long_text = smart_split_text


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _table_key(table: dict[str, Any]) -> tuple[str, Any]:
    table_index = table.get("table_index")
    if table_index not in (None, ""):
        return ("table_index", str(table_index))
    return ("object", id(table))


def _non_table_block_text(block: Any) -> str:
    if not isinstance(block, dict):
        return ""
    if block.get("type") == "table":
        return ""

    direct = build_chunks_module.extract_content_text(block)
    if direct:
        return build_chunks_module.clean_text(direct)

    values: list[str] = []
    for key, child in block.items():
        if key in {"source", "structured_table", "domain"}:
            continue
        if isinstance(child, list):
            for item in child:
                text = _non_table_block_text(item)
                if text:
                    values.append(text)
        elif isinstance(child, dict):
            text = _non_table_block_text(child)
            if text:
                values.append(text)
    return "\n".join(values)


def _direct_nested_tables(table: dict[str, Any]) -> Iterator[tuple[dict[str, Any], list[str]]]:
    cells = [cell for cell in table.get("cells") or [] if isinstance(cell, dict)]
    cells.sort(
        key=lambda cell: (
            _safe_int(cell.get("row"), 0),
            _safe_int(cell.get("col", cell.get("column")), 0),
        )
    )
    for cell in cells:
        row = _safe_int(cell.get("row"), 0)
        col = _safe_int(cell.get("col", cell.get("column")), 0)
        for block_index, block in enumerate(cell.get("blocks") or []):
            if isinstance(block, dict) and block.get("type") == "table":
                yield block, [f"cell:{row},{col}", f"block:{block_index}"]


class RecursiveChunkBuilder(build_chunks_module.ChunkBuilder):
    """기존 ChunkBuilder의 표 변환 규칙을 유지하면서 nested table만 재귀 확장."""

    def __init__(self, final_document: dict[str, Any]) -> None:
        super().__init__(final_document)
        self._processed_table_keys: set[tuple[str, Any]] = set()

    def extract_cell_text(self, cell: dict[str, Any]) -> str:
        """부모 fallback text에서 nested table 본문을 제외한다."""
        blocks = [block for block in cell.get("blocks") or [] if isinstance(block, dict)]
        if blocks:
            texts = [text for block in blocks if (text := _non_table_block_text(block))]
            if texts:
                return "\n".join(texts)
            if any(block.get("type") == "table" for block in blocks):
                return ""
        return build_chunks_module.clean_text(cell.get("text"))

    def process_table(
        self,
        table: dict[str, Any],
        *,
        section_id: Any,
        section_path: list[str],
        domain: Any,
        content_index: int,
        table_contexts: list[dict[str, Any]] | None = None,
        _nested_path: list[str] | None = None,
        _parent_table_index: Any = None,
        **_: Any,
    ) -> None:
        key = _table_key(table)
        if key in self._processed_table_keys:
            return
        self._processed_table_keys.add(key)

        chunk_start = len(self.chunks)
        base_method = super().process_table
        parameters = inspect.signature(base_method).parameters
        call_kwargs: dict[str, Any] = {
            "section_id": section_id,
            "section_path": section_path,
            "domain": domain,
            "content_index": content_index,
        }
        if "table_contexts" in parameters:
            call_kwargs["table_contexts"] = table_contexts
        base_method(table, **call_kwargs)

        if _nested_path:
            for chunk in self.chunks[chunk_start:]:
                metadata = chunk.setdefault("metadata", {})
                metadata["nested_table"] = True
                metadata["parent_table_index"] = _parent_table_index
                metadata["nested_table_path"] = copy.deepcopy(_nested_path)
                source = metadata.get("source")
                if not isinstance(source, dict):
                    source = {"original_source": copy.deepcopy(source)}
                source.update(
                    {
                        "nested_table": True,
                        "parent_table_index": _parent_table_index,
                        "nested_table_path": copy.deepcopy(_nested_path),
                    }
                )
                metadata["source"] = source

        parent_index = table.get("table_index")
        for nested_table, relative_path in _direct_nested_tables(table):
            nested_path = [*(_nested_path or []), *relative_path]
            self.process_table(
                nested_table,
                section_id=section_id,
                section_path=section_path,
                domain=domain,
                content_index=content_index,
                table_contexts=table_contexts,
                _nested_path=nested_path,
                _parent_table_index=parent_index,
            )


def load_structured_document(input_path: Path) -> dict[str, Any]:
    if not input_path.exists():
        raise FileNotFoundError(f"구조화 JSON을 찾을 수 없습니다.\n{input_path}")
    with input_path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ValueError("구조화 JSON의 최상위 구조가 객체(dict)가 아닙니다.")
    return data


def split_chunk_to_limit(chunk: dict[str, Any], max_chars: int) -> list[dict[str, Any]]:
    text = str(chunk.get("text") or "")
    if len(text) <= max_chars:
        return [copy.deepcopy(chunk)]

    metadata = copy.deepcopy(chunk.get("metadata") or {})
    section_path = metadata.get("section_path") or []
    prefix = build_chunks_module.build_embedding_prefix(section_path)
    body = str(chunk.get("content") or "")
    body_limit = max(1, max_chars - len(prefix) - 2)

    parts = smart_split_text(
        body,
        max_chars=body_limit,
        overlap_chars=min(OVERLAP_CHARS, max(0, body_limit // 4)),
    )
    if not parts:
        parts = split_oversize_unit(body, body_limit) if body else []
    if not parts:
        return []

    result: list[dict[str, Any]] = []
    for part_index, part in enumerate(parts):
        cloned = copy.deepcopy(chunk)
        cloned["content"] = part
        cloned["text"] = f"{prefix}\n\n{part}".strip()
        cloned["char_count"] = len(cloned["text"])

        cloned_metadata = cloned.setdefault("metadata", {})
        source = cloned_metadata.get("source")
        if not isinstance(source, dict):
            source = {"original_source": copy.deepcopy(source)}
        source.update(
            {
                "length_limit_part_index": part_index,
                "length_limit_part_count": len(parts),
                "original_chunk_id": chunk.get("chunk_id"),
            }
        )
        cloned_metadata["source"] = source
        result.append(cloned)
    return result


def enforce_chunk_limits(
    chunks: list[dict[str, Any]],
    max_chars: int = MAX_CHARS,
) -> list[dict[str, Any]]:
    limited: list[dict[str, Any]] = []
    for chunk in chunks:
        limited.extend(split_chunk_to_limit(chunk, max_chars))

    for sequence, chunk in enumerate(limited, start=1):
        chunk["chunk_id"] = f"chunk_{sequence:06d}"
        chunk["char_count"] = len(str(chunk.get("text") or ""))
        if chunk["char_count"] > max_chars:
            raise ValueError(
                "Chunk 길이 제한 적용에 실패했습니다. "
                f"chunk_id={chunk['chunk_id']}, "
                f"char_count={chunk['char_count']}, max_chars={max_chars}"
            )
    return limited


def build_chunk_result(final_document: dict[str, Any]) -> dict[str, Any]:
    patch_chunking_splitter()
    builder = RecursiveChunkBuilder(final_document)
    chunks = enforce_chunk_limits(builder.build())

    return {
        "document": copy.deepcopy(final_document.get("document") or {}),
        "chunking_method": {
            "version": "step4-v5-recursive-nested-semantic-overlap",
            "input": "step3-3_structured_tables",
            "embedding_context_policy": (
                "임베딩 text에는 현재 Section 제목만 포함하고 "
                "문서명과 전체 section_path는 metadata에만 보존"
            ),
            "rules": {
                "paragraph": "문단·목록·문장 경계를 우선해 분할",
                "overlap": (
                    "완전한 문단/목록/문장만 사용하며 마지막 단위가 "
                    "overlap_chars보다 길거나 불완전하면 overlap 생략"
                ),
                "nested_table": (
                    "table cell.blocks를 재귀 순회하고 table_index 기준 중복 없이 "
                    "nested table을 독립 Chunk로 생성"
                ),
                "parent_fallback": (
                    "부모 fallback 표의 일반 텍스트는 유지하되 nested table 텍스트는 제외"
                ),
                "length_limit": f"최종 text {MAX_CHARS}자 이하 후검증",
                "row_records": "record 한 행당 Chunk 하나",
                "key_value": "key-value 한 쌍당 Chunk 하나",
            },
            "max_chars": MAX_CHARS,
            "overlap_chars": OVERLAP_CHARS,
        },
        "summary": build_chunks_module.build_summary(chunks),
        "chunks": chunks,
    }


def run_chunking_pipeline(input_path: Path, output_path: Path) -> dict[str, Any]:
    print()
    print("=" * 72)
    print("Chunking Pipeline 시작")
    print("=" * 72)
    print(f"입력: {input_path}")
    print(f"출력: {output_path}")

    final_document = load_structured_document(input_path)
    result = build_chunk_result(final_document)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    build_chunks_module.save_json(str(output_path), result)
    build_chunks_module.print_result(str(output_path), result)

    print()
    print("=" * 72)
    print("Chunking Pipeline 완료")
    print("=" * 72)
    return result


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Step 3 최종 구조화 JSON을 Step 4 Chunk JSON으로 변환합니다."
    )
    parser.add_argument("--input", required=True, help="step3-3_structured_tables.json 경로")
    parser.add_argument("--output", required=True, help="chunks.json 저장 경로")
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()
    run_chunking_pipeline(Path(args.input).resolve(), Path(args.output).resolve())


if __name__ == "__main__":
    main()
