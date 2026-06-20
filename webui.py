"""小说AI Gradio Web UI。

启动：python webui.py
然后浏览器打开 http://127.0.0.1:7860
"""

from __future__ import annotations

import gradio as gr

from novel_agent import Config
from novel_agent.agents import NovelAgent
from novel_agent.core.outline import ChapterStatus


def _load_agent(project_name: str) -> NovelAgent:
    """打开项目；失败时抛 gr.Error（gradio 前端会显示）。"""
    if not project_name:
        raise gr.Error("请先选择一个项目")
    try:
        return NovelAgent.open(project_name)
    except Exception as e:  # noqa: BLE001
        raise gr.Error(f"打开项目失败：{e}")


def refresh_projects() -> list[str]:
    return NovelAgent.list_projects() or ["(无项目)"]


# ============ Tab: 项目管理 ============
def ui_project_tab() -> "gr.Dropdown":
    gr.Markdown("## 项目管理\n新建小说项目或打开已有项目。")

    with gr.Row():
        proj_dropdown = gr.Dropdown(
            choices=refresh_projects(), label="已有项目", scale=3
        )
        refresh_btn = gr.Button("🔄 刷新", scale=1)

    with gr.Accordion("➕ 新建项目", open=False):
        with gr.Row():
            in_name = gr.Textbox(label="项目目录名(英文)", value="mybook")
            in_title = gr.Textbox(label="书名", value="")
        in_genre = gr.Textbox(label="题材(玄幻/都市/科幻...)", value="")
        in_style = gr.Textbox(label="风格(如：古龙风/轻小说)", value="")
        in_logline = gr.Textbox(label="一句话简介", value="")
        in_synopsis = gr.Textbox(label="故事简介(200-500字)", lines=4, value="")
        in_worldview = gr.Textbox(label="世界观", lines=2, value="")
        with gr.Row():
            in_init = gr.Checkbox(label="创建后自动生成大纲+设定", value=True)
            in_chapters = gr.Slider(5, 100, value=20, step=1, label="目标章节数")
        create_btn = gr.Button("✓ 创建项目", variant="primary")

    info_box = gr.Markdown("", label="项目信息")

    def do_create(
        name, title, genre, style, logline, synopsis, worldview, init, chapters
    ):
        try:
            agent = NovelAgent.create(
                name=name,
                title=title or name,
                genre=genre,
                style=style,
                logline=logline,
                synopsis=synopsis,
                worldview=worldview,
            )
        except FileExistsError:
            raise gr.Error(f"项目已存在：{name}")
        msg = f"✓ 已创建 **{name}**\n\n书名：{title or name}\n题材：{genre}"
        if init and synopsis:
            r = agent.init_from_synopsis(chapter_count=chapters)
            msg += (
                f"\n\n**自动生成完成**\n- 主线：{agent.outline.premise}\n"
                f"- 卷数：{r.get('volume_count')}，章节：{r.get('chapter_count')}\n"
                f"- 设定条目：{r.get('bible_entries', 0)}"
            )
        return msg, gr.update(choices=refresh_projects(), value=name)

    create_btn.click(
        do_create,
        [
            in_name,
            in_title,
            in_genre,
            in_style,
            in_logline,
            in_synopsis,
            in_worldview,
            in_init,
            in_chapters,
        ],
        [info_box, proj_dropdown],
    )

    def do_refresh():
        return gr.update(choices=refresh_projects())

    refresh_btn.click(do_refresh, [], [proj_dropdown])

    def show_info(name):
        if not name or name == "(无项目)":
            return "请选择或创建项目。"
        try:
            agent = _load_agent(name)
            ch_all = agent.outline.all_chapters()
            done = sum(1 for c in ch_all if c.status != ChapterStatus.pending)
            return (
                f"### 《{agent.project.title or name}》\n"
                f"- 题材：{agent.project.genre}\n"
                f"- 一句话：{agent.project.logline or '(无)'}\n"
                f"- 大纲：{len(ch_all)} 章（已完成 {done}）\n"
                f"- 设定：{len(agent.bible.characters)} 人物 / "
                f"{len(agent.bible.locations)} 地点 / {len(agent.bible.lore)} 设定\n"
                f"- 目录：`{agent.dir}`"
            )
        except Exception as e:  # noqa: BLE001
            return f"⚠️ {e}"

    proj_dropdown.change(show_info, [proj_dropdown], [info_box])

    return proj_dropdown


