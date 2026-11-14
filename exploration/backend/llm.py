"""OpenAI-compatible JSON extraction client.

The client records token usage only when the response includes it. It does not
invent token counts. Callers still have to ground every quotation.
"""

from __future__ import annotations

import json
from typing import Any

import httpx

from exploration.backend.config import HTTP_TIMEOUT_SECONDS, llm_api_key, llm_base_url, llm_model


class LLMNotConfigured(RuntimeError):
    pass


def strip_json_fence(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1]
        if cleaned.endswith("```"):
            cleaned = cleaned[: cleaned.rfind("```")]
    return cleaned.strip()


class OpenAICompatibleClient:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float = 15.0,
    ):
        self.api_key = api_key if api_key is not None else llm_api_key()
        self.base_url = (base_url or llm_base_url()).rstrip("/")
        self.model = model or llm_model()
        self.timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def complete_json(self, system: str, user: str) -> tuple[dict[str, Any], dict[str, Any]]:
        if not self.api_key:
            raise LLMNotConfigured("LLM_API_KEY and OPENAI_API_KEY are missing")
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "temperature": 0,
            "max_tokens": 300,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        timeout = httpx.Timeout(self.timeout, connect=10.0)
        with httpx.Client(timeout=timeout) as client:
            response = client.post(
                url,
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json=payload,
            )
            response.raise_for_status()
            body = response.json()
        content = body["choices"][0]["message"]["content"]
        parsed = json.loads(strip_json_fence(content))
        usage = body.get("usage") if isinstance(body.get("usage"), dict) else {}
        return parsed, usage
