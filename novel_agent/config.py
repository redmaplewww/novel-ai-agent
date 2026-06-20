"""配置加载：合并 config.yaml + 环境变量。"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = ROOT / "config.yaml"


def _expand(value: Any) -> Any:
    """递归把字符串里的 ${VAR} 展开成环境变量。"""
    if isinstance(value, str):
        return re.sub(r"\$\{([A-Z0-9_]+)\}", lambda m: os.getenv(m.group(1), ""), value)
    if isinstance(value, dict):
        return {k: _expand(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand(v) for v in value]
    return value


class Config:
    def __init__(self, path: str | Path | None = None) -> None:
        load_dotenv(ROOT / ".env", override=False)
        path = Path(path) if path else DEFAULT_CONFIG
        if not path.exists():
            # 没有配置文件时给个默认空壳，便于靠环境变量驱动
            self.raw: dict[str, Any] = {"backend": os.getenv("NOVEL_BACKEND", "openai")}
        else:
            with open(path, "r", encoding="utf-8") as f:
                self.raw = yaml.safe_load(f) or {}
        self.raw = _expand(self.raw)
        # backend 允许被环境变量覆盖
        if os.getenv("NOVEL_BACKEND"):
            self.raw["backend"] = os.getenv("NOVEL_BACKEND")

    @property
    def backend(self) -> str:
        return str(self.raw.get("backend", "openai")).lower()

    @property
    def openai(self) -> dict[str, Any]:
        return self.raw.get("openai", {})

    @property
    def ollama(self) -> dict[str, Any]:
        return self.raw.get("ollama", {})

    @property
    def writing(self) -> dict[str, Any]:
        return self.raw.get("writing", {})

    @property
    def embedding(self) -> dict[str, Any]:
        return self.raw.get("embedding", {})

    @property
    def pricing(self) -> dict[str, Any]:
        return self.raw.get("pricing", {})

    @property
    def feishu(self) -> dict[str, Any]:
        return self.raw.get("feishu", {})

    def get(self, key: str, default: Any = None) -> Any:
        return self.raw.get(key, default)
