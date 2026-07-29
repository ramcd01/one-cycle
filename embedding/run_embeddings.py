from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

import numpy as np
import torch
from sentence_transformers import SentenceTransformer


MODEL_NAME = "Qwen/Qwen3-Embedding-0.6B"
DEFAULT_BATCH_SIZE = 4


def load_chunk_file(input_path: Path) -> dict[str, Any]:
    if not input_path.exists():
        raise FileNotFoundError(f"Chunk JSON을 찾을 수 없습니다: {input_path}")

    with input_path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, dict):
        raise ValueError("Chunk JSON 최상위 구조는 객체(dict)여야 합니다.")

    chunks = data.get("chunks")
    if not isinstance(chunks, list):
        raise ValueError("Chunk JSON에 chunks 배열이 없습니다.")
    if not chunks:
        raise ValueError("임베딩할 청크가 없습니다.")

    return data


def extract_texts(
    chunks: list[Any],
) -> tuple[list[str], list[dict[str, Any]]]:
    texts: list[str] = []
    metadata_items: list[dict[str, Any]] = []

    for chunk in chunks:
        if not isinstance(chunk, dict):
            continue

        text = str(chunk.get("text") or "").strip()
        if not text:
            print(f"[WARN] text가 비어 있어 제외: {chunk.get('chunk_id')}")
            continue

        vector_index = len(texts)
        texts.append(text)
        metadata_items.append(
            {
                "vector_index": vector_index,
                "chunk_id": chunk.get("chunk_id"),
                "chunk_type": chunk.get("chunk_type"),
                "text": text,
                "content": chunk.get("content"),
                "char_count": chunk.get("char_count"),
                "metadata": deepcopy(chunk.get("metadata")),
            }
        )

    if not texts:
        raise ValueError("text 필드가 있는 유효한 청크가 없습니다.")

    return texts, metadata_items


def resolve_device(requested_device: str) -> str:
    requested_device = requested_device.lower().strip()

    if requested_device == "auto":
        return "cuda" if torch.cuda.is_available() else "cpu"

    if requested_device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA를 요청했지만 현재 환경에서 사용할 수 없습니다.")

    if requested_device not in {"cpu", "cuda"}:
        raise ValueError(f"지원하지 않는 device입니다: {requested_device}")

    return requested_device


def load_model(device: str) -> SentenceTransformer:
    print(f"사용 장치: {device}")
    print(f"모델 로딩: {MODEL_NAME}")

    model = SentenceTransformer(
        MODEL_NAME,
        device=device,
    )
    model.eval()
    return model


def create_embeddings(
    model: SentenceTransformer,
    texts: list[str],
    batch_size: int,
) -> np.ndarray:
    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=True,
    )

    embeddings = np.asarray(embeddings)

    if embeddings.ndim != 2:
        raise ValueError(
            f"임베딩 배열은 2차원이어야 합니다: {embeddings.shape}"
        )

    return embeddings.astype(np.float32)


def get_output_paths(input_path: Path) -> tuple[Path, Path]:
    document_format = input_path.parent.name.lower()

    if document_format not in {"hwp", "hwpx"}:
        raise ValueError(
            f"지원하지 않는 문서 형식 폴더입니다: {document_format}"
        )

    chunks_dir = input_path.parent.parent
    if chunks_dir.name != "04_chunks":
        raise ValueError(
            "예상한 Chunk 경로가 아닙니다.\n"
            "예상: outputs/<document_id>/04_chunks/<hwp|hwpx>/chunks.json\n"
            f"실제: {input_path}"
        )

    document_root = chunks_dir.parent
    output_dir = document_root / "05_embeddings" / document_format
    output_dir.mkdir(parents=True, exist_ok=True)

    return (
        output_dir / "embeddings.npy",
        output_dir / "metadata.json",
    )


