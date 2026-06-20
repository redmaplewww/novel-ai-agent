"""飞书 Bot 命令路由器。

把飞书收到的文本消息解析成命令，调用 NovelAgent 对应功能，返回文本回复。
完全不依赖飞书 SDK，可独立单元测试。

命令格式（前缀 # 或 /）：
    #帮助 / #help              列出所有命令
    #项目 [名字]                查看/切换默认项目
    #想法 <内容> [#标签] [@人物] 记录灵感到 idea 库
    #想法列表                   查看灵感
    #下一章                     写下一章（长任务，异步）
    #进度                       查看写作进度
    #大纲                       查看大纲
    #预览 [章节id]              预览章节正文
    #搜索 <关键词>              全文搜索
    #设定                       查看设定集
    #连续性                     查看连续性追踪表
    #节奏                       查看节奏曲线
    #文风                       查看文风指纹
    #成本                       查看成本统计
    #知识库 / #kb               查看完整知识库
    #备份                       手动备份
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable

from ..agents import NovelAgent
from ..config import Config


@dataclass
class CommandResult:
    """命令执行结果。"""

    text: str = ""  # 回复文本
    is_task: bool = False  # 是否长任务（需异步）
    task_kind: str = ""  # 任务类型（write 等）
    task_args: dict[str, Any] = field(default_factory=dict)
    project: str = ""  # 涉及的项目


class CommandRouter:
    """解析飞书消息 → 调用 NovelAgent → 返回 CommandResult。"""

    HELP_TEXT = """📖 小说AI 飞书助手 · 命令列表

💡 记录想法思路：
  #想法 <内容> [#标签] [@人物]   记录灵感到 idea 库
  #想法列表                       查看所有灵感

🚀 推进小说进度：
  #下一章                         写下一章（约1-3分钟，完成后推送）
  #进度                           查看写作进度仪表盘

👀 预览生成结果：
  #预览 [章节id]                  预览章节正文（默认最新章）
  #预览 下一章                    预览下一个待写章节的计划

🔍 查询 Agent 状态：
  #项目 [名字]                    查看/切换当前项目
  #大纲                           查看故事大纲
  #设定                           查看设定集（人物/地点/势力）
  #连续性                         查看连续性追踪（伏笔/承诺/事实）
  #节奏                           查看节奏曲线分析
  #文风                           查看文风指纹
  #搜索 <关键词>                  全文搜索
  #知识库                         查看完整知识库
  #成本                           查看成本统计

🛠️ 其他：
  #备份                           手动备份项目
  #帮助                           显示本帮助

