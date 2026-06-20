"""NovelAgent —— 项目级总管。

封装一个项目从"开新书"到"批量出章节"的全部高层操作，
是 CLI 和 Web UI 调用的主入口。
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Iterator

from ..config import Config
from ..core import (
    Bible,
    ChapterStore,
    ChapterPlan,
    ChapterStatus,
    Continuity,
    IdeaBank,
    Memory,
    Outline,
    Project,
    ThreadNetwork,
    Volume,
    World,
    create_project,
)
from ..core.project import PROJECTS_ROOT  # noqa: F401  (kept for compat)
from ..core.usage import UsageLog
from ..core.pacing import PacingData
from ..core.search import SearchEngine
from ..kb import KnowledgeBase
from ..llm import LLMBackend, build_backend
from ..llm.embedding import build_embedding
from .pacing_agent import PacingAgent
from .planner import PlannerAgent
from .reviewer import ReviewerAgent
from .rewrite_agent import RewriteAgent
from .style_agent import StyleAgent
from .tracker import StateTracker
from .writer import WriterAgent


def _to_str(v: Any) -> str:
    """把 LLM 返回的 str 或 list[str] 统一成 str。"""
    if isinstance(v, list):
        return "\n".join(str(x) for x in v)
    return str(v) if v else ""


class NovelAgent:
    """一个实例 = 打开一个项目并干活。"""

    def __init__(
        self, project: Project, config: Config, *, backend: LLMBackend | None = None
    ) -> None:
        self.project = project
        self.config = config
        self.dir: Path = project.dir
        self.backend: LLMBackend = backend or build_backend(config)
        writer_model = getattr(self.backend, "writer_model", None)
        # 用量记账（在构造 agent 前初始化，供 log 回调使用）
        self.usage_log = UsageLog(self.dir)
        self.pricing = config.pricing
        log_fn = self.log_usage if not backend else None
        self.planner = PlannerAgent(self.backend, log=log_fn)
        self.writer = WriterAgent(self.backend, writer_model, log=log_fn)
        self.reviewer = ReviewerAgent(self.backend, writer_model, log=log_fn)
        self.tracker = StateTracker(self.backend, log=log_fn)
        self.pacing_agent = PacingAgent(self.backend, log=log_fn)
        self.rewrite_agent = RewriteAgent(self.backend, writer_model, log=log_fn)
        self.style_agent = StyleAgent(self.backend, log=log_fn)
        self.outline = Outline.load(self.dir, project.name)
        # 统一知识库：bible + continuity + world + ideas + threads
        self.kb = KnowledgeBase.load(project)
        # 别名（兼容老代码 & 便捷访问）
        self.bible = self.kb.bible
        self.store = ChapterStore.load(self.dir)
        self.continuity = self.kb.continuity
        self.world = self.kb.world
        self.ideas = self.kb.ideas
        self.threads = self.kb.threads
        w = config.writing
        self.chapter_words = int(w.get("chapter_words", 2500))
        self.recent_summary_count = int(w.get("recent_summary_count", 3))
        self.recent_text_chars = int(w.get("recent_text_chars", 600))
        self.max_retries = int(w.get("max_retries", 2))
        self.auto_review = bool(w.get("auto_review", True))
        # 是否在写完每章后自动跑状态追踪
        self.auto_track = bool(w.get("auto_track", True))

    # ---------------- 项目管理 ----------------
    @classmethod
    def open(cls, name: str, config: Config | None = None) -> "NovelAgent":
        config = config or Config()
        return cls(Project.load(name), config)

    @classmethod
    def create(cls, config: Config | None = None, **kwargs: Any) -> "NovelAgent":
        config = config or Config()
        p = create_project(**kwargs)
        return cls(p, config)

    @classmethod
    def list_projects(cls) -> list[str]:
        return Project.list_all()

    def save_all(self) -> None:
        self.project.save()
        self.outline.save(self.dir)
        self.store.save(self.dir)
        self.kb.save_all()  # 严格持久化全部知识库

    # ---------------- 记忆 ----------------
    def _memory(self) -> Memory:
        return Memory(
            self.dir,
            self.outline,
            self.bible,
            self.store,
            self.continuity,
            world=self.world,
            ideas=self.ideas,
            threads=self.threads,
            recent_summary_count=self.recent_summary_count,
            recent_text_chars=self.recent_text_chars,
        )

    # ---------------- 高层工作流 ----------------
    def init_from_synopsis(
        self, chapter_count: int = 20, auto_bible: bool = True
    ) -> dict[str, Any]:
        """从项目简介一键生成 主线+大纲+设定集。"""
        result: dict[str, Any] = {}

        # 1) 主线 + 卷纲
        plan = self.planner.generate_premise_and_outline(
            self.project.synopsis or self.project.logline,
            self.project.genre,
            self.project.style,
            chapter_count,
        )
        if not plan:
            raise RuntimeError("LLM 没有返回有效的主线 JSON")
        self.outline.premise = plan.get("premise", "")
        if plan.get("themes"):
            self.project.themes = plan["themes"]
        for v in plan.get("volumes", []):
            vol = Volume(
                volume_id=f"v{len(self.outline.volumes) + 1}",
                title=v.get("title", ""),
                summary=v.get("summary", ""),
            )
            self.outline.volumes.append(vol)  # 先加入，next_chapter_id 才能正确递增
            for ch in v.get("chapters", []):
                cid = self.outline.next_chapter_id()
                vol.chapters.append(
                    ChapterPlan(
                        chapter_id=cid,
                        title=ch.get("title", ""),
                        beat=ch.get("beat", ""),
                        word_target=self.chapter_words,
                    )
                )
        result["premise"] = self.outline.premise
        result["volume_count"] = len(self.outline.volumes)
        result["chapter_count"] = len(self.outline.all_chapters())

        # 2) 设定集
        if auto_bible:
            bible = self.planner.generate_bible(self.project.meta_for_prompt())
            if bible:
                self._merge_bible(bible)
                result["bible_entries"] = (
                    len(self.bible.characters)
                    + len(self.bible.locations)
                    + len(self.bible.factions)
                    + len(self.bible.items)
                    + len(self.bible.lore)
                )

        self.save_all()
        return result

    def _merge_bible(self, data: dict[str, Any]) -> None:
        from ..core.bible import Character, Faction, Item, Location, Lore

        for c in data.get("characters", []) or []:
            self.bible.characters.append(
                Character(**{k: v for k, v in c.items() if k in Character.model_fields})
            )  # type: ignore[arg-type]
        for l in data.get("locations", []) or []:
            self.bible.locations.append(
                Location(**{k: v for k, v in l.items() if k in Location.model_fields})
            )  # type: ignore[arg-type]
        for f in data.get("factions", []) or []:
            self.bible.factions.append(
                Faction(**{k: v for k, v in f.items() if k in Faction.model_fields})
            )  # type: ignore[arg-type]
        for i in data.get("items", []) or []:
            self.bible.items.append(
                Item(**{k: v for k, v in i.items() if k in Item.model_fields})
            )  # type: ignore[arg-type]
        for l in data.get("lore", []) or []:
            self.bible.lore.append(
                Lore(**{k: v for k, v in l.items() if k in Lore.model_fields})
            )  # type: ignore[arg-type]

    def enrich_next_chapter_plan(self, hint: str = "") -> ChapterPlan | None:
        """把"下一个待写章节"的粗 beat 扩展成详细计划。"""
        ch = next(
            (
                c
                for c in self.outline.all_chapters()
                if c.status == ChapterStatus.pending
            ),
            None,
        )
        if ch is None:
            return None
        ctx = self.project.meta_for_prompt() + "\n\n" + self.outline.render_for_prompt()
        detailed = self.planner.plan_single_chapter(ctx, hint or ch.beat)
        if not detailed:
            return ch
        for k in (
            "title",
            "pov",
            "setting",
            "time",
            "beat",
            "goal",
            "conflict",
            "ending",
        ):
            if detailed.get(k):
                setattr(ch, k, detailed[k])
        if detailed.get("characters"):
            ch.characters = detailed["characters"]
        self.save_all()
        return ch

    def write_chapter(
        self, chapter_id: str, *, review: bool | None = None, verbose: bool = False
    ) -> dict[str, Any]:
        """写指定章节：组装上下文 → 生成正文 → 存盘 → (可选)审校。"""
        plan = self.outline.find(chapter_id)
        if plan is None:
            raise ValueError(f"大纲里没有章节 {chapter_id}")
        review = self.auto_review if review is None else review
        plan.status = ChapterStatus.writing
        self.save_all()

        ctx = self._memory().build_context_for_chapter(chapter_id)

        # 生成正文（带重试）
        content = ""
        last_err = None
        for attempt in range(self.max_retries + 1):
            try:
                content = self.writer.write_chapter(
                    ctx, plan.word_target or self.chapter_words, chapter_id=chapter_id
                )
                if len(content) > 50:
                    break
            except Exception as e:  # noqa: BLE001
                last_err = e
                if verbose:
                    print(f"  [重试 {attempt + 1}/{self.max_retries + 1}] {e}")
                time.sleep(1)
        if not content:
            plan.status = ChapterStatus.pending
            self.save_all()
            raise RuntimeError(f"章节 {chapter_id} 生成失败: {last_err}")

        # 清理：去掉模型可能自己加的标题行
        content = self._strip_self_title(content)

        # 生成摘要
        try:
            summary = self.writer.summarize(chapter_id, plan.title, content)
        except Exception:  # noqa: BLE001
            summary = content[:200]

        self.store.write_chapter(self.dir, plan, content, summary, source="ai")
        plan.status = ChapterStatus.drafted
        self.save_all()

        # 自动备份（防丢稿）
        try:
            from ..core.backup import backup_project

            backup_project(self.dir)
        except Exception:  # noqa: BLE001
            pass

        # 记录写作进度
        try:
            from ..core.progress import ProgressData

            pd = ProgressData.load(self.dir, self.project.name)
            pd.record_today(len([c for c in content if c.strip()]))
            pd.save(self.dir)
        except Exception:  # noqa: BLE001
            pass

        # 状态追踪：从本章正文提取状态变化，回写 bible + continuity
        # 这是防止长篇崩坏的关键步骤。放在审校前，让审校也能用到最新状态。
        tracking: dict[str, Any] | None = None
        if self.auto_track:
            try:
                tracking = self.track_chapter(chapter_id, verbose=verbose)
            except Exception as e:  # noqa: BLE001
                if verbose:
                    print(f"  [状态追踪失败，不影响写作] {e}")

        review_result: dict[str, Any] | None = None
        if review:
            review_result = self.review_chapter(chapter_id)
        return {
            "chapter_id": chapter_id,
            "title": plan.title,
            "word_count": len([c for c in content if c.strip()]),
            "summary": summary,
            "tracking": tracking,
            "review": review_result,
            "content": content,
        }

    def review_chapter(
        self, chapter_id: str, auto_revise: bool = False
    ) -> dict[str, Any]:
        plan = self.outline.find(chapter_id)
        ch = self.store.read_chapter(self.dir, chapter_id)
        if plan is None or ch is None:
            raise ValueError(f"章节 {chapter_id} 不存在或未写")
        ctx = self._memory().build_context_for_chapter(chapter_id)
        # 把本章大纲计划传给审校，用于偏离检测
        result = self.reviewer.review(ctx, ch.content, plan.render_for_prompt()) or {}
        ch.review_note = str(result.get("overall", ""))[:500]
        self.store.write_chapter(
            self.dir, plan, ch.content, summary=self.store.summaries[chapter_id].summary
        )
        # 审校意见入库
        self.store.summaries[chapter_id].summary += f"\n[审校] {ch.review_note}"
        self.store.save(self.dir)

        # 若检测到重大偏离，记录到大纲备注
        dev = result.get("deviation") or {}
        if dev.get("deviated") and dev.get("degree") in ("minor", "major"):
            plan.note = (
                plan.note + " | " if plan.note else ""
            ) + f"[偏离:{dev.get('degree')}] {dev.get('description', '')}"
            self.save_all()

        revised_content = None
        # 修订触发条件：严重问题 或 重大偏离
        issues = result.get("issues", []) or []
        cont_violations = result.get("continuity_violations", []) or []
        need_revise = auto_revise and (
            any(i.get("severity") == "high" for i in issues)
            or any(v.get("severity") == "high" for v in cont_violations)
            or dev.get("degree") == "major"
        )
        if need_revise:
            problem_lines = []
            for v in cont_violations:
                if v.get("severity") == "high":
                    problem_lines.append(
                        f"- [连续性违反/{v.get('type')}] {v.get('description')}（建议：{v.get('suggestion')}）"
                    )
            if dev.get("degree") == "major":
                problem_lines.append(f"- [偏离大纲] {dev.get('description')}")
                for mb in dev.get("missing_beats", []) or []:
                    problem_lines.append(f"  缺失节拍：{mb}")
            for i in issues:
                if i.get("severity") == "high":
                    problem_lines.append(
                        f"- [{i.get('type')}] {i.get('description')}（建议：{i.get('suggestion')}）"
                    )
            issues_text = "\n".join(problem_lines) or "请根据审校意见优化"
            revised_content = self.reviewer.revise(ch.content, issues_text)
            if revised_content and len(revised_content) > 50:
                revised_content = self._strip_self_title(revised_content)
                self.store.write_chapter(
                    self.dir,
                    plan,
                    revised_content,
                    self.store.summaries[chapter_id].summary,
                )
                # 重写后重新追踪状态
                if self.auto_track:
                    try:
                        self.track_chapter(chapter_id, verbose=False)
                    except Exception:  # noqa: BLE001
                        pass
                plan.status = ChapterStatus.reviewed
                self.save_all()
        if plan.status != ChapterStatus.reviewed:
            plan.status = ChapterStatus.reviewed
            self.save_all()
        return {"review": result, "revised": revised_content}

    # ---------------- 状态追踪 ----------------
    def track_chapter(
        self, chapter_id: str, *, verbose: bool = False
    ) -> dict[str, Any]:
        """对指定章节跑状态追踪：提取状态变化 → 回写 bible + continuity。"""
        ch = self.store.read_chapter(self.dir, chapter_id)
        if ch is None or not ch.content:
            raise ValueError(f"章节 {chapter_id} 不存在或未写")
        if verbose:
            print(f"  [追踪] 分析 {chapter_id} 的状态变化...")
        report = self.tracker.track_chapter(
            chapter_id, ch.content, self.bible, self.continuity
        )
        self.save_all()
        if verbose and report.get("extracted"):
            cu = report.get("bible_characters_updated", 0)
            cont = report.get("continuity", {})
            tot = sum(cont.values()) if cont else 0
            print(f"  [追踪] 更新 {cu} 个人物状态，新增 {tot} 条连续性记录")
        return report

    def track_all(self, *, verbose: bool = False) -> list[dict[str, Any]]:
        """对全部已写章节补跑状态追踪（用于已有项目的迁移）。"""
        reports = []
        for cid in self.store.ordered_ids():
            if verbose:
                print(f"  [追踪] {cid}...")
            try:
                reports.append(self.track_chapter(cid, verbose=verbose))
            except Exception as e:  # noqa: BLE001
                reports.append({"chapter_id": cid, "error": str(e)})
        return reports

    def view_continuity(self) -> str:
        """查看连续性追踪表。"""
        return (
            self.continuity.render_for_prompt() or "(暂无连续性记录，写章后会自动生成)"
        )

    def write_next(
        self, *, review: bool | None = None, verbose: bool = False
    ) -> dict[str, Any] | None:
        """写下一个待写章节。"""
        ch = next(
            (
                c
                for c in self.outline.all_chapters()
                if c.status == ChapterStatus.pending
            ),
            None,
        )
        if ch is None:
            return None
        return self.write_chapter(ch.chapter_id, review=review, verbose=verbose)

    def write_batch(
        self, count: int, *, review: bool | None = None, verbose: bool = False
    ) -> Iterator[dict[str, Any]]:
        """连续写 count 个待写章节，逐章 yield（供流式 UI 用）。"""
        for _ in range(count):
            r = self.write_next(review=review, verbose=verbose)
            if r is None:
                break
            yield r

    # ---------------- 导出 ----------------
    def export_markdown(self) -> str:
        lines = [f"# {self.project.title or self.project.name}\n"]
        if self.project.synopsis:
            lines.append(f"> {self.project.synopsis}\n")
        for v in self.outline.volumes:
            if v.title:
                lines.append(f"\n## {v.title}\n")
            for c in v.chapters:
                ch = self.store.read_chapter(self.dir, c.chapter_id)
                if ch:
                    lines.append(ch.render_markdown())
                    lines.append("\n---\n")
        return "\n".join(lines)

    def export_to_file(self, path: str | Path | None = None) -> Path:
        path = Path(path) if path else self.dir / f"{self.project.name}_全文.md"
        path.write_text(self.export_markdown(), encoding="utf-8")
        return path

    # ---------------- 工具 ----------------
    @staticmethod
    def _strip_self_title(text: str) -> str:
        """去掉模型可能自己加的'第X章 标题'行。"""
        lines = text.lstrip().split("\n")
        if lines and (lines[0].startswith("第") and "章" in lines[0][:20]):
            lines = lines[1:]
        elif lines and lines[0].startswith("#"):
            lines = lines[1:]
        return "\n".join(lines).lstrip("\n")

    def test_backend(self) -> str:
        """测试后端连通性。"""
        return self.backend.test()

    # ================ 统一知识库接口（四大能力）================
    def kb_ops(self):
        """返回绑定当前后端的知识库智能操作对象。"""
        return self.kb.with_agent(self.backend)

    def build_world(self, focus: str = "") -> dict[str, Any]:
        """【世界观搭建】生成/补全世界观，落盘到 world.json。"""
        ops = self.kb_ops()
        r = ops.build_world(self.project.meta_for_prompt(), focus)
        # 同步本地引用
        self.world = self.kb.world
        return r

    def weave_threads(self, target_chapters: int = 5) -> dict[str, Any]:
        """【故事线串联】根据大纲+已写+idea 串联故事线，落盘到 threads.json。"""
        ops = self.kb_ops()
        summaries = "\n".join(
            f"【{cid} {s.title}】{s.summary}" for cid, s in self.store.summaries.items()
        )
        r = ops.weave_threads(self.outline, summaries, target_chapters)
        self.threads = self.kb.threads
        return r

    def audit_timeline(self) -> dict[str, Any]:
        """【时间线校核】检查时间线一致性，返回冲突报告（不落盘）。"""
        return self.kb_ops().audit_timeline()

    def place_ideas(self) -> dict[str, Any]:
        """【idea 安插建议】分析哪些 idea 适合放哪章（不落盘）。"""
        return self.kb_ops().place_ideas(self.outline)

    def view_kb(self) -> str:
        """查看完整知识库。"""
        return self.kb.render_full()

    # ================ 成本/用量 ================
    def log_usage(
        self, *, op: str, model: str, usage: dict[str, int], chapter_id: str = ""
    ) -> None:
        """记录一次 LLM 调用到 usage_log.json。"""
        self.usage_log.log(
            op=op,
            model=model,
            usage=usage,
            chapter_id=chapter_id,
            cached_tokens=usage.get("cached_tokens", 0),
        )

    def cost_summary(self) -> dict[str, Any]:
        """成本汇总。"""
        return self.usage_log.summary(self.pricing)

    # ================ 备份 ================
    def backup(self, *, keep: int = 10):
        """手动触发项目备份，返回 zip 路径。"""
        from ..core.backup import backup_project

        return backup_project(self.dir, keep=keep)

    def list_backups(self) -> list[dict]:
        from ..core.backup import list_backups

        return list_backups(self.dir)

    # ================ 章节版本管理 ================
    def list_versions(self, chapter_id: str) -> list[dict]:
        return self.store.list_versions(self.dir, chapter_id)

    def get_version(self, chapter_id: str, version: int):
        return self.store.get_version(self.dir, chapter_id, version)

    def rollback_version(self, chapter_id: str, version: int):
        r = self.store.rollback(self.dir, chapter_id, version)
        if r:
            self.save_all()
        return r

    def diff_versions(
        self, chapter_id: str, v1: int = 0, v2: int = 1
    ) -> dict[str, list[str]]:
        return self.store.diff(self.dir, chapter_id, v1, v2)

    # ================ 节奏曲线 ================
    def analyze_pacing(
        self, chapter_id: str | None = None, *, verbose: bool = False
    ) -> dict[str, Any]:
        """分析章节节奏。chapter_id=None 则分析全部已写章节。"""
        data = PacingData.load(self.dir, self.project.name)
        targets = [chapter_id] if chapter_id else self.store.ordered_ids()
        analyzed = []
        for cid in targets:
            ch = self.store.read_chapter(self.dir, cid)
            if not ch or not ch.content:
                continue
            if verbose:
                print(f"  [节奏] 分析 {cid}...")
            plan = self.outline.find(cid)
            beat = plan.beat if plan else ""
            cp = self.pacing_agent.analyze_chapter(cid, ch.title, ch.content, beat)
            if cp:
                data.chapters[cid] = cp
                analyzed.append(cid)
        data.save(self.dir)
        report = data.detect_problems()
        return {
            "analyzed": analyzed,
            "curve": data.curve_ascii(),
            "problems": [p for p in report.problems],
            "suggestions": report.suggestions,
            "data": data,
        }

    def view_pacing(self) -> str:
        """查看节奏曲线（不重新分析）。"""
        data = PacingData.load(self.dir, self.project.name)
        if not data.chapters:
            return "(暂无节奏数据，用 pacing --analyze 生成)"
        report = data.detect_problems()
        parts = [data.curve_ascii(), ""]
        parts.append("各章评分：")
        for cp in data.ordered():
            parts.append(
                f"  {cp.chapter_id} 张力{cp.tension} 情绪{cp.emotion} 信息{cp.info_density} "
                f"[{cp.pace.value}|{cp.mood}|钩子{'有' if cp.cliffhanger else '无'}]"
            )
        if report.problems:
            parts.append("\n⚠ 检测到的问题：")
            for p in report.problems:
                parts.append(
                    f"  [{p.get('type')}|{p.get('severity')}] {p.get('description')} @ {p.get('chapters')}"
                )
        if report.suggestions:
            parts.append("\n建议：")
            for s in report.suggestions:
                parts.append(f"  • {s}")
        return "\n".join(parts)

    # ================ 局部重写 ================
    def rewrite_passage(
        self,
        chapter_id: str,
        passage: str,
        instruction: str,
        *,
        context_chars: int = 400,
    ) -> dict[str, Any]:
        """重写章节中选中的片段。

        passage: 要重写的原文（必须在章节中能定位到）
        instruction: 重写指令（如"更紧张"、"去掉说教感"）
        返回 {old, new, full_content, diff}
        会自动归档旧版（write_chapter 的 source="revise"）。
        """
        ch = self.store.read_chapter(self.dir, chapter_id)
        if not ch or not ch.content:
            raise ValueError(f"章节 {chapter_id} 不存在或无内容")
        # 定位片段
        pos = ch.content.find(passage)
        if pos < 0:
            # 容错：尝试去除首尾空白后匹配
            pos = ch.content.find(passage.strip())
            if pos >= 0:
                passage = passage.strip()
        if pos < 0:
            raise ValueError("指定的片段在章节中找不到，请确认原文完全一致")
        before = ch.content[max(0, pos - context_chars) : pos]
        after_start = pos + len(passage)
        after = ch.content[after_start : after_start + context_chars]
        # 取文风指纹（若已有）
        style_fp = ""
        try:
            from ..core.style import StyleData

            sd = StyleData.load(self.dir)
            if sd.prose_fingerprint:
                style_fp = sd.prose_fingerprint
        except Exception:  # noqa: BLE001
            pass
        new_passage = self.rewrite_agent.rewrite_passage(
            passage,
            before,
            after,
            instruction,
            chapter_id=chapter_id,
            style_fingerprint=style_fp,
        )
        # diff 校验：长度差异过大则警告但仍返回
        len_ratio = len(new_passage) / max(len(passage), 1)
        warning = ""
        if len_ratio < 0.5 or len_ratio > 2.0:
            warning = (
                f"重写后长度变化较大（{len(passage)}→{len(new_passage)}字），请人工核查"
            )
        # 拼接新全文
        new_full = ch.content[:pos] + new_passage + ch.content[after_start:]
        # 写回（自动归档旧版）
        plan = self.outline.find(chapter_id)
        if plan:
            summary = self.store.summaries.get(chapter_id)
            self.store.write_chapter(
                self.dir,
                plan,
                new_full,
                summary.summary if summary else "",
                source="revise",
            )
            self.save_all()
        return {
            "chapter_id": chapter_id,
            "old_passage": passage,
            "new_passage": new_passage,
            "warning": warning,
            "len_ratio": round(len_ratio, 2),
        }

    # ================ 文风一致性 ================
    def analyze_style(
        self, *, sample_chars: int = 6000, verbose: bool = False
    ) -> dict[str, Any]:
        """从已写正文提取文风指纹。sample_chars 控制取样总字数。"""
        from ..core.style import StyleData

        cids = self.store.ordered_ids()
        if not cids:
            raise ValueError("还没有已写章节，无法分析文风")
        # 均匀取样
        samples_parts: list[str] = []
        per = max(800, sample_chars // len(cids))
        for cid in cids:
            ch = self.store.read_chapter(self.dir, cid)
            if ch and ch.content:
                samples_parts.append(f"【{cid}】\n{ch.content[:per]}")
        samples = "\n\n".join(samples_parts)[:sample_chars]
        known = [c.name for c in self.bible.characters]
        if verbose:
            print(f"  [文风] 分析 {len(cids)} 章样本...")
        data = self.style_agent.extract_style(samples, known)
        if not data:
            return {"extracted": False}
        sd = StyleData.load(self.dir, self.project.name)
        sd.prose_summary = _to_str(data.get("prose_summary", ""))
        sd.prose_fingerprint = _to_str(data.get("prose_fingerprint", ""))
        cv = data.get("character_voices", {}) or {}
        if isinstance(cv, dict):
            sd.character_voices = {str(k): _to_str(v) for k, v in cv.items()}
        sd.last_analyzed_chapters = cids
        sd.save(self.dir)
        return {"extracted": True, "style": sd.render_for_prompt()}

    def check_style_drift(self, chapter_id: str) -> dict[str, Any]:
        """检测某章是否偏离既有文风。"""
        from ..core.style import StyleData

        sd = StyleData.load(self.dir, self.project.name)
        if not sd.prose_fingerprint:
            raise ValueError("还没有文风指纹，先用 style --analyze 提取")
        ch = self.store.read_chapter(self.dir, chapter_id)
        if not ch:
            raise ValueError(f"章节 {chapter_id} 不存在")
        result = self.style_agent.check_drift(ch.content, sd, chapter_id) or {}
        return {"chapter_id": chapter_id, "drift": result}

    def view_style(self) -> str:
        from ..core.style import StyleData

        sd = StyleData.load(self.dir, self.project.name)
        return sd.render_for_prompt() or "(暂无文风指纹，用 style --analyze 提取)"

    # ================ 搜索 ================
    def build_search_index(
        self, *, with_vectors: bool = True, verbose: bool = False
    ) -> dict[str, int]:
        """构建搜索索引（文本 + 向量）。"""
        engine = SearchEngine(self.dir)
        embedder = None
        if with_vectors:
            try:
                embedder = build_embedding(self.config.embedding)
            except Exception as e:  # noqa: BLE001
                if verbose:
                    print(f"  [搜索] embedding 不可用，仅建文本索引：{e}")
        counts = engine.index_project(
            bible=self.bible,
            continuity=self.continuity,
            world=self.world,
            ideas=self.ideas,
            store=self.store,
            project_dir=self.dir,
            embedder=embedder,
        )
        if verbose:
            print(f"  [搜索] 索引完成：{counts}")
        return counts

    def search(
        self,
        query: str,
        *,
        semantic: bool = False,
        kinds: list[str] | None = None,
        top_k: int = 10,
    ) -> list[dict[str, Any]]:
        """搜索。semantic=True 用语义搜索，否则关键词。"""
        engine = SearchEngine(self.dir)
        if not engine.docs:
            # 自动构建文本索引
            engine.index_project(
                bible=self.bible,
                continuity=self.continuity,
                world=self.world,
                ideas=self.ideas,
                store=self.store,
                project_dir=self.dir,
                embedder=None,
            )
        if semantic:
            embedder = build_embedding(self.config.embedding)
            hits = engine.search_semantic(query, embedder, kinds=kinds, top_k=top_k)
        else:
            hits = engine.search_keyword(query, kinds=kinds, limit=top_k)
        return [
            {
                "id": h.doc.id,
                "kind": h.doc.kind,
                "ref": h.doc.ref,
                "title": h.doc.title,
                "score": round(h.score, 3),
                "snippet": h.snippet,
            }
            for h in hits
        ]

    # ================ 进度仪表盘 ================
    def stats(self) -> dict[str, Any]:
        """写作进度统计。"""
        from ..core.progress import ProgressData

        pd = ProgressData.load(self.dir, self.project.name)
        all_ch = self.outline.all_chapters()
        done_ch = sum(1 for c in all_ch if c.status.value not in ("pending",))
        # 自动推算目标总字数
        if not pd.target_total_words:
            pd.target_total_words = sum(
                (c.word_target or self.chapter_words) for c in all_ch
            ) or (len(all_ch) * self.chapter_words)
        return pd.stats(total_chapters=len(all_ch), done_chapters=done_ch)

    def set_targets(
        self,
        *,
        daily_target: int | None = None,
        total_target: int | None = None,
        deadline: str | None = None,
    ) -> None:
        """设置写作目标。"""
        from ..core.progress import ProgressData

        pd = ProgressData.load(self.dir, self.project.name)
        if daily_target is not None:
            pd.daily_target = daily_target
        if total_target is not None:
            pd.target_total_words = total_target
        if deadline is not None:
            pd.deadline = deadline
        pd.save(self.dir)
