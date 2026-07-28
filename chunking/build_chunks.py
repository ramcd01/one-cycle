"""
4단계 청킹

입력
- structure 단계의 최종 결과:
  *_step3-3_structured_tables.json

출력
- chunking/output/<원본명>_step4_chunks.json

청킹 규칙
1. 같은 section 안에서 연속된 paragraph를 묶어 paragraph chunk 생성
2. row_records 표는 record 한 행당 table_row chunk 생성
3. row_records의 values와 merged_values를 모두 청크에 포함
4. key_value 표는 key-value 한 쌍당 table_key_value chunk 생성
5. 구조화되지 않은 표는 원본 cells를 행 순서대로 합쳐
   table_fallback chunk 생성
6. 임베딩용 text에는 전체 계층 경로를 넣지 않고
   현재 Section 제목만 사용
7. 전체 section_path는 metadata에 그대로 보존
8. 표 바로 앞의 짧은 단위·기준 문장을 표 문맥으로 연결
9. 모든 청크에 domain, table_index, row_index 등의
   출처 메타데이터 유지
"""

from __future__ import annotations

import json
import os
import re

from collections import Counter
from copy import deepcopy
from tkinter import Tk, messagebox
from tkinter.filedialog import askopenfilename
from typing import Any


# ===========================================================================
# 기본 설정
# ===========================================================================

# 테스트 단계 기본값
MAX_CHARS = 1200
OVERLAP_CHARS = 150


# ===========================================================================
# 텍스트 처리
# ===========================================================================

def clean_text(
    value: Any,
) -> str:
    """줄바꿈은 유지하되 불필요한 공백을 정리한다."""

    if value is None:
        return ""

    text = (
        str(value)
        .replace(
            "\r\n",
            "\n",
        )
        .replace(
            "\r",
            "\n",
        )
    )

    lines: list[str] = []

    for line in text.split(
        "\n"
    ):
        cleaned = re.sub(
            r"[ \t]+",
            " ",
            line,
        ).strip()

        if cleaned:
            lines.append(
                cleaned
            )

    return "\n".join(
        lines
    ).strip()


def compact_text(
    value: Any,
) -> str:
    """메타데이터나 헤더 비교에 사용할 한 줄 텍스트."""

    return re.sub(
        r"\s+",
        " ",
        clean_text(
            value
        ),
    ).strip()


def get_document_name(
    document: dict[str, Any],
) -> str:
    """문서명을 반환한다."""

    return (
        compact_text(
            document.get(
                "filename"
            )
        )
        or compact_text(
            document.get(
                "document_name"
            )
        )
        or compact_text(
            document.get(
                "title"
            )
        )
        or "unknown_document"
    )


# ===========================================================================
# 표 문맥 추출
# ===========================================================================

TABLE_CONTEXT_MAX_CHARS = 120

UNIT_WORDS = (
    "원",
    "천원",
    "만원",
    "억원",
    "%",
    "㎡",
    "m²",
    "m2",
    "호",
    "세대",
)


def classify_table_context(
    text: str,
) -> str | None:
    """표 바로 앞의 짧은 문장이 단위·기준 문맥인지 판별한다.

    보수적으로 다음만 표 문맥으로 취급한다.
    - 길이가 짧고 "단위"와 실제 단위 표현을 포함한 문장
    - 길이가 짧고 숫자와 "기준"을 함께 포함한 문장

    일반 설명 문단을 잘못 표 전체에 복제하지 않도록
    표와 바로 인접한 paragraph의 연속된 꼬리 부분에만 적용한다.
    """

    cleaned = compact_text(
        text
    )

    if (
        not cleaned
        or len(cleaned)
        > TABLE_CONTEXT_MAX_CHARS
    ):
        return None

    lowered = cleaned.lower()

    if (
        "단위"
        in lowered
        and any(
            unit.lower()
            in lowered
            for unit
            in UNIT_WORDS
        )
    ):
        return "unit"

    if (
        "기준"
        in cleaned
        and re.search(
            r"\d",
            cleaned,
        )
    ):
        return "basis"

    return None


def format_table_context_line(
    text: str,
    context_type: str,
) -> str:
    """표 문맥을 청크에 넣을 표준 문자열로 변환한다."""

    cleaned = compact_text(
        text
    )

    if not cleaned:
        return ""

    if context_type == "unit":
        match = re.search(
            r"단위\s*[:：]?\s*([^\]\)]+)",
            cleaned,
            flags=re.IGNORECASE,
        )

        if match:
            unit_value = (
                match.group(1)
                .strip()
                .strip("[](){}")
                .strip()
            )

            if unit_value:
                return (
                    f"[단위] "
                    f"{unit_value}"
                )

    if context_type == "basis":
        basis_value = (
            cleaned
            .strip()
            .strip("[](){}")
            .strip()
        )

        basis_value = re.sub(
            r"\s*기준\s*$",
            "",
            basis_value,
        ).strip()

        if basis_value:
            return (
                f"[기준] "
                f"{basis_value}"
            )

    return (
        f"[표 문맥] "
        f"{cleaned}"
    )


def split_trailing_table_contexts(
    paragraph_items: list[
        tuple[
            int,
            dict[str, Any],
            str,
        ]
    ],
) -> tuple[
    list[
        tuple[
            int,
            dict[str, Any],
            str,
        ]
    ],
    list[dict[str, Any]],
]:
    """표 직전 paragraph_buffer의 연속된 꼬리에서 표 문맥을 분리한다."""

    if not paragraph_items:
        return [], []

    context_start = len(
        paragraph_items
    )

    while context_start > 0:
        (
            content_index,
            content,
            text,
        ) = paragraph_items[
            context_start - 1
        ]

        context_type = (
            classify_table_context(
                text
            )
        )

        if context_type is None:
            break

        context_start -= 1

    normal_items = (
        paragraph_items[
            :context_start
        ]
    )

    context_items: list[
        dict[str, Any]
    ] = []

    for (
        content_index,
        content,
        text,
    ) in paragraph_items[
        context_start:
    ]:
        context_type = (
            classify_table_context(
                text
            )
        )

        if context_type is None:
            continue

        formatted_text = (
            format_table_context_line(
                text,
                context_type,
            )
        )

        if not formatted_text:
            continue

        context_items.append(
            {
                "context_type": (
                    context_type
                ),
                "text": (
                    clean_text(
                        text
                    )
                ),
                "formatted_text": (
                    formatted_text
                ),
                "content_index": (
                    content_index
                ),
                "paragraph_index": (
                    content.get(
                        "paragraph_index"
                    )
                ),
                "origin_path": (
                    deepcopy(
                        content.get(
                            "origin_path"
                        )
                    )
                ),
            }
        )

    return (
        normal_items,
        context_items,
    )


