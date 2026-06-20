"""世界观（Worldbuilding）：底层设定体系。

分类：
  - rule         : 规则体系（魔法/科技/修炼/物理法则），含硬性约束
  - cosmology    : 宇宙观（世界起源/结构/本质）
  - history      : 历史大事件年表
  - geography    : 地理（区域/地图）
  - culture      : 文化风俗（语言/宗教/节庆/衣食）
  - organization : 组织势力（门派/公司/政权）
  - term         : 术语表（专有名词解释）

支持层级（parent），便于表达"火系法术属于元素魔法体系"。
constraints 字段是写作时【绝对不能违反】的硬规则。
"""

from __future__ import annotations

import time
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field


class WorldCategory(str, Enum):
    rule = "rule"
    cosmology = "cosmology"
    history = "history"
    geography = "geography"
    culture = "culture"
    organization = "organization"
    term = "term"


class WorldElement(BaseModel):
    id: str
    category: WorldCategory = WorldCategory.rule
    name: str
    summary: str = ""  # 一句话
    detail: str = ""  # 详细说明
    constraints: list[str] = Field(default_factory=list)  # 硬性约束（写作时必须遵守）
    parent: str = ""  # 父元素 id（体系层级）
    tags: list[str] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)


class World(BaseModel):
    project: str = ""
    elements: list[WorldElement] = Field(default_factory=list)
    # 顶层设定陈述（世界观总纲）
    premise: str = ""

    @classmethod
    def path_of(cls, project_dir: Path) -> Path:
        return project_dir / "world.json"

    @classmethod
    def load(cls, project_dir: Path, project_name: str = "") -> "World":
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
            int(e.id[2:])
            for e in self.elements
            if e.id.startswith("w_") and e.id[2:].isdigit()
        ]
        return f"w_{(max(nums) + 1) if nums else 1:03d}"

    def add(self, **kwargs) -> WorldElement:
        if "id" not in kwargs or not kwargs["id"]:
            kwargs["id"] = self.next_id()
        if isinstance(kwargs.get("category"), str):
            kwargs["category"] = WorldCategory(kwargs["category"])
        elem = WorldElement(
            **{k: v for k, v in kwargs.items() if k in WorldElement.model_fields}
        )
        self.elements.append(elem)
        return elem

    def get(self, elem_id: str) -> WorldElement | None:
        return next((e for e in self.elements if e.id == elem_id), None)

    def remove(self, elem_id: str) -> bool:
        for i, e in enumerate(self.elements):
            if e.id == elem_id:
                self.elements.pop(i)
                return True
        return False

    def by_category(self, cat: WorldCategory | str) -> list[WorldElement]:
        c = WorldCategory(cat) if isinstance(cat, str) else cat
        return [e for e in self.elements if e.category == c]

    def children_of(self, parent_id: str) -> list[WorldElement]:
        return [e for e in self.elements if e.parent == parent_id]

    # ---- 所有硬性约束（写作时强制注入）----
    def all_constraints(self) -> list[str]:
        out: list[str] = []
        for e in self.elements:
            out.extend(e.constraints)
        return out

    # ---- 渲染给 LLM ----
    def render_for_prompt(self, *, with_constraints_only: bool = False) -> str:
        """渲染世界观。with_constraints_only=True 只输出硬性约束（省 token）。"""
        if with_constraints_only:
            cs = self.all_constraints()
            return (
                "【世界观硬性约束（绝对不能违反）】\n" + "\n".join(f"• {c}" for c in cs)
                if cs
                else ""
            )
        if not self.elements and not self.premise:
            return ""
        parts: list[str] = []
        if self.premise:
            parts.append(f"【世界观总纲】{self.premise}")
        # 按类别分组
        for cat in WorldCategory:
            items = self.by_category(cat)
            if not items:
                continue
            lines = [f"【{self._cat_label(cat)}】"]
            for e in items:
                head = f"• {e.name}"
                if e.summary:
                    head += f"：{e.summary}"
                lines.append(head)
                if e.detail:
                    lines.append(f"   {e.detail}")
                if e.constraints:
                    for c in e.constraints:
                        lines.append(f"   ⚠硬约束：{c}")
            parts.append("\n".join(lines))
        return "\n\n".join(parts)

    @staticmethod
    def _cat_label(cat: WorldCategory) -> str:
        return {
            WorldCategory.rule: "规则体系",
            WorldCategory.cosmology: "宇宙观",
            WorldCategory.history: "历史",
            WorldCategory.geography: "地理",
            WorldCategory.culture: "文化风俗",
            WorldCategory.organization: "组织势力",
            WorldCategory.term: "术语表",
        }[cat]
