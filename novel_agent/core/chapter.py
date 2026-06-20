"""章节正文与存储。

每章存成 chapters/<chapter_id>.md（正文）+ chapters/summaries.json（摘要表）。
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from .outline import ChapterPlan


class Chapter(BaseModel):
    chapter_id: str
    title: str = ""
    content: str = ""
    word_count: int = 0
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    review_note: str = ""  # 审校意见

    @property
    def filename(self) -> str:
        return f"{self.chapter_id}.md"

    def render_markdown(self) -> str:
        head = f"# {self.title}\n\n" if self.title else ""
        return f"{head}{self.content}\n"


class ChapterSummary(BaseModel):
    chapter_id: str
    title: str = ""
    summary: str = ""  # 这一章发生了什么（供后续章节参考）
    word_count: int = 0


class ChapterStore(BaseModel):
    """所有章节摘要的索引表。"""

    summaries: dict[str, ChapterSummary] = Field(default_factory=dict)

    # ---- 路径 ----
    @staticmethod
    def chapters_dir(project_dir: Path) -> Path:
        return project_dir / "chapters"

    @staticmethod
    def summaries_path(project_dir: Path) -> Path:
        return ChapterStore.chapters_dir(project_dir) / "summaries.json"

    @staticmethod
    def chapter_path(project_dir: Path, chapter_id: str) -> Path:
        return ChapterStore.chapters_dir(project_dir) / f"{chapter_id}.md"

    # ---- 加载/保存 ----
    @classmethod
    def load(cls, project_dir: Path) -> "ChapterStore":
        p = cls.summaries_path(project_dir)
        if not p.exists():
            return cls()
        with open(p, "r", encoding="utf-8") as f:
            data = __import__("json").load(f)
        # data: dict[str, dict]
        return cls(
            summaries={
                k: ChapterSummary(**v) for k, v in data.get("summaries", {}).items()
            }
        )

    def save(self, project_dir: Path) -> None:
        import json

        self.chapters_dir(project_dir).mkdir(parents=True, exist_ok=True)
        data = {"summaries": {k: v.model_dump() for k, v in self.summaries.items()}}
        with open(self.summaries_path(project_dir), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # ---- 操作 ----
    def write_chapter(
        self,
        project_dir: Path,
        plan: ChapterPlan,
        content: str,
        summary: str = "",
        *,
        source: str = "ai",
    ) -> Chapter:
        """写入章节正文。

        若该章已存在，会自动把旧版归档到 versions/<cid>.v{n}.md。
        source: 'ai' | 'human' | 'revise'，记录版本来源。
        """
        self.chapters_dir(project_dir).mkdir(parents=True, exist_ok=True)
        cid = plan.chapter_id
        # 归档旧版（若存在）
        cur_path = self.chapter_path(project_dir, cid)
        if cur_path.exists():
            self._archive_version(
                project_dir, cid, cur_path.read_text(encoding="utf-8")
            )
        wc = len([c for c in content if c.strip()])
        ch = Chapter(
            chapter_id=cid,
            title=plan.title,
            content=content,
            word_count=wc,
        )
        with open(cur_path, "w", encoding="utf-8") as f:
            f.write(ch.render_markdown())
        self.summaries[cid] = ChapterSummary(
            chapter_id=cid,
            title=plan.title,
            summary=summary or content[:200],
            word_count=wc,
        )
        self.save(project_dir)
        self._log_version_meta(project_dir, cid, wc, source)
        return ch

    # ============ 多版本管理 ============
    @staticmethod
    def versions_dir(project_dir: Path) -> Path:
        return ChapterStore.chapters_dir(project_dir) / "versions"

    @staticmethod
    def versions_meta_path(project_dir: Path) -> Path:
        return ChapterStore.versions_dir(project_dir) / "versions.json"

    def _archive_version(self, project_dir: Path, cid: str, text: str) -> None:
        """把旧内容归档为 v{n}.md。"""
        vdir = self.versions_dir(project_dir)
        vdir.mkdir(parents=True, exist_ok=True)
        existing = self.list_versions(project_dir, cid)
        n = len(existing) + 1
        (vdir / f"{cid}.v{n}.md").write_text(text, encoding="utf-8")

    def _log_version_meta(
        self, project_dir: Path, cid: str, word_count: int, source: str
    ) -> None:
        """记录版本元信息。"""
        import json
        import time as _t

        vdir = self.versions_dir(project_dir)
        vdir.mkdir(parents=True, exist_ok=True)
        meta_path = self.versions_meta_path(project_dir)
        meta: dict[str, Any] = {"versions": {}}
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        versions = meta.setdefault("versions", {}).setdefault(cid, [])
        versions.append(
            {
                "version": len(versions) + 1,
                "ts": _t.time(),
                "word_count": word_count,
                "source": source,
                "is_current": False,
            }
        )
        meta_path.write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def list_versions(self, project_dir: Path, cid: str) -> list[dict]:
        """返回某章的版本历史（不含当前版）。"""
        import json

        meta_path = self.versions_meta_path(project_dir)
        if not meta_path.exists():
            return []
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        return meta.get("versions", {}).get(cid, [])

    def get_version(self, project_dir: Path, cid: str, version: int) -> Chapter | None:
        """读取某历史版本。version=0 表示当前版。"""
        if version == 0:
            return self.read_chapter(project_dir, cid)
        p = self.versions_dir(project_dir) / f"{cid}.v{version}.md"
        if not p.exists():
            return None
        text = p.read_text(encoding="utf-8")
        lines = text.split("\n")
        title = ""
        content = text
        if lines and lines[0].startswith("# "):
            title = lines[0][2:].strip()
            content = "\n".join(lines[1:]).lstrip("\n")
        return Chapter(
            chapter_id=cid,
            title=title,
            content=content,
            word_count=len([c for c in content if c.strip()]),
        )

    def rollback(self, project_dir: Path, cid: str, version: int) -> Chapter | None:
        """回滚到某历史版本：把当前版也归档，再用历史版覆盖当前。"""
        target = self.get_version(project_dir, cid, version)
        if target is None:
            return None
        # 当前版归档（作为新版本）
        cur_path = self.chapter_path(project_dir, cid)
        if cur_path.exists():
            self._archive_version(
                project_dir, cid, cur_path.read_text(encoding="utf-8")
            )
        cur_path.write_text(target.render_markdown(), encoding="utf-8")
        self._log_version_meta(project_dir, cid, target.word_count, "rollback")
        if cid in self.summaries:
            self.summaries[cid].word_count = target.word_count
            self.save(project_dir)
        return target

    def diff(
        self, project_dir: Path, cid: str, v1: int = 0, v2: int = 1
    ) -> dict[str, list[str]]:
        """简单行级 diff（v1 vs v2，0=当前）。返回 {'added':[], 'removed':[]}。"""
        import difflib

        c1 = self.get_version(project_dir, cid, v1)
        c2 = self.get_version(project_dir, cid, v2)
        if c1 is None or c2 is None:
            return {"added": [], "removed": []}
        lines1 = c1.content.splitlines()
        lines2 = c2.content.splitlines()
        sm = difflib.SequenceMatcher(None, lines2, lines1)
        added: list[str] = []
        removed: list[str] = []
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag in ("insert", "replace"):
                added.extend(lines1[j1:j2])
            if tag in ("delete", "replace"):
                removed.extend(lines2[i1:i2])
        return {"added": added, "removed": removed}

    def read_chapter(self, project_dir: Path, chapter_id: str) -> Chapter | None:
        p = self.chapter_path(project_dir, chapter_id)
        if not p.exists():
            return None
        text = p.read_text(encoding="utf-8")
        # 去掉 markdown 标题行
        lines = text.split("\n")
        title = ""
        content = text
        if lines and lines[0].startswith("# "):
            title = lines[0][2:].strip()
            content = "\n".join(lines[1:]).lstrip("\n")
        s = self.summaries.get(chapter_id)
        return Chapter(
            chapter_id=chapter_id,
            title=title,
            content=content,
            word_count=s.word_count if s else len(content),
        )

    def tail(self, project_dir: Path, chapter_id: str, chars: int) -> str:
        """取某章末尾 chars 个字符，作为"上一章结尾"上下文。"""
        ch = self.read_chapter(project_dir, chapter_id)
        if not ch or not ch.content:
            return ""
        return ch.content[-chars:] if len(ch.content) > chars else ch.content

    def has(self, chapter_id: str) -> bool:
        return chapter_id in self.summaries

    def ordered_ids(self) -> list[str]:
        return sorted(self.summaries.keys())