def prepend_table_contexts(
    body_text: str,
    table_contexts: list[
        dict[str, Any]
    ] | None,
) -> str:
    """표 행 본문 앞에 단위·기준 문맥을 한 번씩 붙인다."""

    body_text = clean_text(
        body_text
    )

    context_lines: list[str] = []

    for context in (
        table_contexts
        or []
    ):
        if not isinstance(
            context,
            dict,
        ):
            continue

        formatted_text = clean_text(
            context.get(
                "formatted_text"
            )
        )

        append_candidate = (
            formatted_text
            if formatted_text
            else format_table_context_line(
                clean_text(
                    context.get(
                        "text"
                    )
                ),
                str(
                    context.get(
                        "context_type"
                    )
                    or ""
                ),
            )
        )

        if (
            append_candidate
            and append_candidate
            not in context_lines
        ):
            context_lines.append(
                append_candidate
            )

    if not context_lines:
        return body_text

    if not body_text:
        return "\n".join(
            context_lines
        )

    return (
        "\n".join(
            context_lines
        )
        + "\n\n"
        + body_text
    )


# ===========================================================================
# 임베딩 Context
# ===========================================================================

def get_current_section_title(
    section_path: list[str],
) -> str:
    """전체 계층 경로 중 현재 Section 제목만 반환한다.

    예:
        [
            "서류제출, 동호지정 및 계약체결 등",
            "계약 시 구비서류"
        ]

    결과:
        "계약 시 구비서류"
    """

    cleaned = [
        compact_text(
            title
        )
        for title
        in (
            section_path
            or []
        )
        if compact_text(
            title
        )
    ]

    if not cleaned:
        return "문서 도입부"

    return cleaned[-1]


def build_embedding_prefix(
    section_path: list[str],
) -> str:
    """임베딩용 Context를 생성한다.

    중요:
    - 문서명은 임베딩 text에 넣지 않는다.
    - 전체 section_path도 임베딩 text에 넣지 않는다.
    - 현재 Section 제목만 사용한다.

    전체 section_path와 문서명은 metadata에 보존된다.
    """

    current_title = (
        get_current_section_title(
            section_path
        )
    )

    return (
        f"[섹션] "
        f"{current_title}"
    )


# ===========================================================================
# 긴 텍스트 분할
# ===========================================================================

def split_long_text(
    text: str,
    max_chars: int = MAX_CHARS,
    overlap_chars: int = OVERLAP_CHARS,
) -> list[str]:
    """긴 텍스트를 문장/줄 경계를 우선해 분할한다."""

    text = clean_text(
        text
    )

    if not text:
        return []

    if (
        len(text)
        <= max_chars
    ):
        return [
            text
        ]

    # 줄바꿈과 문장 종결 표현을 기준으로
    # 의미 단위를 최대한 보존한다.
    units = [
        unit.strip()
        for unit
        in re.split(
            r"(?<=[.!?。])\s+|\n+",
            text,
        )
        if unit.strip()
    ]

    if not units:
        units = [
            text
        ]

    chunks: list[str] = []

    current = ""

    for unit in units:
        candidate = (
            f"{current}\n{unit}".strip()
            if current
            else unit
        )

        if (
            len(candidate)
            <= max_chars
        ):
            current = (
                candidate
            )

            continue

        if current:
            chunks.append(
                current
            )

        # 한 문장 자체가 너무 긴 경우
        if (
            len(unit)
            > max_chars
        ):
            start = 0

            step = max(
                1,
                max_chars
                - overlap_chars,
            )

            while (
                start
                < len(unit)
            ):
                piece = (
                    unit[
                        start:
                        start
                        + max_chars
                    ]
                    .strip()
                )

                if piece:
                    chunks.append(
                        piece
                    )

                start += step

            current = ""

        else:
            current = (
                unit
            )

    if current:
        chunks.append(
            current
        )

    # 인접 청크 간 약간의 문맥 유지
    if (
        overlap_chars > 0
        and len(chunks)
        > 1
    ):
        overlapped: list[
            str
        ] = [
            chunks[0]
        ]

        for index in range(
            1,
            len(chunks),
        ):
            previous_tail = (
                chunks[
                    index - 1
                ][
                    -overlap_chars:
                ]
                .strip()
            )

            current_chunk = (
                chunks[
                    index
                ]
            )

            if (
                previous_tail
                and not current_chunk.startswith(
                    previous_tail
                )
            ):
                current_chunk = (
                    f"{previous_tail}\n"
                    f"{current_chunk}"
                ).strip()

            overlapped.append(
                current_chunk
            )

        chunks = (
            overlapped
        )

    return chunks


# ===========================================================================
# 일반 Content 텍스트 추출
# ===========================================================================

