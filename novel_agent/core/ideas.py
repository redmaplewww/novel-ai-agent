"""灵感库（Idea Bank）：记录暂时无处安放的好点子。

场景、情节点、对话、反转、人物创意——想到了先存这里，
写作时按相关性检索注入，或由 Weaver 串联进故事线。
"""

from __future__ import annotations

import time
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field


class IdeaType(str, Enum):
    scene = "scene"  # 场景画面
    plot = "plot"  # 情节节拍/事件
    dialogue = "dialogue"  # 对话/台词
    twist = "twist"  # 反转/悬念
    character = "character"  # 人物细节
    worldbuilding = "world"  # 世界观设定点
    emotion = "emotion"  # 情感/氛围
    other = "other"


class IdeaStatus(str, Enum):
    pending = "pending"  # 待用
    planned = "planned"  # 已规划到某章
    used = "used"  # 已使用
    dropped = "dropped"  # 已放弃


class Idea(BaseModel):
    id: str
    type: IdeaType = IdeaType.other
    title: str = ""
    content: str = ""
    tags: list[str] = Field(default_factory=list)
    status: IdeaStatus = IdeaStatus.pending
    priority: int = 3  # 1-5，5 为最想用
    placed_chapter: str = ""  # 规划放入哪章
    used_chapter: str = ""  # 实际用在哪章
    related_chars: list[str] = Field(default_factory=list)  # 相关人物
    note: str = ""
    created_at: float = Field(default_factory=time.time)


class IdeaBank(BaseModel):
    project: str = ""
    ideas: list[Idea] = Field(default_factory=list)

    @classmethod
    def path_of(cls, project_dir: Path) -> Path:
        return project_dir / "ideas.json"

    @classmethod
    def load(cls, project_dir: Path, project_name: str = "") -> "IdeaBank":
        p = cls.path_of(project_dir)
        if not p.exists():
            return cls(project=project_name)
        with open(p, "r", encoding="utf-8") as f:
            return cls.model_validate_json(f.read())

    def save(self, project_dir: Path) -> None:
        with open(self.path_of(project_dir), "w", encoding="utf-8") as f:
            f.write(self.model_dump_json(indent=2))

    # ---- 操作 ----
    def next_id(self) -> str:
        nums = [
            int(i.id[2:])
            for i in self.ideas
            if i.id.startswith("i_") and i.id[2:].isdigit()
        ]
        return f"i_{(max(nums) + 1) if nums else 1:03d}"

    def add(
        self,
        content: str,
        *,
        title: str = "",
        type: IdeaType | str = IdeaType.other,
        tags: list[str] | None = None,
        priority: int = 3,
        related_chars: list[str] | None = None,
        note: str = "",
    ) -> Idea:
        if isinstance(type, str):
            type = IdeaType(type)
        idea = Idea(
            id=self.next_id(),
            type=type,
            title=title or content[:20],
            content=content,
            tags=tags or [],
            priority=max(1, min(5, priority)),
            related_chars=related_chars or [],
            note=note,
        )
        self.ideas.append(idea)
        return idea

    def get(self, idea_id: str) -> Idea | None:
        return next((i for i in self.ideas if i.id == idea_id), None)

    def remove(self, idea_id: str) -> bool:
        for i, idea in enumerate(self.ideas):
            if idea.id == idea_id:
                self.ideas.pop(i)
                return True
        return False

    def mark_used(self, idea_id: str, chapter_id: str) -> bool:
        idea = self.get(idea_id)
        if idea is None:
            return False
        idea.status = IdeaStatus.used
        idea.used_chapter = chapter_id
        return True

    def mark_planned(self, idea_id: str, chapter_id: str) -> bool:
        idea = self.get(idea_id)
        if idea is None:
            return False
        idea.status = IdeaStatus.planned
        idea.placed_chapter = chapter_id
        return True

    def query(
        self,
        *,
        type: IdeaType | str | None = None,
        status: IdeaStatus | str | None = None,
        tag: str | None = None,
        char: str | None = None,
        keyword: str | None = None,
    ) -> list[Idea]:
        result = self.ideas
        if type is not None:
            t = IdeaType(type) if isinstance(type, str) else type
            result = [i for i in result if i.type == t]
        if status is not None:
            s = IdeaStatus(status) if isinstance(status, str) else status
            result = [i for i in result if i.status == s]
        if tag:
            result = [i for i in result if tag in i.tags]
        if char:
            result = [
                i
                for i in result
                if any(char in c or c in char for c in i.related_chars)
            ]
        if keyword:
            kw = keyword.lower()
            result = [
                i
                for i in result
                if kw in i.title.lower()
                or kw in i.content.lower()
                or kw in i.note.lower()
            ]
        return result

    def available(self) -> list[Idea]:
        """未使用、未放弃的（可用于注入/串联）。"""
        return [
            i
            for i in self.ideas
            if i.status in (IdeaStatus.pending, IdeaStatus.planned)
        ]

    def render_for_prompt(self, ideas: list[Idea] | None = None) -> str:
        """渲染给 LLM 看。ideas=None 表示渲染所有可用 idea。"""
        pool = ideas if ideas is not None else self.available()
        if not pool:
            return ""
        # 按 priority 降序
        pool = sorted(pool, key=lambda i: -i.priority)
        lines = []
        for i in pool:
            head = f"• [{i.id}|{i.type.value}|优先级{i.priority}] {i.title}"
            if i.related_chars:
                head += f"  相关人物：{','.join(i.related_chars)}"
            if i.placed_chapter:
                head += f"  (计划放入{i.placed_chapter})"
            lines.append(head)
            if i.content:
                lines.append(f"   {i.content}")
            if i.tags:
                lines.append(f"   标签：{','.join(i.tags)}")
        return "\n".join(lines)

    def stats(self) -> dict[str, int]:
        return {
            "total": len(self.ideas),
            "pending": len([i for i in self.ideas if i.status == IdeaStatus.pending]),
            "planned": len([i for i in self.ideas if i.status == IdeaStatus.planned]),
            "used": len([i for i in self.ideas if i.status == IdeaStatus.used]),
            "dropped": len([i for i in self.ideas if i.status == IdeaStatus.dropped]),
        }
