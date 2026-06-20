"""LLM 后端抽象层。

所有后端实现统一接口 `LLMBackend`，对外只暴露 `chat()`。
"""

from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import Any

from ..config import Config


@dataclass
class Message:
    role: str  # system | user | assistant
    content: str

    def to_dict(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content}


class LLMBackend(abc.ABC):
    """所有后端的统一接口。"""

    name: str = "base"
    # 写作章节时使用的更强/更长模型（可选）；默认与 chat 模型一致
    writer_model: str | None = None
    # 上次调用的 usage（token 数），供上层记账；None 表示未取到
    last_usage: dict[str, int] | None = None

    @abc.abstractmethod
    def chat(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        temperature: float = 0.85,
        max_tokens: int | None = None,
        stop: list[str] | None = None,
        **kwargs: Any,
    ) -> str:
        """同步对话，返回助手回复的纯文本。"""
        raise NotImplementedError

    def chat_with_usage(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        temperature: float = 0.85,
        max_tokens: int | None = None,
        stop: list[str] | None = None,
        **kwargs: Any,
    ) -> tuple[str, dict[str, int]]:
        """同步对话，返回 (文本, usage)。

        usage 形如 {"prompt_tokens":100,"completion_tokens":50,"total_tokens":150}。
        默认实现复用 chat() 并返回空 usage；具体子类应覆写以拿到真实 usage。
        """
        text = self.chat(
            messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            stop=stop,
            **kwargs,
        )
        return text, {}

    def test(self) -> str:
        """连通性测试，返回一句模型回复。"""
        return self.chat(
            [Message("user", "用一句话介绍你自己。")],
            temperature=0.3,
            max_tokens=64,
        )


def build_backend(config: Config) -> LLMBackend:
    """根据 config.backend 选择具体后端。"""
    backend = config.backend
    if backend == "openai":
        from .openai_api import OpenAIBackend

        return OpenAIBackend(config.openai)
    if backend == "ollama":
        from .ollama import OllamaBackend

        return OllamaBackend(config.ollama)
    raise ValueError(f"未知 backend: {backend}（可选: openai / ollama）")
