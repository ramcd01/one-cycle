from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import numpy as np

@dataclass(frozen=True)
class CorpusItem:
    vector_index: int
    chunk_id: str
    document_id: str | None
    announcement_id: str | None
    chunk_order: int | None
    chunk_type: str | None
    section_path: list[str]
    title: str | None
    content: str
    search_text: str
    source: dict[str, Any] | None
    raw_metadata: dict[str, Any]

@dataclass(frozen=True)
class LoadedCorpus:
    announcement_directory: str
    document_format: str
    embeddings_path: Path
    metadata_path: Path
    embeddings: np.ndarray
    items: list[CorpusItem]
    model_name: str | None
    embedding_dimension: int
    normalized: bool

    @property
    def size(self) -> int:
        return len(self.items)

    def get_item(self, vector_index: int) -> CorpusItem:
        if vector_index < 0 or vector_index >= self.size:
            raise IndexError(f"vector_index 범위 오류: index={vector_index}, size={self.size}")
        return self.items[vector_index]

@dataclass
class SearchResult:
    vector_index: int
    chunk_id: str
    item: CorpusItem
    vector_score: float | None = None
    vector_rank: int | None = None
    bm25_score: float | None = None
    bm25_rank: int | None = None
    fusion_score: float = 0.0
    fusion_rank: int | None = None
    matched_by: set[str] = field(default_factory=set)

    def to_dict(self) -> dict[str, Any]:
        return {
            "vector_index": self.vector_index,
            "chunk_id": self.chunk_id,
            "vector_score": self.vector_score,
            "vector_rank": self.vector_rank,
            "bm25_score": self.bm25_score,
            "bm25_rank": self.bm25_rank,
            "fusion_score": self.fusion_score,
            "fusion_rank": self.fusion_rank,
            "matched_by": sorted(self.matched_by),
            "announcement_id": self.item.announcement_id,
            "document_id": self.item.document_id,
            "chunk_type": self.item.chunk_type,
            "section_path": self.item.section_path,
            "title": self.item.title,
            "content": self.item.content,
            "search_text": self.item.search_text,
            "source": self.item.source,
        }
