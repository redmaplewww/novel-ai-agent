"""项目元信息。"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

# 项目根目录
PROJECTS_ROOT = Path(__file__).resolve().parent.parent.parent / "projects"


class Project(BaseModel):
    """一部小说 = 一个项目。"""

    name: str  # 也是目录名，必须合法
    title: str = ""  # 书名
    genre: str = ""  # 题材：玄幻 / 都市 / 科幻 / 武侠 / 言情 / 悬疑 ...
    style: str = ""  # 风格参考：如"古龙风"、"轻小说"
    audience: str = ""  # 目标读者
    logline: str = ""  # 一句话简介（核心冲突）
    synopsis: str = ""  # 完整简介（200-500字）
    worldview: str = ""  # 世界观说明
    themes: list[str] = Field(default_factory=list)  # 主题
    notes: str = ""  # 作者自由备注
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)

    @property
    def dir(self) -> Path:
        return PROJECTS_ROOT / self.name

    @classmethod
    def list_all(cls) -> list[str]:
        if not PROJECTS_ROOT.exists():
            return []
        return sorted(
            p.name for p in PROJECTS_ROOT.iterdir() if (p / "project.json").exists()
        )

    @classmethod
    def load(cls, name: str) -> "Project":
        path = PROJECTS_ROOT / name / "project.json"
        if not path.exists():
            raise FileNotFoundError(f"项目不存在: {name}（在 {path}）")
        with open(path, "r", encoding="utf-8") as f:
            return cls.model_validate_json(f.read())

    def save(self) -> None:
        self.updated_at = time.time()
        self.dir.mkdir(parents=True, exist_ok=True)
        (self.dir / "chapters").mkdir(exist_ok=True)
        with open(self.dir / "project.json", "w", encoding="utf-8") as f:
            f.write(self.model_dump_json(indent=2))

    def ensure_dirs(self) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        (self.dir / "chapters").mkdir(exist_ok=True)

    def meta_for_prompt(self) -> str:
        """给 LLM 的项目元信息摘要。"""
        parts: list[str] = []
        if self.title:
            parts.append(f"【书名】{self.title}")
        if self.genre:
            parts.append(f"【题材】{self.genre}")
        if self.style:
            parts.append(f"【风格】{self.style}")
        if self.audience:
            parts.append(f"【目标读者】{self.audience}")
        if self.themes:
            parts.append(f"【主题】{'、'.join(self.themes)}")
        if self.logline:
            parts.append(f"【一句话简介】{self.logline}")
        if self.worldview:
            parts.append(f"【世界观】\n{self.worldview}")
        if self.synopsis:
            parts.append(f"【故事简介】\n{self.synopsis}")
        return "\n".join(parts) if parts else "(未填写项目元信息)"


def list_projects() -> list[str]:
    return Project.list_all()


def create_project(**kwargs: Any) -> Project:
    name = kwargs.get("name")
    if not name:
        raise ValueError("项目必须指定 name")
    # 简单的合法化目录名
    safe = "".join(c for c in name if c.isalnum() or c in "-_") or "novel"
    kwargs["name"] = safe
    p = Project(**kwargs)
    if (PROJECTS_ROOT / safe / "project.json").exists():
        raise FileExistsError(f"项目已存在: {safe}")
    p.save()
    return p
