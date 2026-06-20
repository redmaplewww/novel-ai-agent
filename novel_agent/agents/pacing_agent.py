"""节奏分析 Agent：给章节打分 + 全书节奏问题检测。"""

from __future__ import annotations

from typing import Any, Callable

from ..core.pacing import ChapterPacing, Pace, PacingData
from ..llm import LLMBackend
from .llm_helpers import call_json_with_usage

LogFn = Callable[..., None]


class PacingAgent:
    def __init__(self, backend: LLMBackend, *, log: LogFn | None = None) -> None:
        self.backend = backend
        self._log = log

    def analyze_chapter(
        self,
        chapter_id: str,
        title: str,
        content: str,
        outline_beat: str = "",
    ) -> ChapterPacing | None:
        """对单章打分。"""
        from ..prompts import PACING_SYSTEM, analyze_pacing_prompt

        turns = analyze_pacing_prompt(chapter_id, title, content, outline_beat)
        data, usage = call_json_with_usage(
            self.backend, PACING_SYSTEM, turns, temperature=0.3, max_tokens=500
        )
        if self._log:
            try:
                self._log(op="pacing", model="", usage=usage, chapter_id=chapter_id)
            except Exception:  # noqa: BLE001
                pass
        if not data:
            return None
        wc = len([c for c in content if c.strip()])
        try:
            pace = Pace(data.get("pace", "medium"))
        except ValueError:
            pace = Pace.medium
        return ChapterPacing(
            chapter_id=chapter_id,
            tension=int(data.get("tension", 5)),
            emotion=int(data.get("emotion", 5)),
            info_density=int(data.get("info_density", 5)),
            pace=pace,
            mood=str(data.get("mood", "")),
            cliffhanger=bool(data.get("cliffhanger", False)),
            word_count=wc,
            notes=str(data.get("notes", "")),
        )
