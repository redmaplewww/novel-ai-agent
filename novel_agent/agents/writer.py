"""写作 Agent：根据上下文写章节正文 + 生成摘要。"""

from __future__ import annotations

from typing import Any, Callable

from ..llm import LLMBackend
from .llm_helpers import call_llm_with_usage


# 记账回调类型：(op, model, usage, chapter_id) -> None
LogFn = Callable[..., None]


class WriterAgent:
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

    def _run(
        self,
        system: str,
        turns: list[tuple[str, str]],
        *,
        op: str,
        chapter_id: str = "",
        **kwargs: Any,
    ) -> str:
        content, usage = call_llm_with_usage(self.backend, system, turns, **kwargs)
        if self._log:
            try:
                self._log(
                    op=op,
                    model=kwargs.get("model") or "",
                    usage=usage,
                    chapter_id=chapter_id,
                )
            except Exception:  # noqa: BLE001
                pass
        return content

    def write_chapter(
        self, context: str, word_target: int, chapter_id: str = ""
    ) -> str:
        from ..prompts import WRITE_SYSTEM, write_chapter_prompt

        turns = write_chapter_prompt(context, word_target)
        kwargs: dict[str, Any] = {"temperature": 0.85}
        if self.writer_model:
            kwargs["model"] = self.writer_model
        return self._run(
            WRITE_SYSTEM, turns, op="write", chapter_id=chapter_id, **kwargs
        )

    def summarize(self, chapter_id: str, title: str, content: str) -> str:
        from ..prompts import summarize_chapter_prompt

        turns = summarize_chapter_prompt(chapter_id, title, content)
        return self._run(
            "",
            turns,
            op="summarize",
            chapter_id=chapter_id,
            temperature=0.3,
            max_tokens=600,
        )
