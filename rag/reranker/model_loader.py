from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import torch


class RerankerLoadError(RuntimeError):
    """Reranker 모델을 로드하지 못했을 때 발생한다."""


@dataclass(frozen=True)
class RerankerRuntimeInfo:
    """Reranker 실행 환경 정보."""

    model_name: str
    device: str
    device_name: str
    use_fp16: bool

    cuda_available: bool
    cuda_version: str | None
    torch_version: str

    gpu_memory_gb: float | None


@dataclass(frozen=True)
class LoadedRerankerModel:
    """로드된 Reranker 모델과 실행 환경."""

    model: Any
    runtime: RerankerRuntimeInfo


def _get_gpu_memory_gb(device_index: int) -> float | None:
    if not torch.cuda.is_available():
        return None

    properties = torch.cuda.get_device_properties(device_index)
    return round(properties.total_memory / (1024 ** 3), 2)


def get_reranker_runtime_info(
    *,
    model_name: str,
    use_fp16: bool,
    require_cuda: bool,
    device_index: int,
) -> RerankerRuntimeInfo:
    cuda_available = torch.cuda.is_available()

    if require_cuda and not cuda_available:
        raise RerankerLoadError(
            "CUDA를 사용할 수 없습니다.\n"
            "현재 프로젝트는 AWS GPU Reranker 실행을 전제로 합니다.\n"
            "다음 명령으로 확인하세요.\n"
            "python -c \"import torch; "
            "print(torch.cuda.is_available())\""
        )

    if cuda_available:
        device = f"cuda:{device_index}"
        device_name = torch.cuda.get_device_name(device_index)
        gpu_memory_gb = _get_gpu_memory_gb(device_index)
    else:
        device = "cpu"
        device_name = "CPU"
        gpu_memory_gb = None

    return RerankerRuntimeInfo(
        model_name=model_name,
        device=device,
        device_name=device_name,
        use_fp16=bool(use_fp16 and cuda_available),
        cuda_available=cuda_available,
        cuda_version=torch.version.cuda,
        torch_version=torch.__version__,
        gpu_memory_gb=gpu_memory_gb,
    )


def load_reranker_model(
    *,
    model_name: str = "BAAI/bge-reranker-v2-m3",
    use_fp16: bool = True,
    require_cuda: bool = True,
    device_index: int = 0,
) -> LoadedRerankerModel:
    """
    FlagEmbedding의 FlagReranker를 로드한다.

    첫 실행에서는 Hugging Face에서 모델을 다운로드하고,
    이후 실행에서는 로컬 캐시를 재사용한다.
    """
    runtime = get_reranker_runtime_info(
        model_name=model_name,
        use_fp16=use_fp16,
        require_cuda=require_cuda,
        device_index=device_index,
    )

    try:
        from FlagEmbedding import FlagReranker
    except Exception as exc:
        raise RerankerLoadError(
            "FlagReranker import에 실패했습니다.\n"
            f"실제 오류: {type(exc).__name__}: {exc}\n"
            "현재 Python 환경에 FlagEmbedding이 설치되어 있는지 "
            "확인하세요.\n"
            "python -m pip install FlagEmbedding"
        ) from exc

    print()
    print("=" * 70)
    print("BGE Reranker 모델 로드")
    print("=" * 70)
    print(f"모델          : {runtime.model_name}")
    print(f"장치          : {runtime.device}")
    print(f"장치 이름     : {runtime.device_name}")
    print(f"CUDA 사용     : {runtime.cuda_available}")
    print(f"CUDA 버전     : {runtime.cuda_version}")
    print(f"PyTorch 버전  : {runtime.torch_version}")
    print(f"FP16 사용     : {runtime.use_fp16}")

    if runtime.gpu_memory_gb is not None:
        print(f"GPU 메모리    : {runtime.gpu_memory_gb} GB")

    try:
        # 일부 FlagEmbedding 버전은 devices 인자를 지원하지 않는다.
        # 우선 명시적으로 전달하고, TypeError 발생 시 제거하여 재시도한다.
        try:
            model = FlagReranker(
                model_name,
                use_fp16=runtime.use_fp16,
                devices=runtime.device,
            )
        except TypeError:
            model = FlagReranker(
                model_name,
                use_fp16=runtime.use_fp16,
            )
    except Exception as exc:
        raise RerankerLoadError(
            "Reranker 모델 로드에 실패했습니다.\n"
            f"모델: {model_name}\n"
            f"장치: {runtime.device}\n"
            f"실제 오류: {type(exc).__name__}: {exc}"
        ) from exc

    return LoadedRerankerModel(
        model=model,
        runtime=runtime,
    )


def print_reranker_gpu_memory(prefix: str) -> None:
    if not torch.cuda.is_available():
        return

    allocated = torch.cuda.memory_allocated() / (1024 ** 3)
    reserved = torch.cuda.memory_reserved() / (1024 ** 3)

    print(
        f"{prefix} GPU 메모리: "
        f"allocated={allocated:.2f} GB, "
        f"reserved={reserved:.2f} GB"
    )


def clear_reranker_cuda_cache() -> None:
    """사용하지 않는 CUDA 캐시를 정리한다."""

    if torch.cuda.is_available():
        torch.cuda.empty_cache()
