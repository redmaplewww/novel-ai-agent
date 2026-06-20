"""状态追踪 Prompt：从已写章节提取人物状态变化 + 连续性条目。"""

TRACK_SYSTEM = """你是一位严谨的小说连续性编辑。你的任务是从一章小说正文里，精确提取对后续章节有影响的「状态变化」与「连续性条目」。
只提取正文中明确发生的事实，不要推测，不要虚构。没有就不填，宁缺毋滥。
输出必须是严格的 JSON。"""


def extract_state_prompt(
    chapter_id: str, content: str, known_characters: list[str]
) -> list[tuple[str, str]]:
    """提取本章人物状态变化 + 连续性条目。返回 [(role, content)]"""
    chars = "、".join(known_characters) if known_characters else "(未知，请从正文识别)"
    return [
        (
            "user",
            f"""请仔细阅读下面这一章正文，提取本章带来的所有「状态变化」与「连续性条目」。

【第 {chapter_id} 章】
【已知人物】{chars}

【正文】
{content}

请输出 JSON（```json 代码块），结构如下（任何类别没有就给空数组）：
```json
{{
  "character_status": [
    {{
      "name": "人物名（必须与已知人物匹配，或正文出现的新人物）",
      "status": "本章结束时该人物的当前状态（如：左臂受伤、获得火系能力、与沈渡决裂、下落不明等）",
      "permanent_change": true或false（是否为不可逆的永久变化，如死亡/残疾/能力永久丧失）
    }}
  ],
  "timeline": [
    {{ "time_label": "故事内时间（如'逃亡第3天'，看不出来就空）", "event": "本章发生的里程碑事件（1句）" }}
  ],
  "foreshadows": [
    {{ "description": "本章埋下的伏笔（未解之谜/暗示/未说明的细节）" }}
  ],
  "foreshadows_resolved": [
    {{ "description": "本章回收的伏笔描述（与之前埋下的对应）" }}
  ],
  "possessions": [
    {{ "owner": "持有者", "item": "物品或能力名", "detail": "说明", "acquired": true或false（true=获得，false=失去） }}
  ],
  "promises": [
    {{ "maker": "承诺者", "receiver": "对象", "content": "承诺内容", "made": true或false（true=新承诺，false=兑现了旧承诺） }}
  ],
  "facts": [
    {{ "category": "规则/事件/关系/地理等", "content": "本章确立的、后续不可违反的既定事实" }}
  ]
}}
```
提取原则：
- 只提取正文明示发生的、对后续有影响的条目
- 人物状态要写「本章结束时的当前状态」，而不是过程
- 既定事实( facts )要包含：新出现的世界规则、确认的关系、不可逆的事件结果
- 伏笔只记录明显是作者有意埋下的悬念，不要把普通情节当伏笔""",
        )
    ]
