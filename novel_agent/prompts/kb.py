"""知识库操作 Prompt：世界观搭建、故事线串联、时间线校核、idea 安插。"""

KB_SYSTEM = """你是一位资深的世界观架构师与故事编辑，擅长构建自洽的世界设定、梳理复杂故事线、检查时间线一致性。
输出严格遵循要求的 JSON 格式，不要解释，不要寒暄。"""


# ============ 世界观搭建 ============
def worldbuild_prompt(meta: str, focus: str = "") -> list[tuple[str, str]]:
    """从项目简介生成/补全世界观。"""
    return [
        (
            "user",
            f"""请基于以下项目信息，构建一份系统化的【世界观设定】。

【项目信息】
{meta}

{f"【本次重点补全】{focus}" if focus else ""}

请输出 JSON（```json 代码块）：
```json
{{
  "premise": "世界观总纲（2-3句，描述这个世界的本质与基调）",
  "elements": [
    {{
      "category": "rule|cosmology|history|geography|culture|organization|term",
      "name": "元素名（如：元素魔法体系/九州地理/星历纪年）",
      "summary": "一句话简介",
      "detail": "详细说明（2-4句）",
      "constraints": ["硬性约束1（写作时绝对不能违反，如：火系无法克制水系）", "硬性约束2"],
      "parent": "父元素名（无则空，用于体系层级）"
    }}
  ]
}}
```
要求：
- rule（规则体系）必须包含核心能力/技术的运作方式与限制
- 至少给出 3-6 条 constraints（硬约束），这是防止后续写作矛盾的关键
- history 至少给出 3 个历史大事件
- geography 给出主要区域/地点
- term 解释专有名词
- 各元素要能自洽，不互相矛盾""",
        )
    ]


# ============ 故事线串联 ============
def weave_threads_prompt(
    outline_text: str,
    summaries_text: str,
    ideas_text: str,
    existing_threads: str,
    target_chapters: int,
) -> list[tuple[str, str]]:
    """根据大纲+已写摘要+idea，串联/规划故事线。"""
    return [
        (
            "user",
            f"""请根据现有素材，梳理并规划【故事线网络】。

【大纲】
{outline_text}

【已写章节摘要】
{summaries_text or "(尚未写章)"}

【可用 idea 灵感】
{ideas_text or "(暂无)"}

【现有故事线】
{existing_threads or "(暂无)"}

请输出 JSON（```json 代码块），规划未来 {target_chapters} 章的故事线推进：
```json
{{
  "threads": [
    {{
      "type": "main|subplot|character|mystery",
      "name": "线名（如：主线·寻塔之旅 / 支线·林夕身世 / 人物线·陆铮动摇）",
      "summary": "这条线讲什么",
      "importance": 1到5,
      "nodes": [
        {{
          "chapter_id": "建议放入哪章（如 c003，可空=暂不安排）",
          "from_idea": "来源 idea id（来自上面灵感，无则空）",
          "title": "节点标题",
          "description": "这个节点发生什么（推动该线的具体事件）",
          "intersections": {{"其他线名或id": "与该线如何交汇"}}
        }}
      ],
      "resolved": false
    }}
  ],
  "weaving_notes": "整体串联说明：哪些线在哪章交汇、如何制造张力（2-3句）"
}}
```
要求：
- 必须有 1 条 main 主线，串起全书核心推进
- 把可用的 idea 尽量安插到合适的节点（from_idea 填 idea id）
- 标注线与线的交汇点（intersections），制造交织感
- 节点要具体，说明"这一章这条线推进了什么"
- 不要凭空发明大纲里没有的核心转折，但可以补充细节性支线""",
        )
    ]


# ============ 时间线校核 ============
def audit_timeline_prompt(timeline_text: str, facts_text: str) -> list[tuple[str, str]]:
    """检查时间线一致性。"""
    return [
        (
            "user",
            f"""请仔细检查以下时间线，找出所有【时序冲突与不合理之处】。

【时间线事件（按章节顺序）】
{timeline_text}

【已确立的既定事实】
{facts_text}

请检查并输出 JSON（```json 代码块）：
```json
{{
  "consistent": true或false,
  "normalized_timeline": [
    {{
      "chapter_id": "章节",
      "anchor": "推断的绝对/相对时间锚点（如'T+0d'=故事开始当天、'银河历3047年春'）",
      "event": "事件",
      "participants": ["参与者"]
    }}
  ],
  "conflicts": [
    {{
      "severity": "high|medium|low",
      "type": "时序矛盾|人物分身|时间跨度不合理|与事实冲突|因果倒置",
      "events": ["涉及的事件描述"],
      "description": "为什么是冲突",
      "suggestion": "如何修正"
    }}
  ],
  "overall": "时间线整体评价（是否自洽、节奏是否合理）"
}}
```
检查重点：
1. 事件先后是否自洽（A 不应该发生在 B 之前却排在前面）
2. 同一人物是否在同一时间段出现在两个地方（分身）
3. 时间跨度是否合理（一天内发生的事不可能比一天多）
4. 是否与既定事实矛盾（如某地到某地需3天，却在当天到达）
5. 因果关系是否倒置（结果先于原因）

如果时间线完全自洽，conflicts 给空数组。""",
        )
    ]


# ============ idea 安插建议 ============
def place_ideas_prompt(ideas_text: str, outline_text: str) -> list[tuple[str, str]]:
    """分析哪些 idea 适合安插到哪些章节。"""
    return [
        (
            "user",
            f"""请分析以下灵感 idea，建议它们最适合安插到哪个章节。

【可用 idea】
{ideas_text}

【大纲章节】
{outline_text}

请输出 JSON（```json 代码块）：
```json
{{
  "placements": [
    {{
      "idea_id": "i_xxx",
      "suggested_chapter": "c00x",
      "reason": "为什么适合放这里",
      "how": "具体如何融入该章情节（1-2句）",
      "confidence": "high|medium|low"
    }}
  ],
  "unsuitable": [
    {{ "idea_id": "i_xxx", "reason": "为什么暂时不适合安插" }}
  ]
}}
```
只对确实能自然融入的 idea 给出 placement，牵强的归入 unsuitable。""",
        )
    ]
