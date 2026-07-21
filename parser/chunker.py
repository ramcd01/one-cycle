import argparse
import json
import os
import re
import sys
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
            f"JSON 파일을 찾을 수 없습니다: {file_path}"
        )

    with file_path.open(
        "r",
        encoding="utf-8",
    ) as file:

        return json.load(
            file
        )


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
# 기본 텍스트 정리
# ============================================================
def normalize_text(
    text: str,
) -> str:
    """
    Chunk 생성용 기본 텍스트 정리.

    - 줄바꿈 / 탭 → 공백
    - 연속 공백 → 하나의 공백

    단, HWP와 HWPX의 공백 차이를
    완전히 삭제하지는 않습니다.
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
# 제목처럼 보이는 Paragraph 판별
# ============================================================
def is_heading(
    text: str,
) -> bool:
    """
    LH 공고문에서 자주 등장하는
    제목 / 소제목 패턴을 단순 휴리스틱으로 판별합니다.

    너무 강한 규칙을 사용하지 않고,
    Chunk 경계를 잡는 보조 수단으로만 사용합니다.
    """

    text = normalize_text(
        text
    )

    if not text:
        return False

    # 지나치게 긴 문장은 제목으로 보지 않음
    if len(text) > 100:
        return False

    # --------------------------------------------------------
    # 예:
    # ■ 신청자격
    # ■ 유의사항
    # ■ 신청기간 및 방법
    # --------------------------------------------------------
    if text.startswith(
        "■"
    ):
        return True

    # --------------------------------------------------------
    # 예:
    # Ⅰ
    # Ⅱ
    # Ⅲ
    # --------------------------------------------------------
    if re.fullmatch(
        r"[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ]+",
        text,
    ):
        return True

    # --------------------------------------------------------
    # 예:
    # 신청기준 (지역별 물량배정...)
    # 신청자격 및 당첨자 선정방법
    # --------------------------------------------------------
    heading_keywords = [
        "신청자격",
        "신청기간",
        "신청방법",
        "유의사항",
        "당첨자 선정방법",
        "공급신청 자격자",
        "자산보유기준",
        "자산보유 조사방법",
        "조사대상자의 의무",
        "소득기준 적용",
        "공급규모",
        "공급대상",
        "공급가격",
        "청약신청 시 유의사항",
        "부동산",
        "차량기준가액",
        "공간선택",
        "추가선택품목",
        "발코니 확장비용",
        "입주금",
    ]

    for keyword in heading_keywords:

        if (
            text == keyword
            or
            text.startswith(
                keyword
            )
        ):

            return True

    # --------------------------------------------------------
    # <표1> ...
    # <표2> ...
    # --------------------------------------------------------
    if re.match(
        r"^<표\s*\d+>",
        text,
    ):
        return True

    return False


# ============================================================
# 긴 Paragraph를 문장 단위로 분할
# ============================================================
def split_long_paragraph(
    text: str,
    max_chars: int,
) -> list[str]:
    """
    너무 긴 단일 Paragraph를
    문장 단위 중심으로 분할합니다.

    우선순위:
    1. 문장 끝
    2. 최대 길이 강제 분할
    """

    text = normalize_text(
        text
    )

    if not text:
        return []

    if len(text) <= max_chars:
        return [
            text
        ]

    # --------------------------------------------------------
    # 문장 끝 기준 분리
    #
    # . ? ! 뒤에 공백이 오는 경우를 중심으로 분리
    # 행정문서 특성상 "함", "됨" 등은 강제로 쪼개지 않음
    # --------------------------------------------------------
    sentences = re.split(
        r"(?<=[.!?])\s+",
        text,
    )

    parts = []

    current = ""

    for sentence in sentences:

        sentence = sentence.strip()

        if not sentence:
            continue

        if not current:

            # 문장 하나가 max_chars보다 큰 경우
            if len(sentence) > max_chars:

                parts.extend(
                    hard_split_text(
                        sentence,
                        max_chars,
                    )
                )

            else:

                current = sentence

            continue

        candidate = (
            current
            +
            " "
            +
            sentence
        )

        if (
            len(candidate)
            <=
            max_chars
        ):

            current = candidate

        else:

            parts.append(
                current
            )

            if len(sentence) > max_chars:

                long_parts = (
                    hard_split_text(
                        sentence,
                        max_chars,
                    )
                )

                # 마지막 조각은 다음 문장과
                # 이어질 수 있도록 current로 유지
                if long_parts:

                    parts.extend(
                        long_parts[
                            :-1
                        ]
                    )

                    current = (
                        long_parts[
                            -1
                        ]
                    )

                else:

                    current = ""

            else:

                current = sentence

    if current:

        parts.append(
            current
        )

    return parts


# ============================================================
# 최대 길이 강제 분할
# ============================================================
def hard_split_text(
    text: str,
    max_chars: int,
) -> list[str]:
    """
    문장 단위로도 분리할 수 없는
    긴 텍스트를 max_chars 단위로 분할합니다.

    가능하면 공백 위치에서 자릅니다.
    """

    text = normalize_text(
        text
    )

    if not text:
        return []

    parts = []

    remaining = text

    while (
        len(
            remaining
        )
        >
        max_chars
    ):

        cut_position = max_chars

        # ----------------------------------------------------
        # max_chars 이전의 마지막 공백을 찾아
        # 자연스러운 위치에서 자르기
        # ----------------------------------------------------
        space_position = (
            remaining.rfind(
                " ",
                0,
                max_chars,
            )
        )

        if (
            space_position
            >
            int(
                max_chars
                *
                0.6
            )
        ):

            cut_position = (
                space_position
            )

        part = (
            remaining[
                :cut_position
            ]
            .strip()
        )

        if part:

            parts.append(
                part
            )

        remaining = (
            remaining[
                cut_position:
            ]
            .strip()
        )

    if remaining:

        parts.append(
            remaining
        )

    return parts


# ============================================================
# Cell Paragraph 준비
# ============================================================
def prepare_paragraphs(
    cell: dict,
    max_paragraph_chars: int,
) -> list[dict]:
    """
    Cell 내부 paragraphs를
    Chunk 생성 가능한 단위로 변환합니다.

    긴 paragraph는 여러 조각으로 나눕니다.
    """

    result = []

    paragraphs = cell.get(
        "paragraphs",
        [],
    )

    # --------------------------------------------------------
    # paragraphs 정보가 없으면
    # 기존 cell.text를 fallback으로 사용
    # --------------------------------------------------------
    if not paragraphs:

        fallback_text = normalize_text(
            cell.get(
                "text",
                "",
            )
        )

        if not fallback_text:

            return result

        split_parts = (
            split_long_paragraph(
                fallback_text,
                max_paragraph_chars,
            )
        )

        for split_index, part in enumerate(
            split_parts
        ):

            result.append(
                {
                    "paragraph_index":
                        None,

                    "split_index":
                        split_index,

                    "text":
                        part,
                }
            )

        return result

    # --------------------------------------------------------
    # 일반 paragraphs 처리
    # --------------------------------------------------------
    for paragraph in paragraphs:

        paragraph_index = (
            paragraph.get(
                "paragraph_index"
            )
        )

        text = normalize_text(
            paragraph.get(
                "text",
                "",
            )
        )

        if not text:
            continue

        split_parts = (
            split_long_paragraph(
                text,
                max_paragraph_chars,
            )
        )

        for split_index, part in enumerate(
            split_parts
        ):

            result.append(
                {
                    "paragraph_index":
                        paragraph_index,

                    "split_index":
                        split_index,

                    "text":
                        part,
                }
            )

    return result


# ============================================================
# 하나의 Cell을 Chunk로 분할
# ============================================================
def chunk_cell(
    cell: dict,
    section_index: int,
    table_index: int,
    target_chars: int,
    max_chars: int,
    max_paragraph_chars: int,
) -> list[dict]:
    """
    하나의 Cell 내부 paragraphs를
    RAG용 Chunk 단위로 묶습니다.

    규칙:
    - 제목이 나오면 새 Chunk 경계
    - target_chars를 넘으면 적절히 분리
    - max_chars는 절대 최대값
    """

    prepared = (
        prepare_paragraphs(
            cell,
            max_paragraph_chars,
        )
    )

    if not prepared:
        return []

    chunks = []

    current_parts = []

    current_paragraph_refs = []

    current_length = 0

    current_heading = None

    def flush_chunk() -> None:
        """
        현재 누적된 Chunk를 저장합니다.
        """

        nonlocal current_parts
        nonlocal current_paragraph_refs
        nonlocal current_length
        nonlocal current_heading

        if not current_parts:
            return

        chunk_text = "\n".join(
            current_parts
        ).strip()

        if not chunk_text:
            return

        chunks.append(
            {
                "text":
                    chunk_text,

                "heading":
                    current_heading,

                "paragraph_refs":
                    list(
                        current_paragraph_refs
                    ),

                "char_count":
                    len(
                        chunk_text
                    ),
            }
        )

        current_parts = []

        current_paragraph_refs = []

        current_length = 0

        current_heading = None

    # ========================================================
    # Paragraph 순회
    # ========================================================
    for item in prepared:

        text = item[
            "text"
        ]

        heading = is_heading(
            text
        )

        paragraph_ref = {
            "paragraph_index":
                item[
                    "paragraph_index"
                ],

            "split_index":
                item[
                    "split_index"
                ],
        }

        # ----------------------------------------------------
        # 제목 Paragraph가 나왔고
        # 기존 Chunk가 이미 충분히 있는 경우
        # 새 Chunk 시작
        # ----------------------------------------------------
        if (
            heading
            and
            current_parts
        ):

            flush_chunk()

        # ----------------------------------------------------
        # 현재 Chunk에 추가했을 때 예상 길이
        # ----------------------------------------------------
        separator_length = (
            1
            if current_parts
            else 0
        )

        candidate_length = (
            current_length
            +
            separator_length
            +
            len(
                text
            )
        )

        # ----------------------------------------------------
        # 절대 최대 길이를 넘으면 먼저 flush
        # ----------------------------------------------------
        if (
            current_parts
            and
            candidate_length
            >
            max_chars
        ):

            flush_chunk()

        # ----------------------------------------------------
        # target_chars를 이미 넘었고
        # 새 문단을 추가하면 더 길어질 경우
        # ----------------------------------------------------
        elif (
            current_parts
            and
            current_length
            >=
            target_chars
        ):

            flush_chunk()

        # ----------------------------------------------------
        # 제목 저장
        # ----------------------------------------------------
        if (
            heading
            and
            current_heading
            is None
        ):

            current_heading = text

        current_parts.append(
            text
        )

        current_paragraph_refs.append(
            paragraph_ref
        )

        current_length = len(
            "\n".join(
                current_parts
            )
        )

    flush_chunk()

    # ========================================================
    # Chunk metadata 부여
    # ========================================================
    result = []

    for local_chunk_index, chunk in enumerate(
        chunks
    ):

        result.append(
            {
                "chunk_index_in_cell":
                    local_chunk_index,

                "text":
                    chunk[
                        "text"
                    ],

                "heading":
                    chunk[
                        "heading"
                    ],

                "char_count":
                    chunk[
                        "char_count"
                    ],

                "source": {
                    "section_index":
                        section_index,

                    "table_index":
                        table_index,

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
                            "row_span"
                        ),

                    "col_span":
                        cell.get(
                            "col_span"
                        ),

                    "paragraph_refs":
                        chunk[
                            "paragraph_refs"
                        ],
                },
            }
        )

    return result


# ============================================================
# 전체 Common JSON → Chunk JSON
# ============================================================
def build_chunks(
    document: dict,
    target_chars: int = 800,
    max_chars: int = 1200,
    max_paragraph_chars: int = 1000,
) -> dict:
    """
    Common JSON 전체를 순회하여
    RAG용 Chunk JSON을 생성합니다.
    """

    document_info = document.get(
        "document",
        {},
    )

    chunks = []

    global_chunk_index = 0

    sections = document.get(
        "sections",
        [],
    )

    for section in sections:

        section_index = (
            section.get(
                "section_index"
            )
        )

        blocks = section.get(
            "blocks",
            [],
        )

        for block_index, block in enumerate(
            blocks
        ):

            block_type = block.get(
                "type"
            )

            # =================================================
            # 일반 Paragraph Block
            # =================================================
            if (
                block_type
                ==
                "paragraph"
            ):

                text = normalize_text(
                    block.get(
                        "text",
                        "",
                    )
                )

                if not text:
                    continue

                split_parts = (
                    split_long_paragraph(
                        text,
                        max_chars,
                    )
                )

                for split_index, part in enumerate(
                    split_parts
                ):

                    chunk = {
                        "chunk_id":
                            f"chunk_{global_chunk_index:06d}",

                        "text":
                            part,

                        "heading":
                            (
                                part
                                if is_heading(
                                    part
                                )
                                else None
                            ),

                        "char_count":
                            len(
                                part
                            ),

                        "source": {
                            "section_index":
                                section_index,

                            "block_index":
                                block_index,

                            "block_type":
                                "paragraph",

                            "paragraph_index":
                                (
                                    block
                                    .get(
                                        "source",
                                        {},
                                    )
                                    .get(
                                        "paragraph_index"
                                    )
                                ),

                            "split_index":
                                split_index,
                        },
                    }

                    chunks.append(
                        chunk
                    )

                    global_chunk_index += 1

            # =================================================
            # Table Block
            # =================================================
            elif (
                block_type
                ==
                "table"
            ):

                table_index = block.get(
                    "table_index"
                )

                cells = block.get(
                    "cells",
                    [],
                )

                # ---------------------------------------------
                # 문서/표 안의 기본 Cell 순서를 안정적으로 유지
                # ---------------------------------------------
                sorted_cells = sorted(
                    cells,
                    key=lambda cell: (
                        cell.get(
                            "row",
                            0,
                        ),
                        cell.get(
                            "col",
                            0,
                        ),
                    ),
                )

                for cell in sorted_cells:

                    cell_chunks = (
                        chunk_cell(
                            cell=cell,
                            section_index=
                                section_index,
                            table_index=
                                table_index,
                            target_chars=
                                target_chars,
                            max_chars=
                                max_chars,
                            max_paragraph_chars=
                                max_paragraph_chars,
                        )
                    )

                    for cell_chunk in cell_chunks:

                        cell_chunk[
                            "chunk_id"
                        ] = (
                            f"chunk_"
                            f"{global_chunk_index:06d}"
                        )

                        cell_chunk[
                            "source"
                        ][
                            "block_index"
                        ] = block_index

                        cell_chunk[
                            "source"
                        ][
                            "block_type"
                        ] = "table"

                        chunks.append(
                            cell_chunk
                        )

                        global_chunk_index += 1

    result = {
        "document": {
            "filename":
                document_info.get(
                    "filename"
                ),

            "format":
                document_info.get(
                    "format"
                ),
        },

        "chunk_config": {
            "target_chars":
                target_chars,

            "max_chars":
                max_chars,

            "max_paragraph_chars":
                max_paragraph_chars,
        },

        "statistics": {
            "chunk_count":
                len(
                    chunks
                ),
        },

        "chunks":
            chunks,
    }

    return result


# ============================================================
# CLI
# ============================================================
def main():

    parser = argparse.ArgumentParser(
        description=(
            "HWP/HWPX Common JSON을 "
            "RAG용 Chunk JSON으로 변환합니다."
        )
    )

    parser.add_argument(
        "--input",
        required=True,
        help=(
            "Common JSON 입력 경로"
        ),
    )

    parser.add_argument(
        "--output",
        required=True,
        help=(
            "Chunk JSON 출력 경로"
        ),
    )

    parser.add_argument(
        "--target_chars",
        type=int,
        default=800,
        help=(
            "Chunk 권장 길이 "
            "(기본값: 800)"
        ),
    )

    parser.add_argument(
        "--max_chars",
        type=int,
        default=1200,
        help=(
            "Chunk 최대 길이 "
            "(기본값: 1200)"
        ),
    )

    parser.add_argument(
        "--max_paragraph_chars",
        type=int,
        default=1000,
        help=(
            "단일 Paragraph 최대 길이 "
            "(기본값: 1000)"
        ),
    )

    args = parser.parse_args()

    common_json = load_json(
        args.input
    )

    result = build_chunks(
        document=
            common_json,

        target_chars=
            args.target_chars,

        max_chars=
            args.max_chars,

        max_paragraph_chars=
            args.max_paragraph_chars,
    )

    save_json(
        result,
        args.output,
    )

    print()

    print(
        "=" * 80
    )

    print(
        "RAG Chunk 생성 완료"
    )

    print(
        "=" * 80
    )

    print(
        "입력 파일:",
        os.path.abspath(
            args.input
        ),
    )

    print(
        "출력 파일:",
        os.path.abspath(
            args.output
        ),
    )

    print(
        "Chunk 수:",
        result[
            "statistics"
        ][
            "chunk_count"
        ],
    )

    print(
        "Target chars:",
        args.target_chars,
    )

    print(
        "Max chars:",
        args.max_chars,
    )


# ============================================================
# Entry Point
# ============================================================
if __name__ == "__main__":
    main()