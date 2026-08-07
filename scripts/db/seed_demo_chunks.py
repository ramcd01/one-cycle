from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"

sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(BACKEND_ROOT))

from app.db.session import SessionLocal
from app.models import (
    Announcement,
    Chunk,
    ChunkSet,
    CollectionRun,
    Document,
    DocumentStructure,
    ProcessingRun,
)


EXECUTION_ID = "demo-announcement-001"
ANNOUNCEMENT_KEY = "announcement_001"

CHUNKS_PATH = (
    PROJECT_ROOT
    / "outputs"
    / ANNOUNCEMENT_KEY
    / "04_chunks"
    / "hwpx"
    / "chunks.json"
)


def load_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(
            f"파일을 찾을 수 없습니다: {path}"
        )

    return json.loads(
        path.read_text(encoding="utf-8")
    )


def sha256_text(text: str) -> str:
    return hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()


def extract_source_block_ids(source: dict) -> list[str]:
    result: list[str] = []

    for origin_path in source.get("origin_paths", []):
        if not isinstance(origin_path, list):
            continue

        for value in origin_path:
            if (
                isinstance(value, str)
                and value.startswith("block:")
                and value not in result
            ):
                result.append(value)

    return result


def build_source_table_id(source: dict) -> str | None:
    table_index = source.get("table_index")

    if table_index is None:
        return None

    return f"table:{table_index}"


