"""局部重写 Agent：重写选中的段落片段，自动归档旧版。"""

from __future__ import annotations

from typing import Any, Callable

from ..llm import LLMBackend
from .llm_helpers import call_llm_with_usage

LogFn = Callable[..., None]


class RewriteAgent:
    def __init__(
        self,
        backend: LLMBackend,
        writer_model: str | None = None,
        *,
        log: LogFn | None = None,
    ) -> None:
        self.backend = backend
        self.writer_model = writer_model
        self._log = log

    def rewrite_passage(
        self,
        passage: str,
        context_before: str,
        context_after: str,
        instruction: str,
        *,
        chapter_id: str = "",
        style_fingerprint: str = "",
    ) -> str:
        """重写片段，返回重写后的文本。"""
        from ..prompts import REWRITE_SYSTEM, rewrite_passage_prompt

        turns = rewrite_passage_prompt(
            passage,
            context_before,
            context_after,
            instruction,
            style_fingerprint=style_fingerprint,
        )
        kwargs: dict[str, Any] = {"temperature": 0.85, "max_tokens": 2048}
        if self.writer_model:
            kwargs["model"] = self.writer_model
        text, usage = call_llm_with_usage(self.backend, REWRITE_SYSTEM, turns, **kwargs)
        if self._log:
            try:
                self._log(
                    op="rewrite",
                    model=self.writer_model or "",
                    usage=usage,
                    chapter_id=chapter_id,
                )
            except Exception:  # noqa: BLE001
                pass
        # 清理：去掉可能的多余空行和引号包裹
        text = text.strip().strip('"').strip("「」").strip("“”").strip()
        return text
