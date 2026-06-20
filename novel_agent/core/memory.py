"""记忆系统：为长篇小说提供"上下文压缩"。

核心思路：
  - 写第 N 章时，不可能把 1..N-1 章全文塞进去（上下文爆炸）
  - 改为：全书设定集 + 大纲 + 最近 K 章的【摘要】+ 第 N-1 章末尾若干字
  - 这样既保持连贯，又控制 token 数
"""

from __future__ import annotations

from pathlib import Path

from .bible import Bible
from .chapter import ChapterStore
from .continuity import Continuity
from .ideas import IdeaBank
from .outline import Outline, ChapterStatus
from .threads import ThreadNetwork
from .world import World


class Memory:
    """把项目里散落的"记忆"打包成一份给 LLM 的上下文。"""

    def __init__(
        self,
        project_dir: Path,
        outline: Outline,
        bible: Bible,
        store: ChapterStore,
        continuity: Continuity | None = None,
        *,
        world: World | None = None,
        ideas: IdeaBank | None = None,
        threads: ThreadNetwork | None = None,
        recent_summary_count: int = 3,
        recent_text_chars: int = 600,
    ) -> None:
        self.project_dir = project_dir
        self.outline = outline
        self.bible = bible
        self.store = store
        self.continuity = continuity or Continuity()
        self.world = world or World()
        self.ideas = ideas or IdeaBank()
        self.threads = threads or ThreadNetwork()
        self.recent_summary_count = recent_summary_count
        self.recent_text_chars = recent_text_chars

    def build_context_for_chapter(self, chapter_id: str) -> str:
        """为"写第 chapter_id 章"组装上下文。

        包含：
          1. 全书设定集（人物/地点/势力/物品/设定）
          2. 大纲（已写章节 + 当前章节计划 + 后续 1-2 章）
          3. 最近 K 章的摘要
          4. 上一章末尾原文（衔接）
          5. 当前章节详细计划
        """
        plan = self.outline.find(chapter_id)
        if plan is None:
            raise ValueError(f"大纲里找不到章节 {chapter_id}")

        all_ch = self.outline.all_chapters()
        try:
            idx = all_ch.index(plan)
        except ValueError:
            idx = 0

        # 1. 设定集（优先本章涉及的人物/地点）
        related: set[str] = set()
        for name in (
            (plan.characters or [])
            + ([plan.pov] if plan.pov else [])
            + ([plan.setting] if plan.setting else [])
        ):
            for c in self.bible.characters:
                if name and (name in c.name or c.name in name):
                    related.add(c.id)
            for l in self.bible.locations:
                if name and (name in l.name or l.name in name):
                    related.add(l.id)
        bible_text = self.bible.render_for_prompt(related if related else None)

        # 2. 大纲（只显示"已写 + 当前 + 后 1"）
        upcoming = all_ch[: idx + 2]
        outline_text = self.outline.render_for_prompt()
        # 简化：直接全量大纲也可以，但太长时截断
        if len(outline_text) > 2500:
            outline_text = self._compact_outline(upcoming)

        # 3. 最近 K 章摘要
        done_ids = [c.chapter_id for c in all_ch[:idx] if self.store.has(c.chapter_id)]
        recent = (
            done_ids[-self.recent_summary_count :] if self.recent_summary_count else []
        )
        summaries_block = self._format_summaries(recent)

        # 4. 上一章末尾原文
        prev_text = ""
        if done_ids:
            prev_text = self.store.tail(
                self.project_dir, done_ids[-1], self.recent_text_chars
            )

        # 5. 当前章节计划
        current = plan.render_for_prompt()

        # 连续性约束（伏笔/持有物/承诺/既定事实）——防止长篇崩坏的关键
        continuity_text = self.continuity.render_for_prompt()

        # 世界观硬约束（绝对不能违反）
        world_constraints = self.world.render_for_prompt(with_constraints_only=True)

        # 故事线脉络（让 LLM 知道当前在哪条线的哪个节点）
        threads_text = self.threads.render_for_prompt(only_active=True)

        # 相关 idea（本章出场人物/关键词相关的高优先级灵感）
        ideas_text = ""
        available = self.ideas.available()
        if available:
            pool = available
            # 按本章人物筛选
            chapter_chars = (
                [plan.pov] + (plan.characters or [])
                if plan.pov
                else (plan.characters or [])
            )
            if chapter_chars:
                filtered = [
                    i
                    for i in pool
                    if any(
                        any(ic in ch or ch in ic for ic in i.related_chars)
                        for ch in chapter_chars
                    )
                ]
                pool = filtered or pool
            pool = sorted(pool, key=lambda i: -i.priority)[:5]
            ideas_text = self.ideas.render_for_prompt(pool)

        parts = [
            "===== 故事设定 =====",
            bible_text,
        ]
        if world_constraints:
            parts.append("===== 世界观硬约束（绝对不能违反）=====")
            parts.append(world_constraints)
        if continuity_text:
            parts.append("===== 连续性约束（务必遵守，不得违反）=====")
            parts.append(continuity_text)
        if threads_text:
            parts.append("===== 故事线脉络（本章需推进的线）=====")
            parts.append(threads_text)
        parts.append("===== 故事大纲（节选）=====")
        parts.append(outline_text)
        if summaries_block:
            parts.append("===== 前情提要（已发生章节摘要）=====")
            parts.append(summaries_block)
        if prev_text:
            parts.append("===== 上一章结尾原文（用于衔接）=====")
            parts.append(prev_text)
        if ideas_text:
            parts.append("===== 可用灵感 idea（可酌情融入本章）=====")
            parts.append(ideas_text)
        parts.append("===== 本章写作计划 =====")
        parts.append(current)
        return "\n\n".join(parts)

    def _compact_outline(self, chapters) -> str:  # type: ignore[no-untyped-def]
        lines = []
        for v in self.outline.volumes:
            vch = [c for c in v.chapters if c in chapters]
            if not vch:
                continue
            lines.append(f"《{v.title or v.volume_id}》")
            for c in vch:
                status = (
                    "✓"
                    if c.status in (ChapterStatus.done, ChapterStatus.reviewed)
                    else "·"
                )
                lines.append(f"  {status} {c.chapter_id} {c.title}：{c.beat}")
        return "\n".join(lines) if lines else "(暂无)"

    def _format_summaries(self, chapter_ids: list[str]) -> str:
        if not chapter_ids:
            return ""
        lines = []
        for cid in chapter_ids:
            s = self.store.summaries.get(cid)
            if s:
                lines.append(f"【{cid} {s.title}】{s.summary}")
        return "\n".join(lines)
