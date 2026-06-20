"""故事线（Story Threads）：把剧情和 idea 串成脉络。

  - main      : 主线（通常 1 条，全书核心推进）
  - subplot   : 支线（次要情节线，可与主线交织）
  - character : 人物线（某角色的个人弧光轨迹）
  - mystery   : 悬念线（谜题/伏笔的铺开与揭示）

每条线由有序的 ThreadNode 组成，每个 node 对应一个章节节点或计划节点。
node 可来自已写章节，也可来自 idea（待安插）。
"""

from __future__ import annotations

import time
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field


class ThreadType(str, Enum):
    main = "main"
    subplot = "subplot"
    character = "character"
    mystery = "mystery"


class NodeStatus(str, Enum):
    planned = "planned"  # 计划中
    written = "written"  # 已写入章节
    skipped = "skipped"  # 跳过


class ThreadNode(BaseModel):
    id: str
    chapter_id: str = ""  # 对应章节（已写或计划放入）
    from_idea: str = ""  # 来源 idea id
    title: str = ""
    description: str = ""  # 这个节点发生什么
    status: NodeStatus = NodeStatus.planned
    # 与其他线的交汇点（key=其他thread_id, value=交汇说明）
    intersections: dict[str, str] = Field(default_factory=dict)
    created_at: float = Field(default_factory=time.time)


class StoryThread(BaseModel):
    id: str
    type: ThreadType = ThreadType.subplot
    name: str
    summary: str = ""  # 这条线讲什么
    nodes: list[ThreadNode] = Field(default_factory=list)
    resolved: bool = False  # 是否已收束
    importance: int = 3  # 1-5
    created_at: float = Field(default_factory=time.time)

    def add_node(self, node: ThreadNode) -> None:
        self.nodes.append(node)

    def next_node_id(self) -> str:
        nums = [
            int(n.id[2:])
            for n in self.nodes
            if n.id.startswith("n_") and n.id[2:].isdigit()
        ]
        return f"n_{(max(nums) + 1) if nums else 1:03d}"


class ThreadNetwork(BaseModel):
    project: str = ""
    threads: list[StoryThread] = Field(default_factory=list)

    @classmethod
    def path_of(cls, project_dir: Path) -> Path:
        return project_dir / "threads.json"

    @classmethod
    def load(cls, project_dir: Path, project_name: str = "") -> "ThreadNetwork":
        p = cls.path_of(project_dir)
        if not p.exists():
            return cls(project=project_name)
        with open(p, "r", encoding="utf-8") as f:
            return cls.model_validate_json(f.read())

    def save(self, project_dir: Path) -> None:
        with open(self.path_of(project_dir), "w", encoding="utf-8") as f:
            f.write(self.model_dump_json(indent=2))

    # ---- 操作 ----
    def next_thread_id(self) -> str:
        nums = [
            int(t.id[2:])
            for t in self.threads
            if t.id.startswith("t_") and t.id[2:].isdigit()
        ]
        return f"t_{(max(nums) + 1) if nums else 1:03d}"

    def add_thread(self, **kwargs) -> StoryThread:
        if "id" not in kwargs or not kwargs["id"]:
            kwargs["id"] = self.next_thread_id()
        if isinstance(kwargs.get("type"), str):
            kwargs["type"] = ThreadType(kwargs["type"])
        t = StoryThread(
            **{k: v for k, v in kwargs.items() if k in StoryThread.model_fields}
        )
        self.threads.append(t)
        return t

    def get(self, thread_id: str) -> StoryThread | None:
        return next((t for t in self.threads if t.id == thread_id), None)

    def main_thread(self) -> StoryThread | None:
        mains = [t for t in self.threads if t.type == ThreadType.main]
        return mains[0] if mains else None

    def by_type(self, ttype: ThreadType | str) -> list[StoryThread]:
        tt = ThreadType(ttype) if isinstance(ttype, str) else ttype
        return [t for t in self.threads if t.type == tt]

    def remove(self, thread_id: str) -> bool:
        for i, t in enumerate(self.threads):
            if t.id == thread_id:
                self.threads.pop(i)
                return True
        return False

    def add_node_to(self, thread_id: str, **kwargs) -> ThreadNode | None:
        t = self.get(thread_id)
        if t is None:
            return None
        if "id" not in kwargs or not kwargs["id"]:
            kwargs["id"] = t.next_node_id()
        node = ThreadNode(
            **{k: v for k, v in kwargs.items() if k in ThreadNode.model_fields}
        )
        t.add_node(node)
        return node

    # ---- 渲染 ----
    def render_for_prompt(self, *, only_active: bool = True) -> str:
        """渲染故事线脉络。only_active=True 只显示未收束的线。"""
        if not self.threads:
            return ""
        pool = self.threads
        if only_active:
            pool = [t for t in pool if not t.resolved]
        if not pool:
            return ""
        parts: list[str] = ["【故事线脉络】"]
        # 主线在前
        pool = sorted(pool, key=lambda t: (t.type != ThreadType.main, -t.importance))
        for t in pool:
            mark = "✓收束" if t.resolved else "●进行中"
            head = f"《{t.name}》[{t.type.value}|{mark}]"
            if t.summary:
                head += f"：{t.summary}"
            parts.append(head)
            for n in t.nodes:
                tag = {"planned": "□", "written": "■", "skipped": "×"}.get(
                    n.status.value, "·"
                )
                ch = f"@{n.chapter_id}" if n.chapter_id else "@计划"
                src = f" ←idea:{n.from_idea}" if n.from_idea else ""
                parts.append(f"   {tag} {n.id} {ch}{src} {n.title}：{n.description}")
            # 交汇
            inter_lines = []
            for n in t.nodes:
                for other_id, desc in n.intersections.items():
                    inter_lines.append(f"   ⤖ 与 {other_id} 交汇于 {n.id}：{desc}")
            if inter_lines:
                parts.extend(inter_lines)
        return "\n".join(parts)

    def unresolved_threads(self) -> list[StoryThread]:
        return [t for t in self.threads if not t.resolved]
