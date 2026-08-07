from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


# 다음 두 실행 방식을 모두 지원합니다.
# 1. VS Code 오른쪽 위 실행 버튼
# 2. python -m rag.retrieval.run_hybrid_search
#
# 파일을 직접 실행하면 프로젝트 루트가 Python import 경로에
# 포함되지 않을 수 있으므로 one-cycle 루트를 추가합니다.
if __package__ in (None, ""):
    PROJECT_ROOT = Path(__file__).resolve().parents[2]

    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))


from embedding.model_loader import clear_cuda_cache
from rag.retrieval.config import (
    DEFAULT_RETRIEVAL_CONFIG,
    RetrievalConfig,
)
from rag.retrieval.hybrid_search import HybridSearcher


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "embeddings.npy + metadata.json 기반 "
            "Vector Search와 BM25를 RRF로 결합합니다."
        )
    )

    parser.add_argument(
        "--announcement",
        default=None,
        help=(
            "outputs 아래 공고 폴더명. 예: announcement_001. "
            "생략하면 실행 시 목록에서 선택합니다."
        ),
    )
    parser.add_argument(
        "--format",
        choices=("hwp", "hwpx"),
        default=None,
        help=(
            "문서 형식. 생략하면 실행 시 선택합니다. "
            "비대화형 실행에서는 HWPX 우선, 없으면 HWP를 사용합니다."
        ),
    )
    parser.add_argument(
        "--query",
        default=None,
        help="검색 질문. 생략하면 실행 중 입력합니다.",
    )
    parser.add_argument(
        "--vector-top-k",
        type=int,
        default=DEFAULT_RETRIEVAL_CONFIG.vector_top_k,
    )
    parser.add_argument(
        "--bm25-top-k",
        type=int,
        default=DEFAULT_RETRIEVAL_CONFIG.bm25_top_k,
    )
    parser.add_argument(
        "--hybrid-top-k",
        type=int,
        default=DEFAULT_RETRIEVAL_CONFIG.hybrid_top_k,
    )
    parser.add_argument(
        "--rrf-k",
        type=int,
        default=DEFAULT_RETRIEVAL_CONFIG.rrf_k,
    )
    parser.add_argument(
        "--outputs-root",
        type=Path,
        default=DEFAULT_RETRIEVAL_CONFIG.outputs_root,
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        default=None,
        help="검색 결과 JSON 저장 경로",
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help=(
            "대화형 선택을 사용하지 않습니다. "
            "이 경우 --announcement와 --query가 필요합니다."
        ),
    )

    return parser.parse_args()


def discover_announcements(
    outputs_root: Path,
) -> list[dict[str, object]]:
    """
    임베딩 결과가 존재하는 announcement_* 폴더를 탐색합니다.

    반환 형식:
        {
            "name": "announcement_001",
            "formats": ["hwp", "hwpx"]
        }
    """
    root = outputs_root.expanduser().resolve()

    if not root.is_dir():
        raise RuntimeError(
            f"outputs 폴더를 찾을 수 없습니다: {root}"
        )

    announcements: list[dict[str, object]] = []

    for announcement_dir in sorted(root.glob("announcement_*")):
        if not announcement_dir.is_dir():
            continue

        formats: list[str] = []

        for document_format in ("hwp", "hwpx"):
            embedding_dir = (
                announcement_dir
                / "05_embeddings"
                / document_format
            )

            if (
                (embedding_dir / "embeddings.npy").is_file()
                and (embedding_dir / "metadata.json").is_file()
            ):
                formats.append(document_format)

        if formats:
            announcements.append(
                {
                    "name": announcement_dir.name,
                    "formats": formats,
                }
            )

    if not announcements:
        raise RuntimeError(
            "검색 가능한 임베딩 결과를 찾지 못했습니다.\n"
            f"확인 경로: {root}/announcement_*/05_embeddings/"
        )

    return announcements


def select_announcement(
    announcements: list[dict[str, object]],
) -> tuple[str, list[str]]:
    print()
    print("=" * 70)
    print("검색할 공고 선택")
    print("=" * 70)

    for index, item in enumerate(announcements, start=1):
        name = str(item["name"])
        formats = ", ".join(item["formats"])
        print(f"{index}. {name} [{formats}]")

    while True:
        raw = input(
            f"\n공고 번호를 선택하세요 (1-{len(announcements)}): "
        ).strip()

        try:
            selected_index = int(raw)
        except ValueError:
            print("숫자를 입력하세요.")
            continue

        if 1 <= selected_index <= len(announcements):
            selected = announcements[selected_index - 1]
            return (
                str(selected["name"]),
                [str(value) for value in selected["formats"]],
            )

        print("목록에 있는 번호를 입력하세요.")


def select_format(
    available_formats: list[str],
) -> str:
    if len(available_formats) == 1:
        selected = available_formats[0]
        print(f"\n사용 가능한 형식이 하나이므로 '{selected}'를 사용합니다.")
        return selected

    print()
    print("문서 형식을 선택하세요.")

    for index, document_format in enumerate(
        available_formats,
        start=1,
    ):
        print(f"{index}. {document_format}")

    while True:
        raw = input(
            f"형식 번호를 선택하세요 (1-{len(available_formats)}): "
        ).strip()

        try:
            selected_index = int(raw)
        except ValueError:
            print("숫자를 입력하세요.")
            continue

        if 1 <= selected_index <= len(available_formats):
            return available_formats[selected_index - 1]

        print("목록에 있는 번호를 입력하세요.")


