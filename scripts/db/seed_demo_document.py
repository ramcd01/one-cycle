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
    CollectionRun,
    Document,
    DocumentStructure,
    ProcessingRun,
)


ANNOUNCEMENT_KEY = "announcement_001"
EXECUTION_ID = "demo-announcement-001"

DOCUMENT_DIR = PROJECT_ROOT / "test_documents" / ANNOUNCEMENT_KEY
OUTPUT_ROOT = PROJECT_ROOT / "outputs" / ANNOUNCEMENT_KEY

STRUCTURE_PATH = (
    OUTPUT_ROOT
    / "03_structured"
    / "hwpx"
    / "step4-1_value_normalized.json"
)

VERIFICATION_PATH = (
    OUTPUT_ROOT
    / "03_structured"
    / "hwpx"
    / "step4-3_verification.json"
)

PARSED_PATH = (
    OUTPUT_ROOT
    / "01_parsed"
    / "hwpx.json"
)

NORMALIZED_PATH = (
    OUTPUT_ROOT
    / "02_normalized"
    / "hwpx.json"
)


def load_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"파일을 찾을 수 없습니다: {path}")

    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)

    return digest.hexdigest()


def find_source_document() -> Path:
    candidates = list(DOCUMENT_DIR.glob("*.hwpx"))
    candidates += list(DOCUMENT_DIR.glob("*.hwp"))

    if len(candidates) != 1:
        raise RuntimeError(
            f"{DOCUMENT_DIR}에서 HWP/HWPX 문서 1개가 필요합니다. "
            f"현재 발견된 문서 수: {len(candidates)}"
        )

    return candidates[0]


def count_structure_elements(structure: dict) -> int:
    """
    Structure의 실제 콘텐츠 요소 수를 계산한다.

    - intro의 각 항목을 1개 요소로 계산
    - 각 section.contents의 paragraph/table 등을 요소로 계산
    - children은 재귀적으로 순회
    - section 자체는 콘텐츠 요소 수에 포함하지 않음
    """

    total = len(structure.get("intro", []))

    def walk_sections(sections: list[dict]) -> int:
        count = 0

        for section in sections:
            count += len(section.get("contents", []))
            count += walk_sections(section.get("children", []))

        return count

    total += walk_sections(structure.get("sections", []))

    return total


def extract_title(structure: dict) -> str:
    for item in structure.get("intro", []):
        if item.get("type") == "table":
            for cell in item.get("cells", []):
                text = (cell.get("text") or "").strip()

                if text:
                    return text.splitlines()[0].strip()

        text = (item.get("text") or "").strip()

        if text:
            return text.splitlines()[0].strip()

    return ANNOUNCEMENT_KEY


def read_warning_count(path: Path) -> int:
    if not path.exists():
        return 0

    data = load_json(path)

    for key in (
        "warnings",
        "parser_warnings",
        "normalizer_warnings",
    ):
        value = data.get(key)

        if isinstance(value, list):
            return len(value)

    return 0


def relative_path(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


def main() -> None:
    source_document = find_source_document()

    structure = load_json(STRUCTURE_PATH)
    verification = load_json(VERIFICATION_PATH)

    verification_status = verification.get("status")

    if verification_status != "pass":
        raise RuntimeError(
            "Structure 검증 결과가 pass가 아닙니다. "
            f"현재 상태: {verification_status}"
        )

    verification_summary = verification.get("summary", {})

    document_format = source_document.suffix.lower().lstrip(".")

    if document_format not in {"hwp", "hwpx"}:
        raise RuntimeError(
            f"지원하지 않는 문서 형식입니다: {document_format}"
        )

    now = datetime.now(timezone.utc)

    element_count = count_structure_elements(structure)
    document_checksum = sha256_file(source_document)
    structure_checksum = sha256_file(STRUCTURE_PATH)

    parser_warning_count = read_warning_count(PARSED_PATH)
    normalizer_warning_count = read_warning_count(NORMALIZED_PATH)

    title = extract_title(structure)

    with SessionLocal() as db:
        try:
            existing_run = db.scalar(
                select(CollectionRun).where(
                    CollectionRun.execution_id == EXECUTION_ID
                )
            )

            if existing_run is not None:
                print(
                    "[중단] 이미 동일한 demo 데이터가 존재합니다."
                )
                print(
                    f"collection_run_id: {existing_run.id}"
                )
                print(
                    f"execution_id: {existing_run.execution_id}"
                )
                return

            collection_run = CollectionRun(
                execution_id=EXECUTION_ID,
                status="success",
                total_announcement_count=1,
                successful_announcement_count=1,
                failed_announcement_count=0,
                started_at=now,
                finished_at=now,
            )

            db.add(collection_run)
            db.flush()

            announcement = Announcement(
                collection_run_id=collection_run.id,
                source_announcement_id=ANNOUNCEMENT_KEY,
                title=title,
                detail_url=f"local://{ANNOUNCEMENT_KEY}",
                publication_status=None,
                announcement_date=None,
                region=None,
            )

            db.add(announcement)
            db.flush()

            document = Document(
                announcement_id=announcement.id,
                original_filename=source_document.name,
                document_format=document_format,
                storage_path=relative_path(source_document),
                file_size_bytes=source_document.stat().st_size,
                checksum_sha256=document_checksum,
                download_status="completed",
                error_message=None,
            )

            db.add(document)
            db.flush()

            processing_run = ProcessingRun(
                document_id=document.id,
                execution_status="succeeded",
                verification_status="pass",
                current_stage="structure",
                pipeline_version="mvp-v0.1",
                output_root_path=relative_path(OUTPUT_ROOT),
                exit_code=0,
                error_stage=None,
                error_code=None,
                error_message=None,
                parser_warning_count=parser_warning_count,
                normalizer_warning_count=normalizer_warning_count,
                verification_error_count=int(
                    verification_summary.get("error_count", 0)
                ),
                verification_warning_count=int(
                    verification_summary.get("warning_count", 0)
                ),
                started_at=now,
                finished_at=now,
                is_active=True,
                activated_at=now,
            )

            db.add(processing_run)
            db.flush()

            document_structure = DocumentStructure(
                processing_run_id=processing_run.id,
                schema_version=str(
                    structure.get("schema_version", "unknown")
                ),
                structure_json=structure,
                element_count=element_count,
                content_hash=structure_checksum,
            )

            db.add(document_structure)

            db.commit()

            print()
            print("[DB 적재 완료]")
            print(
                f"collection_run_id     : {collection_run.id}"
            )
            print(
                f"announcement_id       : {announcement.id}"
            )
            print(
                f"document_id           : {document.id}"
            )
            print(
                f"processing_run_id     : {processing_run.id}"
            )
            print(
                f"document_structure_id : {document_structure.id}"
            )
            print(
                f"schema_version        : "
                f"{document_structure.schema_version}"
            )
            print(
                f"element_count         : {element_count}"
            )
            print(
                f"verification_status   : "
                f"{processing_run.verification_status}"
            )
            print(
                f"is_active             : "
                f"{processing_run.is_active}"
            )
            print(
                f"source_document       : "
                f"{relative_path(source_document)}"
            )

        except Exception:
            db.rollback()
            raise


if __name__ == "__main__":
    main()
