from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GenerationConfig:
    """llama.cpp 기반 Qwen 답변 생성 설정."""

    # llama.cpp OpenAI 호환 Chat Completions endpoint
    base_url: str = "http://127.0.0.1:8080"
    chat_completions_path: str = "/v1/chat/completions"

    # llama.cpp 서버에서는 실제 모델 ID와 달라도 동작할 수 있으므로
    # 서버 설정에 맞춰 변경 가능
    model_name: str = "qwen"

    temperature: float = 0.1
    top_p: float = 0.9
    max_tokens: int = 512

    timeout_seconds: int = 180
    context_top_k: int = 5

    # 청크 하나가 지나치게 길 때 프롬프트 폭증 방지
    max_chars_per_context: int = 6000

    # 응답 마지막에 [근거 N] 형식 요구
    require_source_markers: bool = True

    def validate(self) -> None:
        if not self.base_url.strip():
            raise ValueError("base_url이 비어 있습니다.")

        if not self.chat_completions_path.startswith("/"):
            raise ValueError(
                "chat_completions_path는 '/'로 시작해야 합니다."
            )

        if not self.model_name.strip():
            raise ValueError("model_name이 비어 있습니다.")

        if self.temperature < 0:
            raise ValueError("temperature는 0 이상이어야 합니다.")

        if not 0 < self.top_p <= 1:
            raise ValueError("top_p는 0 초과 1 이하여야 합니다.")

        if self.max_tokens <= 0:
            raise ValueError("max_tokens는 1 이상이어야 합니다.")

        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds는 1 이상이어야 합니다.")

        if self.context_top_k <= 0:
            raise ValueError("context_top_k는 1 이상이어야 합니다.")

        if self.max_chars_per_context <= 0:
            raise ValueError(
                "max_chars_per_context는 1 이상이어야 합니다."
            )

    @property
    def chat_completions_url(self) -> str:
        return (
            self.base_url.rstrip("/")
            + self.chat_completions_path
        )


DEFAULT_GENERATION_CONFIG = GenerationConfig()
