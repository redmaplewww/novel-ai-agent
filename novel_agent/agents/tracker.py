"""StateTracker —— 连续性追踪引擎。

每写完一章后调用 `track_chapter()`：
  1. 用 LLM 从正文提取状态变化/伏笔/持有物/承诺/既定事实
  2. 回写人物 status_history 到 bible
  3. 更新 continuity 表（含伏笔回收、持有物变更、承诺兑现的自动匹配）

这是防止长篇小说「写着写着就崩」的核心模块。
"""

from __future__ import annotations

from typing import Any

from ..core import Bible, Continuity, ForeshadowStatus
from ..llm import LLMBackend
from .llm_helpers import call_json_with_usage


class StateTracker:
    def __init__(self, backend: LLMBackend, *, log=None) -> None:
        self.backend = backend
        self._log = log

    def extract(
        self, chapter_id: str, content: str, known_characters: list[str]
    ) -> dict[str, Any] | None:
        """从一章正文提取所有状态/连续性变化。"""
        from ..prompts import TRACK_SYSTEM, extract_state_prompt

        turns = extract_state_prompt(chapter_id, content, known_characters)
        content_out, usage = call_json_with_usage(
            self.backend, TRACK_SYSTEM, turns, temperature=0.2, max_tokens=2000
        )
        if self._log:
            try:
                self._log(op="track", model="", usage=usage, chapter_id=chapter_id)
            except Exception:  # noqa: BLE001
                pass
        return content_out

    def apply_to_bible(
        self, bible: Bible, chapter_id: str, data: dict[str, Any]
    ) -> int:
        """把人物状态变化回写到 bible.characters[].status_history。返回更新条数。"""
        updated = 0
        for cs in data.get("character_status", []) or []:
            name = cs.get("name", "").strip()
            status = cs.get("status", "").strip()
            if not name or not status:
                continue
            # 模糊匹配人物
            target = None
            for c in bible.characters:
                if name in c.name or c.name in name:
                    target = c
                    break
            if target is None:
                continue
            # 避免重复记录同一章
            if (
                target.status_history
                and target.status_history[-1].get("chapter") == chapter_id
            ):
                target.status_history[-1]["text"] = status
            else:
                target.status_history.append({"chapter": chapter_id, "text": status})
            updated += 1
        return updated

    def apply_to_continuity(
        self, continuity: Continuity, chapter_id: str, data: dict[str, Any]
    ) -> dict[str, int]:
        """更新连续性表。返回各类新增/变更计数。"""
        counts = {
            "timeline": 0,
            "foreshadows": 0,
            "possessions": 0,
            "promises": 0,
            "facts": 0,
        }

        # 时间线
        for t in data.get("timeline", []) or []:
            event = t.get("event", "").strip()
            if not event:
                continue
            continuity.timeline.append(_mk_timeline(chapter_id, t))
            counts["timeline"] += 1

        # 伏笔：新埋 + 回收
        all_fs = continuity.foreshadows
        for f in data.get("foreshadows", []) or []:
            desc = f.get("description", "").strip()
            if not desc:
                continue
            fid = f"fs_{len(all_fs) + 1:03d}"
            all_fs.append(_mk_foreshadow(fid, chapter_id, desc))
            counts["foreshadows"] += 1
        # 回收：尝试模糊匹配已存在的未回收伏笔
        for fr in data.get("foreshadows_resolved", []) or []:
            desc = fr.get("description", "").strip()
            if not desc:
                continue
            for existing in all_fs:
                if existing.status == ForeshadowStatus.planted and _similar(
                    desc, existing.description
                ):
                    existing.status = ForeshadowStatus.resolved
                    existing.resolved_at = chapter_id
                    counts["foreshadows"] += 1
                    break

        # 持有物
        for p in data.get("possessions", []) or []:
            owner = p.get("owner", "").strip()
            item = p.get("item", "").strip()
            if not owner or not item:
                continue
            acquired = p.get("acquired", True)
            if acquired:
                pid = f"pos_{len(continuity.possessions) + 1:03d}"
                continuity.possessions.append(
                    _mk_possession(pid, chapter_id, owner, item, p.get("detail", ""))
                )
                counts["possessions"] += 1
            else:
                # 失去：匹配同名持有物
                for existing in continuity.possessions:
                    if (
                        not existing.lost
                        and existing.owner in owner
                        and existing.item in item
                    ):
                        existing.lost = True
                        existing.lost_at = chapter_id
                        counts["possessions"] += 1
                        break

        # 承诺
        for pm in data.get("promises", []) or []:
            maker = pm.get("maker", "").strip()
            content = pm.get("content", "").strip()
            if not maker or not content:
                continue
            made = pm.get("made", True)
            if made:
                pmid = f"pm_{len(continuity.promises) + 1:03d}"
                continuity.promises.append(
                    _mk_promise(
                        pmid, chapter_id, maker, pm.get("receiver", ""), content
                    )
                )
                counts["promises"] += 1
            else:
                for existing in continuity.promises:
                    if (
                        not existing.fulfilled
                        and existing.maker in maker
                        and _similar(content, existing.content)
                    ):
                        existing.fulfilled = True
                        existing.fulfilled_at = chapter_id
                        counts["promises"] += 1
                        break

        # 既定事实
        for f in data.get("facts", []) or []:
            c = f.get("content", "").strip()
            if not c:
                continue
            # 去重：避免重复记录相同事实
            if any(_similar(c, x.content) for x in continuity.facts):
                continue
            fid = f"fact_{len(continuity.facts) + 1:03d}"
            continuity.facts.append(_mk_fact(fid, chapter_id, c, f.get("category", "")))
            counts["facts"] += 1

        return counts

    def track_chapter(
        self,
        chapter_id: str,
        content: str,
        bible: Bible,
        continuity: Continuity,
        known_characters: list[str] | None = None,
    ) -> dict[str, Any]:
        """一站式：提取 + 回写 bible + 更新 continuity。返回报告。"""
        if known_characters is None:
            known_characters = [c.name for c in bible.characters]
        data = self.extract(chapter_id, content, known_characters)
        if not data:
            return {"extracted": False}
        bible_updated = self.apply_to_bible(bible, chapter_id, data)
        cont_counts = self.apply_to_continuity(continuity, chapter_id, data)
        return {
            "extracted": True,
            "bible_characters_updated": bible_updated,
            "continuity": cont_counts,
            "raw": data,
        }


