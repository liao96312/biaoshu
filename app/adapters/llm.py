from __future__ import annotations

import json
import urllib.request
from typing import Protocol

from app.config import settings


class LLMClient(Protocol):
    def complete_json(self, prompt: str, schema_name: str) -> dict:
        """Return structured JSON for an agent prompt."""


class DisabledLLMClient:
    name = "disabled"

    def complete_json(self, prompt: str, schema_name: str) -> dict:
        raise RuntimeError("LLM client is not configured")


class OpenAICompatibleClient:
    name = "openai_compatible"

    def __init__(self, base_url: str, api_key: str, model: str) -> None:
        if not api_key:
            raise ValueError("LLM API key is required")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    def complete_json(self, prompt: str, schema_name: str) -> dict:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": f"Return strict JSON for schema: {schema_name}."},
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
        }
        data = _post_json(
            f"{self.base_url}/chat/completions",
            payload,
            {"Authorization": f"Bearer {self.api_key}"},
        )
        content = data["choices"][0]["message"]["content"]
        return json.loads(content)


class AnthropicClient:
    name = "anthropic"

    def __init__(self, api_key: str, model: str) -> None:
        if not api_key:
            raise ValueError("LLM API key is required")
        self.api_key = api_key
        self.model = model

    def complete_json(self, prompt: str, schema_name: str) -> dict:
        payload = {
            "model": self.model,
            "max_tokens": 4096,
            "system": f"Return strict JSON for schema: {schema_name}.",
            "messages": [{"role": "user", "content": prompt}],
        }
        data = _post_json(
            "https://api.anthropic.com/v1/messages",
            payload,
            {
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
            },
        )
        text = "".join(block.get("text", "") for block in data.get("content", []))
        return json.loads(text)


def create_llm_client() -> LLMClient:
    provider = settings.llm_provider
    if provider in {"openai", "deepseek", "qwen", "openai_compatible"}:
        base_url = settings.llm_base_url or {
            "openai": "https://api.openai.com/v1",
            "deepseek": "https://api.deepseek.com/v1",
            "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        }.get(provider, "https://api.openai.com/v1")
        model = settings.llm_model or "gpt-4o"
        return OpenAICompatibleClient(base_url=base_url, api_key=settings.llm_api_key, model=model)
    if provider in {"anthropic", "claude"}:
        return AnthropicClient(api_key=settings.llm_api_key, model=settings.llm_model or "claude-3-5-sonnet-latest")
    return DisabledLLMClient()


def _post_json(url: str, payload: dict, headers: dict[str, str]) -> dict:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


llm_client = create_llm_client()
