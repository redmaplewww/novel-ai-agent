"""规划 Agent：主线 → 卷纲 → 详细章节计划 → 设定集。"""

from __future__ import annotations

from typing import Any, Callable

from ..llm import LLMBackend
from .llm_helpers import call_llm_with_usage, extract_json_block

LogFn = Callable[..., None]


class PlannerAgent:
    def __init__(self, backend: LLMBackend, *, log: LogFn | None = None) -> None:
        self.backend = backend
        self._log = log

    def _run_json(
        self,
        system: str,
        turns: list[tuple[str, str]],
        *,
        op: str = "plan",
        **kwargs: Any,
    ) -> Any:
        content, usage = call_llm_with_usage(self.backend, system, turns, **kwargs)
        if self._log:
            try:
                self._log(op=op, model=kwargs.get("model") or "", usage=usage)
            except Exception:  # noqa: BLE001
                pass
        return extract_json_block(content)

    def generate_premise_and_outline(
        self, synopsis: str, genre: str, style: str, chapter_count: int
    ) -> dict[str, Any] | None:
        from ..prompts import PLAN_SYSTEM, premise_prompt

        turns = premise_prompt(synopsis, genre, style, chapter_count)
        return self._run_json(PLAN_SYSTEM, turns, op="plan", temperature=0.8)

    def expand_volume(
        self,
        volume_title: str,
        volume_summary: str,
        rough_beats: list[str],
        chapter_count: int,
    ) -> dict[str, Any] | None:
        from ..prompts import PLAN_SYSTEM, expand_outline_prompt

        turns = expand_outline_prompt(
            volume_title, volume_summary, rough_beats, chapter_count
        )
        return self._run_json(PLAN_SYSTEM, turns, op="plan", temperature=0.8)

    def plan_single_chapter(
        self, context: str, hint: str = ""
    ) -> dict[str, Any] | None:
        from ..prompts import PLAN_SYSTEM, chapter_plan_prompt

        turns = chapter_plan_prompt(context, hint)
        return self._run_json(PLAN_SYSTEM, turns, op="plan", temperature=0.75)

    def generate_bible(self, project_meta_text: str) -> dict[str, Any] | None:
        from ..prompts import PLAN_SYSTEM, bible_from_synopsis_prompt

        turns = bible_from_synopsis_prompt(project_meta_text)
        return self._run_json(PLAN_SYSTEM, turns, op="plan", temperature=0.8)
