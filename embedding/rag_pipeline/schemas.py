from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


Intent = Literal[
    "fact_lookup",
    "requirement_check",
    "list_lookup",
    "aggregate",
    "procedure",
    "contact_lookup",
    "overview",
    "explanation",
]

AnswerMode = Literal[
    "single_value",
    "boolean_with_conditions",
    "complete_list",
    "complete_grouped_list",
    "explicit_total",
    "procedure_steps",
    "all_matching_items",
    "overview",
    "grounded_explanation",
]


class QueryPlan(BaseModel):
    intent: Intent
    target: str = Field(min_length=1)
    answer_mode: AnswerMode
    scope: str | None = None
    completeness: Literal["single", "relevant", "all"] = "relevant"
    requested_fields: list[str] = Field(default_factory=list)


class StructuredField(BaseModel):
    label: str
    value: str


class EvidenceLocation(BaseModel):
    section_path: list[str] = Field(default_factory=list)
    source_type: str
    table_index: int | str | None = None
    row_index: int | str | None = None


class EvidenceItem(BaseModel):
    evidence_id: str
    chunk_id: str
    document_name: str
    location: EvidenceLocation
    excerpt: str
    structured_fields: list[StructuredField] = Field(default_factory=list)
    similarity: float = 0.0
    rerank_score: float = 0.0
    retrieval_reasons: list[str] = Field(default_factory=list)
    direct_rank: int | None = None
    debug: dict[str, Any] = Field(default_factory=dict)


class CoverageResult(BaseModel):
    supported: bool
    reason: str
    missing_requirements: list[str] = Field(default_factory=list)
    required_evidence_ids: list[str] = Field(default_factory=list)


class AnswerClaim(BaseModel):
    text: str = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=1)
    kind: Literal[
        "conclusion",
        "condition",
        "exception",
        "item",
        "total",
        "step",
        "explanation",
    ] = "item"
    group: str | None = None


class AnswerPlan(BaseModel):
    answer_mode: AnswerMode
    claims: list[AnswerClaim] = Field(min_length=1)


class Citation(BaseModel):
    citation_id: int
    evidence_id: str
    document_name: str
    location: EvidenceLocation
    excerpt: str
    structured_fields: list[StructuredField] = Field(default_factory=list)


class RagResponse(BaseModel):
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    query_plan: QueryPlan
    coverage: CoverageResult
    debug: dict[str, Any] = Field(default_factory=dict)
