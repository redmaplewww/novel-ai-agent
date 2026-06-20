"""设定集（Story Bible）：人物 / 地点 / 势力 / 物品 / 杂项设定。

一切需要在全书保持一致的"事实"都放在这里。生成章节时会把相关条目塞进 prompt。
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class _Entry(BaseModel):
    id: str
    name: str
    summary: str = ""  # 一句话
    description: str = ""  # 详细描述
    tags: list[str] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)


class Character(_Entry):
    kind: Literal["character"] = "character"
    role: str = ""  # 主角/反派/配角/...
    age: str = ""
    gender: str = ""
    appearance: str = ""
    personality: str = ""
    background: str = ""
    motivation: str = ""  # 核心动机
    abilities: str = ""  # 能力/技能
    relationships: str = ""  # 与其他人物的关系
    arc: str = ""  # 人物弧光
    # 动态状态时间线：每章写完后自动追加，记录"此刻该人物的当前状态"
    # 例：[{chapter:"c003", text:"左臂被陆铮的记忆抹除波擦伤，暂时失忆半小时"}]
    status_history: list[dict[str, str]] = Field(default_factory=list)

    def current_status(self) -> str:
        """取最新一条动态状态，供写作时注入。"""
        return self.status_history[-1].get("text", "") if self.status_history else ""


class Location(_Entry):
    kind: Literal["location"] = "location"
    geography: str = ""
    culture: str = ""
    significance: str = ""


class Faction(_Entry):
    kind: Literal["faction"] = "faction"
    leader: str = ""
    goals: str = ""
    resources: str = ""


class Item(_Entry):
    kind: Literal["item"] = "item"
    origin: str = ""
    power: str = ""
    owner: str = ""


class Lore(_Entry):
    """杂项设定：魔法体系、历史、规则、术语等。"""

    kind: Literal["lore"] = "lore"


Entry = Character | Location | Faction | Item | Lore


class Bible(BaseModel):
    project: str
    characters: list[Character] = Field(default_factory=list)
    locations: list[Location] = Field(default_factory=list)
    factions: list[Faction] = Field(default_factory=list)
    items: list[Item] = Field(default_factory=list)
    lore: list[Lore] = Field(default_factory=list)

    @classmethod
    def path_of(cls, project_dir: Path) -> Path:
        return project_dir / "bible.json"

    @classmethod
    def load(cls, project_dir: Path, project_name: str) -> "Bible":
        p = cls.path_of(project_dir)
        if not p.exists():
            return cls(project=project_name)
        with open(p, "r", encoding="utf-8") as f:
            return cls.model_validate_json(f.read())

    def save(self, project_dir: Path) -> None:
        with open(self.path_of(project_dir), "w", encoding="utf-8") as f:
            f.write(self.model_dump_json(indent=2))

    def all_entries(self) -> list[_Entry]:
        return [
            *self.characters,
            *self.locations,
            *self.factions,
            *self.items,
            *self.lore,
        ]  # type: ignore[list-item]

    def render_for_prompt(self, include_ids: set[str] | None = None) -> str:
        """渲染成给 LLM 看的设定说明。include_ids=None 表示全部。"""

        def _ok(e: _Entry) -> bool:
            return include_ids is None or e.id in include_ids

        sections: list[str] = []

        chars = [c for c in self.characters if _ok(c)]
        if chars:
            lines = []
            for c in chars:
                head = f"• {c.name}"
                if c.role:
                    head += f"（{c.role}）"
                lines.append(head)
                bits = [
                    c.summary,
                    f"性格：{c.personality}" if c.personality else "",
                    f"动机：{c.motivation}" if c.motivation else "",
                    f"能力：{c.abilities}" if c.abilities else "",
                    f"关系：{c.relationships}" if c.relationships else "",
                    f"外貌：{c.appearance}" if c.appearance else "",
                    f"背景：{c.background}" if c.background else "",
                    f"弧光：{c.arc}" if c.arc else "",
                    f"【当前状态】{c.current_status()}" if c.current_status() else "",
                ]
                desc = "；".join(b for b in bits if b)
                if desc:
                    lines.append(f"   {desc}")
            sections.append("【人物】\n" + "\n".join(lines))

        locs = [x for x in self.locations if _ok(x)]
        if locs:
            sections.append(
                "【地点】\n"
                + "\n".join(
                    f"• {l.name}：{l.summary}{'；地理：' + l.geography if l.geography else ''}{'；意义：' + l.significance if l.significance else ''}"
                    for l in locs
                )
            )

        facs = [x for x in self.factions if _ok(x)]
        if facs:
            sections.append(
                "【势力】\n"
                + "\n".join(
                    f"• {f.name}：{f.summary}{'；首领：' + f.leader if f.leader else ''}{'；目标：' + f.goals if f.goals else ''}"
                    for f in facs
                )
            )

        its = [x for x in self.items if _ok(x)]
        if its:
            sections.append(
                "【物品】\n"
                + "\n".join(
                    f"• {i.name}：{i.summary}{'；能力：' + i.power if i.power else ''}{'；持有：' + i.owner if i.owner else ''}"
                    for i in its
                )
            )

        los = [x for x in self.lore if _ok(x)]
        if los:
            sections.append(
                "【设定】\n"
                + "\n".join(f"• {l.name}：{l.summary}\n  {l.description}" for l in los)
            )

        return "\n\n".join(sections) if sections else "(暂无设定集)"
