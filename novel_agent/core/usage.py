"""用量与成本记账。

每次 LLM 调用记录一条 entry，持久化到 usage_log.json。
按操作类型 / 章节 / 模型 / 天 聚合统计成本。
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


class UsageLog:
    def __init__(self, project_dir: Path) -> None:
        self.dir = project_dir
        self.path = project_dir / "usage_log.json"

    @classmethod
    def load(cls, project_dir: Path) -> "UsageLog":
        u = cls(project_dir)
        return u

    def _all(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        with open(self.path, "r", encoding="utf-8") as f:
            return json.load(f).get("entries", [])

    def log(
        self,
        *,
        op: str,
        model: str,
        usage: dict[str, int],
        chapter_id: str = "",
        cached_tokens: int = 0,
    ) -> None:
        """记录一次调用。op: write/summarize/review/track/plan/embed/other。"""
        entries = self._all()
        entries.append(
            {
                "ts": time.time(),
                "op": op,
                "model": model,
                "chapter_id": chapter_id,
                "prompt_tokens": int(usage.get("prompt_tokens", 0)),
                "completion_tokens": int(usage.get("completion_tokens", 0)),
                "total_tokens": int(usage.get("total_tokens", 0)),
                "cached_tokens": int(cached_tokens or usage.get("cached_tokens", 0)),
            }
        )
        self.dir.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump({"entries": entries}, f, ensure_ascii=False, indent=2)

    def estimate_cost(self, entry: dict[str, Any], pricing: dict[str, Any]) -> float:
        """估算单条成本（人民币元）。"""
        model = entry.get("model", "")
        # 模糊匹配定价表 key
        price = pricing.get(model) or pricing.get("default") or {}
        p_in = float(price.get("input", 1.0))
        p_cached = float(price.get("cached_input", p_in))
        p_out = float(price.get("output", 2.0))
        prompt = int(entry.get("prompt_tokens", 0))
        cached = int(entry.get("cached_tokens", 0))
        completion = int(entry.get("completion_tokens", 0))
        # 缓存命中的部分按 cached_input 价；其余按 input 价
        non_cached_in = max(prompt - cached, 0)
        cost = (
            non_cached_in * p_in + cached * p_cached + completion * p_out
        ) / 1_000_000
        return cost

    def summary(self, pricing: dict[str, Any]) -> dict[str, Any]:
        """汇总统计。"""
        entries = self._all()
        total_cost = sum(self.estimate_cost(e, pricing) for e in entries)
        total_prompt = sum(int(e.get("prompt_tokens", 0)) for e in entries)
        total_completion = sum(int(e.get("completion_tokens", 0)) for e in entries)
        total_cached = sum(int(e.get("cached_tokens", 0)) for e in entries)

        # 按 op 聚合
        by_op: dict[str, dict[str, float]] = {}
        for e in entries:
            op = e.get("op", "other")
            c = self.estimate_cost(e, pricing)
            if op not in by_op:
                by_op[op] = {"calls": 0, "cost": 0.0, "tokens": 0}
            by_op[op]["calls"] += 1
            by_op[op]["cost"] += c
            by_op[op]["tokens"] += int(e.get("total_tokens", 0))

        # 按章节聚合
        by_chapter: dict[str, dict[str, float]] = {}
        for e in entries:
            cid = e.get("chapter_id") or "(无)"
            c = self.estimate_cost(e, pricing)
            if cid not in by_chapter:
                by_chapter[cid] = {"calls": 0, "cost": 0.0}
            by_chapter[cid]["calls"] += 1
            by_chapter[cid]["cost"] += c

        # 按天聚合
        by_day: dict[str, dict[str, float]] = {}
        for e in entries:
            day = time.strftime("%Y-%m-%d", time.localtime(e.get("ts", 0)))
            c = self.estimate_cost(e, pricing)
            if day not in by_day:
                by_day[day] = {"calls": 0, "cost": 0.0}
            by_day[day]["calls"] += 1
            by_day[day]["cost"] += c

        return {
            "total_calls": len(entries),
            "total_cost": round(total_cost, 4),
            "total_prompt_tokens": total_prompt,
            "total_completion_tokens": total_completion,
            "total_cached_tokens": total_cached,
            "by_op": {k: {**v, "cost": round(v["cost"], 4)} for k, v in by_op.items()},
            "by_chapter": {
                k: {**v, "cost": round(v["cost"], 4)} for k, v in by_chapter.items()
            },
            "by_day": {
                k: {**v, "cost": round(v["cost"], 4)} for k, v in by_day.items()
            },
        }