# ============ Tab: 大纲与设定 ============
def ui_outline_tab(proj_dropdown) -> None:
    gr.Markdown(
        "## 大纲 & 设定集\n查看自动生成（或手动编辑 JSON）的剧情骨架与世界观设定。"
    )
    with gr.Row():
        load_btn = gr.Button("📂 加载", variant="primary")
    outline_md = gr.Markdown("", label="大纲")
    with gr.Accordion("设定集", open=False):
        bible_md = gr.Markdown("")

    def load(name):
        agent = _load_agent(name)
        if agent.outline.all_chapters():
            text = agent.outline.render_for_prompt()
        else:
            text = "_(暂无大纲，请到「项目」标签创建并勾选自动生成，或在「写作」标签里逐章规划)_"
        return text, agent.bible.render_for_prompt()

    load_btn.click(load, [proj_dropdown], [outline_md, bible_md])


# ============ Tab: 写作 ============
def ui_write_tab(proj_dropdown) -> tuple:
    gr.Markdown("## 章节写作\n选择章节写正文，或一键连写多章。")
    with gr.Row():
        chap_dropdown = gr.Dropdown([], label="章节")
        load_ch_btn = gr.Button("🔄 加载章节列表")
    with gr.Row():
        write_btn = gr.Button("✍️ 写这一章", variant="primary")
        write_next_btn = gr.Button("⏭️ 写下一章")
        review_chk = gr.Checkbox(value=True, label="写完自动审校")
    out_title = gr.Markdown("")
    out_text = gr.Textbox(label="正文", lines=22, interactive=True)
    out_review = gr.Markdown("")
    save_btn = gr.Button("💾 保存正文修改")
    save_status = gr.Markdown("")

    def load_chapters(name):
        agent = _load_agent(name)
        chs = agent.outline.all_chapters()
        if not chs:
            return gr.update(choices=[], value=None)
        choices = [
            (f"{c.chapter_id} {c.title} [{c.status.value}]", c.chapter_id) for c in chs
        ]
        return gr.update(choices=choices, value=chs[0].chapter_id)

    def read_existing(name, cid):
        """切章节时把已有正文读出来。"""
        if not cid:
            return "", ""
        agent = _load_agent(name)
        ch = agent.store.read_chapter(agent.dir, cid)
        if ch:
            return f"### {cid} 《{ch.title}》", ch.content
        plan = agent.outline.find(cid)
        return f"### {cid} 《{plan.title if plan else ''}》 _(未写)_", ""

    def do_write(name, cid, review):
        agent = _load_agent(name)
        if not cid:
            # 写下一章
            r = agent.write_next(review=review)
            if r is None:
                return "没有待写章节了", "", "", ""
        else:
            r = agent.write_chapter(cid, review=review)
        rv = r.get("review") or {}
        rv_inner = rv.get("review") or rv
        review_md = ""
        if rv_inner:
            review_md = f"**审校评分**：{rv_inner.get('score', '-')}\n\n{rv_inner.get('overall', '')}"
            issues = rv_inner.get("issues", [])
            if issues:
                review_md += "\n\n**问题**：\n" + "\n".join(
                    f"- [{i.get('severity')}] {i.get('description')}" for i in issues
                )
        return (
            f"### {r['chapter_id']} 《{r['title']}》  ({r['word_count']}字)",
            r["content"],
            review_md,
            f"✓ 已保存 {r['chapter_id']}",
        )

    def do_save(name, cid, text):
        if not cid:
            return "没有选中章节"
        agent = _load_agent(name)
        plan = agent.outline.find(cid)
        if plan is None:
            return f"找不到 {cid}"
        summary = agent.store.summaries.get(cid)
        agent.store.write_chapter(
            agent.dir, plan, text, summary.summary if summary else ""
        )
        return f"✓ 已保存 {cid}"

    load_ch_btn.click(load_chapters, [proj_dropdown], [chap_dropdown])
    chap_dropdown.change(
        read_existing, [proj_dropdown, chap_dropdown], [out_title, out_text]
    )
    write_btn.click(
        do_write,
        [proj_dropdown, chap_dropdown, review_chk],
        [out_title, out_text, out_review, save_status],
    )
    write_next_btn.click(
        lambda n, c, r: do_write(n, None, r),
        [proj_dropdown, chap_dropdown, review_chk],
        [out_title, out_text, out_review, save_status],
    )
    save_btn.click(do_save, [proj_dropdown, chap_dropdown, out_text], [save_status])

    # 暴露给 batch tab
    return chap_dropdown, load_ch_btn


# ============ Tab: 批量连写 ============
def ui_batch_tab(proj_dropdown) -> None:
    gr.Markdown("## 批量连写\n一口气生成 N 章，进度实时显示。")
    with gr.Row():
        batch_n = gr.Slider(1, 20, value=3, step=1, label="连写章数")
        batch_review = gr.Checkbox(value=True, label="每章自动审校")
        batch_btn = gr.Button("🚀 开始批量写作", variant="primary")
    batch_log = gr.Markdown("", label="进度")

    def run(name, n, review):
        agent = _load_agent(name)
        lines = ["**批量写作进行中...**\n"]
        for i, r in enumerate(agent.write_batch(n, review=review), 1):
            lines.append(
                f"{i}. ✅ {r['chapter_id']} 《{r['title']}》 — {r['word_count']}字"
            )
            yield "\n".join(lines)
        lines.append("\n**🎉 批量完成！**")
        yield "\n".join(lines)

    batch_btn.click(run, [proj_dropdown, batch_n, batch_review], [batch_log])


