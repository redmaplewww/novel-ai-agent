"""审校 Agent：偏离大纲检测 + 一致性检查 + 修订。"""

from __future__ import annotations

from typing import Any, Callable

from ..llm import LLMBackend
from .llm_helpers import call_json, call_llm_with_usage, extract_json_block, to_messages

LogFn = Callable[..., None]


class ReviewerAgent:
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

    def _run_json(
        self,
        system: str,
        turns: list[tuple[str, str]],
        *,
        op: str,
        chapter_id: str = "",
        **kwargs: Any,
    ) -> Any:
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
        return extract_json_block(content)

    def _run_text(
        self,
        turns: list[tuple[str, str]],
        *,
        op: str,
        chapter_id: str = "",
        **kwargs: Any,
    ) -> str:
        content, usage = self.backend.chat_with_usage(to_messages("", turns), **kwargs)
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

    def review(
        self, context: str, content: str, chapter_plan: str = ""
    ) -> dict[str, Any] | None:
        from ..prompts import REVIEW_SYSTEM, review_chapter_prompt

        turns = review_chapter_prompt(context, content, chapter_plan)
        return self._run_json(REVIEW_SYSTEM, turns, op="review", temperature=0.4)

    def revise(self, content: str, review_text: str, chapter_id: str = "") -> str:
        from ..prompts import revise_chapter_prompt

        turns = revise_chapter_prompt(content, review_text)
        kwargs: dict[str, Any] = {"temperature": 0.8}
        if self.writer_model:
            kwargs["model"] = self.writer_model
        return self._run_text(turns, op="revise", chapter_id=chapter_id, **kwargs)
