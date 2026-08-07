from __future__ import annotations

import json
from pathlib import Path
from typing import Any
import numpy as np
from .config import DEFAULT_FORMAT_PRIORITY, OUTPUT_ROOT, SUPPORTED_FORMATS
from .models import CorpusItem, LoadedCorpus

class CorpusLoadError(RuntimeError):
    pass

def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise CorpusLoadError(f"JSON 파일을 찾을 수 없습니다: {path}")
    try:
        with path.open('r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        raise CorpusLoadError(f"JSON 형식 오류: {path} line={exc.lineno} col={exc.colno}") from exc
    if not isinstance(data, dict):
        raise CorpusLoadError(f"JSON 최상위 값은 객체여야 합니다: {path}")
    return data

def _load_embeddings(path: Path) -> np.ndarray:
    if not path.is_file():
        raise CorpusLoadError(f"임베딩 파일을 찾을 수 없습니다: {path}")
    try:
        arr = np.load(path, allow_pickle=False)
    except (OSError, ValueError) as exc:
        raise CorpusLoadError(f"임베딩 파일을 읽지 못했습니다: {path}") from exc
    if arr.ndim != 2 or arr.shape[0] == 0 or arr.shape[1] == 0:
        raise CorpusLoadError(f"올바르지 않은 임베딩 shape: {arr.shape}")
    if not np.isfinite(arr).all():
        raise CorpusLoadError(f"임베딩에 NaN 또는 Infinity가 있습니다: {path}")
    return arr.astype(np.float32, copy=False)

def _opt(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None

def _build_item(raw: dict[str, Any], expected_index: int) -> CorpusItem:
    if raw.get('vector_index') != expected_index:
        raise CorpusLoadError(f"vector_index 불일치: expected={expected_index}, actual={raw.get('vector_index')}")
    chunk_id = raw.get('chunk_id')
    content = raw.get('content')
    search_text = raw.get('search_text')
    if not isinstance(chunk_id, str) or not chunk_id.strip():
        raise CorpusLoadError(f"chunk_id 오류: index={expected_index}")
    if not isinstance(content, str) or not content.strip():
        raise CorpusLoadError(f"content가 비어 있습니다: {chunk_id}")
    if not isinstance(search_text, str) or not search_text.strip():
        raise CorpusLoadError(f"search_text가 비어 있습니다: {chunk_id}")
    section_path = raw.get('section_path', [])
    if not isinstance(section_path, list):
        raise CorpusLoadError(f"section_path가 배열이 아닙니다: {chunk_id}")
    source = raw.get('source')
    if source is not None and not isinstance(source, dict):
        source = {'raw_value': source}
    chunk_order = raw.get('chunk_order')
    if chunk_order is not None and not isinstance(chunk_order, int):
        try:
            chunk_order = int(chunk_order)
        except (TypeError, ValueError):
            chunk_order = None
    return CorpusItem(
        vector_index=expected_index,
        chunk_id=chunk_id.strip(),
        document_id=_opt(raw.get('document_id')),
        announcement_id=_opt(raw.get('announcement_id')),
        chunk_order=chunk_order,
        chunk_type=_opt(raw.get('chunk_type')),
        section_path=[str(v).strip() for v in section_path if str(v).strip()],
        title=_opt(raw.get('title')),
        content=content.strip(),
        search_text=search_text.strip(),
        source=source,
        raw_metadata=dict(raw),
    )

def resolve_embedding_directory(announcement_directory: str, *, document_format: str | None = None, outputs_root: str | Path = OUTPUT_ROOT, format_priority: tuple[str, ...] = DEFAULT_FORMAT_PRIORITY) -> tuple[Path, str]:
    root = Path(outputs_root).expanduser().resolve()
    ann_root = root / announcement_directory
    if not ann_root.is_dir():
        raise CorpusLoadError(f"공고 출력 폴더를 찾을 수 없습니다: {ann_root}")
    if document_format is not None:
        fmt = document_format.lower()
        if fmt not in SUPPORTED_FORMATS:
            raise CorpusLoadError(f"지원하지 않는 문서 형식입니다: {document_format}")
        candidates = (fmt,)
    else:
        candidates = format_priority
    for fmt in candidates:
        d = ann_root / '05_embeddings' / fmt
        if (d/'embeddings.npy').is_file() and (d/'metadata.json').is_file():
            return d, fmt
    raise CorpusLoadError(f"사용 가능한 임베딩 결과를 찾지 못했습니다: {announcement_directory}, {list(candidates)}")

def load_corpus(announcement_directory: str, *, document_format: str | None = None, outputs_root: str | Path = OUTPUT_ROOT) -> LoadedCorpus:
    emb_dir, fmt = resolve_embedding_directory(announcement_directory, document_format=document_format, outputs_root=outputs_root)
    emb_path = emb_dir/'embeddings.npy'
    meta_path = emb_dir/'metadata.json'
    embeddings = _load_embeddings(emb_path)
    metadata = _read_json(meta_path)
    raw_items = metadata.get('items')
    if not isinstance(raw_items, list):
        raise CorpusLoadError(f"metadata.json의 items는 배열이어야 합니다: {meta_path}")
    if embeddings.shape[0] != len(raw_items):
        raise CorpusLoadError(f"벡터 수와 metadata 수 불일치: {embeddings.shape[0]} != {len(raw_items)}")
    items=[]
    seen=set()
    for i, raw in enumerate(raw_items):
        if not isinstance(raw, dict):
            raise CorpusLoadError(f"metadata.items[{i}]는 객체여야 합니다.")
        item = _build_item(raw, i)
        if item.chunk_id in seen:
            raise CorpusLoadError(f"중복 chunk_id: {item.chunk_id}")
        seen.add(item.chunk_id)
        items.append(item)
    model_info = metadata.get('model', {})
    if not isinstance(model_info, dict):
        model_info = {}
    recorded_dim = model_info.get('dimension')
    if isinstance(recorded_dim, int) and recorded_dim != embeddings.shape[1]:
        raise CorpusLoadError(f"임베딩 차원 불일치: recorded={recorded_dim}, actual={embeddings.shape[1]}")
    return LoadedCorpus(announcement_directory, fmt, emb_path, meta_path, embeddings, items, _opt(model_info.get('name')), int(embeddings.shape[1]), bool(model_info.get('normalized', False)))
