from __future__ import annotations

import re

from rag.reranker.models import RerankResult

from .config import DEFAULT_GENERATION_CONFIG, GenerationConfig
from .context_builder import build_source_contexts
from .llm_client import call_llama_cpp_chat
from .models import GeneratedAnswer
from .prompt_builder import build_prompt


class GenerationError(RuntimeError):
    """답변 생성 전체 흐름 실패 시 발생."""


SOURCE_MARKER_PATTERN = re.compile(r"\[근거\s*\d+\]")


def generate_answer(
    *,
    query: str,
    announcement_directory: str,
    document_format: str,
    rerank_results: list[RerankResult],
    config: GenerationConfig = DEFAULT_GENERATION_CONFIG,
) -> GeneratedAnswer:
    config.validate()

    try:
        sources = build_source_contexts(
            rerank_results,
            document_format=document_format,
            config=config,
        )

        prompt = build_prompt(
            query=query,
            announcement_directory=announcement_directory,
            document_format=document_format,
            sources=sources,
        )

        answer, raw_response = call_llama_cpp_chat(
            prompt,
            config=config,
        )
    except Exception as exc:
        if isinstance(exc, GenerationError):
            raise

        raise GenerationError(
            "Qwen 답변 생성에 실패했습니다.\n"
            f"실제 오류: {type(exc).__name__}: {exc}"
        ) from exc

    if (
        config.require_source_markers
        and answer != "제공된 LH 공고문 근거에서 확인할 수 없습니다."
        and SOURCE_MARKER_PATTERN.search(answer) is None
    ):
        print(
            "[경고] 생성된 답변에 [근거 N] 표시가 없습니다. "
            "프롬프트 또는 모델 응답 품질을 확인하세요."
        )

    return GeneratedAnswer(
        answer=answer,
        query=query,
        announcement_directory=announcement_directory,
        document_format=document_format,
        sources=sources,
        prompt=prompt,
        raw_response=raw_response,
    )