def save_embedding_files(
    *,
    embedding_path: Path,
    metadata_path: Path,
    embeddings: np.ndarray,
    chunk_data: dict[str, Any],
    metadata_items: list[dict[str, Any]],
    device: str,
    batch_size: int,
) -> None:
    np.save(embedding_path, embeddings)

    metadata_output = {
        "document": deepcopy(chunk_data.get("document") or {}),
        "embedding_model": {
            "model_name": MODEL_NAME,
            "dimension": int(embeddings.shape[1]),
            "normalized": True,
            "device": device,
            "batch_size": batch_size,
        },
        "summary": {
            "total_vectors": int(embeddings.shape[0]),
            "vector_dimension": int(embeddings.shape[1]),
            "vector_file": embedding_path.name,
        },
        "chunks": metadata_items,
    }

    with metadata_path.open("w", encoding="utf-8") as file:
        json.dump(metadata_output, file, ensure_ascii=False, indent=2)


def validate_saved_results(
    embedding_path: Path,
    metadata_path: Path,
) -> None:
    embeddings = np.load(embedding_path)

    with metadata_path.open("r", encoding="utf-8") as file:
        metadata = json.load(file)

    if embeddings.ndim != 2:
        raise ValueError(
            f"저장된 임베딩 배열은 2차원이어야 합니다: {embeddings.shape}"
        )

    metadata_chunks = metadata.get("chunks") or []
    if embeddings.shape[0] != len(metadata_chunks):
        raise ValueError(
            "벡터 개수와 메타데이터 청크 개수가 일치하지 않습니다: "
            f"{embeddings.shape[0]} != {len(metadata_chunks)}"
        )

    dimension = int(
        metadata.get("embedding_model", {}).get("dimension", 0)
    )
    if embeddings.shape[1] != dimension:
        raise ValueError(
            "실제 벡터 차원과 메타데이터 dimension 값이 다릅니다."
        )


def existing_result_matches_input(
    input_path: Path,
    metadata_path: Path,
) -> bool:
    chunk_data = load_chunk_file(input_path)
    _, expected_items = extract_texts(chunk_data["chunks"])

    with metadata_path.open("r", encoding="utf-8") as file:
        metadata = json.load(file)

    saved_items = metadata.get("chunks")
    if not isinstance(saved_items, list):
        return False

    if len(expected_items) != len(saved_items):
        return False

    for expected, saved in zip(expected_items, saved_items):
        if not isinstance(saved, dict):
            return False
        if expected.get("chunk_id") != saved.get("chunk_id"):
            return False
        if expected.get("text") != saved.get("text"):
            return False

    return True


def is_existing_result_valid(input_path: Path) -> bool:
    embedding_path, metadata_path = get_output_paths(input_path)

    if not embedding_path.exists() or not metadata_path.exists():
        return False

    try:
        validate_saved_results(
            embedding_path,
            metadata_path,
        )
        return existing_result_matches_input(
            input_path,
            metadata_path,
        )
    except (
        OSError,
        json.JSONDecodeError,
        ValueError,
        TypeError,
    ) as error:
        print("[WARN] 기존 임베딩 결과를 재사용할 수 없습니다.")
        print(f"입력: {input_path}")
        print(f"원인: {error}")
        return False


def process_chunk_file(
    *,
    input_path: Path,
    model: SentenceTransformer,
    device: str,
    batch_size: int,
) -> tuple[Path, Path]:
    chunk_data = load_chunk_file(input_path)
    texts, metadata_items = extract_texts(chunk_data["chunks"])
    embedding_path, metadata_path = get_output_paths(input_path)

    print()
    print("=" * 72)
    print("청크 임베딩 시작")
    print("=" * 72)
    print(f"입력: {input_path}")
    print(f"벡터 출력: {embedding_path}")
    print(f"메타데이터 출력: {metadata_path}")
    print(f"전체 원본 청크: {len(chunk_data['chunks'])}개")
    print(f"임베딩 대상 청크: {len(texts)}개")

    embeddings = create_embeddings(
        model,
        texts,
        batch_size,
    )

    save_embedding_files(
        embedding_path=embedding_path,
        metadata_path=metadata_path,
        embeddings=embeddings,
        chunk_data=chunk_data,
        metadata_items=metadata_items,
        device=device,
        batch_size=batch_size,
    )

    validate_saved_results(
        embedding_path,
        metadata_path,
    )

    print()
    print("-" * 72)
    print(f"임베딩 배열: {embeddings.shape}")
    print("벡터 개수와 메타데이터 개수 일치: PASS")
    print(f"저장 완료: {embedding_path}")
    print(f"저장 완료: {metadata_path}")
    print("-" * 72)

    return embedding_path, metadata_path


