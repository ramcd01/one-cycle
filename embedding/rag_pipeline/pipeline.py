from __future__ import annotations

from typing import Any

import numpy as np

from .answer_planner import AnswerPlanner
from .coverage_checker import CoverageChecker
from .evidence_builder import EvidenceBuilder
from .evidence_selector import EvidenceSelector
from .llama_client import LlamaClient
from .query_planner import QueryPlanner
from .renderer import render_answer
from .retriever import Retriever
from .schemas import RagResponse


class RagPipeline:
    def __init__(
        self,
        *,
        embedding_model: Any,
        embeddings: np.ndarray,
        chunks: list[dict[str, Any]],
        llama_client: LlamaClient | None = None,
        min_similarity: float = 0.35,
    ) -> None:
        self.llama = llama_client or LlamaClient()
        self.query_planner = QueryPlanner(self.llama)
        self.retriever = Retriever(
            embedding_model=embedding_model,
            embeddings=embeddings,
            chunks=chunks,
        )
        self.evidence_builder = EvidenceBuilder()
        self.evidence_selector = EvidenceSelector(self.llama, embedding_model)
        self.coverage_checker = CoverageChecker(min_similarity=min_similarity)
        self.answer_planner = AnswerPlanner(self.llama)

    def answer(self, question: str) -> RagResponse:
        query_plan = self.query_planner.plan(question)
        retrieval = self.retriever.retrieve(question)
        raw_evidence = self.evidence_builder.build(retrieval.context_results)
        selected_evidence = self.evidence_selector.select(
            question=question,
            query_plan=query_plan,
            evidence=raw_evidence,
        )
        coverage = self.coverage_checker.check(query_plan, selected_evidence)

        if not coverage.supported:
            return RagResponse(
                answer=(
                    "현재 문서 근거만으로는 확인할 수 없습니다. "
                    f"{coverage.reason}"
                ),
                citations=[],
                query_plan=query_plan,
                coverage=coverage,
                debug={
                    "max_raw_similarity": retrieval.max_raw_similarity,
                    "max_context_similarity": retrieval.max_context_similarity,
                    "raw_chunk_ids": [
                        item.get("chunk", {}).get("chunk_id")
                        for item in retrieval.raw_results
                    ],
                    "context_chunk_ids": [item.chunk_id for item in raw_evidence],
                    "selected_evidence_ids": [
                        item.evidence_id for item in selected_evidence
                    ],
                },
            )

        answer_plan = self.answer_planner.create(
            question=question,
            query_plan=query_plan,
            coverage=coverage,
            evidence=selected_evidence,
        )
        answer, citations = render_answer(answer_plan, selected_evidence)

        return RagResponse(
            answer=answer,
            citations=citations,
            query_plan=query_plan,
            coverage=coverage,
            debug={
                "max_raw_similarity": retrieval.max_raw_similarity,
                "max_context_similarity": retrieval.max_context_similarity,
                "raw_chunk_ids": [
                    item.get("chunk", {}).get("chunk_id")
                    for item in retrieval.raw_results
                ],
                "context_chunk_ids": [item.chunk_id for item in raw_evidence],
                "selected_evidence_ids": [
                    item.evidence_id for item in selected_evidence
                ],
                "selected_excerpts": {
                    item.evidence_id: item.excerpt for item in selected_evidence
                },
                "expanded_tables": retrieval.expansion.get("expanded_tables", []),
                "answer_plan": answer_plan.model_dump(),
            },
        )
