"""청킹 JSON을 Qwen3 임베딩 벡터와 메타데이터 파일로 변환한다."""
from __future__ import annotations

import json
import os
from copy import deepcopy
from tkinter import Tk, messagebox
from tkinter.filedialog import askopenfilename
from typing import Any

import numpy as np
import torch
from sentence_transformers import SentenceTransformer

MODEL_NAME = "Qwen/Qwen3-Embedding-0.6B"
BATCH_SIZE = 4


def select_chunk_json() -> str | None:
    root = Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    selected = askopenfilename(
        title="청킹 최종 JSON 선택",
        filetypes=[
            ("청킹 최종 JSON", "*_step4_chunks.json"),
            ("JSON Files", "*.json"),
        ],
    )
    root.destroy()
    return selected or None


def load_chunk_file(input_path: str) -> dict[str, Any]:
    with open(input_path, "r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ValueError("최상위 JSON은 객체(dict) 형태여야 합니다.")
    chunks = data.get("chunks")
    if not isinstance(chunks, list):
        raise ValueError("선택한 JSON에 chunks 배열이 없습니다.")
    if not chunks:
        raise ValueError("임베딩할 청크가 없습니다.")
    return data


def extract_texts(chunks: list[dict[str, Any]]) -> tuple[list[str], list[dict[str, Any]]]:
    texts: list[str] = []
    metadata_items: list[dict[str, Any]] = []
    for chunk in chunks:
        if not isinstance(chunk, dict):
            continue
        text = str(chunk.get("text") or "").strip()
        if not text:
            print("[WARN] text가 비어 있어 제외:", chunk.get("chunk_id"))
            continue
        vector_index = len(texts)
        texts.append(text)
        metadata_items.append({
            "vector_index": vector_index,
            "chunk_id": chunk.get("chunk_id"),
            "chunk_type": chunk.get("chunk_type"),
            "text": text,
            "content": chunk.get("content"),
            "char_count": chunk.get("char_count"),
            "metadata": deepcopy(chunk.get("metadata")),
        })
    if not texts:
        raise ValueError("text 필드가 있는 유효한 청크가 없습니다.")
    return texts, metadata_items


def load_model() -> tuple[SentenceTransformer, str]:
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"사용 장치: {device}")
    print(f"모델 로딩: {MODEL_NAME}")
    model = SentenceTransformer(MODEL_NAME, device=device)
    return model, device


def create_embeddings(model: SentenceTransformer, texts: list[str]) -> np.ndarray:
    embeddings = model.encode(
        texts,
        batch_size=BATCH_SIZE,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=True,
    )
    embeddings = np.asarray(embeddings)
    if embeddings.ndim != 2:
        raise ValueError(f"임베딩 배열은 2차원이어야 합니다: {embeddings.shape}")
    return embeddings.astype(np.float32)


def make_output_paths(input_path: str) -> tuple[str, str]:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(script_dir, "output")
    os.makedirs(output_dir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(input_path))[0]
    suffix = "_step4_chunks"
    if stem.endswith(suffix):
        stem = stem[:-len(suffix)]
    return (
        os.path.join(output_dir, f"{stem}_embeddings.npy"),
        os.path.join(output_dir, f"{stem}_embedding_metadata.json"),
    )


def save_embedding_files(*, embedding_path: str, metadata_path: str, embeddings: np.ndarray,
                         chunk_data: dict[str, Any], metadata_items: list[dict[str, Any]],
                         device: str) -> None:
    np.save(embedding_path, embeddings)
    metadata_output = {
        "document": deepcopy(chunk_data.get("document") or {}),
        "embedding_model": {
            "model_name": MODEL_NAME,
            "dimension": int(embeddings.shape[1]),
            "normalized": True,
            "device": device,
            "batch_size": BATCH_SIZE,
        },
        "summary": {
            "total_vectors": int(embeddings.shape[0]),
            "vector_dimension": int(embeddings.shape[1]),
            "vector_file": os.path.basename(embedding_path),
        },
        "chunks": metadata_items,
    }
    with open(metadata_path, "w", encoding="utf-8") as file:
        json.dump(metadata_output, file, ensure_ascii=False, indent=2)


def validate_saved_results(embedding_path: str, metadata_path: str) -> None:
    embeddings = np.load(embedding_path)
    with open(metadata_path, "r", encoding="utf-8") as file:
        metadata = json.load(file)
    metadata_chunks = metadata.get("chunks") or []
    if embeddings.shape[0] != len(metadata_chunks):
        raise ValueError(
            "벡터 개수와 메타데이터 청크 개수가 일치하지 않습니다: "
            f"{embeddings.shape[0]} != {len(metadata_chunks)}"
        )
    dimension = int(metadata.get("embedding_model", {}).get("dimension", 0))
    if embeddings.shape[1] != dimension:
        raise ValueError("실제 벡터 차원과 메타데이터 dimension 값이 다릅니다.")


def main() -> None:
    input_path = select_chunk_json()
    if not input_path:
        print("청킹 JSON을 선택하지 않았습니다.")
        return
    try:
        chunk_data = load_chunk_file(input_path)
        texts, metadata_items = extract_texts(chunk_data["chunks"])
        print(f"전체 원본 청크: {len(chunk_data['chunks'])}개")
        print(f"임베딩 대상 청크: {len(texts)}개")
        model, device = load_model()
        embeddings = create_embeddings(model, texts)
        embedding_path, metadata_path = make_output_paths(input_path)
        save_embedding_files(
            embedding_path=embedding_path,
            metadata_path=metadata_path,
            embeddings=embeddings,
            chunk_data=chunk_data,
            metadata_items=metadata_items,
            device=device,
        )
        validate_saved_results(embedding_path, metadata_path)
        print("\n" + "=" * 72)
        print("청크 임베딩 완료")
        print("=" * 72)
        print(f"임베딩 배열: {embeddings.shape}")
        print(f"벡터 파일: {embedding_path}")
        print(f"메타데이터 파일: {metadata_path}")
        print("벡터 개수와 메타데이터 개수 일치: PASS")
        print("=" * 72 + "\n")
        messagebox.showinfo(
            "임베딩 완료",
            "임베딩 결과를 생성했습니다.\n\n"
            f"벡터 파일:\n{embedding_path}\n\n"
            f"메타데이터 파일:\n{metadata_path}",
        )
    except (OSError, json.JSONDecodeError, ValueError, TypeError, RuntimeError) as error:
        messagebox.showerror("임베딩 실패", str(error))
        raise


if __name__ == "__main__":
    main()