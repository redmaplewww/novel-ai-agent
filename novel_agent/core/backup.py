"""自动备份：把项目目录打包成 zip 快照，保留最近 N 个。"""

from __future__ import annotations

import time
from pathlib import Path


def backup_project(project_dir: Path, *, keep: int = 10) -> Path:
    """把项目目录打包成 backups/<timestamp>.zip，保留最近 keep 个。

    会跳过 backups/ 和 embeddings/（体积大且可重建）。
    """
    project_dir = Path(project_dir)
    backup_dir = project_dir / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    zip_path = backup_dir / f"{project_dir.name}_{ts}.zip"

    import zipfile

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in project_dir.rglob("*"):
            if p.is_dir():
                continue
            rel = p.relative_to(project_dir)
            # 跳过 backups 和 embeddings 目录下的内容（体积大且可重建）
            parts = rel.parts
            if parts and parts[0] in ("backups", "embeddings"):
                continue
            zf.write(p, rel)

    # 清理旧备份，保留最近 keep 个
    backups = sorted(
        backup_dir.glob("*.zip"), key=lambda x: x.stat().st_mtime, reverse=True
    )
    for old in backups[keep:]:
        old.unlink(missing_ok=True)

    return zip_path


def list_backups(project_dir: Path) -> list[dict]:
    """列出项目的所有备份。"""
    backup_dir = Path(project_dir) / "backups"
    if not backup_dir.exists():
        return []
    out = []
    for p in sorted(
        backup_dir.glob("*.zip"), key=lambda x: x.stat().st_mtime, reverse=True
    ):
        st = p.stat()
        out.append(
            {
                "name": p.name,
                "path": str(p),
                "size_kb": round(st.st_size / 1024, 1),
                "ts": st.st_mtime,
            }
        )
    return out
