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
# JSON
# ============================================================
def load_json(path: str) -> dict[str, Any]:

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


def save_json(
    data: dict,
    path: str,
) -> None:

    file_path = Path(path)

    file_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with file_path.open(
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
# 로마 숫자 대분류 판별
# ============================================================
def is_section_number(
    text: str,
) -> bool:

    if not text:
        return False

    text = text.strip()

    return bool(
        re.fullmatch(
            r"[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ]+",
            text,
        )
    )


# ============================================================
# 대분류 제목 후보 판별
# ============================================================
def is_section_title_candidate(
    text: str,
) -> bool:
    """
    로마 숫자와 같은 행에 존재하는
    대분류 제목 후보인지 판단합니다.
    """

    if not text:
        return False

    text = text.strip()

    if is_section_number(text):
        return False

    # 대분류 제목은 보통 짧음
    if len(text) > 100:
        return False

    return True


# ============================================================
# 위치 Key
# ============================================================
def get_row_key(
    chunk: dict,
) -> tuple:

    source = chunk.get(
        "source",
        {},
    )

    return (
        source.get(
            "section_index"
        ),
        source.get(
            "table_index"
        ),
        source.get(
            "row"
        ),
    )


# ============================================================
# 대분류 Header 찾기
# ============================================================
def find_section_headers(
    chunks: list[dict],
) -> dict:
    """
    같은 Section/Table/Row에 있는

    Ⅰ + 공급규모...
    Ⅱ + 신청기준...

    구조를 찾아서 대분류 제목으로 만듭니다.

    반환:

    {
        (section, table, row): {
            "section_number": "Ⅰ",
            "section_name": "...",
            "section_title": "Ⅰ. ..."
        }
    }
    """

    row_groups = {}

    # --------------------------------------------------------
    # 같은 Row의 Chunk끼리 모으기
    # --------------------------------------------------------
    for chunk in chunks:

        key = get_row_key(
            chunk
        )

        row_groups.setdefault(
            key,
            [],
        ).append(
            chunk
        )

    section_headers = {}

    # --------------------------------------------------------
    # Row별 분석
    # --------------------------------------------------------
    for key, row_chunks in row_groups.items():

        section_number = None
        section_name = None

        # Col 순서
        row_chunks = sorted(
            row_chunks,
            key=lambda item: (
                item
                .get(
                    "source",
                    {},
                )
                .get(
                    "col",
                    0,
                )
            ),
        )

        # 로마 숫자 찾기
        for chunk in row_chunks:

            text = (
                chunk
                .get(
                    "text",
                    "",
                )
                .strip()
            )

            if is_section_number(
                text
            ):

                section_number = text

                break

        if section_number is None:
            continue

        # 같은 행의 다른 짧은 텍스트를 제목 후보로 사용
        for chunk in row_chunks:

            text = (
                chunk
                .get(
                    "text",
                    "",
                )
                .strip()
            )

            if (
                text == section_number
            ):
                continue

            if is_section_title_candidate(
                text
            ):

                section_name = text

                break

        # 제목을 못 찾으면 번호만 사용
        if section_name:

            section_title = (
                f"{section_number}. "
                f"{section_name}"
            )

        else:

            section_title = (
                section_number
            )

        section_headers[
            key
        ] = {
            "section_number":
                section_number,

            "section_name":
                section_name,

            "section_title":
                section_title,
        }

    return section_headers


# ============================================================
# Section Context 추가
# ============================================================
def add_section_context(
    data: dict,
) -> dict:

    chunks = data.get(
        "chunks",
        [],
    )

    section_headers = (
        find_section_headers(
            chunks
        )
    )

    current_section_title = None
    current_section_number = None
    current_section_name = None

    enriched_chunks = []

    for chunk in chunks:

        new_chunk = dict(
            chunk
        )

        source = dict(
            new_chunk.get(
                "source",
                {},
            )
        )

        new_chunk[
            "source"
        ] = source

        row_key = get_row_key(
            chunk
        )

        # ====================================================
        # 새로운 대분류 시작
        # ====================================================
        if row_key in section_headers:

            header = section_headers[
                row_key
            ]

            current_section_title = (
                header[
                    "section_title"
                ]
            )

            current_section_number = (
                header[
                    "section_number"
                ]
            )

            current_section_name = (
                header[
                    "section_name"
                ]
            )

        # ====================================================
        # 현재 Section Context 상속
        # ====================================================
        new_chunk[
            "section_title"
        ] = current_section_title

        new_chunk[
            "section_number"
        ] = current_section_number

        new_chunk[
            "section_name"
        ] = current_section_name

        # ====================================================
        # 이 Chunk 자체가 Section Header인지 표시
        # ====================================================
        text = (
            new_chunk
            .get(
                "text",
                "",
            )
            .strip()
        )

        if (
            row_key
            in
            section_headers
        ):

            header = (
                section_headers[
                    row_key
                ]
            )

            if (
                text
                ==
                header[
                    "section_number"
                ]
                or
                text
                ==
                header[
                    "section_name"
                ]
            ):

                new_chunk[
                    "is_section_header"
                ] = True

            else:

                new_chunk[
                    "is_section_header"
                ] = False

        else:

            new_chunk[
                "is_section_header"
            ] = False

        enriched_chunks.append(
            new_chunk
        )

    result = dict(
        data
    )

    result[
        "chunks"
    ] = enriched_chunks

    result[
        "section_context_statistics"
    ] = {
        "detected_section_count":
            len(
                section_headers
            ),

        "detected_sections": [
            {
                "section_index":
                    key[0],

                "table_index":
                    key[1],

                "row":
                    key[2],

                **value,
            }

            for key, value
            in section_headers.items()
        ],
    }

    return result


# ============================================================
# CLI
# ============================================================
def main():

    parser = argparse.ArgumentParser(
        description=(
            "RAG Chunk JSON에서 "
            "Ⅰ, Ⅱ, Ⅲ 등의 대분류와 제목을 연결하여 "
            "section context를 추가합니다."
        )
    )

    parser.add_argument(
        "--input",
        required=True,
    )

    parser.add_argument(
        "--output",
        required=True,
    )

    args = parser.parse_args()

    data = load_json(
        args.input
    )

    result = add_section_context(
        data
    )

    save_json(
        result,
        args.output,
    )

    statistics = result.get(
        "section_context_statistics",
        {},
    )

    print()

    print(
        "=" * 80
    )

    print(
        "Section Context 추가 완료"
    )

    print(
        "=" * 80
    )

    print(
        "감지된 Section 수:",
        statistics.get(
            "detected_section_count",
            0,
        ),
    )

    print()

    for section in statistics.get(
        "detected_sections",
        [],
    ):

        print(
            f"Table={section['table_index']} "
            f"Row={section['row']} "
            f"→ {section['section_title']}"
        )

    print()

    print(
        "출력:",
        str(
            Path(
                args.output
            ).resolve()
        ),
    )


if __name__ == "__main__":
    main()