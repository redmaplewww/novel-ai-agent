"""核心数据模型与项目持久化。

项目结构（一个项目 = projects/<name>/ 下的若干 JSON）：
    project.json   —— 项目元信息（书名/类型/简介/世界观）
    bible.json     —— 设定集（人物/地点/物品/势力/设定）
    outline.json   —— 大纲树（卷 → 章，每章有 beat 与 status）
    chapters/*.md  —— 已写好的章节正文
    chapters/summaries.json —— 每章摘要（供记忆系统使用）
"""

from __future__ import annotations

from .project import Project, create_project, list_projects
from .bible import Bible, Character, Location, Faction, Item, Lore
from .outline import Outline, Volume, ChapterPlan, ChapterStatus
from .chapter import Chapter, ChapterStore, ChapterSummary
from .continuity import (
    Continuity,
    TimelineEvent,
    Foreshadow,
    ForeshadowStatus,
    Possession,
    Promise,
    Fact,
)
from .ideas import IdeaBank, Idea, IdeaType, IdeaStatus
from .world import World, WorldElement, WorldCategory
from .threads import ThreadNetwork, StoryThread, ThreadNode, ThreadType, NodeStatus
from .memory import Memory

__all__ = [
    "Project",
    "create_project",
    "list_projects",
    "Bible",
    "Character",
    "Location",
    "Faction",
    "Item",
    "Lore",
    "Outline",
    "Volume",
    "ChapterPlan",
    "ChapterStatus",
    "Chapter",
    "ChapterStore",
    "ChapterSummary",
    "Continuity",
    "TimelineEvent",
    "Foreshadow",
    "ForeshadowStatus",
    "Possession",
    "Promise",
    "Fact",
    "IdeaBank",
    "Idea",
    "IdeaType",
    "IdeaStatus",
    "World",
    "WorldElement",
    "WorldCategory",
    "ThreadNetwork",
    "StoryThread",
    "ThreadNode",
    "ThreadType",
    "NodeStatus",
    "Memory",
]
