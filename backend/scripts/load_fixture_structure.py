from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = PROJECT_ROOT / "backend"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


from app.db.session import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    Announcement,
    CollectionRun,
    Document,
    DocumentStructure,
    ProcessingRun,
    SystemState,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "통합 테스트용 공고 1건과 Structure JSON을 서비스 DB에 적재합니다. "
            "Chunk/Embedding 및 system_state 활성화는 수행하지 않습니다."
        )
    )

    parser.add_argument(
        "--announcement-key",
        required=True,
    )

    parser.add_argument(
        "--structure",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--storage-file",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--execution-id",
        default="integration_fixture_announcement_001_v1",
    )

    return parser.parse_args()


def count_structure_elements(data: dict) -> int:
    total = len(data.get("intro") or [])

    def walk(sections: list[dict]) -> int:
        count = 0

        for section in sections:
            count += len(section.get("contents") or [])
            count += walk(section.get("children") or [])

        return count

    total += walk(data.get("sections") or [])
    return total


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)

    return digest.hexdigest()


def main() -> int:
    args = parse_args()

    structure_path = args.structure.expanduser().resolve()
    storage_file = args.storage_file.expanduser().resolve()

    if not structure_path.is_file():
        raise FileNotFoundError(
            f"Structure JSON을 찾을 수 없습니다: {structure_path}"
        )

    if not storage_file.is_file():
        raise FileNotFoundError(
            f"원본 문서를 찾을 수 없습니다: {storage_file}"
        )

    data = json.loads(
        structure_path.read_text(encoding="utf-8")
    )

    document_meta = data.get("document") or {}

    filename = document_meta.get("filename")
    source_format = str(
        document_meta.get("format") or ""
    ).lower()

    if not isinstance(filename, str) or not filename:
        raise ValueError(
            "Structure JSON의 document.filename이 없습니다."
        )

    if source_format not in {"hwp", "hwpx"}:
        raise ValueError(
            f"지원하지 않는 문서 형식입니다: {source_format}"
        )

    if storage_file.name != filename:
        raise ValueError(
            "Structure JSON의 filename과 원본 파일명이 다릅니다. "
            f"structure={filename!r}, "
            f"storage={storage_file.name!r}"
        )

    structure_hash = sha256_file(structure_path)
    document_hash = sha256_file(storage_file)

    element_count = count_structure_elements(data)

    now = datetime.now(timezone.utc)

    with SessionLocal.begin() as session:
        existing_run = session.scalar(
            select(CollectionRun).where(
                CollectionRun.execution_id
                == args.execution_id
            )
        )

        if existing_run is not None:
            raise RuntimeError(
                "동일 execution_id의 collection_run이 "
                f"이미 존재합니다: {args.execution_id}"
            )

        system_state = session.get(SystemState, 1)

        if system_state is None:
            raise RuntimeError(
                "system_state singleton(id=1)이 없습니다."
            )

        if system_state.active_collection_run_id is not None:
            raise RuntimeError(
                "fixture 초기 적재 단계에서는 "
                "active_collection_run_id가 NULL이어야 합니다."
            )

        collection_run = CollectionRun(
            execution_id=args.execution_id,
            status="success",
            total_announcement_count=1,
            successful_announcement_count=1,
            failed_announcement_count=0,
            started_at=now,
            finished_at=now,
        )

        session.add(collection_run)
        session.flush()

        announcement = Announcement(
            collection_run_id=collection_run.id,
            source_announcement_id=args.announcement_key,
            title=Path(filename).stem,
            detail_url=f"fixture://{args.announcement_key}",
            publication_status="fixture",
        )

        session.add(announcement)
        session.flush()

        document = Document(
            announcement_id=announcement.id,
            original_filename=filename,
            document_format=source_format,
            storage_path=str(storage_file),
            file_size_bytes=storage_file.stat().st_size,
            checksum_sha256=document_hash,
            download_status="completed",
        )

        session.add(document)
        session.flush()

        processing_run = ProcessingRun(
            document_id=document.id,
            execution_status="succeeded",
            verification_status="pass",
            current_stage="structure",
            pipeline_version="integration-mvp",
            output_root_path=str(
                structure_path.parent.parent.parent
            ),
            exit_code=0,
            started_at=now,
            finished_at=now,
            is_active=True,
            activated_at=now,
        )

        session.add(processing_run)
        session.flush()

        document_structure = DocumentStructure(
            processing_run_id=processing_run.id,
            schema_version=str(
                data.get("schema_version") or "unknown"
            ),
            structure_json=data,
            element_count=element_count,
            content_hash=structure_hash,
        )

        session.add(document_structure)
        session.flush()

        ids = {
            "collection_run_id": collection_run.id,
            "announcement_id": announcement.id,
            "document_id": document.id,
            "processing_run_id": processing_run.id,
            "document_structure_id": document_structure.id,
        }

    print()
    print("DB STRUCTURE FIXTURE LOAD: PASS")
    print(f"announcement_key: {args.announcement_key}")
    print(f"schema_version: {data.get('schema_version')}")
    print(f"element_count: {element_count}")
    print(f"document_size: {storage_file.stat().st_size}")
    print(f"document_sha256: {document_hash}")
    print(f"structure_sha256: {structure_hash}")

    for key, value in ids.items():
        print(f"{key}: {value}")

    print("system_state activated: NO")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