# ============ Tab: 导出 ============
def ui_export_tab(proj_dropdown) -> None:
    gr.Markdown("## 导出全文\n把已写章节合并成一个 markdown 文件。")
    export_btn = gr.Button("📄 导出 Markdown", variant="primary")
    export_path = gr.Markdown("")
    export_preview = gr.Textbox(label="预览（前 3000 字）", lines=18)

    def do_export(name):
        agent = _load_agent(name)
        path = agent.export_to_file()
        md = agent.export_markdown()
        return f"✓ 已导出到：`{path}`", md[:3000]

    export_btn.click(do_export, [proj_dropdown], [export_path, export_preview])


# ============ Tab: 连续性追踪 ============
def ui_continuity_tab(proj_dropdown) -> None:
    gr.Markdown(
        "## 连续性追踪\n"
        "自动记录的：人物动态状态、时间线、未回收伏笔、角色持有物、未兑现承诺、既定事实。\n"
        "写完每章会自动更新；这里可查看与手动补跑。"
    )
    with gr.Row():
        view_btn = gr.Button("📋 查看追踪表", variant="primary")
        track_all_btn = gr.Button("🔄 对全部章节补跑")
    cont_box = gr.Markdown("")

    def do_view(name):
        agent = _load_agent(name)
        text = agent.view_continuity()
        return (
            text
            if text and text != "(暂无连续性记录，写章后会自动生成)"
            else "_(暂无记录，写章后会自动生成；或点「补跑」对已有章节提取)_"
        )

    def do_track_all(name):
        agent = _load_agent(name)
        reports = agent.track_all(verbose=False)
        n = sum(1 for r in reports if r.get("extracted"))
        return f"✓ 已对 {n}/{len(reports)} 章提取状态。\n\n" + agent.view_continuity()

    view_btn.click(do_view, [proj_dropdown], [cont_box])
    track_all_btn.click(do_track_all, [proj_dropdown], [cont_box])


