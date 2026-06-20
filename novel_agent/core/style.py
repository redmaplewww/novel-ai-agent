"""文风指纹（Style Fingerprint）：全书文风特征 + 人物语言指纹。

纯 LLM 分析：让模型从已写正文总结文风描述，新章节对比检测漂移。
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field


class StyleData(BaseModel):
    project: str = ""
    prose_fingerprint: str = ""  # 全书文风特征描述（LLM 总结）
    prose_summary: str = ""  # 一句话文风概括
    character_voices: dict[str, str] = Field(default_factory=dict)  # 角色名 -> 语言指纹
    last_analyzed_chapters: list[str] = Field(default_factory=list)  # 上次分析用的章节
    updated_at: float = 0.0

    @classmethod
    def path_of(cls, project_dir: Path) -> Path:
        return project_dir / "style.json"

    @classmethod
    def load(cls, project_dir: Path, project_name: str = "") -> "StyleData":
        p = cls.path_of(project_dir)
        if not p.exists():
            return cls(project=project_name)
        with open(p, "r", encoding="utf-8") as f:
            return cls.model_validate_json(f.read())

    def save(self, project_dir: Path) -> None:
        import time as _t

        self.updated_at = _t.time()
        with open(self.path_of(project_dir), "w", encoding="utf-8") as f:
            f.write(self.model_dump_json(indent=2))

    def render_for_prompt(self) -> str:
        parts: list[str] = []
        if self.prose_summary:
            parts.append(f"【文风概括】{self.prose_summary}")
        if self.prose_fingerprint:
            parts.append(f"【文风特征】\n{self.prose_fingerprint}")
        if self.character_voices:
            parts.append("【人物语言指纹】")
            for name, voice in self.character_voices.items():
                parts.append(f"• {name}：{voice}")
        return "\n\n".join(parts) if parts else ""
