from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
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
    Embedding,
    ProcessingRun,
)


DEFAULT_EXECUTION_ID = (
    "integration_fixture_announcement_001_v1"
)
DEFAULT_ANNOUNCEMENT_KEY = "announcement_001"


def sha256_text(text: str) -> str:
    return hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()


def load_context(
    db,
    *,
    execution_id: str,
    announcement_key: str,
):
    collection_run = db.scalar(
        select(CollectionRun).where(
            CollectionRun.execution_id
            == execution_id
        )
    )

    if collection_run is None:
        raise RuntimeError(
            "collection_run not found: "
            f"{execution_id}"
        )

    announcement = db.scalar(
        select(Announcement).where(
            Announcement.collection_run_id
            == collection_run.id,
            Announcement.source_announcement_id
            == announcement_key,
        )
    )

    if announcement is None:
        raise RuntimeError(
            "announcement not found: "
            f"{announcement_key}"
        )

    document = db.scalar(
        select(Document).where(
            Document.announcement_id
            == announcement.id
        )
    )

    if document is None:
        raise RuntimeError(
            "document not found"
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
            "active processing_run not found"
        )

    chunk_set = db.scalar(
        select(ChunkSet).where(
            ChunkSet.processing_run_id
            == processing_run.id,
            ChunkSet.is_active.is_(True),
        )
    )

    if chunk_set is None:
        raise RuntimeError(
            "active chunk_set not found"
        )

    chunks = list(
        db.scalars(
            select(Chunk)
            .where(
                Chunk.chunk_set_id
                == chunk_set.id
            )
            .order_by(
                Chunk.chunk_index.asc()
            )
        )
    )

    if not chunks:
        raise RuntimeError(
            "chunks not found"
        )

    if len(chunks) != chunk_set.chunk_count:
        raise RuntimeError(
            "chunk count mismatch: "
            f"chunk_set={chunk_set.chunk_count}, "
            f"actual={len(chunks)}"
        )

    return (
        announcement,
        document,
        processing_run,
        chunk_set,
        chunks,
    )


def export_chunks(args: argparse.Namespace) -> int:
    output_path = (
        args.output.expanduser().resolve()
    )

    with SessionLocal() as db:
        (
            announcement,
            document,
            processing_run,
            chunk_set,
            chunks,
        ) = load_context(
            db,
            execution_id=args.execution_id,
            announcement_key=args.announcement_key,
        )

        first_metadata = (
            chunks[0].chunk_metadata or {}
        )

        logical_announcement_id = (
            first_metadata.get(
                "logical_announcement_id"
            )
            or announcement.source_announcement_id
        )

        chunk_document_id = (
            first_metadata.get(
                "chunk_document_id"
            )
            or f"db-document-{document.id}"
        )

        chunking_config = (
            chunk_set.chunking_config or {}
        )

        payload_chunks = []

        for chunk in chunks:
            if not chunk.embedding_text:
                raise RuntimeError(
                    "empty embedding_text: "
                    f"chunk_id={chunk.id}"
                )

            metadata = (
                chunk.chunk_metadata or {}
            )

            source = (
                chunk.source_reference or {}
            )

            payload_chunks.append(
                {
                    "chunk_id": (
                        chunk.external_chunk_key
                    ),
                    "chunk_order": (
                        chunk.chunk_index
                    ),
                    "chunk_type": (
                        chunk.content_type
                    ),
                    "document_id": (
                        metadata.get(
                            "chunk_document_id"
                        )
                        or chunk_document_id
                    ),
                    "announcement_id": (
                        metadata.get(
                            "logical_announcement_id"
                        )
                        or logical_announcement_id
                    ),
                    "source_filename": (
                        metadata.get(
                            "source_filename"
                        )
                        or document.original_filename
                    ),
                    "source_format": (
                        chunk.document_format
                    ),
                    "section_id": (
                        metadata.get(
                            "section_id"
                        )
                    ),
                    "section_level": (
                        metadata.get(
                            "section_level"
                        )
                    ),
                    "section_path": (
                        chunk.section_path or []
                    ),
                    "title": chunk.title,
                    "normalized_title": (
                        metadata.get(
                            "normalized_title"
                        )
                    ),
                    "search_title": (
                        metadata.get(
                            "search_title"
                        )
                    ),
                    "content": chunk.content,
                    "search_text": (
                        chunk.search_text
                    ),
                    "embedding_text": (
                        chunk.embedding_text
                    ),
                    "domain": (
                        metadata.get("domain")
                    ),
                    "source": source,
                    "entities": (
                        metadata.get(
                            "entities",
                            [],
                        )
                    ),
                    "token_count": (
                        chunk.token_count
                    ),
                    "char_count": (
                        chunk.character_count
                    ),
                    "chunking": (
                        metadata.get(
                            "chunking",
                            {},
                        )
                    ),
                }
            )

        payload = {
            "document": {
                "document_id": (
                    chunk_document_id
                ),
                "announcement_id": (
                    logical_announcement_id
                ),
                "filename": (
                    document.original_filename
                ),
                "source_format": (
                    document.document_format
                ),
            },
            "chunking": {
                "strategy": (
                    chunk_set.strategy
                ),
                "version": (
                    chunk_set.chunker_version
                ),
                "tokenizer": (
                    chunking_config.get(
                        "tokenizer"
                    )
                ),
                "target_tokens": (
                    chunking_config.get(
                        "target_tokens"
                    )
                ),
                "max_tokens": (
                    chunking_config.get(
                        "max_tokens"
                    )
                ),
                "min_tokens": (
                    chunking_config.get(
                        "min_tokens"
                    )
                ),
                "overlap_tokens": (
                    chunking_config.get(
                        "overlap_tokens"
                    )
                ),
            },
            "chunks": payload_chunks,
        }

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temp_path = output_path.with_suffix(
        output_path.suffix + ".tmp"
    )

    temp_path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    temp_path.replace(output_path)

    print()
    print("DB EMBEDDING EXPORT: PASS")
    print(
        "announcement_id:",
        announcement.id,
    )
    print(
        "announcement_key:",
        announcement.source_announcement_id,
    )
    print(
        "chunk_set_id:",
        chunk_set.id,
    )
    print(
        "chunks:",
        len(payload_chunks),
    )
    print(
        "output:",
        output_path,
    )

    return 0


