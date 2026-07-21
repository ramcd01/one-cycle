import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


# ============================================================
# UTF-8 출력
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

    file_path = Path(path)

    if not file_path.exists():
        raise FileNotFoundError(
            f"파일을 찾을 수 없습니다: {file_path}"
        )

    with file_path.open(
        "r",
        encoding="utf-8",
    ) as file:

        return json.load(file)


# ============================================================
# 텍스트 정규화
# ============================================================
def normalize_text(
    text: str | None,
) -> str:

    if text is None:
        return ""

    return re.sub(
        r"\s+",
        " ",
        str(text),
    ).strip()


def compact_text(
    text: str | None,
) -> str:
    """
    모든 공백을 제거한 비교용 문자열.

    HWP / HWPX 간 공백 차이 여부를
    별도로 확인하기 위해 사용합니다.
    """

    if text is None:
        return ""

    return re.sub(
        r"\s+",
        "",
        str(text),
    )


# ============================================================
# Source 정규화
# ============================================================
def normalize_source(
    source: dict,
) -> dict:
    """
    비교할 source metadata만 추출합니다.
    """

    return {
        "section_index":
            source.get(
                "section_index"
            ),

        "block_index":
            source.get(
                "block_index"
            ),

        "block_type":
            source.get(
                "block_type"
            ),

        "table_index":
            source.get(
                "table_index"
            ),

        "row":
            source.get(
                "row"
            ),

        "col":
            source.get(
                "col"
            ),

        "row_span":
            source.get(
                "row_span"
            ),

        "col_span":
            source.get(
                "col_span"
            ),

        "paragraph_refs":
            source.get(
                "paragraph_refs",
                [],
            ),
    }