def extract_content_text(
    content: dict[str, Any],
) -> str:
    """paragraph/block 등의 공통 JSON 표현에서 텍스트를 찾는다."""

    for key in (
        "text",
        "content",
        "value",
        "plain_text",
    ):
        value = (
            content.get(
                key
            )
        )

        if (
            isinstance(
                value,
                str,
            )
            and clean_text(
                value
            )
        ):
            return clean_text(
                value
            )

    paragraphs = (
        content.get(
            "paragraphs"
        )
    )

    if isinstance(
        paragraphs,
        list,
    ):
        values = [
            clean_text(
                paragraph.get(
                    "text"
                )
            )
            for paragraph
            in paragraphs
            if (
                isinstance(
                    paragraph,
                    dict,
                )
                and clean_text(
                    paragraph.get(
                        "text"
                    )
                )
            )
        ]

        return "\n".join(
            values
        )

    return ""


# ===========================================================================
# Header Path
# ===========================================================================

def header_path_to_label(
    header_path: Any,
    column: Any = None,
) -> str:
    """header_path를 청크용 라벨 문자열로 변환한다."""

    if isinstance(
        header_path,
        list,
    ):
        cleaned = [
            compact_text(
                value
            )
            for value
            in header_path
            if compact_text(
                value
            )
        ]

        if cleaned:
            # 연속 중복 Header 제거
            unique: list[
                str
            ] = []

            for value in (
                cleaned
            ):
                if (
                    not unique
                    or unique[-1]
                    != value
                ):
                    unique.append(
                        value
                    )

            return " > ".join(
                unique
            )

    if (
        isinstance(
            header_path,
            str,
        )
        and compact_text(
            header_path
        )
    ):
        return compact_text(
            header_path
        )

    if (
        column
        is not None
    ):
        return (
            f"열 {column}"
        )

    return "항목"


# ===========================================================================
# 중복 Line 방지
# ===========================================================================

def append_unique_line(
    lines: list[str],
    line: str,
) -> None:
    """같은 청크 안에서 동일한 텍스트 줄이 중복되는 것을 방지한다."""

    line = clean_text(
        line
    )

    if not line:
        return

    if (
        line
        not in lines
    ):
        lines.append(
            line
        )


# ===========================================================================
# merged_values 처리
# ===========================================================================

def merged_value_to_line(
    merged_item: dict[str, Any],
) -> str:
    """가로 병합된 데이터 Cell을 청크 텍스트 한 줄로 변환한다.

    같은 Header가 여러 열에 반복된 경우:
        (현장) 계약서류: 주민등록표등본

    서로 다른 Header 여러 개를 덮는 경우:
        [병합 영역: 주택형 ~ 공유대지 면적 (㎡)] 소 계

    이를 통해 병합 셀 값을 여러 Header에 각각 복제하지 않는다.
    """

    value = clean_text(
        merged_item.get(
            "value"
        )
    )

    if not value:
        return ""

    covered_header_paths = (
        merged_item.get(
            "covered_header_paths"
        )
        or []
    )

    labels: list[str] = []

    for header_info in (
        covered_header_paths
    ):
        if not isinstance(
            header_info,
            dict,
        ):
            continue

        label = (
            header_path_to_label(
                header_info.get(
                    "header_path"
                ),
                header_info.get(
                    "column"
                ),
            )
        )

        if (
            label
            and label
            not in labels
        ):
            labels.append(
                label
            )

    # 모든 병합 열이 같은 의미 Header인 경우
    if (
        len(labels)
        == 1
    ):
        return (
            f"{labels[0]}: "
            f"{value}"
        )

    # 여러 서로 다른 Header를 가로지르는 경우
    if (
        len(labels)
        > 1
    ):
        first_label = (
            labels[0]
        )

        last_label = (
            labels[-1]
        )

        return (
            "[병합 영역: "
            f"{first_label}"
            " ~ "
            f"{last_label}"
            "] "
            f"{value}"
        )

    return (
        f"[병합 값] "
        f"{value}"
    )


# ===========================================================================
# Metadata
# ===========================================================================

def make_metadata(
    *,
    document: dict[str, Any],
    section_id: Any,
    section_path: list[str],
    domain: Any,
    content_index: int | None = None,
    table_index: Any = None,
    row_index: Any = None,
    row_kind: Any = None,
    table_status: Any = None,
    table_layout: Any = None,
    source: Any = None,
) -> dict[str, Any]:
    """청크 Metadata 생성."""

    metadata: dict[
        str,
        Any,
    ] = {
        "document_name": (
            get_document_name(
                document
            )
        ),
        "document_format": (
            document.get(
                "format"
            )
        ),
        "section_id": (
            section_id
        ),

        # 전체 계층은 Metadata에 유지
        "section_path": (
            deepcopy(
                section_path
            )
        ),

        # 검색/디버깅용 현재 Section 제목
        "section_title": (
            get_current_section_title(
                section_path
            )
        ),

        "domain": (
            deepcopy(
                domain
            )
        ),
    }

    optional_values = {
        "content_index": (
            content_index
        ),
        "table_index": (
            table_index
        ),
        "row_index": (
            row_index
        ),
        "row_kind": (
            row_kind
        ),
        "table_status": (
            table_status
        ),
        "table_layout": (
            table_layout
        ),
        "source": (
            deepcopy(
                source
            )
        ),
    }

    for (
        key,
        value,
    ) in optional_values.items():

        if (
            value
            is not None
        ):
            metadata[
                key
            ] = value

    return metadata


# ===========================================================================
# Chunk Builder
# ===========================================================================

