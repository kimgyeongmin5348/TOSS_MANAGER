"""NVIDIA NIM Qwen adapter for Porto's provider-neutral messages."""

from __future__ import annotations

import time
from typing import Any

import requests

from toss_manager.config import NvidiaLLMSettings


class NvidiaLLMError(RuntimeError):
    pass


class NvidiaQwenClient:
    def __init__(self, settings: NvidiaLLMSettings | None = None, *, timeout: float = 60) -> None:
        self.settings = settings or NvidiaLLMSettings.from_env()
        self.timeout = timeout
        self.session = requests.Session()

    @property
    def configured(self) -> bool:
        return bool(self.settings.api_key)

    def complete(self, messages: list[dict[str, str]]) -> str:
        if not self.configured:
            raise NvidiaLLMError("NVIDIA_API_KEY가 설정되지 않았습니다.")
        response = self._post(messages)
        if response.status_code == 429:
            retry_after = min(float(response.headers.get("Retry-After", "1")), 10)
            time.sleep(max(retry_after, 0))
            response = self._post(messages)
        if not response.ok:
            request_id = response.headers.get("X-Request-Id", "unknown")
            try:
                detail: Any = response.json()
            except ValueError:
                detail = response.text[:300]
            raise NvidiaLLMError(
                f"NVIDIA Qwen API {response.status_code} (request_id={request_id}): {detail}"
            )
        try:
            content = response.json()["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise NvidiaLLMError("NVIDIA Qwen 응답 형식이 올바르지 않습니다.") from exc
        if not str(content).strip():
            raise NvidiaLLMError("NVIDIA Qwen이 빈 답변을 반환했습니다.")
        return str(content).strip()

    def _post(self, messages: list[dict[str, str]]) -> requests.Response:
        try:
            return self.session.post(
                f"{self.settings.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.settings.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.settings.model,
                    "messages": messages,
                    "temperature": 0.2,
                    "top_p": 0.7,
                    "max_tokens": 1200,
                    "stream": False,
                },
                timeout=self.timeout,
            )
        except requests.Timeout as exc:
            raise NvidiaLLMError("NVIDIA Qwen 응답 시간이 초과되었습니다.") from exc
        except requests.RequestException as exc:
            raise NvidiaLLMError("NVIDIA Qwen API에 연결하지 못했습니다.") from exc
