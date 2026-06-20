"""大纲树：卷 → 章。每章是一个写作单元（beat）。

status: pending(待写) / writing(写作中) / drafted(已起草) / reviewed(已审校) / done(定稿)
"""

from __future__ import annotations

import time
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field


class ChapterStatus(str, Enum):
    pending = "pending"
    writing = "writing"
    drafted = "drafted"
    reviewed = "reviewed"
    done = "done"


class ChapterPlan(BaseModel):
    """单章计划。chapter_id 全局唯一，形如 'c001'。"""

    chapter_id: str  # c001, c002...
    title: str = ""
    pov: str = ""  # 视角人物
    setting: str = ""  # 发生地点
    time: str = ""  # 时间线
    characters: list[str] = Field(default_factory=list)  # 出场人物 id/名字
    beat: str = ""  # 核心情节节拍（这一章发生了什么）
    goal: str = ""  # 这一章要达成的叙事目标
    conflict: str = ""  # 主要冲突
    ending: str = ""  # 章末钩子/收束
    word_target: int = 2500
    status: ChapterStatus = ChapterStatus.pending
    note: str = ""

    def render_for_prompt(self) -> str:
        parts = [f"【第 {self.chapter_id} 章】{self.title}".strip()]
        if self.pov:
            parts.append(f"视角：{self.pov}")
        if self.setting:
            parts.append(f"地点：{self.setting}")
        if self.time:
            parts.append(f"时间：{self.time}")
        if self.characters:
            parts.append("出场：" + "、".join(self.characters))
        if self.goal:
            parts.append(f"叙事目标：{self.goal}")
        if self.conflict:
            parts.append(f"核心冲突：{self.conflict}")
        if self.beat:
            parts.append(f"情节节拍：{self.beat}")
        if self.ending:
            parts.append(f"章末收束：{self.ending}")
        return "\n".join(parts)


class Volume(BaseModel):
    volume_id: str  # v1, v2...
    title: str = ""
    summary: str = ""  # 本卷主线
    chapters: list[ChapterPlan] = Field(default_factory=list)


class Outline(BaseModel):
    project: str
    premise: str = ""  # 全书核心前提/主线
    volumes: list[Volume] = Field(default_factory=list)
    updated_at: float = Field(default_factory=time.time)

    @classmethod
    def path_of(cls, project_dir: Path) -> Path:
        return project_dir / "outline.json"

    @classmethod
    def load(cls, project_dir: Path, project_name: str) -> "Outline":
        p = cls.path_of(project_dir)
        if not p.exists():
            return cls(project=project_name)
        with open(p, "r", encoding="utf-8") as f:
            return cls.model_validate_json(f.read())

    def save(self, project_dir: Path) -> None:
        import time as _t

        self.updated_at = _t.time()
        with open(self.path_of(project_dir), "w", encoding="utf-8") as f:
            f.write(self.model_dump_json(indent=2))

    # ---- 查询/编辑 ----
    def all_chapters(self) -> list[ChapterPlan]:
        return [c for v in self.volumes for c in v.chapters]

    def find(self, chapter_id: str) -> ChapterPlan | None:
        for c in self.all_chapters():
            if c.chapter_id == chapter_id:
                return c
        return None

    def find_volume(self, chapter_id: str) -> Volume | None:
        for v in self.volumes:
            if any(c.chapter_id == chapter_id for c in v.chapters):
                return v
        return None

    def next_chapter_id(self) -> str:
        ids = [c.chapter_id for c in self.all_chapters()]
        nums = [int(i[1:]) for i in ids if i.startswith("c") and i[1:].isdigit()]
        n = max(nums) + 1 if nums else 1
        return f"c{n:03d}"

    def add_chapter(self, plan: ChapterPlan, volume_id: str | None = None) -> None:
        if volume_id:
            vol = next((v for v in self.volumes if v.volume_id == volume_id), None)
        else:
            vol = self.volumes[-1] if self.volumes else None
        if vol is None:
            vol = Volume(volume_id="v1", title="第一卷")
            self.volumes.append(vol)
        vol.chapters.append(plan)

    def remove_chapter(self, chapter_id: str) -> bool:
        for v in self.volumes:
            for i, c in enumerate(v.chapters):
                if c.chapter_id == chapter_id:
                    v.chapters.pop(i)
                    return True
        return False

    def render_for_prompt(self, max_chapters: int | None = None) -> str:
        out = []
        if self.premise:
            out.append(f"【全书主线】{self.premise}")
        for v in self.volumes:
            lines = [f"《{v.title or v.volume_id}》"]
            if v.summary:
                lines.append(f"  本卷主线：{v.summary}")
            chapters = v.chapters
            if max_chapters is not None:
                chapters = chapters[:max_chapters]
            for c in chapters:
                tag = (
                    f"[{c.status.value}] " if c.status != ChapterStatus.pending else ""
                )
                lines.append(f"  {tag}{c.chapter_id} {c.title}：{c.beat}")
            out.append("\n".join(lines))
        return "\n\n".join(out) if out else "(暂无大纲)"
