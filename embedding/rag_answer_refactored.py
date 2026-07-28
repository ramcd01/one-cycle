from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from rag_pipeline import RagPipeline
from rag_pipeline.llama_client import LlamaClient
from search_embeddings import (
    TOP_K,
    find_embedding_file,
    load_embeddings,
    load_metadata,
    load_model,
    select_metadata_json,
)

LINE = "=" * 80
SUB_LINE = "-" * 80


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="문서 기반 RAG 콘솔 테스트"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Query Plan, Coverage, 검색 점수 등 내부 처리 정보를 함께 표시합니다.",
    )
    return parser.parse_args()


def format_location(citation: Any) -> str:
    path = " > ".join(citation.location.section_path) or "문서 도입부"
    if citation.location.table_index is not None:
        path += f" · 표 {citation.location.table_index}"
    if citation.location.row_index is not None:
        path += f" · 행 {citation.location.row_index}"
    return path


def to_console_text(text: str) -> str:
    """Markdown 렌더러가 없는 콘솔에서도 자연스럽게 보이도록 정리한다."""
    output = text.strip()
    output = re.sub(r"\*\*(.+?)\*\*", r"\1", output)
    output = re.sub(r"^#{1,6}\s*", "", output, flags=re.MULTILINE)
    return output


def print_service_response(response: Any) -> None:
    """실제 사용자 화면에 가까운 결과만 출력한다."""
    print("\n" + LINE)
    print("AI 답변")
    print(LINE)
    print(to_console_text(response.answer))

    if response.citations:
        print("\n" + LINE)
        print("답변 근거")
        print(LINE)

        for citation in response.citations:
            print(f"[근거 {citation.citation_id}]")
            print()
            print("공고문 내용")
            print(to_console_text(citation.excerpt))
            print()
            print(f"출처 위치: {format_location(citation)}")
            print(f"문서: {citation.document_name}")
            print(SUB_LINE)

    print("※ 답변은 선택한 공고문의 내용을 기준으로 제공됩니다.")
    print(LINE + "\n")


def print_debug_response(response: Any) -> None:
    """개발자가 명시적으로 --debug를 사용했을 때만 내부 데이터를 출력한다."""
    print("\n" + LINE)
    print("개발자 디버그 정보")
    print(LINE)
    print("Query Plan")
    print(response.query_plan.model_dump_json(indent=2))
    print("\nCoverage")
    print(response.coverage.model_dump_json(indent=2))
    print("\n검색 및 답변 계획")
    print(json.dumps(response.debug, ensure_ascii=False, indent=2))
    print(LINE + "\n")


def main() -> None:
    args = parse_args()

    metadata_path = select_metadata_json()
    if not metadata_path:
        print("메타데이터 JSON을 선택하지 않았습니다.")
        return

    metadata = load_metadata(metadata_path)
    embedding_path = find_embedding_file(metadata_path, metadata)
    embeddings = load_embeddings(embedding_path, metadata)
    embedding_model, _ = load_model(metadata)

    llama = LlamaClient()
    print("llama.cpp 서버 확인 중...")
    llama.check()
    model_id = llama.get_model_id()

    pipeline = RagPipeline(
        embedding_model=embedding_model,
        embeddings=embeddings,
        chunks=metadata["chunks"],
        llama_client=llama,
        min_similarity=0.35,
    )

    print("\n" + LINE)
    print("문서 기반 AI 질의응답 준비 완료")
    print(LINE)
    print(f"분석 문서 청크: {len(metadata['chunks'])}개")
    print(f"생성 모델: {model_id}")
    print("답변 근거: 공고문 내용과 출처 위치 제공")
    if args.debug:
        print("개발자 디버그 모드: 활성화")
    print(LINE)
    print("질문을 입력하세요. 종료하려면 exit, quit 또는 q를 입력하세요.\n")

    while True:
        question = input("질문> ").strip()
        if question.lower() in {"exit", "quit", "q"}:
            print("질의응답을 종료합니다.")
            break
        if not question:
            print("질문을 입력해주세요.")
            continue

        try:
            response = pipeline.answer(question)
            print_service_response(response)
            if args.debug:
                print_debug_response(response)
        except Exception as error:
            if args.debug:
                raise
            print("\n답변을 생성하는 중 문제가 발생했습니다.")
            print(f"오류 내용: {error}\n")


if __name__ == "__main__":
    main()
