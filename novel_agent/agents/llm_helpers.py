"""LLM 调用的小工具：JSON 提取、消息构造。"""

from __future__ import annotations

import json
import re
from typing import Any

from ..llm import LLMBackend, Message


def to_messages(system: str, turns: list[tuple[str, str]]) -> list[Message]:
    msgs: list[Message] = []
    if system:
        msgs.append(Message("system", system))
    for role, content in turns:
        msgs.append(Message(role, content))
    return msgs


def call_llm(
    backend: LLMBackend, system: str, turns: list[tuple[str, str]], **kwargs: Any
) -> str:
    return backend.chat(to_messages(system, turns), **kwargs)


def call_llm_with_usage(
    backend: LLMBackend, system: str, turns: list[tuple[str, str]], **kwargs: Any
) -> tuple[str, dict[str, int]]:
    """调用 LLM 并返回 (文本, usage)。优先用 chat_with_usage。"""
    return backend.chat_with_usage(to_messages(system, turns), **kwargs)


def extract_json_block(text: str) -> Any:
    """从模型回复里抠出 JSON（支持裸 JSON 或 ```json ... ``` 包裹）。"""
    # 先尝试 ```json ... ```
    m = re.search(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", text, re.DOTALL)
    candidate = m.group(1) if m else text.strip()
    # 否则找第一个 { 到最后一个 }
    if not candidate.startswith(("{", "[")):
        start = candidate.find("{")
        if start == -1:
            start = candidate.find("[")
        if start != -1:
            end = max(candidate.rfind("}"), candidate.rfind("]"))
            candidate = candidate[start : end + 1]
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        # 宽松：去掉尾随逗号
        cleaned = re.sub(r",\s*([}\]])", r"\1", candidate)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return None


def call_json(
    backend: LLMBackend, system: str, turns: list[tuple[str, str]], **kwargs: Any
) -> Any:
    """调用 LLM 并解析为 JSON，解析失败返回 None。"""
    text = call_llm(backend, system, turns, **kwargs)
    return extract_json_block(text)


def call_json_with_usage(
    backend: LLMBackend, system: str, turns: list[tuple[str, str]], **kwargs: Any
) -> tuple[Any, dict[str, int]]:
    """调用 LLM 并解析为 JSON，同时返回 usage。"""
    text, usage = call_llm_with_usage(backend, system, turns, **kwargs)
    return extract_json_block(text), usage
