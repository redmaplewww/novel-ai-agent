"""Prompt 模板：所有 LLM 提示词集中管理。"""

from .planner import (
    PLAN_SYSTEM,
    premise_prompt,
    expand_outline_prompt,
    chapter_plan_prompt,
    bible_from_synopsis_prompt,
)
from .writer import WRITE_SYSTEM, write_chapter_prompt, summarize_chapter_prompt
from .reviewer import REVIEW_SYSTEM, review_chapter_prompt, revise_chapter_prompt
from .tracker import TRACK_SYSTEM, extract_state_prompt
from .kb import (
    KB_SYSTEM,
    worldbuild_prompt,
    weave_threads_prompt,
    audit_timeline_prompt,
    place_ideas_prompt,
)
from .pacing import PACING_SYSTEM, analyze_pacing_prompt
from .rewrite import REWRITE_SYSTEM, rewrite_passage_prompt
from .style import STYLE_SYSTEM, extract_style_prompt, check_drift_prompt

__all__ = [
    "PLAN_SYSTEM",
    "premise_prompt",
    "expand_outline_prompt",
    "chapter_plan_prompt",
    "bible_from_synopsis_prompt",
    "WRITE_SYSTEM",
    "write_chapter_prompt",
    "summarize_chapter_prompt",
    "REVIEW_SYSTEM",
    "review_chapter_prompt",
    "revise_chapter_prompt",
    "TRACK_SYSTEM",
    "extract_state_prompt",
    "KB_SYSTEM",
    "worldbuild_prompt",
    "weave_threads_prompt",
    "audit_timeline_prompt",
    "place_ideas_prompt",
    "PACING_SYSTEM",
    "analyze_pacing_prompt",
    "REWRITE_SYSTEM",
    "rewrite_passage_prompt",
]
