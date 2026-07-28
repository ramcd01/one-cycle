"""문서 근거 중심 RAG 파이프라인."""

__all__ = ["RagPipeline", "RagResponse"]


def __getattr__(name: str):
    if name == "RagPipeline":
        from .pipeline import RagPipeline
        return RagPipeline
    if name == "RagResponse":
        from .schemas import RagResponse
        return RagResponse
    raise AttributeError(name)