# ============================================================
# Chunk 비교
# ============================================================
def compare_chunks(
    hwp_data: dict,
    hwpx_data: dict,
) -> None:

    hwp_chunks = hwp_data.get(
        "chunks",
        [],
    )

    hwpx_chunks = hwpx_data.get(
        "chunks",
        [],
    )

    print()
    print(
        "=" * 100
    )
    print(
        "HWP / HWPX Enriched Chunk 비교"
    )
    print(
        "=" * 100
    )

    print(
        "HWP Chunk 수  :",
        len(
            hwp_chunks
        ),
    )

    print(
        "HWPX Chunk 수 :",
        len(
            hwpx_chunks
        ),
    )

    print()

    if (
        len(
            hwp_chunks
        )
        !=
        len(
            hwpx_chunks
        )
    ):
        print(
            "[WARN] Chunk 개수가 다릅니다."
        )

    # ========================================================
    # 통계
    # ========================================================
    total = min(
        len(
            hwp_chunks
        ),
        len(
            hwpx_chunks
        ),
    )

    chunk_id_match = 0

    source_match = 0

    section_number_match = 0

    section_name_match = 0

    section_title_match = 0

    section_header_match = 0

    heading_exact_match = 0

    heading_compact_match = 0

    text_exact_match = 0

    text_normalized_match = 0

    text_compact_match = 0

    mismatch_summary = []

    # ========================================================
    # Chunk 순회
    # ========================================================
    for index in range(
        total
    ):

        hwp_chunk = (
            hwp_chunks[
                index
            ]
        )

        hwpx_chunk = (
            hwpx_chunks[
                index
            ]
        )

        differences = []

        # ----------------------------------------------------
        # chunk_id
        # ----------------------------------------------------
        if (
            hwp_chunk.get(
                "chunk_id"
            )
            ==
            hwpx_chunk.get(
                "chunk_id"
            )
        ):

            chunk_id_match += 1

        else:

            differences.append(
                "chunk_id"
            )

        # ----------------------------------------------------
        # source
        # ----------------------------------------------------
        hwp_source = (
            normalize_source(
                hwp_chunk.get(
                    "source",
                    {},
                )
            )
        )

        hwpx_source = (
            normalize_source(
                hwpx_chunk.get(
                    "source",
                    {},
                )
            )
        )

        if (
            hwp_source
            ==
            hwpx_source
        ):

            source_match += 1

        else:

            differences.append(
                "source"
            )

        # ----------------------------------------------------
        # section_number
        # ----------------------------------------------------
        if (
            hwp_chunk.get(
                "section_number"
            )
            ==
            hwpx_chunk.get(
                "section_number"
            )
        ):

            section_number_match += 1

        else:

            differences.append(
                "section_number"
            )

        # ----------------------------------------------------
        # section_name
        # ----------------------------------------------------
        if (
            hwp_chunk.get(
                "section_name"
            )
            ==
            hwpx_chunk.get(
                "section_name"
            )
        ):

            section_name_match += 1

        else:

            differences.append(
                "section_name"
            )

        # ----------------------------------------------------
        # section_title
        # ----------------------------------------------------
        if (
            hwp_chunk.get(
                "section_title"
            )
            ==
            hwpx_chunk.get(
                "section_title"
            )
        ):

            section_title_match += 1

        else:

            differences.append(
                "section_title"
            )

        # ----------------------------------------------------
        # is_section_header
        # ----------------------------------------------------
        if (
            hwp_chunk.get(
                "is_section_header"
            )
            ==
            hwpx_chunk.get(
                "is_section_header"
            )
        ):

            section_header_match += 1

        else:

            differences.append(
                "is_section_header"
            )

        # ----------------------------------------------------
        # heading
        # ----------------------------------------------------
        hwp_heading = (
            hwp_chunk.get(
                "heading"
            )
        )

        hwpx_heading = (
            hwpx_chunk.get(
                "heading"
            )
        )

        if (
            hwp_heading
            ==
            hwpx_heading
        ):

            heading_exact_match += 1

        else:

            if (
                compact_text(
                    hwp_heading
                )
                ==
                compact_text(
                    hwpx_heading
                )
            ):

                heading_compact_match += 1

            else:

                differences.append(
                    "heading"
                )

        # exact heading도 compact match에 포함
        if (
            compact_text(
                hwp_heading
            )
            ==
            compact_text(
                hwpx_heading
            )
        ):

            if (
                hwp_heading
                ==
                hwpx_heading
            ):
                heading_compact_match += 1

        # ----------------------------------------------------
        # text
        # ----------------------------------------------------
        hwp_text = (
            hwp_chunk.get(
                "text",
                "",
            )
        )

        hwpx_text = (
            hwpx_chunk.get(
                "text",
                "",
            )
        )

        if (
            hwp_text
            ==
            hwpx_text
        ):

            text_exact_match += 1

        elif (
            normalize_text(
                hwp_text
            )
            ==
            normalize_text(
                hwpx_text
            )
        ):

            text_normalized_match += 1

        elif (
            compact_text(
                hwp_text
            )
            ==
            compact_text(
                hwpx_text
            )
        ):

            text_compact_match += 1

        else:

            differences.append(
                "text"
            )

        # ----------------------------------------------------
        # 실질적 구조 차이가 있을 경우 기록
        # ----------------------------------------------------
        if differences:

            mismatch_summary.append(
                {
                    "index":
                        index,

                    "hwp_chunk_id":
                        hwp_chunk.get(
                            "chunk_id"
                        ),

                    "hwpx_chunk_id":
                        hwpx_chunk.get(
                            "chunk_id"
                        ),

                    "differences":
                        differences,

                    "hwp_section_title":
                        hwp_chunk.get(
                            "section_title"
                        ),

                    "hwpx_section_title":
                        hwpx_chunk.get(
                            "section_title"
                        ),

                    "hwp_text":
                        hwp_text[
                            :200
                        ],

                    "hwpx_text":
                        hwpx_text[
                            :200
                        ],
                }
            )

    # ========================================================
    # 결과 출력
    # ========================================================
    print(
        "=" * 100
    )

    print(
        "최종 비교 결과"
    )

    print(
        "=" * 100
    )

    print(
        "전체 비교 Chunk:",
        total,
    )

    print()

    print(
        "Chunk ID 일치:",
        f"{chunk_id_match} / {total}",
    )

    print(
        "Source metadata 일치:",
        f"{source_match} / {total}",
    )

    print()

    print(
        "Section Number 일치:",
        f"{section_number_match} / {total}",
    )

    print(
        "Section Name 일치:",
        f"{section_name_match} / {total}",
    )

    print(
        "Section Title 일치:",
        f"{section_title_match} / {total}",
    )

    print(
        "Section Header 여부 일치:",
        f"{section_header_match} / {total}",
    )

    print()

    print(
        "Heading 완전 일치:",
        f"{heading_exact_match} / {total}",
    )

    print(
        "Heading 공백 제거 후 일치:",
        f"{heading_compact_match} / {total}",
    )

    print()

    print(
        "Text 완전 일치:",
        f"{text_exact_match} / {total}",
    )

    print(
        "Text 공백 정규화 후 추가 일치:",
        text_normalized_match,
    )

    print(
        "Text 모든 공백 제거 후 추가 일치:",
        text_compact_match,
    )

    content_match = (
        text_exact_match
        +
        text_normalized_match
        +
        text_compact_match
    )

    print(
        "Text 내용 기준 일치:",
        f"{content_match} / {total}",
    )

    print()

    # ========================================================
    # 퍼센트
    # ========================================================
    if total > 0:

        print(
            "Chunk ID 일치율:",
            f"{chunk_id_match / total * 100:.2f}%",
        )

        print(
            "Source 일치율:",
            f"{source_match / total * 100:.2f}%",
        )

        print(
            "Section Title 일치율:",
            f"{section_title_match / total * 100:.2f}%",
        )

        print(
            "Text 완전 일치율:",
            f"{text_exact_match / total * 100:.2f}%",
        )

        print(
            "Text 내용 기준 일치율:",
            f"{content_match / total * 100:.2f}%",
        )

    # ========================================================
    # 구조적 불일치 요약
    # ========================================================
    if mismatch_summary:

        print()
        print(
            "=" * 100
        )

        print(
            "구조 / 내용 불일치 Chunk 요약"
        )

        print(
            "=" * 100
        )

        for item in mismatch_summary[
            :30
        ]:

            print()

            print(
                f"Index: "
                f"{item['index']}"
            )

            print(
                f"HWP Chunk : "
                f"{item['hwp_chunk_id']}"
            )

            print(
                f"HWPX Chunk: "
                f"{item['hwpx_chunk_id']}"
            )

            print(
                "차이:",
                ", ".join(
                    item[
                        "differences"
                    ]
                ),
            )

            print(
                "HWP Section:",
                item[
                    "hwp_section_title"
                ],
            )

            print(
                "HWPX Section:",
                item[
                    "hwpx_section_title"
                ],
            )

            print(
                "HWP Text :",
                repr(
                    item[
                        "hwp_text"
                    ]
                ),
            )

            print(
                "HWPX Text:",
                repr(
                    item[
                        "hwpx_text"
                    ]
                ),
            )

    else:

        print()

        print(
            "[SUCCESS]"
        )

        print(
            "실질적인 Chunk 구조 차이가 없습니다."
        )


# ============================================================
# CLI
# ============================================================
def main():

    parser = argparse.ArgumentParser(
        description=(
            "HWP / HWPX Enriched Chunk JSON의 "
            "최종 RAG 구조를 비교합니다."
        )
    )

    parser.add_argument(
        "--hwp",
        required=True,
    )

    parser.add_argument(
        "--hwpx",
        required=True,
    )

    args = parser.parse_args()

    hwp_data = load_json(
        args.hwp
    )

    hwpx_data = load_json(
        args.hwpx
    )

    compare_chunks(
        hwp_data,
        hwpx_data,
    )


if __name__ == "__main__":
    main()