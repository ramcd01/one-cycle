from __future__ import annotations

import argparse
import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


from app.db.session import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    Announcement,
    Chunk,
    ChunkSet,
    CollectionRun,
    Document,
    DocumentStructure,
    ProcessingRun,
)
from chunking.chunker import StructureAwareChunker  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "document_structures.structure_json을 DB에서 읽어 "
            "Chunking한 뒤 chunk_sets/chunks에 저장합니다."
        )
    )

    parser.add_argument(
        "--execution-id",
        default="integration_fixture_announcement_001_v1",
    )

    parser.add_argument(
        "--announcement-key",
        default="announcement_001",
    )

    parser.add_argument(
        "--write",
        action="store_true",
        help="실제 DB에 chunk_set/chunks를 저장합니다.",
    )

    return parser.parse_args()


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


def validate_chunks(
    chunks: list[dict],
    expected_announcement_key: str,
) -> None:
    if not chunks:
        raise RuntimeError("생성된 청크가 없습니다.")

    chunk_ids = [
        str(chunk["chunk_id"])
        for chunk in chunks
    ]

    if len(chunk_ids) != len(set(chunk_ids)):
        raise RuntimeError(
            "중복 chunk_id가 존재합니다."
        )

    expected_orders = list(
        range(1, len(chunks) + 1)
    )

    actual_orders = [
        int(chunk["chunk_order"])
        for chunk in chunks
    ]

    if actual_orders != expected_orders:
        raise RuntimeError(
            "chunk_order가 1부터 연속되지 않습니다."
        )

    for chunk in chunks:
        if (
            chunk.get("announcement_id")
            != expected_announcement_key
        ):
            raise RuntimeError(
                "logical announcement_id 불일치: "
                f"{chunk.get('announcement_id')}"
            )

        if not chunk.get("content"):
            raise RuntimeError(
                "content가 비어 있습니다: "
                f"{chunk.get('chunk_id')}"
            )

        if not chunk.get("embedding_text"):
            raise RuntimeError(
                "embedding_text가 비어 있습니다: "
                f"{chunk.get('chunk_id')}"
            )


