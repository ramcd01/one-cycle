from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


# 다음 실행 방식을 모두 지원한다.
# 1. VS Code 오른쪽 위 실행 버튼
# 2. python rag/reranker/run_reranker.py
# 3. python -m rag.reranker.run_reranker
if __package__ in (None, ""):
    PROJECT_ROOT = Path(__file__).resolve().parents[2]

    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))


from embedding.model_loader import (
    clear_cuda_cache as clear_embedding_cuda_cache,
)
from rag.reranker.config import (
    DEFAULT_RERANKER_CONFIG,
    RerankerConfig,
)
from rag.reranker.model_loader import (
    clear_reranker_cuda_cache,
    load_reranker_model,
    print_reranker_gpu_memory,
)
from rag.reranker.reranker import rerank_results
from rag.retrieval.config import (
    DEFAULT_RETRIEVAL_CONFIG,
    RetrievalConfig,
)
from rag.retrieval.hybrid_search import HybridSearcher
from rag.retrieval.run_hybrid_search import (
    discover_announcements,
    prompt_query,
    select_announcement,
    select_format,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "공고 선택 → Hybrid Search → "
            "BGE Reranker 재정렬을 실행합니다."
        )
    )

    parser.add_argument(
        "--announcement",
        default=None,
        help=(
            "outputs 아래 공고 폴더명. "
            "생략하면 실행 시 목록에서 선택합니다."
        ),
    )
    parser.add_argument(
        "--format",
        choices=("hwp", "hwpx"),
        default=None,
        help="문서 형식. 생략하면 실행 시 선택합니다.",
    )
    parser.add_argument(
        "--query",
        default=None,
        help="검색 질문. 생략하면 실행 중 입력합니다.",
    )
    parser.add_argument(
        "--outputs-root",
        type=Path,
        default=DEFAULT_RETRIEVAL_CONFIG.outputs_root,
    )
    parser.add_argument(
        "--hybrid-candidate-top-k",
        type=int,
        default=DEFAULT_RERANKER_CONFIG.hybrid_candidate_top_k,
        help="Reranker에 전달할 Hybrid 후보 수",
    )
    parser.add_argument(
        "--rerank-top-k",
        type=int,
        default=DEFAULT_RERANKER_CONFIG.rerank_top_k,
        help="Reranker 최종 반환 수",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_RERANKER_CONFIG.batch_size,
    )
    parser.add_argument(
        "--max-length",
        type=int,
        default=DEFAULT_RERANKER_CONFIG.max_length,
    )
    parser.add_argument(
        "--no-normalize",
        action="store_true",
        help="Reranker 점수 sigmoid 정규화를 사용하지 않습니다.",
    )
    parser.add_argument(
        "--allow-cpu",
        action="store_true",
        help="CUDA가 없어도 CPU 실행을 허용합니다.",
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        default=None,
        help="Reranker 결과 JSON 저장 경로",
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


def resolve_inputs(
    args: argparse.Namespace,
) -> tuple[str, str | None, str]:
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


def print_rerank_results(
    *,
    query: str,
    searcher: HybridSearcher,
    hybrid_results,
    rerank_results_list,
) -> None:
    print()
    print("=" * 80)
    print("Hybrid Search + Reranker 결과")
    print("=" * 80)
    print(f"질문              : {query}")
    print(f"공고              : {searcher.corpus.announcement_directory}")
    print(f"문서 형식         : {searcher.corpus.document_format}")
    print(f"전체 청크 수      : {searcher.corpus.size}")
    print(f"Hybrid 후보 수    : {len(hybrid_results)}")
    print(f"Reranker 결과 수  : {len(rerank_results_list)}")

    for result in rerank_results_list:
        search_result = result.search_result
        section = (
            " > ".join(result.item.section_path)
            or "(섹션 없음)"
        )
        preview = result.item.content.replace("\n", " ")[:500]

        print()
        print("-" * 80)
        print(f"Reranker 순위  : {result.reranker_rank}")
        print(f"Reranker 점수  : {result.reranker_score:.8f}")
        print(f"Hybrid 순위    : {result.hybrid_rank}")
        print(f"Vector 순위    : {search_result.vector_rank}")
        print(f"BM25 순위      : {search_result.bm25_rank}")
        print(f"RRF 점수       : {search_result.fusion_score:.8f}")
        print(f"chunk_id       : {result.chunk_id}")
        print(f"section        : {section}")
        print(f"content        : {preview}")


def main() -> int:
    args = parse_args()

    try:
        announcement, document_format, query = resolve_inputs(args)

        if args.hybrid_candidate_top_k <= 0:
            raise ValueError(
                "--hybrid-candidate-top-k는 1 이상이어야 합니다."
            )
        if args.rerank_top_k <= 0:
            raise ValueError(
                "--rerank-top-k는 1 이상이어야 합니다."
            )
        if args.rerank_top_k > args.hybrid_candidate_top_k:
            raise ValueError(
                "--rerank-top-k는 --hybrid-candidate-top-k보다 "
                "클 수 없습니다."
            )

        retrieval_config = RetrievalConfig(
            vector_top_k=max(
                DEFAULT_RETRIEVAL_CONFIG.vector_top_k,
                args.hybrid_candidate_top_k,
            ),
            bm25_top_k=max(
                DEFAULT_RETRIEVAL_CONFIG.bm25_top_k,
                args.hybrid_candidate_top_k,
            ),
            hybrid_top_k=args.hybrid_candidate_top_k,
            rrf_k=DEFAULT_RETRIEVAL_CONFIG.rrf_k,
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
                and not args.allow_cpu
            ),
            device_index=(
                DEFAULT_RETRIEVAL_CONFIG.device_index
            ),
        )

        reranker_config = RerankerConfig(
            model_name=DEFAULT_RERANKER_CONFIG.model_name,
            hybrid_candidate_top_k=args.hybrid_candidate_top_k,
            rerank_top_k=args.rerank_top_k,
            batch_size=args.batch_size,
            max_length=args.max_length,
            use_fp16=DEFAULT_RERANKER_CONFIG.use_fp16,
            require_cuda=(
                DEFAULT_RERANKER_CONFIG.require_cuda
                and not args.allow_cpu
            ),
            device_index=DEFAULT_RERANKER_CONFIG.device_index,
            normalize_scores=not args.no_normalize,
            text_field=DEFAULT_RERANKER_CONFIG.text_field,
        )
        reranker_config.validate()

        # 1. BGE-M3 질문 임베딩 + Hybrid Search
        searcher = HybridSearcher.from_files(
            announcement,
            document_format=document_format,
            outputs_root=args.outputs_root,
            config=retrieval_config,
        )

        hybrid_results = searcher.search(
            query,
            hybrid_top_k=args.hybrid_candidate_top_k,
        )

        if not hybrid_results:
            raise RuntimeError(
                "Hybrid Search 결과가 없어 Reranker를 실행할 수 없습니다."
            )

        print()
        print(
            f"Hybrid Search 완료: "
            f"{len(hybrid_results)}개 후보"
        )

        # 2. Reranker 모델 로드
        loaded_reranker = load_reranker_model(
            model_name=reranker_config.model_name,
            use_fp16=reranker_config.use_fp16,
            require_cuda=reranker_config.require_cuda,
            device_index=reranker_config.device_index,
        )

        print_reranker_gpu_memory("[Reranker 로드 후]")

        # 3. 후보 재정렬
        reranked = rerank_results(
            loaded_reranker,
            query,
            hybrid_results,
            config=reranker_config,
        )

        print_reranker_gpu_memory("[Reranker 실행 후]")

        print_rerank_results(
            query=query,
            searcher=searcher,
            hybrid_results=hybrid_results,
            rerank_results_list=reranked,
        )

        if args.json_output is not None:
            output_path = args.json_output.expanduser().resolve()
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
                "hybrid_candidate_count": len(hybrid_results),
                "rerank_result_count": len(reranked),
                "reranker_model": reranker_config.model_name,
                "results": [
                    result.to_dict() for result in reranked
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
        print("[Reranker 실행 실패]")
        print(f"{type(exc).__name__}: {exc}")
        return 1

    finally:
        clear_reranker_cuda_cache()
        clear_embedding_cuda_cache()


if __name__ == "__main__":
    sys.exit(main())