def prompt_query() -> str:
    while True:
        query = input("\n검색 질문을 입력하세요: ").strip()

        if query:
            return query

        print("질문은 비워둘 수 없습니다.")


def resolve_inputs(
    args: argparse.Namespace,
) -> tuple[str, str | None, str]:
    """
    CLI 인자 또는 대화형 입력으로 공고·형식·질문을 결정합니다.
    """
    if args.non_interactive:
        if not args.announcement:
            raise ValueError(
                "--non-interactive 사용 시 --announcement가 필요합니다."
            )

        if not args.query:
            raise ValueError(
                "--non-interactive 사용 시 --query가 필요합니다."
            )

        return args.announcement, args.format, args.query

    announcements = discover_announcements(args.outputs_root)

    if args.announcement:
        matched = next(
            (
                item
                for item in announcements
                if item["name"] == args.announcement
            ),
            None,
        )

        if matched is None:
            available = ", ".join(
                str(item["name"]) for item in announcements
            )
            raise ValueError(
                f"검색 가능한 공고가 아닙니다: {args.announcement}\n"
                f"사용 가능: {available}"
            )

        announcement = args.announcement
        available_formats = [
            str(value) for value in matched["formats"]
        ]
    else:
        announcement, available_formats = select_announcement(
            announcements
        )

    if args.format:
        if args.format not in available_formats:
            raise ValueError(
                f"{announcement}에 {args.format} 임베딩 결과가 없습니다.\n"
                f"사용 가능 형식: {available_formats}"
            )
        document_format = args.format
    else:
        document_format = select_format(available_formats)

    query = args.query or prompt_query()

    return announcement, document_format, query


def print_results(
    query: str,
    searcher: HybridSearcher,
    results,
) -> None:
    print()
    print("=" * 80)
    print("파일 기반 Hybrid Search 결과")
    print("=" * 80)
    print(f"질문       : {query}")
    print(f"공고       : {searcher.corpus.announcement_directory}")
    print(f"문서 형식  : {searcher.corpus.document_format}")
    print(f"청크 수    : {searcher.corpus.size}")
    print(f"결과 수    : {len(results)}")

    for result in results:
        section = (
            " > ".join(result.item.section_path)
            or "(섹션 없음)"
        )
        preview = result.item.content.replace("\n", " ")[:300]

        print()
        print("-" * 80)
        print(f"순위          : {result.fusion_rank}")
        print(f"chunk_id      : {result.chunk_id}")
        print(f"section       : {section}")
        print(
            f"matched_by    : "
            f"{', '.join(sorted(result.matched_by))}"
        )
        print(
            f"vector        : rank={result.vector_rank}, "
            f"score={result.vector_score}"
        )
        print(
            f"bm25          : rank={result.bm25_rank}, "
            f"score={result.bm25_score}"
        )
        print(f"rrf_score     : {result.fusion_score:.8f}")
        print(f"content       : {preview}")


def main() -> int:
    args = parse_args()

    try:
        announcement, document_format, query = resolve_inputs(args)

        config = RetrievalConfig(
            vector_top_k=args.vector_top_k,
            bm25_top_k=args.bm25_top_k,
            hybrid_top_k=args.hybrid_top_k,
            rrf_k=args.rrf_k,
            outputs_root=args.outputs_root,
            format_priority=(
                DEFAULT_RETRIEVAL_CONFIG.format_priority
            ),
            embedding_model_name=(
                DEFAULT_RETRIEVAL_CONFIG.embedding_model_name
            ),
            query_batch_size=1,
            query_max_length=(
                DEFAULT_RETRIEVAL_CONFIG.query_max_length
            ),
            use_fp16=DEFAULT_RETRIEVAL_CONFIG.use_fp16,
            require_cuda=(
                DEFAULT_RETRIEVAL_CONFIG.require_cuda
            ),
            device_index=(
                DEFAULT_RETRIEVAL_CONFIG.device_index
            ),
        )

        searcher = HybridSearcher.from_files(
            announcement,
            document_format=document_format,
            outputs_root=args.outputs_root,
            config=config,
        )

        results = searcher.search(query)
        print_results(query, searcher, results)

        if args.json_output is not None:
            output_path = (
                args.json_output.expanduser().resolve()
            )
            output_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            payload = {
                "query": query,
                "announcement": (
                    searcher.corpus.announcement_directory
                ),
                "document_format": (
                    searcher.corpus.document_format
                ),
                "result_count": len(results),
                "results": [
                    result.to_dict() for result in results
                ],
            }

            with output_path.open(
                "w",
                encoding="utf-8",
            ) as file:
                json.dump(
                    payload,
                    file,
                    ensure_ascii=False,
                    indent=2,
                )

            print()
            print(f"JSON 저장 완료: {output_path}")

        return 0

    except KeyboardInterrupt:
        print()
        print("사용자에 의해 실행이 중단되었습니다.")
        return 130

    except Exception as exc:
        print()
        print("[Hybrid Search 실패]")
        print(f"{type(exc).__name__}: {exc}")
        return 1

    finally:
        clear_cuda_cache()


if __name__ == "__main__":
    sys.exit(main())