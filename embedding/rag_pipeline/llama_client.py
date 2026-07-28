from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any


class LlamaServerError(RuntimeError):
    pass


class JsonResponseError(RuntimeError):
    pass


class LlamaClient:
    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
        timeout_seconds: int = 600,
    ) -> None:
        self.base_url = (
            base_url
            or os.getenv("LLAMA_BASE_URL", "http://127.0.0.1:8080")
        ).rstrip("/")
        self.model = (model or os.getenv("LLAMA_MODEL", "")).strip()
        self.api_key = (
            api_key or os.getenv("LLAMA_API_KEY", "no-key")
        ).strip()
        self.timeout_seconds = timeout_seconds

    def _http_json(
        self,
        method: str,
        url: str,
        payload: dict[str, Any] | None = None,
        timeout: int | None = None,
    ) -> dict[str, Any]:
        headers = {"Accept": "application/json"}
        data: bytes | None = None

        if payload is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")

        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        request = urllib.request.Request(
            url=url,
            data=data,
            headers=headers,
            method=method,
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=timeout or self.timeout_seconds,
            ) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as error:
            error_body = error.read().decode("utf-8", errors="replace")
            raise LlamaServerError(
                f"llama.cpp HTTP {error.code}: {error_body}"
            ) from error
        except urllib.error.URLError as error:
            raise LlamaServerError(
                f"llama.cpp 서버 연결 실패: {error}"
            ) from error

        try:
            parsed = json.loads(body)
        except json.JSONDecodeError as error:
            raise LlamaServerError(
                f"llama.cpp 응답 JSON 파싱 실패: {body[:500]}"
            ) from error

        if not isinstance(parsed, dict):
            raise LlamaServerError("llama.cpp 응답 최상위가 객체가 아닙니다.")

        return parsed

    def check(self) -> None:
        result = self._http_json(
            "GET",
            f"{self.base_url}/health",
            timeout=30,
        )
        if result.get("status") not in {"ok", "no slot available"}:
            raise LlamaServerError(f"llama.cpp 상태 이상: {result}")

    def get_model_id(self) -> str:
        if self.model:
            return self.model

        result = self._http_json(
            "GET",
            f"{self.base_url}/v1/models",
            timeout=30,
        )
        data = result.get("data")
        if not isinstance(data, list) or not data:
            raise LlamaServerError("/v1/models에서 모델을 찾지 못했습니다.")

        model_id = data[0].get("id")
        if not isinstance(model_id, str) or not model_id.strip():
            raise LlamaServerError("유효한 모델 ID가 없습니다.")

        self.model = model_id.strip()
        return self.model

    def chat(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
        max_tokens: int = 1200,
    ) -> str:
        model_id = self.get_model_id()
        payload = {
            "model": model_id,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        result = self._http_json(
            "POST",
            f"{self.base_url}/v1/chat/completions",
            payload=payload,
        )
        choices = result.get("choices")
        if not isinstance(choices, list) or not choices:
            raise LlamaServerError("답변 choices가 없습니다.")

        content = choices[0].get("message", {}).get("content")
        if not isinstance(content, str) or not content.strip():
            raise LlamaServerError("답변 content가 비어 있습니다.")

        return content.strip()

    def chat_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
        max_tokens: int = 1600,
    ) -> dict[str, Any]:
        text = self.chat(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return extract_json_object(text)


def extract_json_object(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start < 0 or end <= start:
            raise JsonResponseError(
                f"JSON 객체를 찾을 수 없습니다: {text[:500]}"
            )
        try:
            value = json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError as error:
            raise JsonResponseError(
                f"JSON 파싱 실패: {cleaned[start:end + 1][:500]}"
            ) from error

    if not isinstance(value, dict):
        raise JsonResponseError("LLM JSON 응답 최상위가 객체가 아닙니다.")

    return value