# ---- 工厂函数（避免直接 import 子类，减少耦合）----
def _mk_timeline(chapter_id: str, t: dict[str, Any]):
    from ..core import TimelineEvent

    return TimelineEvent(
        chapter_id=chapter_id,
        time_label=t.get("time_label", ""),
        event=t.get("event", ""),
    )


def _mk_foreshadow(fid: str, chapter_id: str, desc: str):
    from ..core import Foreshadow

    return Foreshadow(id=fid, chapter_id=chapter_id, description=desc)


def _mk_possession(pid: str, chapter_id: str, owner: str, item: str, detail: str):
    from ..core import Possession

    return Possession(
        id=pid, chapter_id=chapter_id, owner=owner, item=item, detail=detail
    )


def _mk_promise(pmid: str, chapter_id: str, maker: str, receiver: str, content: str):
    from ..core import Promise

    return Promise(
        id=pmid, chapter_id=chapter_id, maker=maker, receiver=receiver, content=content
    )


def _mk_fact(fid: str, chapter_id: str, content: str, category: str):
    from ..core import Fact

    return Fact(id=fid, chapter_id=chapter_id, content=content, category=category)


def _similar(a: str, b: str) -> bool:
    """宽松的中文相似度：共享的关键词多就算相似。"""
    if not a or not b:
        return False
    # 取 2 字以上的共有子串作为简单衡量
    a_set = {a[i : i + 2] for i in range(len(a) - 1)}
    b_set = {b[i : i + 2] for i in range(len(b) - 1)}
    if not a_set or not b_set:
        return False
    overlap = len(a_set & b_set) / max(len(a_set), len(b_set))
    return overlap >= 0.4
