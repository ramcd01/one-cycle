from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


# 다음 실행 방식을 모두 지원한다.
# 1. VS Code 오른쪽 위 실행 버튼
# 2. python rag/generation/run_generation.py
# 3. python -m rag.generation.run_generation
if __package__ in (None, ""):
    PROJECT_ROOT = Path(__file__).resolve().parents[2]

    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))


from embedding.model_loader import (
    clear_cuda_cache as clear_embedding_cuda_cache,
)
from rag.generation.config import (
    DEFAULT_GENERATION_CONFIG,
    GenerationConfig,
)
from rag.generation.generator import generate_answer
from rag.reranker.config import (
    DEFAULT_RERANKER_CONFIG,
    RerankerConfig,
)
from rag.reranker.model_loader import (
    clear_reranker_cuda_cache,
    load_reranker_model,
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
            "LH 공고 선택 → Hybrid Search → Reranker → "
            "Qwen 프롬프트 기반 답변 생성을 실행합니다."
        )
    )

    parser.add_argument("--announcement", default=None)
    parser.add_argument(
        "--format",
        choices=("hwp", "hwpx"),
        default=None,
    )
    parser.add_argument("--query", default=None)
    parser.add_argument(
        "--outputs-root",
        type=Path,
        default=DEFAULT_RETRIEVAL_CONFIG.outputs_root,
    )

    parser.add_argument(
        "--llm-base-url",
        default=DEFAULT_GENERATION_CONFIG.base_url,
    )
    parser.add_argument(
        "--llm-model",
        default=DEFAULT_GENERATION_CONFIG.model_name,
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=DEFAULT_GENERATION_CONFIG.temperature,
    )
    parser.add_argument(
        "--top-p",
        type=float,
        default=DEFAULT_GENERATION_CONFIG.top_p,
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=DEFAULT_GENERATION_CONFIG.max_tokens,
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=DEFAULT_GENERATION_CONFIG.timeout_seconds,
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        default=None,
    )
    parser.add_argument(
        "--allow-cpu",
        action="store_true",
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
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
            raise ValueError(
                f"검색 가능한 공고가 아닙니다: {args.announcement}"
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
                f"{announcement}에 {args.format} 결과가 없습니다. "
                f"사용 가능: {available_formats}"
            )
        document_format = args.format
    else:
        document_format = select_format(available_formats)

    query = args.query or prompt_query()

    return announcement, document_format, query


def print_answer(generated) -> None:
    print()
    print("=" * 80)
    print("LH 공고문 기반 RAG 답변")
    print("=" * 80)
    print(f"질문      : {generated.query}")
    print(
        f"공고      : {generated.announcement_directory}"
    )
    print(f"문서 형식 : {generated.document_format}")

    print()
    print("[답변]")
    print(generated.answer)

    print()
    print("[사용 근거]")
    for source in generated.sources:
        preview = source.content.replace("\n", " ")[:300]
        print(
            f"{source.source_number}. "
            f"{source.section_label} | "
            f"chunk_id={source.chunk_id}"
        )
        print(f"   {preview}")


def main() -> int:
    args = parse_args()

    try:
        announcement, document_format, query = resolve_inputs(args)

        retrieval_config = RetrievalConfig(
            vector_top_k=20,
            bm25_top_k=20,
            hybrid_top_k=20,
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
            hybrid_candidate_top_k=20,
            rerank_top_k=5,
            batch_size=DEFAULT_RERANKER_CONFIG.batch_size,
            max_length=DEFAULT_RERANKER_CONFIG.max_length,
            use_fp16=DEFAULT_RERANKER_CONFIG.use_fp16,
            require_cuda=(
                DEFAULT_RERANKER_CONFIG.require_cuda
                and not args.allow_cpu
            ),
            device_index=DEFAULT_RERANKER_CONFIG.device_index,
            normalize_scores=True,
            text_field="content",
        )

        generation_config = GenerationConfig(
            base_url=args.llm_base_url,
            chat_completions_path=(
                DEFAULT_GENERATION_CONFIG.chat_completions_path
            ),
            model_name=args.llm_model,
            temperature=args.temperature,
            top_p=args.top_p,
            max_tokens=args.max_tokens,
            timeout_seconds=args.timeout_seconds,
            context_top_k=5,
            max_chars_per_context=(
                DEFAULT_GENERATION_CONFIG.max_chars_per_context
            ),
            require_source_markers=True,
        )

        print()
        print("[1/3] Hybrid Search 실행")
        searcher = HybridSearcher.from_files(
            announcement,
            document_format=document_format,
            outputs_root=args.outputs_root,
            config=retrieval_config,
        )

        hybrid_results = searcher.search(
            query,
            hybrid_top_k=20,
        )

        if not hybrid_results:
            raise RuntimeError("Hybrid Search 결과가 없습니다.")

        print(f"Hybrid 후보: {len(hybrid_results)}개")

        print()
        print("[2/3] Reranker 실행")
        loaded_reranker = load_reranker_model(
            model_name=reranker_config.model_name,
            use_fp16=reranker_config.use_fp16,
            require_cuda=reranker_config.require_cuda,
            device_index=reranker_config.device_index,
        )

        reranked = rerank_results(
            loaded_reranker,
            query,
            hybrid_results,
            config=reranker_config,
        )

        print(f"최종 근거 후보: {len(reranked)}개")

        print()
        print("[3/3] Qwen 답변 생성")
        generated = generate_answer(
            query=query,
            announcement_directory=announcement,
            document_format=document_format or (
                searcher.corpus.document_format
            ),
            rerank_results=reranked,
            config=generation_config,
        )

        print_answer(generated)

        if args.json_output is not None:
            output_path = args.json_output.expanduser().resolve()
            output_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            with output_path.open(
                "w",
                encoding="utf-8",
            ) as file:
                json.dump(
                    generated.to_dict(),
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
        print("[Generation 실행 실패]")
        print(f"{type(exc).__name__}: {exc}")
        return 1

    finally:
        clear_reranker_cuda_cache()
        clear_embedding_cuda_cache()


if __name__ == "__main__":
    sys.exit(main())