def run_embedding_pipeline(
    *,
    input_paths: list[Path],
    requested_device: str,
    batch_size: int,
    force: bool,
) -> None:
    if not input_paths:
        raise ValueError("임베딩 대상 Chunk JSON이 없습니다.")

    if batch_size < 1:
        raise ValueError("batch_size는 1 이상이어야 합니다.")

    unique_paths: list[Path] = []
    seen: set[Path] = set()

    for path in input_paths:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        unique_paths.append(resolved)

    missing_paths = [path for path in unique_paths if not path.exists()]
    if missing_paths:
        missing_text = "\n".join(f"- {path}" for path in missing_paths)
        raise FileNotFoundError(
            f"일부 Chunk JSON을 찾을 수 없습니다.\n{missing_text}"
        )

    pending_paths: list[Path] = []
    skipped_paths: list[Path] = []

    print()
    print("=" * 72)
    print("Embedding 대상 검사")
    print("=" * 72)

    for input_path in unique_paths:
        if not force and is_existing_result_valid(input_path):
            skipped_paths.append(input_path)
            print(f"[SKIP] 기존 결과 재사용: {input_path}")
        else:
            pending_paths.append(input_path)
            print(f"[PENDING] 신규 임베딩: {input_path}")

    print()
    print(f"전체 선택: {len(unique_paths)}개")
    print(f"기존 결과 재사용: {len(skipped_paths)}개")
    print(f"신규 임베딩: {len(pending_paths)}개")

    if not pending_paths:
        print()
        print("모든 임베딩 결과가 이미 최신 상태입니다.")
        print("Embedding 모델을 로딩하지 않습니다.")
        return

    device = resolve_device(requested_device)

    print()
    print("=" * 72)
    print("전체 Embedding Pipeline 시작")
    print("=" * 72)
    print(f"신규 처리 대상: {len(pending_paths)}개")
    print(f"배치 크기: {batch_size}")

    model = load_model(device)

    success = 0
    failed: list[tuple[Path, str]] = []

    for index, input_path in enumerate(pending_paths, start=1):
        print()
        print(f"[{index}/{len(pending_paths)}] {input_path}")

        try:
            process_chunk_file(
                input_path=input_path,
                model=model,
                device=device,
                batch_size=batch_size,
            )
            success += 1
        except Exception as error:
            failed.append((input_path, str(error)))
            print("[ERROR] 임베딩 실패")
            print(f"파일: {input_path}")
            print(f"원인: {error}")

    print()
    print("=" * 72)
    print("전체 Embedding Pipeline 완료")
    print("=" * 72)
    print(f"기존 결과 재사용: {len(skipped_paths)}")
    print(f"신규 성공: {success}")
    print(f"신규 실패: {len(failed)}")
    print(f"전체 완료: {len(skipped_paths) + success}")

    if failed:
        print()
        print("실패 파일:")
        for path, reason in failed:
            print(f"- {path}")
            print(f"  원인: {reason}")

    print("=" * 72)

    if failed:
        sys.exit(1)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "여러 chunks.json을 Qwen3 임베딩 벡터와 "
            "메타데이터 파일로 변환합니다."
        )
    )
    parser.add_argument(
        "--inputs",
        nargs="+",
        required=True,
        help="임베딩할 chunks.json 경로 목록",
    )
    parser.add_argument(
        "--device",
        choices=("auto", "cpu", "cuda"),
        default="auto",
        help="사용 장치. 기본값은 auto입니다.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"임베딩 배치 크기. 기본값은 {DEFAULT_BATCH_SIZE}입니다.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="기존 결과가 있어도 다시 임베딩합니다.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()

    run_embedding_pipeline(
        input_paths=[Path(value) for value in args.inputs],
        requested_device=args.device,
        batch_size=args.batch_size,
        force=args.force,
    )


if __name__ == "__main__":
    main()