"""KnowledgeBase —— 统一知识库接口。

聚合一个项目的所有长期记忆：
  - bible       : 人物/地点/势力/物品设定集
  - continuity  : 连续性追踪表（时间线/伏笔/持有物/承诺/既定事实）
  - world       : 世界观（规则/历史/地理/文化/组织/术语）
  - ideas       : 灵感库
  - threads     : 故事线网络

所有数据【严格持久化为 JSON】，是长篇小说的「长期记忆与知识库」。
NovelAgent 通过本类统一访问；写作时通过 Memory 注入上下文。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .core import (
    Bible,
    Continuity,
    IdeaBank,
    Outline,
    Project,
    ThreadNetwork,
    World,
)
from .agents.kb_agent import KBAgent
from .llm import LLMBackend


class KnowledgeBase:
    """一个项目的全部知识聚合。"""

    def __init__(
        self,
        project_dir: Path,
        project_name: str,
        *,
        bible: Bible | None = None,
        continuity: Continuity | None = None,
        world: World | None = None,
        ideas: IdeaBank | None = None,
        threads: ThreadNetwork | None = None,
    ) -> None:
        self.dir = project_dir
        self.project_name = project_name
        self.bible = bible or Bible.load(project_dir, project_name)
        self.continuity = continuity or Continuity.load(project_dir, project_name)
        self.world = world or World.load(project_dir, project_name)
        self.ideas = ideas or IdeaBank.load(project_dir, project_name)
        self.threads = threads or ThreadNetwork.load(project_dir, project_name)

    @classmethod
    def load(cls, project: Project) -> "KnowledgeBase":
        return cls(project.dir, project.name)

    def save_all(self) -> None:
        """严格持久化全部知识库到磁盘（JSON）。"""
        self.bible.save(self.dir)
        self.continuity.save(self.dir)
        self.world.save(self.dir)
        self.ideas.save(self.dir)
        self.threads.save(self.dir)

    # ============ 智能操作（需 LLM）============
    def with_agent(self, backend: LLMBackend) -> "_KBOps":
        """绑定一个 LLM 后端，返回可执行智能操作的对象。"""
        return _KBOps(self, KBAgent(backend))

    # ============ idea 管理 ============
    def add_idea(self, content: str, **kwargs: Any) -> Any:
        idea = self.ideas.add(content, **kwargs)
        self.save_all()
        return idea

    def query_ideas(self, **kwargs: Any) -> list[Any]:
        return self.ideas.query(**kwargs)

    def mark_idea_used(self, idea_id: str, chapter_id: str) -> bool:
        ok = self.ideas.mark_used(idea_id, chapter_id)
        if ok:
            self.save_all()
        return ok

    # ============ 世界观管理 ============
    def add_world_element(self, **kwargs: Any) -> Any:
        elem = self.world.add(**kwargs)
        self.save_all()
        return elem

    def world_constraints(self) -> list[str]:
        """所有硬性约束（写作强制注入）。"""
        return self.world.all_constraints()

    # ============ 故事线管理 ============
    def add_thread(self, **kwargs: Any) -> Any:
        t = self.threads.add_thread(**kwargs)
        self.save_all()
        return t

    def add_thread_node(self, thread_id: str, **kwargs: Any) -> Any:
        n = self.threads.add_node_to(thread_id, **kwargs)
        if n:
            self.save_all()
        return n

    # ============ 时间线 ============
    def timeline_events(self) -> list[Any]:
        return list(self.continuity.timeline)

    # ============ 统一渲染（给写作/查看用）============
    def render_full(self) -> str:
        """渲染整个知识库（人读）。"""
        parts = ["========== 知识库总览 =========="]
        if self.world.elements or self.world.premise:
            parts.append("\n--- 世界观 ---")
            parts.append(self.world.render_for_prompt() or "(空)")
        if self.bible.all_entries():
            parts.append("\n--- 设定集 ---")
            parts.append(self.bible.render_for_prompt())
        cont = self.continuity.render_for_prompt()
        if cont:
            parts.append("\n--- 连续性追踪 ---")
            parts.append(cont)
        if self.threads.threads:
            parts.append("\n--- 故事线 ---")
            parts.append(self.threads.render_for_prompt())
        if self.ideas.ideas:
            st = self.ideas.stats()
            parts.append(
                f"\n--- 灵感库（共{st['total']}：待用{st['pending']} 规划{st['planned']} "
                f"已用{st['used']} 放弃{st['dropped']}）---"
            )
            parts.append(self.ideas.render_for_prompt())
        return "\n".join(parts)

    def render_for_writing(
        self,
        *,
        chapter_chars: list[str] | None = None,
        chapter_keywords: str = "",
        include_ideas: bool = True,
    ) -> str:
        """渲染写作时要注入的知识库子集（精简，控制 token）。

        - 世界观：只注入硬性约束 + 与本章相关的元素
        - 设定集：与本章人物/地点相关的
        - 连续性：全部（伏笔/持有物/承诺/事实）
        - 故事线：未收束的
        - idea：与本章相关的高优先级
        """
        parts: list[str] = []

        # 世界观硬约束（始终注入，最关键）
        wc = self.world.render_for_prompt(with_constraints_only=True)
        if wc:
            parts.append(wc)

        # 故事线脉络
        tp = self.threads.render_for_prompt(only_active=True)
        if tp:
            parts.append(tp)

        # 相关 idea（按本章人物/关键词检索）
        if include_ideas and self.ideas.available():
            pool = self.ideas.available()
            if chapter_chars:
                pool = [
                    i
                    for i in pool
                    if any(
                        any(c in ch or ch in c for c in i.related_chars)
                        for ch in chapter_chars
                    )
                ] or pool
            if chapter_keywords:
                kw = chapter_keywords.lower()
                pool = [
                    i for i in pool if kw in i.content.lower() or kw in i.title.lower()
                ] or pool
            pool = sorted(pool, key=lambda i: -i.priority)[:5]  # 最多 5 个
            ip = self.ideas.render_for_prompt(pool)
            if ip:
                parts.append("【可用的灵感 idea（可酌情融入本章）】\n" + ip)

        return "\n\n".join(p for p in parts if p)


class _KBOps:
    """绑定 LLM 后的知识库智能操作（桥接 KBAgent + 数据落盘）。"""

    def __init__(self, kb: KnowledgeBase, agent: KBAgent) -> None:
        self.kb = kb
        self.agent = agent

    # ---- 世界观搭建（落盘到 world.json）----
    def build_world(self, project_meta: str, focus: str = "") -> dict[str, Any]:
        data = self.agent.build_world(project_meta, focus) or {}
        if data.get("premise"):
            self.kb.world.premise = data["premise"]
        added = 0
        for e in data.get("elements", []) or []:
            cat = e.get("category", "rule")
            try:
                self.kb.world.add(
                    category=cat,
                    name=e.get("name", ""),
                    summary=e.get("summary", ""),
                    detail=e.get("detail", ""),
                    constraints=e.get("constraints", []) or [],
                    parent=e.get("parent", ""),
                )
                added += 1
            except Exception:  # noqa: BLE001
                pass
        self.kb.save_all()
        return {"premise": data.get("premise", ""), "elements_added": added}

    # ---- 故事线串联（落盘到 threads.json）----
    def weave_threads(
        self,
        outline: Outline,
        summaries_text: str = "",
        target_chapters: int = 5,
    ) -> dict[str, Any]:
        data = (
            self.agent.weave_threads(
                outline.render_for_prompt(),
                summaries_text,
                self.kb.ideas.render_for_prompt(),
                self.kb.threads.render_for_prompt(),
                target_chapters,
            )
            or {}
        )
        added_threads = 0
        added_nodes = 0
        # 把规划写入 threads.json（合并：已有的线更新节点，新线新增）
        for td in data.get("threads", []) or []:
            name = td.get("name", "").strip()
            if not name:
                continue
            existing = next(
                (t for t in self.kb.threads.threads if t.name == name), None
            )
            if existing is None:
                existing = self.kb.threads.add_thread(
                    type=td.get("type", "subplot"),
                    name=name,
                    summary=td.get("summary", ""),
                    importance=td.get("importance", 3),
                )
                added_threads += 1
            else:
                if td.get("summary"):
                    existing.summary = td["summary"]
            for nd in td.get("nodes", []) or []:
                self.kb.threads.add_node_to(
                    existing.id,
                    chapter_id=nd.get("chapter_id", ""),
                    from_idea=nd.get("from_idea", ""),
                    title=nd.get("title", ""),
                    description=nd.get("description", ""),
                )
                added_nodes += 1
                # 如果节点来自 idea，标记 idea 为已规划
                if nd.get("from_idea") and nd.get("chapter_id"):
                    self.kb.ideas.mark_planned(nd["from_idea"], nd["chapter_id"])
        self.kb.save_all()
        return {
            "threads_added": added_threads,
            "nodes_added": added_nodes,
            "notes": data.get("weaving_notes", ""),
        }

    # ---- 时间线校核（只读分析，不落盘；返回冲突报告）----
    def audit_timeline(self) -> dict[str, Any]:
        tl = self.kb.continuity
        timeline_text = "\n".join(
            f"• {t.chapter_id} [{t.time_label}] {t.event}" for t in tl.timeline
        )
        facts_text = "\n".join(f"• [{f.category}] {f.content}" for f in tl.facts)
        if not timeline_text:
            return {"consistent": True, "conflicts": [], "overall": "暂无时间线事件"}
        return self.agent.audit_timeline(timeline_text, facts_text) or {
            "consistent": True,
            "conflicts": [],
            "overall": "校核未返回结果",
        }

    # ---- idea 安插建议（只读分析）----
    def place_ideas(self, outline: Outline) -> dict[str, Any]:
        available = self.kb.ideas.available()
        if not available:
            return {"placements": [], "unsuitable": [], "note": "没有可用的 idea"}
        return self.agent.place_ideas(
            self.kb.ideas.render_for_prompt(available),
            outline.render_for_prompt(),
        ) or {"placements": [], "unsuitable": []}
