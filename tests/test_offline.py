"""离线测试：用 mock backend 验证整个数据流，不依赖真实 LLM/网络。

运行：python tests/test_offline.py
"""

from __future__ import annotations

import io
import json
import shutil
import sys
from pathlib import Path

# Windows 控制台 UTF-8
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# 让脚本能 import 项目根的 novel_agent
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from novel_agent.llm import LLMBackend, Message


class MockBackend(LLMBackend):
    """假装的 LLM：按调用内容返回预设 JSON/正文。"""

    name = "mock"
    writer_model = "mock-writer"

    def __init__(self) -> None:
        self.call_log: list[str] = []

    def chat(
        self, messages, *, model=None, temperature=0.85, max_tokens=None, stop=None, **_
    ):
        text = messages[-1].content if messages else ""
        self.call_log.append(text[:60])
        # 识别调用类型并返回对应内容
        if "故事前提/主线" in text and "volumes" in text or "premise" in text:
            return json.dumps(
                {
                    "premise": "孤儿少年偶得上古传承，在乱世中崛起复仇并守护所爱。",
                    "themes": ["成长", "复仇", "守护"],
                    "volumes": [
                        {
                            "title": "觉醒之卷",
                            "summary": "主角觉醒传承，踏入修炼界。",
                            "chapters": [
                                {
                                    "title": "废柴少年",
                                    "beat": "林尘被族人欺辱，意外坠崖获得传承",
                                },
                                {"title": "初试身手", "beat": "林尘回村击退来犯之敌"},
                            ],
                        }
                    ],
                },
                ensure_ascii=False,
            )
        if "characters" in text and "设定集" in text:
            return json.dumps(
                {
                    "characters": [
                        {
                            "id": "char_linchen",
                            "name": "林尘",
                            "role": "主角",
                            "summary": "废柴少年，实为上古血脉",
                            "personality": "坚韧隐忍，重情义",
                            "motivation": "为父母复仇、守护妹妹",
                            "abilities": "上古传承之力",
                        }
                    ],
                    "locations": [
                        {
                            "id": "loc_qingyun",
                            "name": "青云村",
                            "summary": "主角故乡",
                            "geography": "山间小村",
                        }
                    ],
                    "factions": [],
                    "lore": [
                        {
                            "id": "lore_xiulian",
                            "name": "修炼体系",
                            "summary": "炼气→筑基→金丹",
                            "description": "九重境界",
                        }
                    ],
                },
                ensure_ascii=False,
            )
        if "单章写作计划" in text or "本章写作计划" in text:
            return json.dumps(
                {
                    "title": "废柴少年",
                    "pov": "林尘",
                    "setting": "青云村",
                    "characters": ["林尘", "林霸"],
                    "beat": "林尘被堂兄林霸当众羞辱并夺走灵石，绝望中跌落悬崖，却在崖底古洞获得上古强者残魂传承。",
                    "goal": "建立主角困境与转折",
                    "conflict": "主角的弱小 vs 家族的欺压",
                    "ending": "传承入体，林尘睁开双眼，眼中闪过金光",
                },
                ensure_ascii=False,
            )
        if "压缩成一份【前情提要摘要】" in text or "前情提要" in text:
            return "林尘被林霸欺辱坠崖，在崖底古洞获得上古传承，实力初现，决心回村清算恩怨。"
        if "本章正文" in text or word_target_marker(text):
            return _mock_novel_text()
        if "审校" in text and "score" in text:
            return json.dumps(
                {
                    "score": 8,
                    "issues": [
                        {
                            "severity": "medium",
                            "type": "pacing",
                            "location": "中段",
                            "description": "节奏稍快，传承获得过程可再加细节",
                            "suggestion": "增加崖底古洞的环境描写",
                        }
                    ],
                    "overall": "整体合格，人物动机清晰，建议适度扩写传承场景。",
                },
                ensure_ascii=False,
            )
        # 兜底
        return "好的，这是模拟回复。"


def word_target_marker(text: str) -> bool:
    return "字数要求" in text or "字（中文字符）" in text


