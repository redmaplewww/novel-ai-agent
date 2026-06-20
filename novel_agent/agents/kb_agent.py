"""KBAgent —— 知识库的智能操作 Agent。

封装四大能力的 LLM 调用：
  - build_world       : 世界观搭建
  - weave_threads     : 故事线串联
  - audit_timeline    : 时间线校核
  - place_ideas       : idea 安插建议
"""

from __future__ import annotations

from typing import Any

from ..llm import LLMBackend
from .llm_helpers import call_json


class KBAgent:
    def __init__(self, backend: LLMBackend) -> None:
        self.backend = backend

    # ---- 世界观搭建 ----
    def build_world(self, project_meta: str, focus: str = "") -> dict[str, Any] | None:
        from ..prompts import KB_SYSTEM, worldbuild_prompt

        turns = worldbuild_prompt(project_meta, focus)
        return call_json(
            self.backend, KB_SYSTEM, turns, temperature=0.8, max_tokens=3000
        )

    # ---- 故事线串联 ----
    def weave_threads(
        self,
        outline_text: str,
        summaries_text: str,
        ideas_text: str,
        existing_threads: str,
        target_chapters: int = 5,
    ) -> dict[str, Any] | None:
        from ..prompts import KB_SYSTEM, weave_threads_prompt

        turns = weave_threads_prompt(
            outline_text, summaries_text, ideas_text, existing_threads, target_chapters
        )
        return call_json(
            self.backend, KB_SYSTEM, turns, temperature=0.75, max_tokens=3000
        )

    # ---- 时间线校核 ----
    def audit_timeline(
        self, timeline_text: str, facts_text: str
    ) -> dict[str, Any] | None:
        from ..prompts import KB_SYSTEM, audit_timeline_prompt

        turns = audit_timeline_prompt(timeline_text, facts_text)
        return call_json(
            self.backend, KB_SYSTEM, turns, temperature=0.3, max_tokens=2500
        )

    # ---- idea 安插建议 ----
    def place_ideas(self, ideas_text: str, outline_text: str) -> dict[str, Any] | None:
        from ..prompts import KB_SYSTEM, place_ideas_prompt

        turns = place_ideas_prompt(ideas_text, outline_text)
        return call_json(
            self.backend, KB_SYSTEM, turns, temperature=0.5, max_tokens=2000
        )
