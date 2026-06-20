"""写作进度跟踪：日字数历史、完成度、预计完本。"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class ProgressData(BaseModel):
    project: str = ""
    daily_words: dict[str, int] = Field(default_factory=dict)  # {"2026-06-19": 3500}
    total_words: int = 0
    target_total_words: int = 0  # 目标总字数
    daily_target: int = 2000  # 每日目标字数
    deadline: str = ""  # 截止日期 YYYY-MM-DD
    updated_at: float = 0.0

    @classmethod
    def path_of(cls, project_dir: Path) -> Path:
        return project_dir / "progress.json"

    @classmethod
    def load(cls, project_dir: Path, project_name: str = "") -> "ProgressData":
        p = cls.path_of(project_dir)
        if not p.exists():
            return cls(project=project_name)
        with open(p, "r", encoding="utf-8") as f:
            return cls.model_validate_json(f.read())

    def save(self, project_dir: Path) -> None:
        self.updated_at = time.time()
        with open(self.path_of(project_dir), "w", encoding="utf-8") as f:
            f.write(self.model_dump_json(indent=2))

    def record_today(self, words_added: int) -> None:
        day = time.strftime("%Y-%m-%d")
        self.daily_words[day] = self.daily_words.get(day, 0) + words_added
        self.total_words += words_added

    def stats(
        self, *, total_chapters: int = 0, done_chapters: int = 0
    ) -> dict[str, Any]:
        """计算统计数据。"""
        today = time.strftime("%Y-%m-%d")
        # 近 7 天日均
        days = sorted(self.daily_words.keys())[-7:]
        recent = [self.daily_words[d] for d in days]
        avg = sum(recent) / len(recent) if recent else 0
        # 预计完本
        remaining = max(self.target_total_words - self.total_words, 0)
        eta_days = int(remaining / avg) if avg > 0 else -1
        eta_date = ""
        if eta_days > 0:
            eta_date = time.strftime(
                "%Y-%m-%d", time.localtime(time.time() + eta_days * 86400)
            )
        # 连续打卡
        streak = 0
        cur_day = today
        while cur_day in self.daily_words and self.daily_words[cur_day] > 0:
            streak += 1
            t = time.strptime(cur_day, "%Y-%m-%d")
            cur_day = time.strftime("%Y-%m-%d", time.localtime(time.mktime(t) - 86400))
        return {
            "total_words": self.total_words,
            "today_words": self.daily_words.get(today, 0),
            "daily_target": self.daily_target,
            "today_progress": round(
                self.daily_words.get(today, 0) / max(self.daily_target, 1) * 100, 1
            ),
            "avg_7d": round(avg, 0),
            "target_total": self.target_total_words,
            "target_progress": round(
                self.total_words / max(self.target_total_words, 1) * 100, 1
            ),
            "remaining_words": remaining,
            "eta_days": eta_days,
            "eta_date": eta_date,
            "streak_days": streak,
            "recent_days": days,
            "recent_words": recent,
            "total_chapters": total_chapters,
            "done_chapters": done_chapters,
            "chapter_progress": round(done_chapters / max(total_chapters, 1) * 100, 1),
        }