def main() -> None:
    data = load_json(CHUNKS_PATH)

    document_meta = data.get("document", {})
    chunking_meta = data.get("chunking", {})
    report = data.get("report", {})
    chunks = data.get("chunks", [])

    expected_count = report.get("total_chunks")

    if expected_count != len(chunks):
        raise RuntimeError(
            "청크 수가 일치하지 않습니다. "
            f"report={expected_count}, actual={len(chunks)}"
        )

    if not chunks:
        raise RuntimeError("저장할 청크가 없습니다.")

    chunker_version = str(
        chunking_meta.get("version", "unknown")
    )

    strategy = str(
        chunking_meta.get(
            "strategy",
            "unknown",
        )
    )

    chunk_config = {
        "tokenizer": chunking_meta.get("tokenizer"),
        "target_tokens": chunking_meta.get(
            "target_tokens"
        ),
        "max_tokens": chunking_meta.get(
            "max_tokens"
        ),
        "min_tokens": chunking_meta.get(
            "min_tokens"
        ),
        "overlap_tokens": chunking_meta.get(
            "overlap_tokens"
        ),
    }

    with SessionLocal() as db:
        try:
            collection_run = db.scalar(
                select(CollectionRun).where(
                    CollectionRun.execution_id
                    == EXECUTION_ID
                )
            )

            if collection_run is None:
                raise RuntimeError(
                    "collection_run을 찾을 수 없습니다."
                )

            announcement = db.scalar(
                select(Announcement).where(
                    Announcement.collection_run_id
                    == collection_run.id,
                    Announcement.source_announcement_id
                    == ANNOUNCEMENT_KEY,
                )
            )

            if announcement is None:
                raise RuntimeError(
                    "announcement를 찾을 수 없습니다."
                )

            document = db.scalar(
                select(Document).where(
                    Document.announcement_id
                    == announcement.id
                )
            )

            if document is None:
                raise RuntimeError(
                    "document를 찾을 수 없습니다."
                )

            processing_run = db.scalar(
                select(ProcessingRun).where(
                    ProcessingRun.document_id
                    == document.id,
                    ProcessingRun.is_active.is_(True),
                )
            )

            if processing_run is None:
                raise RuntimeError(
                    "활성 processing_run을 찾을 수 없습니다."
                )

            document_structure = db.scalar(
                select(DocumentStructure).where(
                    DocumentStructure.processing_run_id
                    == processing_run.id
                )
            )

            if document_structure is None:
                raise RuntimeError(
                    "document_structure를 찾을 수 없습니다."
                )

            existing_chunk_set = db.scalar(
                select(ChunkSet).where(
                    ChunkSet.processing_run_id
                    == processing_run.id,
                    ChunkSet.is_active.is_(True),
                )
            )

            if existing_chunk_set is not None:
                print()
                print(
                    "[중단] 이미 활성 chunk_set이 존재합니다."
                )
                print(
                    f"chunk_set_id : "
                    f"{existing_chunk_set.id}"
                )
                print(
                    f"chunk_count  : "
                    f"{existing_chunk_set.chunk_count}"
                )
                return

            now = datetime.now(timezone.utc)

            chunk_set = ChunkSet(
                processing_run_id=processing_run.id,
                chunker_version=chunker_version,
                strategy=strategy,
                chunking_config=chunk_config,
                input_content_version=(
                    document_structure.schema_version
                ),
                status="completed",
                is_active=True,
                chunk_count=len(chunks),
                error_message=None,
                started_at=now,
                finished_at=now,
                activated_at=now,
            )

            db.add(chunk_set)
            db.flush()

            for raw_chunk in chunks:
                source = raw_chunk.get("source") or {}

                content = raw_chunk.get("content") or ""
                embedding_text = (
                    raw_chunk.get("embedding_text")
                    or ""
                )

                if not content:
                    raise RuntimeError(
                        "content가 비어 있는 청크가 있습니다: "
                        f"{raw_chunk.get('chunk_id')}"
                    )

                if not embedding_text:
                    raise RuntimeError(
                        "embedding_text가 비어 있는 청크가 있습니다: "
                        f"{raw_chunk.get('chunk_id')}"
                    )

                metadata = {
                    "domain": raw_chunk.get("domain"),
                    "entities": raw_chunk.get(
                        "entities",
                        [],
                    ),
                    "chunking": raw_chunk.get(
                        "chunking",
                        {},
                    ),
                    "normalized_title": raw_chunk.get(
                        "normalized_title"
                    ),
                    "search_title": raw_chunk.get(
                        "search_title"
                    ),
                    "section_id": raw_chunk.get(
                        "section_id"
                    ),
                    "section_level": raw_chunk.get(
                        "section_level"
                    ),
                    "source_filename": raw_chunk.get(
                        "source_filename"
                    ),
                }

                chunk = Chunk(
                    chunk_set_id=chunk_set.id,
                    announcement_id=announcement.id,
                    document_id=document.id,
                    external_chunk_key=str(
                        raw_chunk["chunk_id"]
                    ),
                    chunk_index=int(
                        raw_chunk["chunk_order"]
                    ),
                    document_format=str(
                        raw_chunk["source_format"]
                    ),
                    content_type=str(
                        raw_chunk["chunk_type"]
                    ),
                    title=raw_chunk.get("title"),
                    section_path=raw_chunk.get(
                        "section_path",
                        [],
                    ),
                    content=content,
                    search_text=raw_chunk.get(
                        "search_text"
                    ),
                    embedding_text=embedding_text,
                    token_count=raw_chunk.get(
                        "token_count"
                    ),
                    character_count=raw_chunk.get(
                        "char_count"
                    ),
                    source_block_ids=(
                        extract_source_block_ids(
                            source
                        )
                    ),
                    source_table_id=(
                        build_source_table_id(
                            source
                        )
                    ),
                    source_page=None,
                    source_reference=source,
                    metadata=metadata,
                    content_hash=sha256_text(content),
                    status="completed",
                )

                db.add(chunk)

            db.commit()
            db.refresh(chunk_set)

            print()
            print("[Chunk DB 저장 완료]")
            print(
                f"chunk_set_id          : "
                f"{chunk_set.id}"
            )
            print(
                f"processing_run_id     : "
                f"{processing_run.id}"
            )
            print(
                f"chunker_version       : "
                f"{chunk_set.chunker_version}"
            )
            print(
                f"strategy              : "
                f"{chunk_set.strategy}"
            )
            print(
                f"input_content_version : "
                f"{chunk_set.input_content_version}"
            )
            print(
                f"chunk_count           : "
                f"{chunk_set.chunk_count}"
            )
            print(
                f"is_active              : "
                f"{chunk_set.is_active}"
            )

        except Exception:
            db.rollback()
            raise


if __name__ == "__main__":
    main()