def _mock_novel_text() -> str:
    return (
        "夕阳斜挂在青云山的山脊上，把整座小村染成一片昏黄。\n\n"
        "林尘蹲在村口的石磨旁，手里紧紧攥着一块指甲大小的下品灵石。"
        "这是他三个月来进山采药换来的全部收获，明日便是妹妹小溪的生辰，"
        "他答应了要给她买一支桃花簪。\n\n"
        "「哟，废物尘儿，还藏着宝贝呢？」\n\n"
        "一个阴阳怪气的声音从身后传来。林尘心头一紧，转过头，"
        "果然看见堂兄林霸带着两个狗腿子，正笑嘻嘻地逼近。\n\n"
        "林霸是家族长房嫡子，先天境三重，在青云村横行惯了。"
        "林尘握紧灵石想跑，却被一掌拍在肩头，半边身子顿时麻了。\n\n"
        "「拿来吧你！」林霸一把夺过灵石，还嫌不够，一脚把林尘踹翻在地，"
        "「天天在村里晃，丢我们林家的脸。滚远点！」\n\n"
        "围观的人不少，却没有一个上前。林尘咬着牙，眼眶发红，却硬是没让眼泪掉下来。"
        "他踉跄着站起来，转身朝后山跑去。\n\n"
        "不知跑了多久，他来到一处熟悉的断崖。这里是他常来独处的地方。"
        "脚下云雾翻涌，深不见底。风从崖底灌上来，吹得他衣衫猎猎。\n\n"
        "「凭什么……」林尘低声喃喃，「就因为我是庶出？就因为我娘是凡人？」\n\n"
        "身后传来林霸的叫骂声，越来越近。林尘回头一看，几人已经追了上来。"
        "林霸狞笑着又是一掌，本就立足不稳的林尘脚下一滑——\n\n"
        "他仰面跌落悬崖。\n\n"
    ) * 1  # 简化版


def main() -> int:
    print("=" * 60)
    print("小说AI 离线测试（mock backend）")
    print("=" * 60)

    # 用临时项目目录
    from novel_agent.core.project import PROJECTS_ROOT

    test_dir = PROJECTS_ROOT / "_test_mock"
    if test_dir.exists():
        shutil.rmtree(test_dir)

    # 1. 创建项目
    from novel_agent.agents import NovelAgent
    from novel_agent.core import Project

    print("\n[1/6] 创建测试项目...")
    proj = Project(
        name="_test_mock",
        title="青云传",
        genre="玄幻",
        style="热血",
        logline="废柴少年偶得传承，踏上修仙路。",
        synopsis="孤儿林尘在青云村受尽欺凌，坠崖后获得上古传承，"
        "从此踏上修仙之路，在乱世中崛起，复仇、守护、成神。",
        worldview="九州大陆，修炼者众多，境界分炼气、筑基、金丹等。",
    )
    proj.save()

    # 用 mock backend 构造 agent（不连真实 LLM）
    from novel_agent import Config

    agent = NovelAgent(proj, Config(), backend=MockBackend())

    # 2. 生成主线+大纲+设定
    print("[2/6] 生成主线/大纲/设定集...")
    r = agent.init_from_synopsis(chapter_count=2, auto_bible=True)
    assert r["chapter_count"] >= 2, f"章节数不对: {r}"
    assert agent.outline.premise, "主线为空"
    assert agent.bible.characters, "人物为空"
    print(f"  ✓ 主线: {agent.outline.premise[:40]}...")
    print(f"  ✓ 章节: {r['chapter_count']}, 人物: {len(agent.bible.characters)}")

    # 3. 丰富第一章计划
    print("[3/6] 丰富第一章详细计划...")
    plan = agent.enrich_next_chapter_plan()
    assert plan is not None, "没有待写章节"
    assert plan.conflict, "冲突字段没填上"
    print(f"  ✓ {plan.chapter_id} 《{plan.title}》冲突: {plan.conflict[:30]}...")

    # 4. 写第一章
    print("[4/6] 写第一章...")
    result = agent.write_chapter(plan.chapter_id, review=True)
    assert result["word_count"] > 100, f"正文字数太少: {result['word_count']}"
    assert result["review"], "审校没跑"
    print(f"  ✓ 字数: {result['word_count']}")
    print(f"  ✓ 摘要: {result['summary'][:40]}...")

    # 5. 验证记忆系统（写第二章时上下文应含第一章摘要）
    print("[5/6] 验证记忆系统...")
    all_ch = agent.outline.all_chapters()
    next_plan = all_ch[1] if len(all_ch) > 1 else all_ch[0]
    ctx = agent._memory().build_context_for_chapter(next_plan.chapter_id)
    assert "前情提要" in ctx, "上下文里没有前情提要"
    assert "废柴少年" in ctx or "林尘" in ctx, "摘要内容没进上下文"
    print(f"  ✓ 上下文长度: {len(ctx)} 字符，含前情提要")

    # 6. 导出
    print("[6/6] 导出 markdown...")
    out = agent.export_to_file()
    assert out.exists() and out.stat().st_size > 0
    print(f"  ✓ 导出: {out} ({out.stat().st_size} bytes)")

    # 清理
    shutil.rmtree(test_dir)
    print("\n" + "=" * 60)
    print("✅ 全部测试通过！整个数据流（设定→大纲→写章→摘要→审校→导出）正常。")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
