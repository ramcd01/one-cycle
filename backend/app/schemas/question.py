from __future__ import annotations

from pydantic import BaseModel, Field


class QuestionRequest(BaseModel):
    question: str = Field(
        min_length=1,
        max_length=1000,
        description="선택한 공고문에 대한 질문",
        examples=["신청 기간은 언제인가요?"],
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="검색할 근거 청크 개수",
    )


class EvidenceItem(BaseModel):
    chunk_id: int
    title: str | None = None
    content: str
    source_page: int | None = None
    score: float | None = None


class QuestionResponse(BaseModel):
    answer: str
    evidence: list[EvidenceItem] = Field(default_factory=list)
