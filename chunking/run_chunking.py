from __future__ import annotations

import argparse
import json

from copy import deepcopy
from pathlib import Path
from typing import Any


# ============================================================
# 기존 Chunking 알고리즘 import
# ============================================================

try:
    from .build_chunks import (
        MAX_CHARS,
        OVERLAP_CHARS,
        ChunkBuilder,
        build_summary,
        print_result,
        save_json,
    )

except ImportError:
    from build_chunks import (
        MAX_CHARS,
        OVERLAP_CHARS,
        ChunkBuilder,
        build_summary,
        print_result,
        save_json,
    )


# ============================================================
# 입력 JSON 로딩
# ============================================================

def load_structured_document(
    input_path: Path,
) -> dict[str, Any]:
    """
    Step 3 최종 구조화 JSON을 로딩합니다.
    """

    if not input_path.exists():
        raise FileNotFoundError(
            "구조화 JSON을 찾을 수 없습니다.\n"
            f"{input_path}"
        )

    with input_path.open(
        "r",
        encoding="utf-8",
    ) as file:
        data = json.load(
            file
        )

    if not isinstance(
        data,
        dict,
    ):
        raise ValueError(
            "구조화 JSON의 최상위 구조가 "
            "객체(dict)가 아닙니다."
        )

    return data


# ============================================================
# Chunking 결과 생성
# ============================================================

def build_chunk_result(
    final_document: dict[str, Any],
) -> dict[str, Any]:
    """
    기존 ChunkBuilder를 이용해
    Step 4 청킹 결과를 생성합니다.
    """

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
                    "해당 표의 모든 청크에 연결하고 "
                    "metadata에 출처 보존"
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

    return result


# ============================================================
# 단일 문서 Chunking
# ============================================================

def run_chunking_pipeline(
    input_path: Path,
    output_path: Path,
) -> dict[str, Any]:
    """
    구조화 최종 JSON 하나를 청킹합니다.

    입력:
        step3-3_structured_tables.json

    출력:
        chunks.json
    """

    print()
    print("=" * 72)
    print("Chunking Pipeline 시작")
    print("=" * 72)

    print(
        f"입력: {input_path}"
    )

    print(
        f"출력: {output_path}"
    )

    final_document = (
        load_structured_document(
            input_path
        )
    )

    result = (
        build_chunk_result(
            final_document
        )
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    save_json(
        str(
            output_path
        ),
        result,
    )

    print_result(
        str(
            output_path
        ),
        result,
    )

    print()
    print("=" * 72)
    print("Chunking Pipeline 완료")
    print("=" * 72)

    return result


# ============================================================
# CLI
# ============================================================

def parse_arguments() -> argparse.Namespace:
    """
    CLI 인자를 읽습니다.
    """

    parser = argparse.ArgumentParser(
        description=(
            "Step 3 최종 구조화 JSON을 "
            "Step 4 Chunk JSON으로 변환합니다."
        )
    )

    parser.add_argument(
        "--input",
        required=True,
        help=(
            "step3-3_structured_tables.json 경로"
        ),
    )

    parser.add_argument(
        "--output",
        required=True,
        help=(
            "chunks.json 저장 경로"
        ),
    )

    return parser.parse_args()


# ============================================================
# Main
# ============================================================

def main() -> None:

    args = (
        parse_arguments()
    )

    input_path = Path(
        args.input
    ).resolve()

    output_path = Path(
        args.output
    ).resolve()

    run_chunking_pipeline(
        input_path,
        output_path,
    )


# ============================================================
# Entry Point
# ============================================================

if __name__ == "__main__":
    main()