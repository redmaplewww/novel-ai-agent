"""OpenAI 兼容后端。

支持 OpenAI、DeepSeek、硅基流动(SiliconFlow)、OpenRouter、Moonshot、
本地 vLLM / LM Studio 等任何遵循 OpenAI Chat Completions 协议的服务。
"""

from __future__ import annotations

import os
from typing import Any

import httpx

from . import LLMBackend, Message


class OpenAIBackend(LLMBackend):
    name = "openai"

    def __init__(self, cfg: dict[str, Any]) -> None:
        self.api_key = (
            str(cfg.get("api_key", "")).strip()
            or os.getenv("NOVEL_API_KEY", "")
            or os.getenv("OPENAI_API_KEY", "")
        ).strip()
        if not self.api_key:
            raise RuntimeError(
                "未配置 API key。请在 .env 设置 NOVEL_API_KEY，或在 config.yaml 的 "
                "openai.api_key 写入，或设置 OPENAI_API_KEY 环境变量。"
            )
        self.base_url = str(cfg.get("base_url", "https://api.openai.com/v1")).rstrip(
            "/"
        )
        self.model = str(cfg.get("model", "gpt-4o-mini"))
        self.writer_model = str(cfg.get("writer_model") or self.model)
        self.default_temperature = float(cfg.get("temperature", 0.85))
        self.default_max_tokens = int(cfg.get("max_tokens", 4096))
        self.timeout = float(cfg.get("timeout", 120))

    def chat(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        stop: list[str] | None = None,
        **_: Any,
    ) -> str:
        return self.chat_with_usage(
            messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            stop=stop,
        )[0]

    def chat_with_usage(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        stop: list[str] | None = None,
        **_: Any,
    ) -> tuple[str, dict[str, int]]:
        payload: dict[str, Any] = {
            "model": model or self.model,
            "messages": [m.to_dict() for m in messages],
            "temperature": temperature
            if temperature is not None
            else self.default_temperature,
            "max_tokens": max_tokens or self.default_max_tokens,
            "stream": False,
        }
        if stop:
            payload["stop"] = stop
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        url = f"{self.base_url}/chat/completions"
        last_err: Exception | None = None
        for attempt in range(3):
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    resp = client.post(url, json=payload, headers=headers)
                    resp.raise_for_status()
                    data = resp.json()
                    content = data["choices"][0]["message"]["content"].strip()
                    usage_raw = data.get("usage") or {}
                    usage = {
                        "prompt_tokens": int(usage_raw.get("prompt_tokens", 0)),
                        "completion_tokens": int(usage_raw.get("completion_tokens", 0)),
                        "total_tokens": int(usage_raw.get("total_tokens", 0)),
                        "cached_tokens": int(
                            usage_raw.get("prompt_cache_hit_tokens", 0)
                            or usage_raw.get("prompt_tokens_details", {}).get(
                                "cached_tokens", 0
                            )
                            or 0
                        ),
                    }
                    self.last_usage = usage
                    return content, usage
            except Exception as e:  # noqa: BLE001
                last_err = e
                if attempt < 2:
                    import time

                    time.sleep(0.5 * (attempt + 1))
        raise RuntimeError(f"OpenAI 后端调用失败（已重试 3 次）: {last_err}")