class ChunkBuilder:

    def __init__(
        self,
        final_document: dict[str, Any],
    ) -> None:

        self.final_document = (
            final_document
        )

        self.document = (
            final_document.get(
                "document"
            )
            or {}
        )

        self.document_name = (
            get_document_name(
                self.document
            )
        )

        self.chunks: list[
            dict[str, Any]
        ] = []

        self.sequence = 0


    # =======================================================================
    # 공통 Chunk 추가
    # =======================================================================

    def add_chunk(
        self,
        *,
        chunk_type: str,
        body_text: str,
        metadata: dict[str, Any],
    ) -> None:
        """청크 하나를 추가한다.

        text:
            실제 임베딩에 사용할 문자열

        content:
            Section Context를 제외한 실제 본문

        중요:
        - 문서명은 text에 포함하지 않는다.
        - 전체 section_path는 text에 포함하지 않는다.
        - 현재 Section 제목만 Context로 사용한다.
        """

        body_text = clean_text(
            body_text
        )

        if not body_text:
            return

        prefix = (
            build_embedding_prefix(
                metadata.get(
                    "section_path"
                )
                or []
            )
        )

        full_text = (
            f"{prefix}\n\n"
            f"{body_text}"
        ).strip()

        self.sequence += 1

        self.chunks.append(
            {
                "chunk_id": (
                    f"chunk_"
                    f"{self.sequence:06d}"
                ),
                "chunk_type": (
                    chunk_type
                ),

                # Embedding 대상
                "text": (
                    full_text
                ),

                # 원문 Body
                "content": (
                    body_text
                ),

                "char_count": (
                    len(
                        full_text
                    )
                ),

                "metadata": (
                    metadata
                ),
            }
        )


    # =======================================================================
    # Paragraph Chunk
    # =======================================================================

    def add_paragraph_group(
        self,
        paragraph_items: list[
            tuple[
                int,
                dict[str, Any],
                str,
            ]
        ],
        *,
        section_id: Any,
        section_path: list[str],
        domain: Any,
    ) -> None:
        """같은 Section 안에서 연속된 Paragraph를 묶는다."""

        if not paragraph_items:
            return

        combined = (
            "\n\n".join(
                text
                for (
                    _,
                    _,
                    text,
                )
                in paragraph_items
                if clean_text(
                    text
                )
            )
            .strip()
        )

        if not combined:
            return

        pieces = (
            split_long_text(
                combined
            )
        )

        content_indexes = [
            index
            for (
                index,
                _,
                _,
            )
            in paragraph_items
        ]

        for (
            part_index,
            piece,
        ) in enumerate(
            pieces
        ):
            metadata = (
                make_metadata(
                    document=(
                        self.document
                    ),
                    section_id=(
                        section_id
                    ),
                    section_path=(
                        section_path
                    ),
                    domain=(
                        domain
                    ),
                    content_index=(
                        content_indexes[0]
                        if content_indexes
                        else None
                    ),
                    source={
                        "content_indexes": (
                            content_indexes
                        ),
                        "paragraph_part_index": (
                            part_index
                        ),
                        "paragraph_part_count": (
                            len(
                                pieces
                            )
                        ),
                    },
                )
            )

            self.add_chunk(
                chunk_type=(
                    "paragraph"
                ),
                body_text=(
                    piece
                ),
                metadata=(
                    metadata
                ),
            )


    # =======================================================================
    # Row Records
    # =======================================================================

    def add_row_record_chunks(
        self,
        table: dict[str, Any],
        structured: dict[str, Any],
        *,
        section_id: Any,
        section_path: list[str],
        domain: Any,
        content_index: int,
    ) -> int:
        """row_records 표를 행 단위 Chunk로 변환한다.

        일반 values:
            Header: Value

        merged_values:
            - 같은 Header 영역이면 Header: Value
            - 서로 다른 Header를 가로지르면 병합 영역으로 한 번만 기록

        즉, Step 3에서 제거한 가로 병합 중복을
        Chunking 단계에서 다시 생성하지 않는다.
        """

        count_before = (
            len(
                self.chunks
            )
        )

        for record in (
            structured.get(
                "records"
            )
            or []
        ):
            if not isinstance(
                record,
                dict,
            ):
                continue

            lines: list[
                str
            ] = []

            value_sources: list[
                Any
            ] = []

            merged_sources: list[
                Any
            ] = []

            # ---------------------------------------------------------------
            # 1. 일반 values
            # ---------------------------------------------------------------

            for value_item in (
                record.get(
                    "values"
                )
                or []
            ):
                if not isinstance(
                    value_item,
                    dict,
                ):
                    continue

                value = clean_text(
                    value_item.get(
                        "value"
                    )
                )

                if not value:
                    continue

                label = (
                    header_path_to_label(
                        value_item.get(
                            "header_path"
                        ),
                        value_item.get(
                            "column"
                        ),
                    )
                )

                append_unique_line(
                    lines,
                    (
                        f"{label}: "
                        f"{value}"
                    ),
                )

                source = (
                    value_item.get(
                        "source"
                    )
                )

                if (
                    source
                    is not None
                ):
                    value_sources.append(
                        deepcopy(
                            source
                        )
                    )

            # ---------------------------------------------------------------
            # 2. merged_values
            # ---------------------------------------------------------------

            for merged_item in (
                record.get(
                    "merged_values"
                )
                or []
            ):
                if not isinstance(
                    merged_item,
                    dict,
                ):
                    continue

                merged_line = (
                    merged_value_to_line(
                        merged_item
                    )
                )

                append_unique_line(
                    lines,
                    merged_line,
                )

                source = (
                    merged_item.get(
                        "source"
                    )
                )

                if (
                    source
                    is not None
                ):
                    merged_sources.append(
                        {
                            "source": (
                                deepcopy(
                                    source
                                )
                            ),
                            "row_span": (
                                merged_item.get(
                                    "row_span"
                                )
                            ),
                            "col_span": (
                                merged_item.get(
                                    "col_span"
                                )
                            ),
                            "covered_columns": (
                                deepcopy(
                                    merged_item.get(
                                        "covered_columns"
                                    )
                                )
                            ),
                            "covered_header_paths": (
                                deepcopy(
                                    merged_item.get(
                                        "covered_header_paths"
                                    )
                                )
                            ),
                        }
                    )

            if not lines:
                continue

            metadata = (
                make_metadata(
                    document=(
                        self.document
                    ),
                    section_id=(
                        section_id
                    ),
                    section_path=(
                        section_path
                    ),
                    domain=(
                        domain
                    ),
                    content_index=(
                        content_index
                    ),
                    table_index=(
                        table.get(
                            "table_index"
                        )
                    ),
                    row_index=(
                        record.get(
                            "row_index"
                        )
                    ),
                    row_kind=(
                        record.get(
                            "row_kind"
                        )
                    ),
                    table_status=(
                        structured.get(
                            "status"
                        )
                    ),
                    table_layout=(
                        structured.get(
                            "layout"
                        )
                    ),
                    source={
                        "record_sources": (
                            value_sources
                        ),
                        "merged_record_sources": (
                            merged_sources
                        ),
                        "original_table_source": (
                            deepcopy(
                                table.get(
                                    "source"
                                )
                            )
                        ),
                    },
                )
            )

            self.add_chunk(
                chunk_type=(
                    "table_row"
                ),
                body_text=(
                    "\n".join(
                        lines
                    )
                ),
                metadata=(
                    metadata
                ),
            )

        return (
            len(
                self.chunks
            )
            - count_before
        )


    # =======================================================================
    # Key-Value
    # =======================================================================

    def add_key_value_chunks(
        self,
        table: dict[str, Any],
        structured: dict[str, Any],
        *,
        section_id: Any,
        section_path: list[str],
        domain: Any,
        content_index: int,
    ) -> int:
        """Key-Value 표를 Chunk로 변환한다."""

        count_before = (
            len(
                self.chunks
            )
        )

        for record in (
            structured.get(
                "records"
            )
            or []
        ):
            if not isinstance(
                record,
                dict,
            ):
                continue

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
                not key
                and not value
            ):
                continue

            if (
                key
                and value
            ):
                body = (
                    f"{key}: "
                    f"{value}"
                )

            elif key:
                body = (
                    key
                )

            else:
                body = (
                    value
                )

            metadata = (
                make_metadata(
                    document=(
                        self.document
                    ),
                    section_id=(
                        section_id
                    ),
                    section_path=(
                        section_path
                    ),
                    domain=(
                        domain
                    ),
                    content_index=(
                        content_index
                    ),
                    table_index=(
                        table.get(
                            "table_index"
                        )
                    ),
                    row_index=(
                        record.get(
                            "row_index"
                        )
                    ),
                    table_status=(
                        structured.get(
                            "status"
                        )
                    ),
                    table_layout=(
                        structured.get(
                            "layout"
                        )
                    ),
                    source={
                        "key_source": (
                            deepcopy(
                                record.get(
                                    "key_source"
                                )
                            )
                        ),
                        "value_source": (
                            deepcopy(
                                record.get(
                                    "value_source"
                                )
                            )
                        ),
                        "original_table_source": (
                            deepcopy(
                                table.get(
                                    "source"
                                )
                            )
                        ),
                    },
                )
            )

            self.add_chunk(
                chunk_type=(
                    "table_key_value"
                ),
                body_text=(
                    body
                ),
                metadata=(
                    metadata
                ),
            )

        return (
            len(
                self.chunks
            )
            - count_before
        )


    # =======================================================================
    # Fallback Cell Text
    # =======================================================================

    def extract_cell_text(
        self,
        cell: dict[str, Any],
    ) -> str:
        """Cell의 text가 없을 경우 blocks까지 확인한다."""

        direct_text = clean_text(
            cell.get(
                "text"
            )
        )

        if direct_text:
            return (
                direct_text
            )

        blocks = (
            cell.get(
                "blocks"
            )
            or []
        )

        block_texts: list[
            str
        ] = []

        for block in (
            blocks
        ):
            if not isinstance(
                block,
                dict,
            ):
                continue

            text = (
                extract_content_text(
                    block
                )
            )

            if text:
                block_texts.append(
                    text
                )

        return "\n".join(
            block_texts
        )


    # =======================================================================
    # Fallback Table
    # =======================================================================

    def build_fallback_table_text(
        self,
        table: dict[str, Any],
    ) -> str:
        """원본 cells를 행/열 순서대로 정렬해 검색 가능한 텍스트로 만든다."""

        cells = [
            cell
            for cell
            in (
                table.get(
                    "cells"
                )
                or []
            )
            if isinstance(
                cell,
                dict,
            )
        ]

        if not cells:
            return (
                extract_content_text(
                    table
                )
            )

        rows: dict[
            int,
            list[
                tuple[
                    int,
                    str,
                ]
            ],
        ] = {}

        for cell in (
            cells
        ):
            try:
                row = int(
                    cell.get(
                        "row",
                        0,
                    )
                    or 0
                )

                col = int(
                    cell.get(
                        "col",
                        0,
                    )
                    or 0
                )

            except (
                TypeError,
                ValueError,
            ):
                row = 0
                col = 0

            text = (
                self.extract_cell_text(
                    cell
                )
            )

            if not text:
                continue

            rows.setdefault(
                row,
                [],
            ).append(
                (
                    col,
                    text,
                )
            )

        row_lines: list[
            str
        ] = []

        for row in sorted(
            rows
        ):
            values = [
                value
                for (
                    _,
                    value,
                )
                in sorted(
                    rows[
                        row
                    ],
                    key=lambda item: (
                        item[
                            0
                        ]
                    ),
                )
                if value
            ]

            if values:
                row_lines.append(
                    " | ".join(
                        values
                    )
                )

        return "\n".join(
            row_lines
        )


    # =======================================================================
    # Fallback Chunk
    # =======================================================================

    def add_fallback_table_chunks(
        self,
        table: dict[str, Any],
        structured: dict[str, Any],
        *,
        section_id: Any,
        section_path: list[str],
        domain: Any,
        content_index: int,
        reason: str,
    ) -> int:

        count_before = (
            len(
                self.chunks
            )
        )

        fallback_text = (
            self.build_fallback_table_text(
                table
            )
        )

        pieces = (
            split_long_text(
                fallback_text
            )
        )

        for (
            part_index,
            piece,
        ) in enumerate(
            pieces
        ):
            metadata = (
                make_metadata(
                    document=(
                        self.document
                    ),
                    section_id=(
                        section_id
                    ),
                    section_path=(
                        section_path
                    ),
                    domain=(
                        domain
                    ),
                    content_index=(
                        content_index
                    ),
                    table_index=(
                        table.get(
                            "table_index"
                        )
                    ),
                    table_status=(
                        structured.get(
                            "status"
                        )
                        or "missing"
                    ),
                    table_layout=(
                        structured.get(
                            "layout"
                        )
                    ),
                    source={
                        "fallback_reason": (
                            reason
                        ),
                        "fallback_part_index": (
                            part_index
                        ),
                        "fallback_part_count": (
                            len(
                                pieces
                            )
                        ),
                        "original_table_source": (
                            deepcopy(
                                table.get(
                                    "source"
                                )
                            )
                        ),
                    },
                )
            )

            self.add_chunk(
                chunk_type=(
                    "table_fallback"
                ),
                body_text=(
                    piece
                ),
                metadata=(
                    metadata
                ),
            )

        return (
            len(
                self.chunks
            )
            - count_before
        )


    # =======================================================================
    # 표 문맥 적용
    # =======================================================================

    def apply_table_context_to_recent_chunks(
        self,
        start_index: int,
        table_contexts: list[
            dict[str, Any]
        ] | None,
    ) -> None:
        """방금 생성한 표 청크들에 단위·기준 문맥을 연결한다."""

        if not table_contexts:
            return

        for chunk in self.chunks[
            start_index:
        ]:
            if not str(
                chunk.get(
                    "chunk_type"
                )
                or ""
            ).startswith(
                "table_"
            ):
                continue

            metadata = (
                chunk.get(
                    "metadata"
                )
                or {}
            )

            body_text = (
                prepend_table_contexts(
                    str(
                        chunk.get(
                            "content"
                        )
                        or ""
                    ),
                    table_contexts,
                )
            )

            prefix = (
                build_embedding_prefix(
                    metadata.get(
                        "section_path"
                    )
                    or []
                )
            )

            full_text = (
                f"{prefix}\n\n"
                f"{body_text}"
            ).strip()

            chunk[
                "content"
            ] = body_text

            chunk[
                "text"
            ] = full_text

            chunk[
                "char_count"
            ] = len(
                full_text
            )

            metadata[
                "table_contexts"
            ] = deepcopy(
                table_contexts
            )


    # =======================================================================
    # Table 처리
    # =======================================================================

    def process_table(
        self,
        table: dict[str, Any],
        *,
        section_id: Any,
        section_path: list[str],
        domain: Any,
        content_index: int,
        table_contexts: list[
            dict[str, Any]
        ] | None = None,
    ) -> None:

        chunk_start_index = len(
            self.chunks
        )

        structured = (
            table.get(
                "structured_table"
            )
        )

        if not isinstance(
            structured,
            dict,
        ):
            structured = {}

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

        generated = 0

        # 부분 구조화라도 유효한 records가 있으면 우선 사용
        if (
            status
            in {
                "structured",
                "partially_structured",
            }
        ):
            if (
                layout
                == "row_records"
            ):
                generated = (
                    self.add_row_record_chunks(
                        table,
                        structured,
                        section_id=(
                            section_id
                        ),
                        section_path=(
                            section_path
                        ),
                        domain=(
                            domain
                        ),
                        content_index=(
                            content_index
                        ),
                    )
                )

            elif (
                layout
                == "key_value"
            ):
                generated = (
                    self.add_key_value_chunks(
                        table,
                        structured,
                        section_id=(
                            section_id
                        ),
                        section_path=(
                            section_path
                        ),
                        domain=(
                            domain
                        ),
                        content_index=(
                            content_index
                        ),
                    )
                )

        # 구조화 정보가 없거나
        # records가 비어 있으면 원본 표 fallback
        if (
            generated
            == 0
        ):
            reason = (
                compact_text(
                    structured.get(
                        "reason"
                    )
                )
                or (
                    "구조화 결과 사용 불가"
                    f"(status={status}, "
                    f"layout={layout})"
                )
            )

            self.add_fallback_table_chunks(
                table,
                structured,
                section_id=(
                    section_id
                ),
                section_path=(
                    section_path
                ),
                domain=(
                    domain
                ),
                content_index=(
                    content_index
                ),
                reason=(
                    reason
                ),
            )

        self.apply_table_context_to_recent_chunks(
            chunk_start_index,
            table_contexts,
        )


    # =======================================================================
    # Contents 처리
    # =======================================================================

    def process_contents(
        self,
        contents: list[Any],
        *,
        section_id: Any,
        section_path: list[str],
        domain: Any,
    ) -> None:

        paragraph_buffer: list[
            tuple[
                int,
                dict[str, Any],
                str,
            ]
        ] = []

        def flush_paragraphs() -> None:
            nonlocal paragraph_buffer

            self.add_paragraph_group(
                paragraph_buffer,
                section_id=(
                    section_id
                ),
                section_path=(
                    section_path
                ),
                domain=(
                    domain
                ),
            )

            paragraph_buffer = []

        for (
            content_index,
            content,
        ) in enumerate(
            contents
            or []
        ):
            if not isinstance(
                content,
                dict,
            ):
                continue

            content_type = (
                compact_text(
                    content.get(
                        "type"
                    )
                )
                .lower()
            )

            if (
                content_type
                in {
                    "paragraph",
                    "text",
                    "block",
                    "list",
                    "notice",
                }
            ):
                text = (
                    extract_content_text(
                        content
                    )
                )

                if text:
                    paragraph_buffer.append(
                        (
                            content_index,
                            content,
                            text,
                        )
                    )

                continue

            if (
                content_type
                == "table"
            ):
                (
                    normal_paragraphs,
                    table_contexts,
                ) = (
                    split_trailing_table_contexts(
                        paragraph_buffer
                    )
                )

                self.add_paragraph_group(
                    normal_paragraphs,
                    section_id=(
                        section_id
                    ),
                    section_path=(
                        section_path
                    ),
                    domain=(
                        domain
                    ),
                )

                paragraph_buffer = []

                self.process_table(
                    content,
                    section_id=(
                        section_id
                    ),
                    section_path=(
                        section_path
                    ),
                    domain=(
                        domain
                    ),
                    content_index=(
                        content_index
                    ),
                    table_contexts=(
                        table_contexts
                    ),
                )

                continue

            # Paragraph 사이에 알 수 없는 타입이 들어오면
            # Paragraph Chunk를 먼저 종료
            flush_paragraphs()

            # 알 수 없는 타입도 Text가 있으면 보존
            fallback_text = (
                extract_content_text(
                    content
                )
            )

            if fallback_text:
                metadata = (
                    make_metadata(
                        document=(
                            self.document
                        ),
                        section_id=(
                            section_id
                        ),
                        section_path=(
                            section_path
                        ),
                        domain=(
                            domain
                        ),
                        content_index=(
                            content_index
                        ),
                        source={
                            "original_content_type": (
                                content_type
                                or None
                            )
                        },
                    )
                )

                self.add_chunk(
                    chunk_type=(
                        "content_fallback"
                    ),
                    body_text=(
                        fallback_text
                    ),
                    metadata=(
                        metadata
                    ),
                )

        flush_paragraphs()


    # =======================================================================
    # Section 처리
    # =======================================================================

    def process_section(
        self,
        section: dict[str, Any],
        parent_path: list[str],
    ) -> None:

        title = compact_text(
            section.get(
                "title"
            )
        )

        current_path = (
            parent_path
            + (
                [
                    title
                ]
                if title
                else []
            )
        )

        self.process_contents(
            section.get(
                "contents"
            )
            or [],
            section_id=(
                section.get(
                    "section_id"
                )
            ),
            section_path=(
                current_path
            ),
            domain=(
                section.get(
                    "domain"
                )
            ),
        )

        for child in (
            section.get(
                "children"
            )
            or []
        ):
            if isinstance(
                child,
                dict,
            ):
                self.process_section(
                    child,
                    current_path,
                )


    # =======================================================================
    # 전체 Build
    # =======================================================================

    def build(
        self,
    ) -> list[
        dict[str, Any]
    ]:

        # 계층에 들어가지 못한 도입부도 검색 대상
        self.process_contents(
            self.final_document.get(
                "intro"
            )
            or [],
            section_id=(
                "intro"
            ),
            section_path=[
                "문서 도입부"
            ],
            domain=None,
        )

        for section in (
            self.final_document.get(
                "sections"
            )
            or []
        ):
            if isinstance(
                section,
                dict,
            ):
                self.process_section(
                    section,
                    [],
                )

        return (
            self.chunks
        )


