"""小说AI 命令行入口。

用法示例：
    python cli.py test                       # 测试后端连通性
    python cli.py new mybook --genre 玄幻 --synopsis "..."  # 新建项目
    python cli.py list                       # 列出项目
    python cli.py init mybook --chapters 20  # 从简介生成主线+大纲+设定
    python cli.py outline mybook             # 查看大纲
    python cli.py bible mybook               # 查看设定集
    python cli.py write mybook               # 写下一章
    python cli.py write mybook c001          # 写指定章节
    python cli.py batch mybook 5             # 连写 5 章
    python cli.py export mybook              # 导出全文 markdown
"""

from __future__ import annotations

import argparse
import sys

# Windows 控制台默认 GBK，强制 UTF-8 以支持 ✓✗ 等符号
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

from novel_agent import Config
from novel_agent.agents import NovelAgent
from novel_agent.core.outline import ChapterStatus


def _print(msg: str = "") -> None:
    print(msg)


def cmd_test(args: argparse.Namespace) -> int:
    cfg = Config(args.config)
    _print(f"后端: {cfg.backend}")
    try:
        # 临时建一个空项目目录的 agent 来访问 backend
        from novel_agent.llm import build_backend

        b = build_backend(cfg)
        _print("连通性测试中...")
        reply = b.test()
        _print(f"✓ 后端可用。模型回复：{reply}")
        return 0
    except Exception as e:  # noqa: BLE001
        _print(f"✗ 后端不可用：{e}")
        return 1


