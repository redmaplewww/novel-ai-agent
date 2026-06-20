"""局部重写 Prompt：只重写选中的片段，保留上下文衔接。"""

REWRITE_SYSTEM = """你是一位顶尖的小说文字编辑，擅长在不改变情节走向的前提下，优化特定段落的文字质量。
你会严格保持人物语气、叙事视角和文风的一致性，只重写指定片段，输出纯净的重写后文本（不加任何说明或标记）。"""


def rewrite_passage_prompt(
    passage: str,
    context_before: str,
    context_after: str,
    instruction: str,
    *,
    style_fingerprint: str = "",
) -> list[tuple[str, str]]:
    """局部重写。返回 [(role, content)]。

    passage: 要重写的原文片段
    context_before/after: 片段前后的正文（保证衔接）
    instruction: 重写指令（如"更紧张"、"去掉说教感"）
    style_fingerprint: 全书文风指纹（可选，保持一致）
    """
    style_block = (
        f"\n【全书文风特征（请保持一致）】\n{style_fingerprint}"
        if style_fingerprint
        else ""
    )
    return [
        (
            "user",
            f"""请重写下面【要重写的片段】，只输出重写后的片段文本。

【片段之前的正文（用于衔接，不要重写）】
{context_before or "(章节开头)"}
{style_block}
【要重写的片段】
{passage}

【片段之后的正文（用于衔接，不要重写）】
{context_after or "(章节结尾)"}

【重写要求】
{instruction}

要求：
1. 只输出重写后的片段，不要包含前后的正文，不要加任何说明
2. 严格保持与前后文的衔接（人称、时态、场景、人物状态）
3. 保持原片段的情节功能，只优化文字
4. 字数与原片段相近（允许 ±30%）""",
        )
    ]
