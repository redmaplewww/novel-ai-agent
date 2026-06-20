"""Embedding 后端抽象（OpenAI 兼容协议）。

默认硅基流动 BAAI/bge-m3（中文检索质量最好）。
也支持 OpenAI、智谱等任何 OpenAI 兼容的 embedding 接口。
"""

from __future__ import annotations

import os
from typing import Any

import httpx


class EmbeddingBackend:
    """OpenAI 兼容的 embedding 后端。"""

    def __init__(self, cfg: dict[str, Any]) -> None:
        self.provider = str(cfg.get("provider", "siliconflow")).lower()
        self.api_key = (
            str(cfg.get("api_key", "")).strip()
            or os.getenv("SILICONFLOW_API_KEY", "")
            or os.getenv("OPENAI_API_KEY", "")
        ).strip()
        if not self.api_key:
            raise RuntimeError(
                "未配置 embedding API key。请在 .env 设置 SILICONFLOW_API_KEY（硅基流动），"
                "或在 config.yaml 的 embedding.api_key 写入。"
            )
        if self.provider == "openai":
            self.base_url = str(
                cfg.get("base_url", "https://api.openai.com/v1")
            ).rstrip("/")
        else:
            self.base_url = str(
                cfg.get("base_url", "https://api.siliconflow.cn/v1")
            ).rstrip("/")
        self.model = str(cfg.get("model", "BAAI/bge-m3"))
        self.dim = int(cfg.get("dim", 1024))
        self.timeout = float(cfg.get("timeout", 60))

    def embed(self, texts: str | list[str]) -> list[list[float]]:
        """把文本（或文本列表）转向量。返回 [vec, ...]。"""
        if isinstance(texts, str):
            texts = [texts]
        payload = {"model": self.model, "input": texts, "encoding_format": "float"}
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        url = f"{self.base_url}/embeddings"
        last_err: Exception | None = None
        for attempt in range(3):
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    resp = client.post(url, json=payload, headers=headers)
                    resp.raise_for_status()
                    data = resp.json()
                    # 按 index 排序保证顺序
                    items = sorted(data["data"], key=lambda x: x.get("index", 0))
                    return [item["embedding"] for item in items]
            except Exception as e:  # noqa: BLE001
                last_err = e
                if attempt < 2:
                    import time

                    time.sleep(0.5 * (attempt + 1))
        raise RuntimeError(f"Embedding 调用失败（已重试 3 次）: {last_err}")

    def embed_one(self, text: str) -> list[float]:
        return self.embed([text])[0]

    def test(self) -> str:
        try:
            vec = self.embed_one("测试")
            return f"✓ embedding 可用（维度 {len(vec)}）"
        except Exception as e:  # noqa: BLE001
            return f"✗ embedding 不可用：{e}"


def build_embedding(cfg: dict[str, Any]) -> EmbeddingBackend:
    return EmbeddingBackend(cfg)
