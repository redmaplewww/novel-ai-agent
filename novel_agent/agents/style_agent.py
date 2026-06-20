"""文风分析 Agent：提取文风指纹 + 检测漂移。纯 LLM 分析。"""

from __future__ import annotations

from typing import Any, Callable

from ..core.style import StyleData
from ..llm import LLMBackend
from .llm_helpers import call_json_with_usage

LogFn = Callable[..., None]


class StyleAgent:
    def __init__(self, backend: LLMBackend, *, log: LogFn | None = None) -> None:
        self.backend = backend
        self._log = log

    def extract_style(
        self,
        samples: str,
        known_characters: list[str],
        *,
        chapter_id: str = "",
    ) -> dict[str, Any] | None:
        """从正文样本提取文风指纹。"""
        from ..prompts import STYLE_SYSTEM, extract_style_prompt

        turns = extract_style_prompt(samples, known_characters)
        data, usage = call_json_with_usage(
            self.backend, STYLE_SYSTEM, turns, temperature=0.4, max_tokens=1500
        )
        if self._log:
            try:
                self._log(op="style", model="", usage=usage, chapter_id=chapter_id)
            except Exception:  # noqa: BLE001
                pass
        return data

    def check_drift(
        self,
        content: str,
        style_data: StyleData,
        chapter_id: str,
    ) -> dict[str, Any] | None:
        """检测某章是否偏离文风。"""
        from ..prompts import STYLE_SYSTEM, check_drift_prompt

        voices = "\n".join(
            f"• {k}：{v}" for k, v in style_data.character_voices.items()
        )
        turns = check_drift_prompt(
            content, style_data.prose_fingerprint, voices, chapter_id
        )
        data, usage = call_json_with_usage(
            self.backend, STYLE_SYSTEM, turns, temperature=0.3, max_tokens=1500
        )
        if self._log:
            try:
                self._log(
                    op="style_check", model="", usage=usage, chapter_id=chapter_id
                )
            except Exception:  # noqa: BLE001
                pass
        return data