def main() -> int:
    args = parse_args()

    with SessionLocal.begin() as db:
        collection_run = db.scalar(
            select(CollectionRun).where(
                CollectionRun.execution_id
                == args.execution_id
            )
        )

        if collection_run is None:
            raise RuntimeError(
                "collection_run을 찾을 수 없습니다: "
                f"{args.execution_id}"
            )

        announcement = db.scalar(
            select(Announcement).where(
                Announcement.collection_run_id
                == collection_run.id,
                Announcement.source_announcement_id
                == args.announcement_key,
            )
        )

        if announcement is None:
            raise RuntimeError(
                "announcement를 찾을 수 없습니다: "
                f"{args.announcement_key}"
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

        structure_json = (
            document_structure.structure_json
        )

        if not isinstance(structure_json, dict):
            raise RuntimeError(
                "structure_json이 dict가 아닙니다."
            )

        chunker = StructureAwareChunker()

        result = chunker.chunk_document(
            structure_json,
            announcement_id=(
                announcement.source_announcement_id
            ),
        )

        document_meta = result["document"]
        chunking_meta = result["chunking"]
        report = result["report"]
        chunks = result["chunks"]

        if report["total_chunks"] != len(chunks):
            raise RuntimeError(
                "Chunk report 수와 실제 수가 다릅니다."
            )

        validate_chunks(
            chunks,
            announcement.source_announcement_id,
        )

        source_format = str(
            document_meta.get("source_format")
            or ""
        ).lower()

        if source_format != document.document_format:
            raise RuntimeError(
                "DB document_format과 Chunk source_format이 "
                "다릅니다: "
                f"db={document.document_format}, "
                f"chunk={source_format}"
            )

        existing_chunk_set = db.scalar(
            select(ChunkSet).where(
                ChunkSet.processing_run_id
                == processing_run.id
            )
        )

        if existing_chunk_set is not None:
            raise RuntimeError(
                "해당 processing_run에 이미 "
                "chunk_set이 존재합니다: "
                f"id={existing_chunk_set.id}"
            )

        print()
        print("DB-FIRST CHUNKING")
        print("=================")
        print(
            "announcement_db_id:",
            announcement.id,
        )
        print(
            "announcement_key:",
            announcement.source_announcement_id,
        )
        print("document_db_id:", document.id)
        print(
            "processing_run_id:",
            processing_run.id,
        )
        print(
            "document_structure_id:",
            document_structure.id,
        )
        print(
            "source_schema_version:",
            document_structure.schema_version,
        )
        print(
            "chunk_schema_version:",
            chunking_meta["version"],
        )
        print(
            "strategy:",
            chunking_meta["strategy"],
        )
        print(
            "tokenizer:",
            chunking_meta["tokenizer"],
        )
        print(
            "total_chunks:",
            len(chunks),
        )
        print(
            "chunk_types:",
            report["chunk_types"],
        )
        print(
            "token_stats:",
            report["token_stats"],
        )
        print(
            "warnings:",
            len(report["warnings"]),
        )

        if not args.write:
            print()
            print(
                "DRY RUN: PASS - DB에는 저장하지 않았습니다."
            )
            return 0

        now = datetime.now(timezone.utc)

        chunk_config = {
            "tokenizer": (
                chunking_meta.get("tokenizer")
            ),
            "target_tokens": (
                chunking_meta.get("target_tokens")
            ),
            "max_tokens": (
                chunking_meta.get("max_tokens")
            ),
            "min_tokens": (
                chunking_meta.get("min_tokens")
            ),
            "overlap_tokens": (
                chunking_meta.get("overlap_tokens")
            ),
        }

        chunk_set = ChunkSet(
            processing_run_id=processing_run.id,
            chunker_version=str(
                chunking_meta["version"]
            ),
            strategy=str(
                chunking_meta["strategy"]
            ),
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
            source = (
                raw_chunk.get("source")
                or {}
            )

            content = str(
                raw_chunk["content"]
            )

            embedding_text = str(
                raw_chunk["embedding_text"]
            )

            chunk_metadata = {
                "domain": (
                    raw_chunk.get("domain")
                ),
                "entities": (
                    raw_chunk.get("entities", [])
                ),
                "chunking": (
                    raw_chunk.get(
                        "chunking",
                        {},
                    )
                ),
                "normalized_title": (
                    raw_chunk.get(
                        "normalized_title"
                    )
                ),
                "search_title": (
                    raw_chunk.get(
                        "search_title"
                    )
                ),
                "section_id": (
                    raw_chunk.get("section_id")
                ),
                "section_level": (
                    raw_chunk.get(
                        "section_level"
                    )
                ),
                "source_filename": (
                    raw_chunk.get(
                        "source_filename"
                    )
                ),
                "source_content_type": (
                    source.get("content_type")
                ),
                "logical_announcement_id": (
                    raw_chunk.get(
                        "announcement_id"
                    )
                ),
                "chunk_document_id": (
                    raw_chunk.get(
                        "document_id"
                    )
                ),
            }

            chunk = Chunk(
                chunk_set_id=chunk_set.id,

                # 여기서는 파일의 문자열 ID가 아니라
                # 실제 서비스 DB PK를 저장한다.
                announcement_id=announcement.id,
                document_id=document.id,

                external_chunk_key=str(
                    raw_chunk["chunk_id"]
                ),
                chunk_index=int(
                    raw_chunk["chunk_order"]
                ),

                document_format=source_format,
                content_type=str(
                    raw_chunk["chunk_type"]
                ),
                title=raw_chunk.get("title"),
                section_path=(
                    raw_chunk.get(
                        "section_path",
                        [],
                    )
                ),

                content=content,
                search_text=(
                    raw_chunk.get(
                        "search_text"
                    )
                ),
                embedding_text=embedding_text,

                token_count=(
                    raw_chunk.get(
                        "token_count"
                    )
                ),
                character_count=(
                    raw_chunk.get(
                        "char_count"
                    )
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

                # ORM attribute는 chunk_metadata이고
                # 실제 DB column 이름은 metadata이다.
                chunk_metadata=chunk_metadata,

                content_hash=(
                    sha256_text(content)
                ),
                status="completed",
            )

            db.add(chunk)

        db.flush()

        chunk_set_id = chunk_set.id
        db_announcement_id = announcement.id
        db_document_id = document.id
        processing_run_id = processing_run.id
        chunk_count = len(chunks)

    print()
    print("DB CHUNK LOAD: PASS")
    print(
        "chunk_set_id:",
        chunk_set_id,
    )
    print(
        "announcement_id:",
        db_announcement_id,
    )
    print(
        "document_id:",
        db_document_id,
    )
    print(
        "processing_run_id:",
        processing_run_id,
    )
    print(
        "chunk_count:",
        chunk_count,
    )
    print("chunk_set active: YES")
    print("system_state activated: NO")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
