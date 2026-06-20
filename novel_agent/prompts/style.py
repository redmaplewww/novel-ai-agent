"""文风分析 Prompt：提取文风指纹、人物语言指纹、检测漂移。"""

STYLE_SYSTEM = """你是一位敏锐的文学评论家与文字编辑，擅长精准识别作者的文风特征与人物的语言习惯。
你只输出严格的 JSON，不解释。"""


def extract_style_prompt(
    samples: str, known_characters: list[str]
) -> list[tuple[str, str]]:
    """从已写正文样本提取文风指纹 + 人物语言指纹。"""
    chars = "、".join(known_characters) if known_characters else "(请从样本中识别)"
    return [
        (
            "user",
            f"""请分析以下小说正文样本，总结【作者文风特征】和【主要人物的语言习惯】。

【已知人物】{chars}

【正文样本】
{samples}

请输出 JSON（```json 代码块）：
```json
{{
  "prose_summary": "一句话概括全书文风（如'冷峻克制，短句为主，善用环境烘托情绪'）",
  "prose_fingerprint": "详细文风特征描述（3-5条，涵盖：句式特点/用词偏好/修辞习惯/叙事节奏/视角处理/情绪表达方式）",
  "character_voices": {{
    "人物名": "该角色的语言指纹（口头禅/用词习惯/语气/说话结构，如'陆铮：语句简短斩钉截铁，少用语气词，常用反问，带命令口吻'）"
  }}
}}
```
要求：
- prose_fingerprint 要具体可操作（能让另一个写手据此模仿），不要空话
- character_voices 只给在样本中有明显对话的角色，没有明显特征的可以不给
- 文风特征要能用于检测"后续章节是否漂移" """,
        )
    ]


def check_drift_prompt(
    content: str, style_fingerprint: str, character_voices: str, chapter_id: str
) -> list[tuple[str, str]]:
    """检测某章是否偏离既有文风。"""
    return [
        (
            "user",
            f"""请检查下面这章小说是否符合既定的【文风特征】与【人物语言指纹】，找出漂移之处。

【既定文风特征】
{style_fingerprint}

【既定人物语言指纹】
{character_voices or "(无)"}

【待检查章节 {chapter_id}】
{content}

请输出 JSON（```json 代码块）：
```json
{{
  "drift_score": 1到10（1=完全一致 10=严重漂移）,
  "prose_issues": [
    {{
      "severity": "high|medium|low",
      "location": "问题位置（引用原文片段）",
      "description": "与文风哪里不一致",
      "suggestion": "如何调整"
    }}
  ],
  "dialogue_issues": [
    {{
      "severity": "high|medium|low",
      "character": "哪个角色的对话",
      "description": "语言指纹哪里不符（如'配角说话像主角'）",
      "suggestion": "如何调整"
    }}
  ],
  "overall": "文风一致性总体评价（1-2句）"
}}
```
没有问题时对应数组给空数组。""",
        )
    ]
