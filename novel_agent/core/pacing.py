"""节奏曲线（Pacing Curve）：每章的张力/情绪/信息密度打分。

用于检测全书节奏问题：平淡谷（连续低张力）、高潮过载（连续高张力）、情绪单调。
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class Pace(str, Enum):
    fast = "fast"  # 快节奏：动作密集、冲突强
    medium = "medium"  # 中等
    slow = "slow"  # 慢节奏：铺垫、抒情、过渡


class ChapterPacing(BaseModel):
    chapter_id: str
    tension: int = 5  # 张力 1-10（冲突强度/紧迫感）
    emotion: int = 5  # 情绪强度 1-10
    info_density: int = 5  # 信息密度 1-10（新设定/新人物/剧情推进量）
    pace: Pace = Pace.medium
    mood: str = ""  # 主导情绪：轻松/紧张/悲伤/希望/震惊/温馨...
    cliffhanger: bool = False  # 是否有章末钩子
    word_count: int = 0
    notes: str = ""  # LLM 给出的节奏说明


class PacingReport(BaseModel):
    """全书节奏分析报告。"""

    problems: list[dict[str, Any]] = Field(default_factory=list)  # 检测到的问题
    suggestions: list[str] = Field(default_factory=list)
    curve_ascii: str = ""


class PacingData(BaseModel):
    project: str = ""
    chapters: dict[str, ChapterPacing] = Field(default_factory=dict)

    @classmethod
    def path_of(cls, project_dir: Path) -> Path:
        return project_dir / "pacing.json"

    @classmethod
    def load(cls, project_dir: Path, project_name: str = "") -> "PacingData":
        p = cls.path_of(project_dir)
        if not p.exists():
            return cls(project=project_name)
        with open(p, "r", encoding="utf-8") as f:
            return cls.model_validate_json(f.read())

    def save(self, project_dir: Path) -> None:
        with open(self.path_of(project_dir), "w", encoding="utf-8") as f:
            f.write(self.model_dump_json(indent=2))

    def ordered(self) -> list[ChapterPacing]:
        """按章节 id 排序。"""
        return [self.chapters[k] for k in sorted(self.chapters.keys())]

    def curve_ascii(self, width: int = 50) -> str:
        """画张力曲线（ASCII）。"""
        items = self.ordered()
        if not items:
            return "(暂无节奏数据)"
        tensions = [c.tension for c in items]
        labels = [c.chapter_id for c in items]
        # 归一化到 width
        n = len(tensions)
        # 简单的散点+连线表示
        height = 10
        grid = [[" "] * max(n, 1) for _ in range(height)]
        for i, t in enumerate(tensions):
            row = height - t  # t=10 在第 0 行（顶部）
            row = max(0, min(height - 1, row))
            grid[row][i] = "●"
        # 纵轴刻度
        out = ["张力曲线（●=该章张力1-10）:"]
        for r in range(height):
            label = str(10 - r)
            out.append(f"{label:>2} |" + "".join(grid[r]))
        out.append("    +" + "-" * max(n, 1))
        out.append("     " + " ".join(l[-3:] for l in labels))
        return "\n".join(out)

    def detect_problems(self) -> PacingReport:
        """检测节奏问题。"""
        items = self.ordered()
        problems: list[dict[str, Any]] = []
        suggestions: list[str] = []
        if len(items) < 3:
            return PacingReport(
                problems=problems,
                suggestions=suggestions,
                curve_ascii=self.curve_ascii(),
            )

        # 1. 平淡谷：连续 >=3 章 tension < 4
        run_start = -1
        for i, c in enumerate(items):
            if c.tension < 4:
                if run_start < 0:
                    run_start = i
            else:
                if run_start >= 0 and i - run_start >= 3:
                    seg = items[run_start:i]
                    problems.append(
                        {
                            "type": "平淡谷",
                            "severity": "medium" if i - run_start >= 4 else "low",
                            "chapters": [s.chapter_id for s in seg],
                            "description": f"连续 {i - run_start} 章张力偏低（<{4}），节奏拖沓",
                        }
                    )
                    suggestions.append(
                        f"在 {seg[-1].chapter_id} 前后插入一个转折或钩子，打破平淡谷"
                    )
                run_start = -1
        # 收尾检查
        if run_start >= 0 and len(items) - run_start >= 3:
            seg = items[run_start:]
            problems.append(
                {
                    "type": "平淡谷",
                    "severity": "medium",
                    "chapters": [s.chapter_id for s in seg],
                    "description": f"连续 {len(items) - run_start} 章张力偏低",
                }
            )

        # 2. 高潮过载：连续 >=2 章 tension >= 9
        run_start = -1
        for i, c in enumerate(items):
            if c.tension >= 9:
                if run_start < 0:
                    run_start = i
            else:
                if run_start >= 0 and i - run_start >= 2:
                    seg = items[run_start:i]
                    problems.append(
                        {
                            "type": "高潮过载",
                            "severity": "high",
                            "chapters": [s.chapter_id for s in seg],
                            "description": f"连续 {i - run_start} 章高张力（>=9），读者易疲劳",
                        }
                    )
                    suggestions.append(
                        f"在 {items[i].chapter_id if i < len(items) else '后续'} 插入一段舒缓/过渡，给读者喘息"
                    )
                run_start = -1

        # 3. 情绪单调：连续 >=4 章同一 mood
        if len(items) >= 4:
            cur_mood = items[0].mood
            run_len = 1
            for i in range(1, len(items)):
                if items[i].mood and items[i].mood == cur_mood:
                    run_len += 1
                    if run_len >= 4:
                        problems.append(
                            {
                                "type": "情绪单调",
                                "severity": "low",
                                "chapters": [
                                    items[j].chapter_id
                                    for j in range(i - run_len + 1, i + 1)
                                ],
                                "description": f"连续 {run_len} 章主导情绪都是「{cur_mood}」，缺乏变化",
                            }
                        )
                        suggestions.append(
                            f"在 {items[i].chapter_id} 转换情绪基调，避免读者审美疲劳"
                        )
                        break
                else:
                    cur_mood = items[i].mood
                    run_len = 1

        # 4. 钩子缺失：连续 >=3 章无 cliffhanger
        run_start = -1
        for i, c in enumerate(items):
            if not c.cliffhanger:
                if run_start < 0:
                    run_start = i
            else:
                if run_start >= 0 and i - run_start >= 3:
                    problems.append(
                        {
                            "type": "钩子缺失",
                            "severity": "low",
                            "chapters": [
                                items[j].chapter_id for j in range(run_start, i)
                            ],
                            "description": f"连续 {i - run_start} 章无章末钩子，章节衔接弱",
                        }
                    )
                run_start = -1

        return PacingReport(
            problems=problems, suggestions=suggestions, curve_ascii=self.curve_ascii()
        )