def import_embeddings(
    args: argparse.Namespace,
) -> int:
    embeddings_path = (
        args.embeddings.expanduser().resolve()
    )

    metadata_path = (
        args.metadata.expanduser().resolve()
    )

    if not embeddings_path.is_file():
        raise FileNotFoundError(
            embeddings_path
        )

    if not metadata_path.is_file():
        raise FileNotFoundError(
            metadata_path
        )

    vectors = np.load(
        embeddings_path,
        allow_pickle=False,
    )

    metadata_payload = json.loads(
        metadata_path.read_text(
            encoding="utf-8"
        )
    )

    model_meta = (
        metadata_payload.get("model")
        or {}
    )

    items = (
        metadata_payload.get("items")
        or []
    )

    model_name = str(
        model_meta.get("name") or ""
    )

    dimension = int(
        model_meta.get("dimension") or 0
    )

    normalized = bool(
        model_meta.get("normalized")
    )

    if model_name != args.model:
        raise RuntimeError(
            "model mismatch: "
            f"expected={args.model}, "
            f"actual={model_name}"
        )

    if vectors.ndim != 2:
        raise RuntimeError(
            f"vectors.ndim={vectors.ndim}"
        )

    if vectors.shape[1] != 1024:
        raise RuntimeError(
            "embedding dimension must be 1024: "
            f"actual={vectors.shape}"
        )

    if dimension != 1024:
        raise RuntimeError(
            "metadata dimension must be 1024: "
            f"actual={dimension}"
        )

    if not normalized:
        raise RuntimeError(
            "embeddings are not normalized"
        )

    if len(items) != vectors.shape[0]:
        raise RuntimeError(
            "metadata/vector count mismatch"
        )

    if not np.isfinite(vectors).all():
        raise RuntimeError(
            "NaN or Inf detected"
        )

    norms = np.linalg.norm(
        vectors,
        axis=1,
    )

    if not np.allclose(
        norms,
        1.0,
        atol=1e-4,
    ):
        raise RuntimeError(
            "L2 normalization validation failed: "
            f"min={norms.min()}, "
            f"max={norms.max()}"
        )

    with SessionLocal.begin() as db:
        (
            announcement,
            document,
            processing_run,
            chunk_set,
            chunks,
        ) = load_context(
            db,
            execution_id=args.execution_id,
            announcement_key=args.announcement_key,
        )

        if len(chunks) != vectors.shape[0]:
            raise RuntimeError(
                "DB chunk/vector count mismatch: "
                f"chunks={len(chunks)}, "
                f"vectors={vectors.shape[0]}"
            )

        chunk_by_key = {
            chunk.external_chunk_key: chunk
            for chunk in chunks
        }

        if (
            len(chunk_by_key)
            != len(chunks)
        ):
            raise RuntimeError(
                "duplicate external_chunk_key"
            )

        existing = db.scalar(
            select(Embedding).where(
                Embedding.model_name
                == args.model,
                Embedding.model_version
                == args.model_version,
                Embedding.chunk_id.in_(
                    [chunk.id for chunk in chunks]
                ),
            )
        )

        if existing is not None:
            raise RuntimeError(
                "embedding already exists: "
                f"id={existing.id}"
            )

        seen_keys = set()

        rows = []

        for item in items:
            chunk_key = str(
                item.get("chunk_id") or ""
            )

            if not chunk_key:
                raise RuntimeError(
                    "metadata chunk_id missing"
                )

            if chunk_key in seen_keys:
                raise RuntimeError(
                    "duplicate metadata chunk_id: "
                    f"{chunk_key}"
                )

            seen_keys.add(chunk_key)

            chunk = chunk_by_key.get(
                chunk_key
            )

            if chunk is None:
                raise RuntimeError(
                    "DB chunk not found for "
                    f"chunk_id={chunk_key}"
                )

            vector_index = item.get(
                "vector_index"
            )

            if not isinstance(
                vector_index,
                int,
            ):
                raise RuntimeError(
                    "invalid vector_index: "
                    f"{vector_index}"
                )

            if not (
                0
                <= vector_index
                < vectors.shape[0]
            ):
                raise RuntimeError(
                    "vector_index out of range: "
                    f"{vector_index}"
                )

            vector = vectors[
                vector_index
            ].astype(
                np.float32,
                copy=False,
            )

            rows.append(
                (
                    chunk,
                    vector.tolist(),
                )
            )

        if len(rows) != len(chunks):
            raise RuntimeError(
                "mapped row count mismatch: "
                f"rows={len(rows)}, "
                f"chunks={len(chunks)}"
            )

        print()
        print("DB EMBEDDING IMPORT")
        print("===================")
        print(
            "announcement_id:",
            announcement.id,
        )
        print(
            "chunk_set_id:",
            chunk_set.id,
        )
        print(
            "model:",
            model_name,
        )
        print(
            "model_version:",
            args.model_version,
        )
        print(
            "vectors:",
            len(rows),
        )
        print(
            "dimension:",
            dimension,
        )
        print(
            "normalized:",
            normalized,
        )
        print(
            "norm_min:",
            float(norms.min()),
        )
        print(
            "norm_max:",
            float(norms.max()),
        )

        if not args.write:
            print()
            print(
                "DRY RUN: PASS - "
                "DB에는 저장하지 않았습니다."
            )
            return 0

        for chunk, vector in rows:
            db.add(
                Embedding(
                    chunk_id=chunk.id,
                    model_name=args.model,
                    model_version=(
                        args.model_version
                    ),
                    dimension=1024,
                    normalized=True,
                    embedding_text_hash=(
                        sha256_text(
                            chunk.embedding_text
                        )
                    ),
                    embedding=vector,
                    status="completed",
                    error_code=None,
                    error_message=None,
                )
            )

        db.flush()

    print()
    print("DB EMBEDDING LOAD: PASS")
    print(
        "embeddings:",
        len(rows),
    )
    print("system_state activated: NO")

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "DB chunks와 BGE-M3 임베딩 결과를 "
            "연결하는 통합 테스트 Adapter"
        )
    )

    parser.add_argument(
        "--execution-id",
        default=DEFAULT_EXECUTION_ID,
    )

    parser.add_argument(
        "--announcement-key",
        default=DEFAULT_ANNOUNCEMENT_KEY,
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    export_parser = (
        subparsers.add_parser("export")
    )

    export_parser.add_argument(
        "--output",
        type=Path,
        required=True,
    )

    import_parser = (
        subparsers.add_parser("import")
    )

    import_parser.add_argument(
        "--embeddings",
        type=Path,
        required=True,
    )

    import_parser.add_argument(
        "--metadata",
        type=Path,
        required=True,
    )

    import_parser.add_argument(
        "--model",
        default="BAAI/bge-m3",
    )

    import_parser.add_argument(
        "--model-version",
        default="default",
    )

    import_parser.add_argument(
        "--write",
        action="store_true",
    )

    return parser


def main() -> int:
    args = build_parser().parse_args()

    if args.command == "export":
        return export_chunks(args)

    if args.command == "import":
        return import_embeddings(args)

    raise RuntimeError(
        f"unknown command: {args.command}"
    )


if __name__ == "__main__":
    raise SystemExit(main())