# ===========================================================================
# Summary
# ===========================================================================

def build_summary(
    chunks: list[
        dict[str, Any]
    ],
) -> dict[str, Any]:

    type_counts = Counter(
        chunk.get(
            "chunk_type",
            "unknown",
        )
        for chunk
        in chunks
    )

    total_chars = sum(
        int(
            chunk.get(
                "char_count",
                0,
            )
            or 0
        )
        for chunk
        in chunks
    )

    merged_source_count = 0

    for chunk in (
        chunks
    ):
        metadata = (
            chunk.get(
                "metadata"
            )
            or {}
        )

        source = (
            metadata.get(
                "source"
            )
            or {}
        )

        merged_sources = (
            source.get(
                "merged_record_sources"
            )
            or []
        )

        merged_source_count += (
            len(
                merged_sources
            )
        )

    table_context_chunk_count = 0
    unit_context_chunk_count = 0
    basis_context_chunk_count = 0

    unique_context_sources: set[
        tuple[Any, ...]
    ] = set()

    for chunk in (
        chunks
    ):
        metadata = (
            chunk.get(
                "metadata"
            )
            or {}
        )

        table_contexts = (
            metadata.get(
                "table_contexts"
            )
            or []
        )

        if not table_contexts:
            continue

        table_context_chunk_count += 1

        context_types = {
            str(
                context.get(
                    "context_type"
                )
                or ""
            )
            for context
            in table_contexts
            if isinstance(
                context,
                dict,
            )
        }

        if "unit" in context_types:
            unit_context_chunk_count += 1

        if "basis" in context_types:
            basis_context_chunk_count += 1

        for context in (
            table_contexts
        ):
            if not isinstance(
                context,
                dict,
            ):
                continue

            origin_path = (
                context.get(
                    "origin_path"
                )
                or []
            )

            if isinstance(
                origin_path,
                list,
            ):
                origin_key = tuple(
                    str(value)
                    for value
                    in origin_path
                )
            else:
                origin_key = (
                    str(
                        origin_path
                    ),
                )

            unique_context_sources.add(
                (
                    context.get(
                        "context_type"
                    ),
                    context.get(
                        "paragraph_index"
                    ),
                    context.get(
                        "content_index"
                    ),
                    origin_key,
                    context.get(
                        "text"
                    ),
                )
            )

    return {
        "total_chunks": (
            len(
                chunks
            )
        ),
        "chunk_type_counts": (
            dict(
                sorted(
                    type_counts.items()
                )
            )
        ),
        "merged_values_included": (
            merged_source_count
        ),
        "table_context_source_count": (
            len(
                unique_context_sources
            )
        ),
        "table_context_chunk_count": (
            table_context_chunk_count
        ),
        "unit_context_chunk_count": (
            unit_context_chunk_count
        ),
        "basis_context_chunk_count": (
            basis_context_chunk_count
        ),
        "total_characters": (
            total_chars
        ),
        "average_characters": (
            round(
                total_chars
                / len(
                    chunks
                ),
                2,
            )
            if chunks
            else 0
        ),
        "max_characters": (
            max(
                (
                    int(
                        chunk.get(
                            "char_count",
                            0,
                        )
                        or 0
                    )
                    for chunk
                    in chunks
                ),
                default=0,
            )
        ),
        "min_characters": (
            min(
                (
                    int(
                        chunk.get(
                            "char_count",
                            0,
                        )
                        or 0
                    )
                    for chunk
                    in chunks
                ),
                default=0,
            )
        ),
    }


