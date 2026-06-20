"""连续性追踪表（Continuity Tracker）。

记录长篇小说中必须保持一致的「跨章事实」：
  - timeline     : 时间线事件（第几章发生了什么里程碑）
  - foreshadows  : 伏笔（埋下的、是否已回收）
  - possessions  : 角色拥有的物品/能力（何时获得、是否还在）
  - promises     : 承诺/誓言/约定（谁对谁承诺了什么，是否兑现）
  - facts        : 关键既定事实（已确立、不可违反的世界规则/事件）

每写完一章，StateTracker 会从正文里提取这些条目并更新本表。
写作新章时，本表会作为「连续性约束」注入上下文。
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field


class ForeshadowStatus(str, Enum):
    planted = "planted"  # 已埋下
    resolved = "resolved"  # 已回收
    dropped = "dropped"  # 已放弃


class TimelineEvent(BaseModel):
    chapter_id: str
    time_label: str = ""  # 故事内时间（如"逃亡第3天"/"银河历末年冬"）
    event: str  # 发生了什么
    # 时间线校核用的显式锚点（便于检测时序冲突；为空则按 chapter_id 顺序推断）
    anchor: str = ""  # 绝对/相对时间锚点（如"T+3d"、"银河历3047年"）
    duration: str = ""  # 事件持续时间（如"3天"、"瞬间"）
    participants: list[str] = Field(
        default_factory=list
    )  # 参与者（检测同一人物同时分身）


class Foreshadow(BaseModel):
    id: str
    chapter_id: str  # 埋下的章节
    description: str  # 伏笔内容
    status: ForeshadowStatus = ForeshadowStatus.planted
    resolved_at: str = ""  # 回收章节


class Possession(BaseModel):
    id: str
    chapter_id: str  # 获得章节
    owner: str  # 持有者
    item: str  # 物品/能力名
    detail: str = ""  # 说明
    lost: bool = False  # 是否已失去
    lost_at: str = ""


class Promise(BaseModel):
    id: str
    chapter_id: str
    maker: str  # 承诺者
    receiver: str = ""  # 对象
    content: str  # 承诺内容
    fulfilled: bool = False
    fulfilled_at: str = ""


class Fact(BaseModel):
    id: str
    chapter_id: str  # 确立章节
    content: str  # 既定事实
    category: str = ""  # 规则/事件/关系/...


class Continuity(BaseModel):
    project: str = ""
    timeline: list[TimelineEvent] = Field(default_factory=list)
    foreshadows: list[Foreshadow] = Field(default_factory=list)
    possessions: list[Possession] = Field(default_factory=list)
    promises: list[Promise] = Field(default_factory=list)
    facts: list[Fact] = Field(default_factory=list)

    @classmethod
    def path_of(cls, project_dir: Path) -> Path:
        return project_dir / "continuity.json"

    @classmethod
    def load(cls, project_dir: Path, project_name: str = "") -> "Continuity":
        p = cls.path_of(project_dir)
        if not p.exists():
            return cls(project=project_name)
        with open(p, "r", encoding="utf-8") as f:
            return cls.model_validate_json(f.read())

    def save(self, project_dir: Path) -> None:
        with open(self.path_of(project_dir), "w", encoding="utf-8") as f:
            f.write(self.model_dump_json(indent=2))

    # ---- 渲染给 LLM 看的「连续性约束」----
    def render_for_prompt(self, *, up_to_chapter: str | None = None) -> str:
        """渲染连续性约束。up_to_chapter 之前(含)的条目视为已确立。"""
        # 简化：默认全部渲染（条目数本身不会爆炸）
        sections: list[str] = []

        if self.timeline:
            sections.append(
                "【时间线】\n"
                + "\n".join(
                    f"• {t.chapter_id} {t.time_label}: {t.event}" for t in self.timeline
                )
            )

        open_fs = [f for f in self.foreshadows if f.status == ForeshadowStatus.planted]
        if open_fs:
            sections.append(
                "【未回收的伏笔（写作时请记得回收或推进）】\n"
                + "\n".join(
                    f"• {f.id} ({f.chapter_id}): {f.description}" for f in open_fs
                )
            )

        active_pos = [p for p in self.possessions if not p.lost]
        if active_pos:
            sections.append(
                "【角色当前持有物/能力（请保持一致）】\n"
                + "\n".join(
                    f"• {p.owner} 持有「{p.item}」(自 {p.chapter_id})"
                    + (f": {p.detail}" if p.detail else "")
                    for p in active_pos
                )
            )

        open_pm = [p for p in self.promises if not p.fulfilled]
        if open_pm:
            sections.append(
                "【未兑现的承诺（写作时注意推进或呼应）】\n"
                + "\n".join(
                    f"• {p.maker}→{p.receiver}: {p.content} ({p.chapter_id})"
                    for p in open_pm
                )
            )

        if self.facts:
            sections.append(
                "【已确立的既定事实（绝对不能违反）】\n"
                + "\n".join(
                    f"• [{f.category or '事实'}] {f.content}" for f in self.facts
                )
            )

        return "\n\n".join(sections) if sections else ""
