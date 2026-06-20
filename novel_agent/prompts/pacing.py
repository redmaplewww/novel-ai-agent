"""节奏分析 Prompt：给章节打分（张力/情绪/信息密度/节奏/钩子）。"""

PACING_SYSTEM = """你是一位资深的小说节奏编辑，擅长分析章节的叙事张力与情绪起伏。
你只输出严格的 JSON，不解释。"""


def analyze_pacing_prompt(
    chapter_id: str, title: str, content: str, outline_beat: str = ""
) -> list[tuple[str, str]]:
    """对单章正文打节奏分。"""
    beat_block = f"\n【本章大纲节拍（参考）】\n{outline_beat}" if outline_beat else ""
    return [
        (
            "user",
            f"""请分析下面这一章小说的【节奏与张力】，给出量化评分。

【第 {chapter_id} 章】{title}{beat_block}

【正文】
{content}

请输出 JSON（```json 代码块）：
```json
{{
  "tension": 1到10的整数（冲突强度/紧迫感：1=极度平淡 10=生死攸关高潮）,
  "emotion": 1到10的整数（情绪强度：1=冷静客观 10=强烈情感冲击）,
  "info_density": 1到10的整数（信息密度：新设定/新人物/剧情推进量，1=纯过渡 10=信息爆炸）,
  "pace": "fast|medium|slow（快节奏动作密集 / 中等 / 慢节奏铺垫抒情）",
  "mood": "主导情绪（一个词：轻松/紧张/悲伤/希望/震惊/温馨/恐惧/愤怒/迷茫/释然 等）",
  "cliffhanger": true或false（章末是否有钩子/悬念/未解问题，吸引读者继续）,
  "notes": "本章节奏特点的简要说明（1-2句，如'前半铺垫缓慢，后半冲突爆发'）"
}}
```
评分标准：
- tension 看的是冲突与紧迫感，不是字数。一章全是日常描写可能 tension=2。
- 高潮章（大战/生死/重大转折）tension 通常 8-10。
- cliffhanger 看章末是否有明确的"未完成"或"勾人"的设计，不是每章都该有。
""",
        )
    ]