# ============ Tab: 知识库（世界观/故事线/时间线/idea）============
def ui_kb_tab(proj_dropdown) -> None:
    gr.Markdown(
        "## 知识库\n"
        "长期记忆中枢：**灵感库**（暂存的点子）、**世界观**（底层设定与硬约束）、"
        "**故事线**（剧情串联）、**时间线校核**（一致性检查）。全部自动持久化。"
    )
    with gr.Tabs():
        # --- 灵感库 ---
        with gr.Tab("💡 灵感库"):
            with gr.Row():
                in_content = gr.Textbox(label="灵感内容", lines=2, scale=4)
                in_title = gr.Textbox(label="标题", scale=2)
            with gr.Row():
                in_type = gr.Dropdown(
                    [
                        t.value
                        for t in __import__(
                            "novel_agent.core.ideas", fromlist=["IdeaType"]
                        ).IdeaType
                    ],
                    value="other",
                    label="类型",
                    scale=2,
                )
                in_priority = gr.Slider(1, 5, value=3, step=1, label="优先级", scale=1)
                in_tags = gr.Textbox(label="标签(逗号)", scale=2)
                in_chars = gr.Textbox(label="相关人物(逗号)", scale=2)
            add_idea_btn = gr.Button("✚ 添加灵感", variant="primary")
            idea_list_btn = gr.Button("🔄 刷新列表")
            idea_box = gr.Markdown("")

            def do_add_idea(name, content, title, itype, prio, tags, chars):
                if not content.strip():
                    raise gr.Error("请输入灵感内容")
                agent = _load_agent(name)
                agent.kb.add_idea(
                    content,
                    title=title,
                    type=itype,
                    priority=int(prio),
                    tags=[t.strip() for t in tags.split(",") if t.strip()],
                    related_chars=[c.strip() for c in chars.split(",") if c.strip()],
                )
                return _render_ideas(name)

            def _render_ideas(name):
                agent = _load_agent(name)
                if not agent.kb.ideas.ideas:
                    return "_(暂无灵感)_"
                lines = []
                for i in agent.kb.ideas.ideas:
                    lines.append(
                        f"**[{i.id}|{i.type.value}|{i.status.value}|优先级{i.priority}]** {i.title}"
                    )
                    if i.content:
                        lines.append(f"  {i.content}")
                    if i.tags:
                        lines.append(f"  标签：{','.join(i.tags)}")
                return "\n".join(lines)

            add_idea_btn.click(
                do_add_idea,
                [
                    proj_dropdown,
                    in_content,
                    in_title,
                    in_type,
                    in_priority,
                    in_tags,
                    in_chars,
                ],
                [idea_box],
            )
            idea_list_btn.click(_render_ideas, [proj_dropdown], [idea_box])

        # --- 世界观 ---
        with gr.Tab("🌍 世界观"):
            build_world_btn = gr.Button("🏗️ 搭建/补全世界观", variant="primary")
            world_focus = gr.Textbox(label="重点补全方向（可空）", value="")
            world_box = gr.Markdown("")

            def do_build_world(name, focus):
                agent = _load_agent(name)
                r = agent.build_world(focus=focus)
                md = agent.kb.world.render_for_prompt()
                return (
                    f"✓ 总纲：{r.get('premise', '')}（新增 {r.get('elements_added', 0)} 元素）\n\n"
                    + (md or "")
                )

            build_world_btn.click(
                do_build_world, [proj_dropdown, world_focus], [world_box]
            )

        # --- 故事线 ---
        with gr.Tab("🧵 故事线"):
            with gr.Row():
                weave_btn = gr.Button("🪡 串联故事线", variant="primary")
                weave_n = gr.Slider(3, 15, value=5, step=1, label="目标章数")
            threads_box = gr.Markdown("")

            def do_weave(name, n):
                agent = _load_agent(name)
                r = agent.weave_threads(target_chapters=int(n))
                md = agent.kb.threads.render_for_prompt(only_active=False)
                return (
                    f"✓ 新增 {r.get('threads_added', 0)} 线 / {r.get('nodes_added', 0)} 节点\n\n> {r.get('notes', '')}\n\n"
                    + (md or "")
                )

            weave_btn.click(do_weave, [proj_dropdown, weave_n], [threads_box])

        # --- 时间线校核 ---
        with gr.Tab("⏱️ 时间线校核"):
            audit_btn = gr.Button("🔍 校核时间线一致性", variant="primary")
            audit_box = gr.Markdown("")

            def do_audit(name):
                import json as _json

                agent = _load_agent(name)
                r = agent.audit_timeline()
                consistent = r.get("consistent")
                head = "### ✅ 时间线自洽" if consistent else "### ❌ 发现时间线冲突"
                conflicts = r.get("conflicts", []) or []
                clines = []
                for c in conflicts:
                    clines.append(
                        f"- **[{c.get('severity')}|{c.get('type')}]** {c.get('description')}\n  → 建议：{c.get('suggestion')}"
                    )
                nl = r.get("normalized_timeline", []) or []
                nlines = ["\n**归一化时间线：**"]
                for e in nl:
                    nlines.append(
                        f"- {e.get('chapter_id')} `{e.get('anchor')}` {e.get('event', '')[:60]}"
                    )
                return (
                    head
                    + "\n\n"
                    + ("\n".join(clines) if clines else "无冲突")
                    + "\n\n"
                    + "\n".join(nlines)
                    + f"\n\n_{r.get('overall', '')}_"
                )

            audit_btn.click(do_audit, [proj_dropdown], [audit_box])


# ============ Tab: 后端测试 ============
def ui_backend_tab() -> None:
    gr.Markdown("## 后端连通性测试\n检查 LLM 后端是否配置正确。")
    test_btn = gr.Button("🔌 测试后端", variant="primary")
    test_result = gr.Markdown("")

    def do_test():
        try:
            from novel_agent.llm import build_backend

            cfg = Config()
            b = build_backend(cfg)
            reply = b.test()
            return f"✅ **后端可用**：`{cfg.backend}`\n\n模型回复：{reply}"
        except Exception as e:  # noqa: BLE001
            return f"❌ **后端不可用**：\n\n```\n{e}\n```"

    test_btn.click(do_test, [], [test_result])


def build_ui() -> gr.Blocks:
    with gr.Blocks(title="小说AI") as demo:
        gr.Markdown(
            "# 📖 小说AI —— 中文小说写作 Agent\n基于 LLM 的设定→大纲→分章→审校全流程。"
        )
        proj_dropdown = ui_project_tab()
        with gr.Tab("大纲/设定"):
            ui_outline_tab(proj_dropdown)
        with gr.Tab("写作"):
            ui_write_tab(proj_dropdown)
        with gr.Tab("批量连写"):
            ui_batch_tab(proj_dropdown)
        with gr.Tab("导出"):
            ui_export_tab(proj_dropdown)
        with gr.Tab("连续性追踪"):
            ui_continuity_tab(proj_dropdown)
        with gr.Tab("知识库"):
            ui_kb_tab(proj_dropdown)
        with gr.Tab("后端测试"):
            ui_backend_tab()
    return demo


if __name__ == "__main__":
    build_ui().launch(
        server_name="127.0.0.1",
        server_port=7860,
        inbrowser=True,
        theme=gr.themes.Soft(),
    )