def cmd_new(args: argparse.Namespace) -> int:
    cfg = Config(args.config)
    kwargs = {
        "name": args.name,
        "title": args.title or args.name,
        "genre": args.genre or "",
        "style": args.style or "",
        "audience": args.audience or "",
        "logline": args.logline or "",
        "synopsis": args.synopsis or "",
        "worldview": args.worldview or "",
        "notes": args.notes or "",
    }
    try:
        agent = NovelAgent.create(cfg, **kwargs)
    except FileExistsError:
        _print(f"✗ 项目已存在：{args.name}")
        return 1
    _print(f"✓ 已创建项目 [{args.name}] @ {agent.dir}")
    _print(f"  书名：{agent.project.title}")
    if args.synopsis and args.init:
        _print("\n自动生成主线/大纲/设定集...")
        r = agent.init_from_synopsis(chapter_count=args.chapters)
        _print(f"  主线：{agent.outline.premise}")
        _print(f"  卷数：{r.get('volume_count')}，章节：{r.get('chapter_count')}")
        _print(f"  设定条目：{r.get('bible_entries', 0)}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    projects = NovelAgent.list_projects()
    if not projects:
        _print("(暂无项目，用 new 创建)")
        return 0
    _print("项目列表：")
    for name in projects:
        try:
            from novel_agent.core.project import Project

            p = Project.load(name)
            ch_count = 0
            outline_path = p.dir / "outline.json"
            if outline_path.exists():
                import json

                d = json.loads(outline_path.read_text(encoding="utf-8"))
                for v in d.get("volumes", []):
                    ch_count += len(v.get("chapters", []))
            _print(f"  • {name}  《{p.title}》  [{p.genre}]  大纲:{ch_count}章")
        except Exception as e:  # noqa: BLE001
            _print(f"  • {name}  (读取失败: {e})")
    return 0


def cmd_init(args: argparse.Namespace) -> int:
    cfg = Config(args.config)
    agent = NovelAgent.open(args.project, cfg)
    _print(f"生成主线/大纲/设定集（目标 {args.chapters} 章）...")
    r = agent.init_from_synopsis(
        chapter_count=args.chapters, auto_bible=not args.no_bible
    )
    _print(f"✓ 主线：{agent.outline.premise}")
    _print(f"✓ 卷数：{r.get('volume_count')}，章节：{r.get('chapter_count')}")
    _print(f"✓ 设定条目：{r.get('bible_entries', 0)}")
    return 0


def cmd_outline(args: argparse.Namespace) -> int:
    cfg = Config(args.config)
    agent = NovelAgent.open(args.project, cfg)
    _print(agent.outline.render_for_prompt())
    pending = sum(
        1 for c in agent.outline.all_chapters() if c.status == ChapterStatus.pending
    )
    drafted = sum(
        1 for c in agent.outline.all_chapters() if c.status != ChapterStatus.pending
    )
    _print(f"\n[统计] 待写 {pending} 章，已完成 {drafted} 章")
    return 0


def cmd_bible(args: argparse.Namespace) -> int:
    cfg = Config(args.config)
    agent = NovelAgent.open(args.project, cfg)
    _print(agent.bible.render_for_prompt())
    return 0


def cmd_write(args: argparse.Namespace) -> int:
    cfg = Config(args.config)
    agent = NovelAgent.open(args.project, cfg)
    review = args.review if args.review is not None else None
    if args.no_review:
        review = False
    if args.chapter:
        _print(f"写章节 {args.chapter} ...")
        r = agent.write_chapter(args.chapter, review=review, verbose=True)
    else:
        _print("写下一章 ...")
        r = agent.write_next(review=review, verbose=True)
        if r is None:
            _print("没有待写章节了，全部完成！")
            return 0
    _print(f"\n✓ 章节 {r['chapter_id']} 《{r['title']}》  字数：{r['word_count']}")
    # 状态追踪摘要
    tk = r.get("tracking") or {}
    if tk.get("extracted"):
        cu = tk.get("bible_characters_updated", 0)
        cont = tk.get("continuity", {}) or {}
        tot = sum(cont.values())
        _print(f"✓ 状态追踪：更新 {cu} 个人物，新增 {tot} 条连续性记录")
        for k, v in cont.items():
            if v:
                _print(f"    · {k}: +{v}")
    if args.full:
        _print("\n" + "=" * 50)
        _print(r["content"])
    else:
        _print(f"摘要：{r['summary']}")
    if r.get("review"):
        rv = r["review"].get("review") or r["review"]
        dev = rv.get("deviation") or {}
        if dev.get("deviated"):
            _print(f"\n[偏离大纲:{dev.get('degree')}] {dev.get('description', '')}")
        _print(f"\n[审校评分] {rv.get('score', '-')}  {rv.get('overall', '')}")
    return 0


def cmd_batch(args: argparse.Namespace) -> int:
    cfg = Config(args.config)
    agent = NovelAgent.open(args.project, cfg)
    review = not args.no_review
    for i, r in enumerate(
        agent.write_batch(args.count, review=review, verbose=True), 1
    ):
        _print(
            f"[{i}/{args.count}] ✓ {r['chapter_id']} 《{r['title']}》 {r['word_count']}字"
        )
    _print("批量完成。")
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    cfg = Config(args.config)
    agent = NovelAgent.open(args.project, cfg)
    path = agent.export_to_file(args.output)
    _print(f"✓ 已导出：{path}")
    return 0


def cmd_track(args: argparse.Namespace) -> int:
    cfg = Config(args.config)
    agent = NovelAgent.open(args.project, cfg)
    if args.all:
        _print("对全部已写章节补跑状态追踪...")
        reports = agent.track_all(verbose=True)
        for r in reports:
            if r.get("extracted"):
                cu = r.get("bible_characters_updated", 0)
                cont = r.get("continuity", {}) or {}
                tot = sum(cont.values())
                _print(f"  ✓ 更新 {cu} 个人物，新增 {tot} 条连续性记录")
        _print("✓ 补跑完成")
        return 0
    if args.chapter:
        _print(f"对 {args.chapter} 跑状态追踪...")
        r = agent.track_chapter(args.chapter, verbose=True)
        if r.get("extracted"):
            cu = r.get("bible_characters_updated", 0)
            cont = r.get("continuity", {}) or {}
            _print(f"✓ 更新 {cu} 个人物，新增 {sum(cont.values())} 条连续性记录")
        else:
            _print("⚠ 未能提取（模型未返回有效结果）")
        return 0
    # 默认：只展示连续性表
    _print(agent.view_continuity())
    return 0


# ============ 知识库统一命令 ============
def cmd_kb(args: argparse.Namespace) -> int:
    """知识库统一入口：idea / world / threads / timeline。"""
    cfg = Config(args.config)
    agent = NovelAgent.open(args.project, cfg)
    sub = args.kb_cmd

    if sub == "view":
        _print(agent.view_kb())
        return 0

    if sub == "idea":
        if args.idea_add:
            idea = agent.kb.add_idea(
                args.idea_add,
                title=args.title or "",
                type=args.type or "other",
                tags=args.tags.split(",") if args.tags else [],
                priority=args.priority or 3,
                related_chars=args.chars.split(",") if args.chars else [],
            )
            _print(f"✓ 已添加 idea {idea.id}: {idea.title}")
            return 0
        if args.idea_list:
            pool = agent.kb.query_ideas(
                type=args.type,
                status=args.status,
                tag=args.tag,
                char=args.char,
                keyword=args.keyword,
            )
            if not pool:
                _print("(没有匹配的 idea)")
                return 0
            for i in pool:
                _print(
                    f"  [{i.id}|{i.type.value}|{i.status.value}|优先级{i.priority}] {i.title}"
                )
                if i.content:
                    _print(f"     {i.content[:80]}")
            return 0
        if args.idea_used:
            ok = agent.kb.mark_idea_used(args.idea_used, args.chapter or "")
            _print("✓ 已标记已用" if ok else "✗ 找不到该 idea")
            return 0
        # 默认列出
        for i in agent.kb.ideas.ideas:
            _print(f"  [{i.id}|{i.type.value}|{i.status.value}] {i.title}")
        return 0

    if sub == "world":
        if args.build:
            _print("搭建世界观...")
            r = agent.build_world(focus=args.focus or "")
            _print(f"✓ 世界观总纲：{r.get('premise', '')}")
            _print(f"✓ 新增 {r.get('elements_added', 0)} 个元素")
            return 0
        _print(agent.kb.world.render_for_prompt() or "(暂无世界观，用 --build 生成)")
        return 0

    if sub == "threads":
        if args.weave:
            _print("串联故事线...")
            r = agent.weave_threads(target_chapters=args.chapters or 5)
            _print(
                f"✓ 新增 {r.get('threads_added', 0)} 条线，{r.get('nodes_added', 0)} 个节点"
            )
            if r.get("notes"):
                _print(f"串联说明：{r['notes']}")
            return 0
        _print(
            agent.kb.threads.render_for_prompt(only_active=False)
            or "(暂无故事线，用 --weave 生成)"
        )
        return 0

    if sub == "timeline":
        _print("时间线校核中...")
        r = agent.audit_timeline()
        _print(f"一致性：{'✓ 自洽' if r.get('consistent') else '✗ 存在冲突'}")
        conflicts = r.get("conflicts", []) or []
        if conflicts:
            _print(f"\n发现 {len(conflicts)} 个冲突：")
            for c in conflicts:
                _print(
                    f"  [{c.get('severity')}|{c.get('type')}] {c.get('description')}"
                )
                _print(f"    → 建议：{c.get('suggestion')}")
        else:
            _print("无冲突。")
        nl = r.get("normalized_timeline", [])
        if nl:
            _print("\n归一化时间线：")
            for e in nl:
                _print(
                    f"  • {e.get('chapter_id')} [{e.get('anchor')}] {e.get('event', '')[:50]}"
                )
        if r.get("overall"):
            _print(f"\n总体：{r['overall']}")
        return 0

    if sub == "place":
        _print("分析 idea 安插建议...")
        r = agent.place_ideas()
        for p in r.get("placements", []):
            _print(
                f"  {p.get('idea_id')} → {p.get('suggested_chapter')} [{p.get('confidence')}]"
            )
            _print(f"    理由：{p.get('reason')}")
            _print(f"    方式：{p.get('how')}")
        for u in r.get("unsuitable", []):
            _print(f"  {u.get('idea_id')} 暂不适合：{u.get('reason')}")
        return 0

    _print("用法: kb <project> {view,idea,world,threads,timeline,place} ...")
    return 1


# ============ 新功能命令 ============
def cmd_cost(args: argparse.Namespace) -> int:
    cfg = Config(args.config)
    agent = NovelAgent.open(args.project, cfg)
    s = agent.cost_summary()
    _print(f"=== 成本统计 ===")
    _print(f"总调用: {s['total_calls']} 次")
    _print(f"总成本: ¥{s['total_cost']}")
    _print(
        f"输入token: {s['total_prompt_tokens']:,} (缓存命中 {s['total_cached_tokens']:,})"
    )
    _print(f"输出token: {s['total_completion_tokens']:,}")
    if s.get("by_op"):
        _print("\n按操作：")
        for op, v in sorted(s["by_op"].items(), key=lambda x: -x[1]["cost"]):
            _print(f"  {op}: {v['calls']}次 ¥{v['cost']} {v['tokens']:,}tok")
    if s.get("by_chapter"):
        _print("\n按章节：")
        for cid, v in sorted(s["by_chapter"].items(), key=lambda x: -x[1]["cost"])[:10]:
            _print(f"  {cid}: {v['calls']}次 ¥{v['cost']}")
    if s.get("by_day"):
        _print("\n按天：")
        for day, v in sorted(s["by_day"].items()):
            _print(f"  {day}: {v['calls']}次 ¥{v['cost']}")
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    cfg = Config(args.config)
    agent = NovelAgent.open(args.project, cfg)
    if args.reindex:
        _print("重建搜索索引...")
        c = agent.build_search_index(with_vectors=not args.keyword_only, verbose=True)
        _print(f"✓ 索引：{c}")
        return 0
    if not args.query:
        _print("请提供搜索词")
        return 1
    hits = agent.search(args.query, semantic=args.semantic, top_k=args.top or 10)
    if not hits:
        _print(f"(未找到「{args.query}」相关内容)")
        return 0
    _print(
        f"搜索「{args.query}」（{'语义' if args.semantic else '关键词'}）共 {len(hits)} 条："
    )
    for i, h in enumerate(hits, 1):
        _print(
            f"\n[{i}] {h['kind']} | {h['title']} (ref:{h['ref']}, score:{h['score']})"
        )
        if h["snippet"]:
            _print(f"    {h['snippet']}")
    return 0


def cmd_pacing(args: argparse.Namespace) -> int:
    cfg = Config(args.config)
    agent = NovelAgent.open(args.project, cfg)
    if args.analyze:
        r = agent.analyze_pacing(args.chapter, verbose=True)
        _print(r["curve"])
        if r["problems"]:
            _print("\n⚠ 检测到的问题：")
            for p in r["problems"]:
                _print(
                    f"  [{p.get('type')}|{p.get('severity')}] {p.get('description')}"
                )
        if r["suggestions"]:
            _print("\n建议：")
            for s in r["suggestions"]:
                _print(f"  • {s}")
        return 0
    _print(agent.view_pacing())
    return 0


def cmd_rewrite(args: argparse.Namespace) -> int:
    cfg = Config(args.config)
    agent = NovelAgent.open(args.project, cfg)
    r = agent.rewrite_passage(
        args.chapter, args.passage, args.to, context_chars=args.context or 400
    )
    _print(f"=== 局部重写 {args.chapter} ===")
    _print(f"\n【原文】{r['old_passage']}")
    _print(f"\n【重写后】{r['new_passage']}")
    if r.get("warning"):
        _print(f"\n⚠ {r['warning']}")
    _print(f"\n长度比: {r['len_ratio']}x")
    return 0


def cmd_style(args: argparse.Namespace) -> int:
    cfg = Config(args.config)
    agent = NovelAgent.open(args.project, cfg)
    if args.analyze:
        r = agent.analyze_style(verbose=True)
        if r.get("extracted"):
            _print("✓ 文风指纹已提取：")
            _print(r["style"])
        else:
            _print("✗ 提取失败")
        return 0
    if args.check:
        r = agent.check_style_drift(args.check)
        drift = r.get("drift", {})
        _print(f"=== 文风漂移检测 {args.check} ===")
        _print(f"漂移度: {drift.get('drift_score', '-')}/10")
        _print(drift.get("overall", ""))
        for issue in drift.get("prose_issues", []) or []:
            _print(f"  [文风/{issue.get('severity')}] {issue.get('description')}")
        for issue in drift.get("dialogue_issues", []) or []:
            _print(
                f"  [对话/{issue.get('severity')}] {issue.get('character')}: {issue.get('description')}"
            )
        return 0
    _print(agent.view_style())
    return 0


def cmd_backup(args: argparse.Namespace) -> int:
    cfg = Config(args.config)
    agent = NovelAgent.open(args.project, cfg)
    if args.list:
        for b in agent.list_backups():
            _print(f"  {b['name']}  {b['size_kb']}KB")
        return 0
    p = agent.backup()
    _print(f"✓ 已备份: {p.name} ({round(p.stat().st_size / 1024, 1)}KB)")
    return 0


def cmd_version(args: argparse.Namespace) -> int:
    cfg = Config(args.config)
    agent = NovelAgent.open(args.project, cfg)
    if args.list:
        vs = agent.list_versions(args.chapter)
        if not vs:
            _print(f"(章节 {args.chapter} 无历史版本)")
        for v in vs:
            _print(
                f"  v{v.get('version')} | {v.get('word_count')}字 | {v.get('source')} | {v.get('ts')}"
            )
        return 0
    if args.rollback:
        r = agent.rollback_version(args.chapter, args.rollback)
        if r:
            _print(f"✓ 已回滚 {args.chapter} 到 v{args.rollback}（{r.word_count}字）")
        else:
            _print(f"✗ 找不到版本 v{args.rollback}")
        return 0
    if args.diff:
        v1, v2 = (
            (args.diff.split(",") + [1])[:2]
            if "," in str(args.diff)
            else (0, int(args.diff))
        )
        d = agent.diff_versions(args.chapter, int(v1), int(v2))
        _print(f"=== diff {args.chapter} v{v1} vs v{v2} ===")
        if d["added"]:
            _print("+ 新增：")
            for line in d["added"][:20]:
                _print(f"  {line}")
        if d["removed"]:
            _print("- 删除：")
            for line in d["removed"][:20]:
                _print(f"  {line}")
        if not d["added"] and not d["removed"]:
            _print("(无差异)")
        return 0
    # 默认列出版本
    vs = agent.list_versions(args.chapter)
    _print(f"章节 {args.chapter} 共 {len(vs)} 个历史版本")
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    cfg = Config(args.config)
    agent = NovelAgent.open(args.project, cfg)
    if args.target:
        agent.set_targets(daily_target=args.target)
        _print(f"✓ 已设置每日目标: {args.target}字")
        return 0
    if args.total:
        agent.set_targets(total_target=args.total)
        _print(f"✓ 已设置目标总字数: {args.total}")
        return 0
    s = agent.stats()
    _print(f"=== 写作进度 ===")
    _print(f"总字数: {s['total_words']:,}")
    _print(f"今日: {s['today_words']:,} / {s['daily_target']} ({s['today_progress']}%)")
    _print(f"近7天日均: {s['avg_7d']:.0f}")
    _print(f"连续打卡: {s['streak_days']}天")
    _print(
        f"章节进度: {s['done_chapters']}/{s['total_chapters']} ({s['chapter_progress']}%)"
    )
    _print(f"目标总字数: {s['target_total']:,} (已完成 {s['target_progress']}%)")
    if s["eta_days"] > 0:
        _print(f"预计完本: 还需 {s['eta_days']}天 → {s['eta_date']}")
    if s["recent_days"]:
        _print(f"\n近{len(s['recent_days'])}天字数：")
        for d, w in zip(s["recent_days"], s["recent_words"]):
            bar = "█" * min(int(w / 500), 20)
            _print(f"  {d}: {w:>5} {bar}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="novel", description="小说AI —— 基于 LLM 的中文小说写作 Agent"
    )
    p.add_argument("--config", default=None, help="配置文件路径（默认 config.yaml）")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("test", help="测试后端连通性")
    sp.set_defaults(func=cmd_test)

    sp = sub.add_parser("new", help="新建项目")
    sp.add_argument("name", help="项目目录名（英文/数字）")
    sp.add_argument("--title", help="书名")
    sp.add_argument("--genre", help="题材")
    sp.add_argument("--style", help="风格")
    sp.add_argument("--audience", help="目标读者")
    sp.add_argument("--logline", help="一句话简介")
    sp.add_argument("--synopsis", help="故事简介")
    sp.add_argument("--worldview", help="世界观")
    sp.add_argument("--notes", help="备注")
    sp.add_argument("--init", action="store_true", help="创建后立即生成大纲/设定")
    sp.add_argument(
        "--chapters", type=int, default=20, help="目标章节数（配合 --init）"
    )
    sp.set_defaults(func=cmd_new)

    sp = sub.add_parser("list", help="列出所有项目")
    sp.set_defaults(func=cmd_list)

    sp = sub.add_parser("init", help="为已有项目生成主线/大纲/设定集")
    sp.add_argument("project", help="项目名")
    sp.add_argument("--chapters", type=int, default=20)
    sp.add_argument("--no-bible", action="store_true", help="跳过设定集生成")
    sp.set_defaults(func=cmd_init)

    sp = sub.add_parser("outline", help="查看大纲")
    sp.add_argument("project")
    sp.set_defaults(func=cmd_outline)

    sp = sub.add_parser("bible", help="查看设定集")
    sp.add_argument("project")
    sp.set_defaults(func=cmd_bible)

    sp = sub.add_parser("write", help="写章节")
    sp.add_argument("project")
    sp.add_argument("chapter", nargs="?", help="章节 id（如 c001），省略则写下一章")
    sp.add_argument(
        "--review", dest="review", action="store_true", default=None, help="强制审校"
    )
    sp.add_argument("--no-review", action="store_true", help="跳过审校")
    sp.add_argument("--full", action="store_true", help="打印完整正文")
    sp.set_defaults(func=cmd_write)

    sp = sub.add_parser("batch", help="连续写多章")
    sp.add_argument("project")
    sp.add_argument("count", type=int, help="连写章数")
    sp.add_argument("--no-review", action="store_true")
    sp.set_defaults(func=cmd_batch)

    sp = sub.add_parser("export", help="导出全文 markdown")
    sp.add_argument("project")
    sp.add_argument("--output", "-o", help="输出文件路径")
    sp.set_defaults(func=cmd_export)

    sp = sub.add_parser("track", help="查看/补跑状态追踪（连续性表）")
    sp.add_argument("project")
    sp.add_argument("chapter", nargs="?", help="对指定章节补跑追踪；省略则只查看")
    sp.add_argument("--all", action="store_true", help="对全部已写章节补跑")
    sp.set_defaults(func=cmd_track)

    # 知识库统一入口
    sp = sub.add_parser(
        "kb", help="统一知识库：idea灵感/世界观/故事线/时间线校核/idea安插"
    )
    sp.add_argument("project")
    sp.add_argument(
        "kb_cmd", choices=["view", "idea", "world", "threads", "timeline", "place"]
    )
    # idea 选项
    sp.add_argument("--add", dest="idea_add", help="添加 idea（内容）")
    sp.add_argument(
        "--list", dest="idea_list", action="store_true", help="列出/筛选 idea"
    )
    sp.add_argument("--used", dest="idea_used", help="标记某 idea 已使用（传 idea id）")
    sp.add_argument("--type", help="idea类型/筛选类型")
    sp.add_argument("--status", help="筛选状态")
    sp.add_argument("--tag", help="筛选标签")
    sp.add_argument("--char", dest="char", help="筛选相关人物")
    sp.add_argument("--keyword", help="关键词搜索")
    sp.add_argument("--title", help="idea 标题")
    sp.add_argument("--tags", help="idea 标签(逗号分隔)")
    sp.add_argument("--chars", dest="chars", help="idea 相关人物(逗号分隔)")
    sp.add_argument("--priority", type=int, help="idea 优先级1-5")
    sp.add_argument("--chapter", help="章节id（配合 --used）")
    # world 选项
    sp.add_argument("--build", action="store_true", help="搭建/补全世界观")
    sp.add_argument("--focus", help="世界观重点补全方向")
    # threads 选项
    sp.add_argument("--weave", action="store_true", help="串联故事线")
    sp.add_argument("--chapters", type=int, help="串联目标章数")
    sp.set_defaults(func=cmd_kb)

    # 成本统计
    sp = sub.add_parser("cost", help="LLM 调用成本统计")
    sp.add_argument("project")
    sp.set_defaults(func=cmd_cost)

    # 搜索
    sp = sub.add_parser("search", help="全文/语义搜索 + 伏笔反查")
    sp.add_argument("project")
    sp.add_argument("query", nargs="?", help="搜索词")
    sp.add_argument("--semantic", action="store_true", help="语义搜索（需 embedding）")
    sp.add_argument("--top", type=int, default=10, help="返回条数")
    sp.add_argument("--reindex", action="store_true", help="重建索引")
    sp.add_argument("--keyword-only", action="store_true", help="重建时仅文本索引")
    sp.set_defaults(func=cmd_search)

    # 节奏曲线
    sp = sub.add_parser("pacing", help="节奏曲线分析")
    sp.add_argument("project")
    sp.add_argument("chapter", nargs="?", help="只分析指定章节")
    sp.add_argument("--analyze", action="store_true", help="重新分析（默认只查看）")
    sp.set_defaults(func=cmd_pacing)

    # 局部重写
    sp = sub.add_parser("rewrite", help="局部重写章节片段")
    sp.add_argument("project")
    sp.add_argument("chapter", help="章节 id")
    sp.add_argument("--passage", required=True, help="要重写的原文片段")
    sp.add_argument("--to", required=True, help="重写指令（如'更紧张'）")
    sp.add_argument("--context", type=int, help="片段前后上下文字符数")
    sp.set_defaults(func=cmd_rewrite)

    # 文风
    sp = sub.add_parser("style", help="文风指纹 / 漂移检测")
    sp.add_argument("project")
    sp.add_argument("--analyze", action="store_true", help="提取文风指纹")
    sp.add_argument("--check", metavar="CHAPTER", help="检测某章是否漂移")
    sp.set_defaults(func=cmd_style)

    # 备份
    sp = sub.add_parser("backup", help="手动备份项目")
    sp.add_argument("project")
    sp.add_argument("--list", action="store_true", help="列出所有备份")
    sp.set_defaults(func=cmd_backup)

    # 版本管理
    sp = sub.add_parser("version", help="章节版本管理")
    sp.add_argument("project")
    sp.add_argument("chapter", help="章节 id")
    sp.add_argument("--list", action="store_true", help="列出历史版本")
    sp.add_argument("--rollback", type=int, metavar="N", help="回滚到第 N 版")
    sp.add_argument("--diff", help="版本对比（如 0,1 或直接传版本号）")
    sp.set_defaults(func=cmd_version)

    # 进度仪表盘
    sp = sub.add_parser("stats", help="写作进度仪表盘")
    sp.add_argument("project")
    sp.add_argument("--target", type=int, help="设置每日目标字数")
    sp.add_argument("--total", type=int, help="设置目标总字数")
    sp.set_defaults(func=cmd_stats)

    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