# ===========================================================================
# JSON 저장
# ===========================================================================

def save_json(
    path: str,
    data: dict[str, Any],
) -> None:

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


# ===========================================================================
# 입력 파일 선택
# ===========================================================================

def select_input_json(
) -> str | None:

    root = Tk()

    root.withdraw()

    root.attributes(
        "-topmost",
        True,
    )

    selected = (
        askopenfilename(
            title=(
                "3단계 최종 구조화 JSON 선택"
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
    )

    root.destroy()

    return (
        selected
        or None
    )


# ===========================================================================
# 출력 경로
# ===========================================================================

def make_output_path(
    input_path: str,
) -> str:

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

    os.makedirs(
        output_dir,
        exist_ok=True,
    )

    filename = (
        os.path.basename(
            input_path
        )
    )

    (
        stem,
        _,
    ) = os.path.splitext(
        filename
    )

    suffix = (
        "_step3-3_structured_tables"
    )

    if stem.endswith(
        suffix
    ):
        stem = (
            stem[
                :-len(
                    suffix
                )
            ]
        )

    return os.path.join(
        output_dir,
        (
            f"{stem}_"
            "step4_chunks.json"
        ),
    )


# ===========================================================================
# 결과 출력
# ===========================================================================

def print_result(
    output_path: str,
    result: dict[str, Any],
) -> None:

    summary = (
        result.get(
            "summary"
        )
        or {}
    )

    print(
        "\n"
        + "=" * 72
    )

    print(
        "4단계 청킹 완료"
    )

    print(
        "=" * 72
    )

    print(
        f"출력 파일: "
        f"{output_path}"
    )

    print(
        f"전체 청크: "
        f"{summary.get('total_chunks', 0)}개"
    )

    print(
        "유형별 청크:"
    )

    for (
        chunk_type,
        count,
    ) in (
        summary.get(
            "chunk_type_counts"
        )
        or {}
    ).items():

        print(
            f"  - "
            f"{chunk_type}: "
            f"{count}개"
        )

    print(
        "청크에 포함된 "
        "merged_values: "
        f"{summary.get('merged_values_included', 0)}개"
    )

    print(
        "표 문맥 원본: "
        f"{summary.get('table_context_source_count', 0)}개"
    )

    print(
        "표 문맥이 연결된 청크: "
        f"{summary.get('table_context_chunk_count', 0)}개 "
        f"(단위 "
        f"{summary.get('unit_context_chunk_count', 0)}개, "
        f"기준 "
        f"{summary.get('basis_context_chunk_count', 0)}개)"
    )

    print(
        "청크 길이(문자): "
        f"최소 "
        f"{summary.get('min_characters', 0)}, "
        f"평균 "
        f"{summary.get('average_characters', 0)}, "
        f"최대 "
        f"{summary.get('max_characters', 0)}"
    )

    print(
        "=" * 72
        + "\n"
    )


# ===========================================================================
# 실행
# ===========================================================================

def main(
) -> None:

    input_path = (
        select_input_json()
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

            final_document = (
                json.load(
                    file
                )
            )

        if not isinstance(
            final_document,
            dict,
        ):
            raise ValueError(
                "최상위 JSON 구조가 "
                "객체(dict)가 아닙니다."
            )

        builder = (
            ChunkBuilder(
                final_document
            )
        )

        chunks = (
            builder.build()
        )

        result = {
            "document": (
                deepcopy(
                    final_document.get(
                        "document"
                    )
                    or {}
                )
            ),

            "chunking_method": {
                "version": (
                    "step4-test-v3"
                ),
                "input": (
                    "step3-3_structured_tables"
                ),

                "embedding_context_policy": (
                    "임베딩 text에는 현재 Section 제목만 포함하고 "
                    "문서명과 전체 section_path는 metadata에만 보존"
                ),

                "rules": {
                    "paragraph": (
                        "같은 section 내 연속 paragraph를 묶고 "
                        "긴 텍스트는 글자 수 기준 분할"
                    ),

                    "row_records": (
                        "record 한 행당 청크 하나. "
                        "values와 merged_values 모두 포함"
                    ),

                    "horizontal_merged_data": (
                        "가로 병합 값은 여러 Header에 복제하지 않고 "
                        "merged_values의 논리 값 한 개로 청크에 포함"
                    ),

                    "key_value": (
                        "key-value 한 쌍당 청크 하나"
                    ),

                    "table_context": (
                        "표 바로 앞의 짧은 단위·기준 문장을 감지해 "
                        "해당 표의 모든 청크에 연결하고 metadata에 출처 보존"
                    ),

                    "fallback": (
                        "구조화 결과를 사용할 수 없는 표는 "
                        "원본 cells와 cell blocks를 "
                        "행 순서대로 합쳐 청크 생성"
                    ),
                },

                "max_chars": (
                    MAX_CHARS
                ),

                "overlap_chars": (
                    OVERLAP_CHARS
                ),
            },

            "summary": (
                build_summary(
                    chunks
                )
            ),

            "chunks": (
                chunks
            ),
        }

        output_path = (
            make_output_path(
                input_path
            )
        )

        save_json(
            output_path,
            result,
        )

        print_result(
            output_path,
            result,
        )

        messagebox.showinfo(
            "청킹 완료",
            (
                "청킹 결과를 생성했습니다.\n\n"
                f"{output_path}\n\n"
                f"전체 청크: "
                f"{len(chunks)}개"
            ),
        )

    except (
        OSError,
        json.JSONDecodeError,
        ValueError,
        TypeError,
    ) as error:

        messagebox.showerror(
            "청킹 실패",
            str(
                error
            ),
        )

        raise


if __name__ == "__main__":
    main()