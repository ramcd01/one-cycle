from __future__ import annotations

import re
from typing import Any

from .schemas import EvidenceItem, EvidenceLocation, StructuredField


PREFIX_PATTERNS = (
    r"^\[문서\].*$",
    r"^\[섹션\].*$",
    r"^\[현재 항목\].*$",
)


def _metadata(chunk: dict[str, Any]) -> dict[str, Any]:
    value = chunk.get("metadata")
    return value if isinstance(value, dict) else {}


def _section_path(metadata: dict[str, Any]) -> list[str]:
    value = metadata.get("section_path") or []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def _document_name(chunk: dict[str, Any], metadata: dict[str, Any]) -> str:
    for key in ("document_name", "filename", "source_filename"):
        value = metadata.get(key)
        if value:
            return str(value)
    for key in ("document_name", "filename"):
        value = chunk.get(key)
        if value:
            return str(value)
    return "선택한 문서"


def _clean_text(chunk: dict[str, Any]) -> str:
    raw = str(chunk.get("content") or chunk.get("text") or "")
    lines: list[str] = []
    seen: set[str] = set()

    for source_line in raw.splitlines():
        line = source_line.strip()
        if not line:
            if lines and lines[-1] != "":
                lines.append("")
            continue
        if any(re.match(pattern, line) for pattern in PREFIX_PATTERNS):
            continue
        normalized = re.sub(r"\s+", " ", line)
        if normalized in seen:
            continue
        seen.add(normalized)
        lines.append(normalized)

    while lines and not lines[-1]:
        lines.pop()

    return "\n".join(lines).strip()


def _structured_fields(excerpt: str) -> list[StructuredField]:
    fields: list[StructuredField] = []
    seen: set[tuple[str, str]] = set()

    for line in excerpt.splitlines():
        match = re.match(r"^([^:：]{1,80})\s*[:：]\s*(.+)$", line.strip())
        if not match:
            continue
        label = match.group(1).strip("-•* []")
        value = match.group(2).strip()
        key = (label, value)
        if not label or not value or key in seen:
            continue
        seen.add(key)
        fields.append(StructuredField(label=label, value=value))

    return fields


def _make_excerpt(text: str, max_chars: int = 1800) -> str:
    if len(text) <= max_chars:
        return text

    clipped = text[:max_chars]
    boundary = max(clipped.rfind("\n"), clipped.rfind("."), clipped.rfind("다."))
    if boundary >= max_chars // 2:
        clipped = clipped[: boundary + 1]
    return clipped.rstrip() + " …"


class EvidenceBuilder:
    def build(
        self,
        context_results: list[dict[str, Any]],
    ) -> list[EvidenceItem]:
        evidence: list[EvidenceItem] = []

        for number, result in enumerate(context_results, start=1):
            chunk = result.get("chunk") or {}
            metadata = _metadata(chunk)
            excerpt = _make_excerpt(_clean_text(chunk))
            if not excerpt:
                continue

            evidence.append(
                EvidenceItem(
                    evidence_id=f"evidence_{number:03d}",
                    chunk_id=str(chunk.get("chunk_id") or f"chunk_{number}"),
                    document_name=_document_name(chunk, metadata),
                    location=EvidenceLocation(
                        section_path=_section_path(metadata),
                        source_type=str(chunk.get("chunk_type") or "unknown"),
                        table_index=metadata.get("table_index"),
                        row_index=metadata.get("row_index"),
                    ),
                    excerpt=excerpt,
                    structured_fields=_structured_fields(excerpt),
                    similarity=float(result.get("similarity", 0.0)),
                    rerank_score=float(result.get("rerank_score", 0.0)),
                    retrieval_reasons=[
                        str(item)
                        for item in result.get("expansion_reasons", [])
                    ],
                    direct_rank=result.get("direct_rank"),
                    debug={
                        "vector_index": result.get("vector_index"),
                        "topic_adjustment": result.get("topic_adjustment", 0.0),
                    },
                )
            )

        return evidence
