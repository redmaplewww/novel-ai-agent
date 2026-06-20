"""规划 Agent 的 Prompt：生成主线、大纲、章节计划、设定集。"""

PLAN_SYSTEM = """你是一位资深中文小说策划编辑，擅长构思严密、可长篇连载的故事。
你的输出必须严格遵循指定的格式（通常用 ```json 代码块包裹）。
不要解释，不要寒暄，只输出要求的内容。"""


def premise_prompt(
    synopsis: str, genre: str, style: str, chapter_count: int
) -> list[tuple[str, str]]:
    """从简介扩展出主线前提。返回 [(role, content), ...]"""
    return [
        (
            "user",
            f"""请基于以下素材，提炼出这部小说的【故事前提/主线】，以及一个约 {chapter_count} 章的整体大纲骨架。

【题材】{genre or "(未指定)"}
【风格】{style or "(未指定)"}
【作者给出的素材】
{synopsis or "(无)"}

请输出 JSON，结构如下（放在 ```json 代码块中）：
```json
{{
  "premise": "一句话核心主线/核心冲突",
  "themes": ["主题1", "主题2"],
  "volumes": [
    {{
      "title": "卷名",
      "summary": "本卷主线（1-2句）",
      "chapters": [
        {{ "title": "章节标题", "beat": "这一章发生的核心事件" }}
      ]
    }}
  ]
}}
```
注意：
- 章节总数尽量接近 {chapter_count} 章
- 每个章节的 beat 要具体、有因果推进，不要"主角继续修炼"这种空话
- 卷与卷之间要有明显递进""",
        )
    ]


def expand_outline_prompt(
    volume_title: str, volume_summary: str, rough_beats: list[str], chapter_count: int
) -> list[tuple[str, str]]:
    """把一卷的粗略 beat 扩展成详细的章节计划。"""
    beats_text = "\n".join(f"- {b}" for b in rough_beats) or "(无)"
    return [
        (
            "user",
            f"""请把以下卷纲扩展为 {chapter_count} 章的【详细章节计划】。

【卷名】{volume_title}
【本卷主线】{volume_summary}
【作者给出的粗略节拍】
{beats_text}

请输出 JSON（```json 代码块）：
```json
{{
  "chapters": [
    {{
      "title": "章节标题",
      "pov": "视角人物（可空）",
      "setting": "发生地点（可空）",
      "time": "时间线（可空）",
      "characters": ["出场人物名"],
      "beat": "本章核心情节（2-3句，具体）",
      "goal": "本章叙事目标（1句）",
      "conflict": "本章核心冲突（1句）",
      "ending": "章末钩子/收束（1句）"
    }}
  ]
}}
```
要求：
- 章节之间要有明确的因果与节奏推进
- 每章都要有冲突与悬念，避免流水账
- 视角、地点、出场人物尽量具体""",
        )
    ]


def chapter_plan_prompt(context: str, hint: str) -> list[tuple[str, str]]:
    """为单章生成详细 ChapterPlan。"""
    return [
        (
            "user",
            f"""请为下一章生成一份详细的【单章写作计划】。

{context}

作者补充要求：{hint or "(无)"}

请输出 JSON（```json 代码块）：
```json
{{
  "title": "章节标题",
  "pov": "视角人物",
  "setting": "地点",
  "time": "时间",
  "characters": ["出场人物"],
  "beat": "核心情节（3-4句）",
  "goal": "叙事目标",
  "conflict": "核心冲突",
  "ending": "章末收束"
}}
```
""",
        )
    ]


def bible_from_synopsis_prompt(meta: str) -> list[tuple[str, str]]:
    """从项目简介生成初始设定集。"""
    return [
        (
            "user",
            f"""请基于以下项目信息，生成一份初始【设定集】，包含主要人物、地点、势力等。

{meta}

请输出 JSON（```json 代码块）：
```json
{{
  "characters": [
    {{
      "id": "char_1",
      "name": "姓名",
      "role": "主角/反派/配角",
      "summary": "一句话简介",
      "personality": "性格特点",
      "motivation": "核心动机",
      "abilities": "能力/特长",
      "appearance": "外貌",
      "background": "背景",
      "relationships": "与其他人物关系",
      "arc": "人物弧光"
    }}
  ],
  "locations": [
    {{ "id": "loc_1", "name": "地名", "summary": "简介", "geography": "地理", "significance": "重要性" }}
  ],
  "factions": [
    {{ "id": "fac_1", "name": "势力名", "summary": "简介", "leader": "首领", "goals": "目标" }}
  ],
  "lore": [
    {{ "id": "lore_1", "name": "设定名（如：修炼体系）", "summary": "简介", "description": "详细规则" }}
  ]
}}
```
只生成对故事必要的内容，宁缺毋滥。id 用 snake_case。""",
        )
    ]
