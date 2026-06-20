"""Ollama 本地后端。

需要先安装 Ollama (https://ollama.com) 并 pull 模型：
    ollama pull qwen2.5:7b-instruct
"""

from __future__ import annotations

from typing import Any

import httpx

from . import LLMBackend, Message


class OllamaBackend(LLMBackend):
    name = "ollama"

    def __init__(self, cfg: dict[str, Any]) -> None:
        self.host = str(cfg.get("host", "http://127.0.0.1:11434")).rstrip("/")
        self.model = str(cfg.get("model", "qwen2.5:7b-instruct"))
        self.writer_model = str(cfg.get("writer_model") or self.model)
        self.default_temperature = float(cfg.get("temperature", 0.85))
        self.num_ctx = int(cfg.get("num_ctx", 16384))
        self.timeout = float(cfg.get("timeout", 600))

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
            "stream": False,
            "options": {
                "temperature": temperature
                if temperature is not None
                else self.default_temperature,
                "num_ctx": self.num_ctx,
            },
        }
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens
        if stop:
            payload["options"]["stop"] = stop
        url = f"{self.host}/api/chat"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()
                content = data.get("message", {}).get("content", "").strip()
                usage_raw = data.get("prompt_eval_count", 0), data.get("eval_count", 0)
                usage = {
                    "prompt_tokens": int(usage_raw[0]),
                    "completion_tokens": int(usage_raw[1]),
                    "total_tokens": int(usage_raw[0]) + int(usage_raw[1]),
                    "cached_tokens": 0,
                }
                self.last_usage = usage
                return content, usage
        except httpx.ConnectError as e:
            raise RuntimeError(
                f"连不上 Ollama ({self.host})。请确认 Ollama 已启动 "
                f"(ollama serve) 或下载安装: https://ollama.com\n原始错误: {e}"
            ) from e

    def test(self) -> str:
        try:
            return self.chat(
                [Message("user", "用一个词回复：你好")],
                temperature=0.1,
                max_tokens=16,
            )
        except RuntimeError as e:
            return str(e)
