"""审校 Agent 的 Prompt：一致性检查与修订。"""

REVIEW_SYSTEM = """你是一位严谨的中文小说责任编辑，负责发现并修正长篇连载中的逻辑与一致性问题。
你的判断要客观，建议要具体可执行。"""


def review_chapter_prompt(
    context: str, content: str, chapter_plan: str = ""
) -> list[tuple[str, str]]:
    plan_block = ""
    if chapter_plan:
        plan_block = f"""
【本章大纲计划（请重点核对正文是否偏离）】
{chapter_plan}
"""
    return [
        (
            "user",
            f"""请审校下面这一章。

【背景资料（设定/连续性约束/大纲/前情）】
{context}
{plan_block}
【待审章节正文】
{content}

请检查并输出 JSON（```json 代码块）：
```json
{{
  "score": 1到10的评分,
  "deviation": {{
    "deviated": true或false,
    "degree": "none|minor|major",
    "description": "正文相对大纲计划的偏离说明（若没有偏离写'基本遵循大纲'）",
    "missing_beats": ["大纲要求但正文未体现的情节点"],
    "added_content": ["正文自行增加的、大纲没有的情节（判断是否合理）"]
  }},
  "continuity_violations": [
    {{
      "severity": "high|medium|low",
      "type": "设定矛盾|伏笔冲突|持有物错误|承诺遗漏|时间线混乱|人物状态矛盾",
      "description": "违反了哪条连续性约束或设定",
      "suggestion": "如何修正"
    }}
  ],
  "issues": [
    {{
      "severity": "high|medium|low",
      "type": "consistency|plot|character|pacing|style|other",
      "location": "问题所在的大致位置（引用原文片段或段落号）",
      "description": "问题描述",
      "suggestion": "修改建议"
    }}
  ],
  "overall": "总体评价与改进方向（2-3句）"
}}
```
重点检查三类问题：
1. **偏离大纲**：正文是否完成了「本章大纲计划」要求的情节节拍？有没有跑题、加了不必要的支线、或漏掉关键转折？
2. **连续性违反**：是否与「连续性约束」（伏笔/持有物/承诺/既定事实）矛盾？人物状态是否与设定一致？
3. **一般质量**：逻辑、人物、节奏、文风
没有问题时对应数组给空数组。""",
        )
    ]


def revise_chapter_prompt(content: str, review_text: str) -> list[tuple[str, str]]:
    return [
        (
            "user",
            f"""请根据审校意见，重写下面这一章。只输出修订后的完整正文。

【审校意见】
{review_text}

【原正文】
{content}

要求：直接输出修订后的正文，不要解释改了哪里。""",
        )
    ]