提示：项目名可在任意命令后加，如 #下一章 mybook；不写则用默认项目。"""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.default_project: str = config.feishu.get("default_project", "") or "demo"
        self.max_chars: int = int(config.feishu.get("max_msg_chars", 2800))

    # ============ 入口 ============
    def handle(self, raw_text: str) -> CommandResult:
        """处理一条消息，返回结果。"""
        text = raw_text.strip()
        if not text:
            return CommandResult(text="（空消息）")

        # 解析命令：支持 #cmd 或 /cmd 开头
        m = re.match(r"^[#/]\s*([^\s]+)\s*(.*)$", text, re.DOTALL)
        if not m:
            # 没有命令前缀，提示用法
            return CommandResult(
                text=f"未识别的命令。消息请以 # 开头。\n\n发送 #帮助 查看可用命令。"
            )
        cmd = m.group(1).lower()
        rest = m.group(2).strip()

        # 帮助
        if cmd in ("帮助", "help", "?", "？"):
            return CommandResult(text=self.HELP_TEXT)

        # 解析可能附带的项目名（rest 末尾的英文标识符）
        project, rest_args = self._parse_project(rest)

        # 路由
        handlers: dict[str, Callable[[str, str], CommandResult]] = {
            "项目": self._cmd_project,
            "project": self._cmd_project,
            "想法": self._cmd_idea,
            "idea": self._cmd_idea,
            "灵感": self._cmd_idea,
            "想法列表": self._cmd_idea_list,
            "idealist": self._cmd_idea_list,
            "下一章": self._cmd_next_chapter,
            "next": self._cmd_next_chapter,
            "进度": self._cmd_progress,
            "progress": self._cmd_progress,
            "大纲": self._cmd_outline,
            "outline": self._cmd_outline,
            "预览": self._cmd_preview,
            "preview": self._cmd_preview,
            "搜索": self._cmd_search,
            "search": self._cmd_search,
            "设定": self._cmd_bible,
            "bible": self._cmd_bible,
            "连续性": self._cmd_continuity,
            "continuity": self._cmd_continuity,
            "节奏": self._cmd_pacing,
            "pacing": self._cmd_pacing,
            "文风": self._cmd_style,
            "style": self._cmd_style,
            "知识库": self._cmd_kb,
            "kb": self._cmd_kb,
            "成本": self._cmd_cost,
            "cost": self._cmd_cost,
            "备份": self._cmd_backup,
            "backup": self._cmd_backup,
        }
        handler = handlers.get(cmd)
        if handler is None:
            return CommandResult(text=f"未知命令：#{cmd}\n\n发送 #帮助 查看可用命令。")
        try:
            return handler(project, rest_args)
        except Exception as e:  # noqa: BLE001
            return CommandResult(text=f"⚠️ 命令执行出错：{e}")

    # ============ 工具 ============
    def _parse_project(self, rest: str) -> tuple[str, str]:
        """从参数末尾抠出项目名（连续的英文/数字/_）。"""
        m = re.search(r"\s+([A-Za-z0-9_\-]+)\s*$", rest)
        if m:
            proj = m.group(1)
            # 排除一些不是项目名的词
            if proj.lower() not in ("下一章", "列表"):
                return proj, rest[: m.start()].rstrip()
        return self.default_project, rest

    def _open(self, project: str) -> NovelAgent:
        return NovelAgent.open(project or self.default_project, self.config)

    def _truncate(self, text: str) -> str:
        if len(text) <= self.max_chars:
            return text
        return (
            text[: self.max_chars]
            + f"\n\n…（共 {len(text)} 字，已截断。用 CLI 查看完整内容）"
        )

    # ============ 各命令实现 ============
    def _cmd_project(self, project: str, args: str) -> CommandResult:
        if not args:
            projects = NovelAgent.list_projects()
            return CommandResult(
                text=f"当前默认项目：{self.default_project}\n\n所有项目：\n"
                + "\n".join(
                    f"  • {p}{' ← 默认' if p == self.default_project else ''}"
                    for p in projects
                )
                + "\n\n用 #项目 <名字> 切换默认项目。"
            )
        # 切换
        self.default_project = args.strip()
        return CommandResult(
            text=f"✓ 已切换默认项目为：{self.default_project}",
            project=self.default_project,
        )

    def _cmd_idea(self, project: str, args: str) -> CommandResult:
        if not args.strip():
            return CommandResult(
                text="用法：#想法 <内容> [#标签] [@人物]\n\n例：#想法 主角在悬崖获得传承 #转折 @林尘"
            )
        agent = self._open(project)
        # 解析标签和人物
        tags = re.findall(r"#([^\s#@]+)", args)
        chars = re.findall(r"@([^\s#@]+)", args)
        # 剩下的纯内容
        content = re.sub(r"[#@][^\s#@]+", "", args).strip()
        if not content:
            content = args.strip()
        idea = agent.kb.add_idea(
            content,
            type="other",
            tags=tags,
            related_chars=chars,
            priority=3,
        )
        return CommandResult(
            text=f"✓ 灵感已记录 [{idea.id}]\n\n📝 {content}\n"
            + (f"🏷 标签：{', '.join(tags)}\n" if tags else "")
            + (f"👥 人物：{', '.join(chars)}\n" if chars else "")
            + f"\n💡 共 {len(agent.kb.ideas.ideas)} 条灵感待用。用 #想法列表 查看。",
            project=project,
        )

    def _cmd_idea_list(self, project: str, args: str) -> CommandResult:
        agent = self._open(project)
        pool = agent.kb.ideas.available()
        if not pool:
            return CommandResult(text="（暂无可用灵感）", project=project)
        lines = [f"💡 可用灵感（{len(pool)} 条）："]
        for i in sorted(pool, key=lambda x: -x.priority):
            status_mark = "📌" if i.status.value == "planned" else "💡"
            head = f"\n{status_mark} [{i.id}|优先级{i.priority}] {i.title}"
            if i.placed_chapter:
                head += f" → 计划放 {i.placed_chapter}"
            lines.append(head)
            lines.append(f"   {i.content[:60]}")
        return CommandResult(text=self._truncate("\n".join(lines)), project=project)

    def _cmd_next_chapter(self, project: str, args: str) -> CommandResult:
        agent = self._open(project)
        # 找下一个待写章节
        from ..core import ChapterStatus

        nxt = next(
            (
                c
                for c in agent.outline.all_chapters()
                if c.status == ChapterStatus.pending
            ),
            None,
        )
        if nxt is None:
            return CommandResult(
                text="🎉 全部章节已写完！没有待写章节了。", project=project
            )
        # 长任务：返回标记，由 bot 层异步执行
        return CommandResult(
            text=f"⏳ 开始写 {nxt.chapter_id} 《{nxt.title}》...\n预计 1-3 分钟，完成后自动推送。",
            is_task=True,
            task_kind="write",
            task_args={"chapter_id": nxt.chapter_id, "project": project},
            project=project,
        )

    def _cmd_progress(self, project: str, args: str) -> CommandResult:
        agent = self._open(project)
        s = agent.stats()
        bar_len = 10
        ch_bar = "█" * int(s["chapter_progress"] / 100 * bar_len) + "░" * (
            bar_len - int(s["chapter_progress"] / 100 * bar_len)
        )
        text = (
            f"📊 《{agent.project.title or project}》写作进度\n\n"
            f"章节：{ch_bar} {s['done_chapters']}/{s['total_chapters']} ({s['chapter_progress']}%)\n"
            f"总字数：{s['total_words']:,} / {s['target_total']:,} ({s['target_progress']}%)\n"
            f"今日：{s['today_words']:,} / {s['daily_target']} ({s['today_progress']}%)\n"
            f"近7天日均：{s['avg_7d']:.0f} 字\n"
            f"连续打卡：{s['streak_days']} 天\n"
        )
        if s["eta_days"] > 0:
            text += f"预计完本：{s['eta_date']}（还需 {s['eta_days']} 天）\n"
        return CommandResult(text=text, project=project)

    def _cmd_outline(self, project: str, args: str) -> CommandResult:
        agent = self._open(project)
        return CommandResult(
            text=self._truncate(agent.outline.render_for_prompt()), project=project
        )

    def _cmd_preview(self, project: str, args: str) -> CommandResult:
        agent = self._open(project)
        args = args.strip()
        if args in ("下一章", "next", "计划"):
            # 预览下一个待写章节的计划
            from ..core import ChapterStatus

            nxt = next(
                (
                    c
                    for c in agent.outline.all_chapters()
                    if c.status == ChapterStatus.pending
                ),
                None,
            )
            if nxt is None:
                return CommandResult(text="没有待写章节了。", project=project)
            return CommandResult(
                text=f"📋 下一章计划：\n\n{nxt.render_for_prompt()}", project=project
            )
        # 预览已写章节
        if args:
            cid = args
        else:
            cids = agent.store.ordered_ids()
            if not cids:
                return CommandResult(text="还没有已写章节。", project=project)
            cid = cids[-1]
        ch = agent.store.read_chapter(agent.dir, cid)
        if not ch:
            return CommandResult(text=f"章节 {cid} 不存在。", project=project)
        head = f"📖 {cid} 《{ch.title}》({ch.word_count}字)\n\n"
        return CommandResult(text=self._truncate(head + ch.content), project=project)

    def _cmd_search(self, project: str, args: str) -> CommandResult:
        if not args.strip():
            return CommandResult(text="用法：#搜索 <关键词>", project=project)
        agent = self._open(project)
        hits = agent.search(args.strip(), top_k=8)
        if not hits:
            return CommandResult(
                text=f"未找到「{args.strip()}」相关内容。", project=project
            )
        lines = [f"🔍 搜索「{args.strip()}」共 {len(hits)} 条："]
        kind_emoji = {
            "chapter": "📖",
            "summary": "📝",
            "character": "👤",
            "location": "📍",
            "foreshadow": "🔮",
            "fact": "📌",
            "promise": "🤝",
            "world": "🌍",
            "idea": "💡",
        }
        for h in hits:
            emoji = kind_emoji.get(h["kind"], "•")
            lines.append(f"\n{emoji} {h['title']} [{h['kind']}] score:{h['score']}")
            if h["snippet"]:
                lines.append(f"   {h['snippet'][:70]}")
        return CommandResult(text=self._truncate("\n".join(lines)), project=project)

    def _cmd_bible(self, project: str, args: str) -> CommandResult:
        agent = self._open(project)
        return CommandResult(
            text=self._truncate(agent.bible.render_for_prompt()), project=project
        )

    def _cmd_continuity(self, project: str, args: str) -> CommandResult:
        agent = self._open(project)
        text = agent.view_continuity()
        return CommandResult(text=self._truncate(text), project=project)

    def _cmd_pacing(self, project: str, args: str) -> CommandResult:
        agent = self._open(project)
        text = agent.view_pacing()
        if "暂无节奏数据" in text:
            return CommandResult(
                text="暂无节奏数据。请先用 CLI 运行 `python cli.py pacing {} --analyze` 生成。".format(
                    project
                ),
                project=project,
            )
        return CommandResult(text=self._truncate(text), project=project)

    def _cmd_style(self, project: str, args: str) -> CommandResult:
        agent = self._open(project)
        text = agent.view_style()
        if "暂无文风指纹" in text:
            return CommandResult(
                text="暂无文风指纹。请先用 CLI 运行 `python cli.py style {} --analyze` 提取。".format(
                    project
                ),
                project=project,
            )
        return CommandResult(text=self._truncate(text), project=project)

    def _cmd_kb(self, project: str, args: str) -> CommandResult:
        agent = self._open(project)
        return CommandResult(
            text=self._truncate(agent.kb.render_full()), project=project
        )

    def _cmd_cost(self, project: str, args: str) -> CommandResult:
        agent = self._open(project)
        s = agent.cost_summary()
        text = (
            f"💰 成本统计《{project}》\n\n"
            f"总调用：{s['total_calls']} 次\n"
            f"总成本：¥{s['total_cost']}\n"
            f"输入：{s['total_prompt_tokens']:,} tok（缓存 {s['total_cached_tokens']:,}）\n"
            f"输出：{s['total_completion_tokens']:,} tok\n"
        )
        if s.get("by_op"):
            text += "\n按操作：\n"
            for op, v in sorted(s["by_op"].items(), key=lambda x: -x[1]["cost"]):
                text += f"  {op}: {v['calls']}次 ¥{v['cost']}\n"
        return CommandResult(text=text, project=project)

    def _cmd_backup(self, project: str, args: str) -> CommandResult:
        agent = self._open(project)
        from pathlib import Path

        p = agent.backup()
        size_kb = round(p.stat().st_size / 1024, 1)
        return CommandResult(
            text=f"✓ 已备份：{p.name}（{size_kb} KB）", project=project
        )
