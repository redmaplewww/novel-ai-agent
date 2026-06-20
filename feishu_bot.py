"""飞书 Bot 主程序：长连接接收消息 + 异步执行任务 + 主动推送结果。

运行：
    python feishu_bot.py

飞书开放平台配置（需在开发者后台完成）：
  1. 创建「企业自建应用」，记下 App ID / App Secret
  2. 权限管理 → 开通：im:message、im:message:send_as_bot、im:chat
  3. 事件与回调 → 长连接模式（无需公网 IP/域名）
  4. 订阅事件：接收消息 v2.0 (im.message.receive_v1)
  5. 发布版本并审核通过

本程序用 ws.Client 维持长连接，收到消息后路由到 CommandRouter。
长任务（写章节）异步执行，完成后用 CreateMessage 主动推送结果。
"""

from __future__ import annotations

import io
import json
import sys
import threading
import time
import traceback
from typing import Any

# Windows 控制台 UTF-8
if sys.platform == "win32":
    try:
        sys.stdout = io.TextIOWrapper(
            sys.stdout.buffer, encoding="utf-8", errors="replace"
        )
        sys.stderr = io.TextIOWrapper(
            sys.stderr.buffer, encoding="utf-8", errors="replace"
        )
    except Exception:  # noqa: BLE001
        pass

import lark_oapi as lark
from lark_oapi.api.im.v1 import (
    P2ImMessageReceiveV1,
    CreateMessageRequest,
    CreateMessageRequestBody,
)

from novel_agent import Config
from novel_agent.agents import NovelAgent
from novel_agent.feishu import CommandRouter, CommandResult


class FeishuBot:
    def __init__(self, config: Config | None = None) -> None:
        self.config = config or Config()
        fcfg = self.config.feishu
        self.app_id = str(fcfg.get("app_id", "")).strip()
        self.app_secret = str(fcfg.get("app_secret", "")).strip()
        if not self.app_id or not self.app_secret:
            raise RuntimeError(
                "未配置飞书 App ID/Secret。请在 .env 设置 FEISHU_APP_ID / FEISHU_APP_SECRET。"
            )
        self.task_timeout = int(fcfg.get("task_timeout", 600))
        self.max_chars = int(fcfg.get("max_msg_chars", 2800))
        self.router = CommandRouter(self.config)
        # lark client（用于发消息）
        self.lark_client = (
            lark.Client.builder()
            .app_id(self.app_id)
            .app_secret(self.app_secret)
            .build()
        )
        # 记住最近的 chat_id（便于主动推送；不依赖事件里的 chat_id）
        self._recent_chat_id: str = ""
        self._lock = threading.Lock()

    # ============ 启动长连接 ============
    def run(self) -> None:
        # 构造事件分发器：注册「接收消息」事件 + 「消息已读」事件（避免 processor not found 噪音）
        handler = (
            lark.EventDispatcherHandler.builder("", "")
            .register_p2_im_message_receive_v1(self._on_message)
            .register_p2_im_message_message_read_v1(self._on_read)
            .build()
        )
        # 长连接 client
        cli = lark.ws.Client(
            self.app_id,
            self.app_secret,
            event_handler=handler,
            log_level=lark.LogLevel.DEBUG,  # 开 DEBUG 看全部事件流
        )
        print("=" * 60, flush=True)
        print("小说AI 飞书 Bot 已启动（长连接模式）", flush=True)
        print(f"默认项目：{self.router.default_project}", flush=True)
        print("在飞书里给 bot 发送 #帮助 试试。", flush=True)
        print("=" * 60, flush=True)
        cli.start()

    # ============ 事件回调 ============
    def _on_read(self, data: Any) -> None:
        """消息已读事件（仅记录，不处理）。"""
        print(f"[{time.strftime('%H:%M:%S')}] [已读事件]（用户读了消息）", flush=True)

    # ============ 收到消息 ============
    def _on_any_event(self, data: Any) -> None:
        """诊断用：任何事件都打印，确认长连接是否真的收到事件。"""
        try:
            import time as _t

            ts = _t.strftime("%H:%M:%S")
            # 尝试取 event_type
            etype = getattr(getattr(data, "header", None), "event_type", "unknown")
            print(f"[{ts}] [事件到达] type={etype}", flush=True)
        except Exception:  # noqa: BLE001
            pass

    def _on_message(self, data: P2ImMessageReceiveV1) -> None:
        print(
            f"[{time.strftime('%H:%M:%S')}] [★★★收到消息事件★★★] 进入处理器", flush=True
        )
        try:
            msg = data.event.message
            chat_id = msg.chat_id
            print(f"[收到] chat_id={chat_id}", flush=True)
            with self._lock:
                self._recent_chat_id = chat_id or ""
            # 只处理文本消息
            msg_type = msg.message_type
            if msg_type != "text":
                self.send_text(chat_id, "目前只支持文本消息。发送 #帮助 查看命令。")
                return
            content = json.loads(msg.content)
            # 飞书文本消息格式是 {"text": "..."}（不是 content）
            text = ""
            if isinstance(content, dict):
                text = (content.get("text") or content.get("content") or "").strip()
            # 飞书 @ 机器人时会带 @_user_1，去掉
            import re as _re

            text = _re.sub(r"@_user_\d+", "", text).strip()
            print(f"[解析] 文本内容: {text[:80]!r}", flush=True)
            if not text:
                self.send_text(chat_id, "（空消息，没识别到文本）")
                return
            result = self.router.handle(text)
            print(
                f"[回复] 长度={len(result.text)} is_task={result.is_task}", flush=True
            )
            # 先回复即时消息
            ok = self.send_text(chat_id, result.text)
            print(f"[发送] 结果={ok}", flush=True)
            # 若是长任务，异步执行
            if result.is_task:
                self._run_task_async(chat_id, result)
        except Exception as e:  # noqa: BLE001
            print(f"[处理消息出错] {e}")
            traceback.print_exc()
            try:
                self.send_text(chat_id or self._recent_chat_id, f"⚠️ 处理出错：{e}")
            except Exception:  # noqa: BLE001
                pass

    # ============ 异步执行长任务 ============
    def _run_task_async(self, chat_id: str, result: CommandResult) -> None:
        kind = result.task_kind
        args = result.task_args
        project = args.get("project", result.project)

        def _worker() -> None:
            try:
                if kind == "write":
                    chapter_id = args.get("chapter_id")
                    agent = NovelAgent.open(project, self.config)
                    t0 = time.time()
                    r = agent.write_chapter(chapter_id, review=True, verbose=False)
                    dt = time.time() - t0
                    msg = (
                        f"✅ 章节 {r['chapter_id']} 《{r['title']}》已完成（{r['word_count']}字，用时 {dt:.0f}s）\n\n"
                        f"📝 摘要：{r.get('summary', '')[:200]}\n"
                    )
                    tk = r.get("tracking")
                    if tk and tk.get("extracted"):
                        cu = tk.get("bible_characters_updated", 0)
                        cont = tk.get("continuity", {}) or {}
                        msg += f"\n🔍 状态追踪：更新 {cu} 人物，新增 {sum(cont.values())} 条连续性记录\n"
                    rv = r.get("review")
                    if rv:
                        inner = rv.get("review") or rv
                        dev = inner.get("deviation") or {}
                        if dev.get("deviated"):
                            msg += f"\n⚠️ 偏离大纲[{dev.get('degree')}]：{dev.get('description', '')[:80]}\n"
                        msg += f"\n📋 审校评分：{inner.get('score', '-')}/10\n{inner.get('overall', '')[:100]}"
                    # 末尾加预览（截断）
                    msg += f"\n\n--- 正文预览（前 600 字）---\n{r['content'][:600]}…"
                    self.send_text(chat_id, msg)
            except Exception as e:  # noqa: BLE001
                self.send_text(
                    chat_id, f"❌ 任务执行失败：{e}\n\n{traceback.format_exc()[-300:]}"
                )

        t = threading.Thread(target=_worker, daemon=True)
        t.start()

        # 看门狗：超时提醒（不杀线程，仅提示）
        def _watchdog() -> None:
            time.sleep(self.task_timeout)
            if t.is_alive():
                self.send_text(
                    chat_id,
                    f"⏰ 任务已运行 {self.task_timeout}s 仍在进行，DeepSeek 可能较慢，请稍候。",
                )

        threading.Thread(target=_watchdog, daemon=True).start()

    # ============ 发送消息 ============
    def send_text(self, chat_id: str, text: str) -> bool:
        """给指定 chat 发文本消息，自动分段。"""
        if not chat_id:
            return False
        # 分段发送
        chunks = self._split(text, self.max_chars)
        for chunk in chunks:
            try:
                req = (
                    CreateMessageRequest.builder()
                    .receive_id_type("chat_id")
                    .request_body(
                        CreateMessageRequestBody.builder()
                        .receive_id(chat_id)
                        .msg_type("text")
                        .content(json.dumps({"text": chunk}))
                        .build()
                    )
                    .build()
                )
                resp = self.lark_client.im.v1.message.create(req)
                if not resp.success():
                    print(f"[发送失败] code={resp.code} msg={resp.msg}")
                    return False
            except Exception as e:  # noqa: BLE001
                print(f"[发送异常] {e}")
                return False
            time.sleep(0.3)  # 避免频率限制
        return True

    @staticmethod
    def _split(text: str, size: int) -> list[str]:
        if len(text) <= size:
            return [text]
        out = []
        for i in range(0, len(text), size):
            out.append(text[i : i + size])
        return out


def main() -> int:
    bot = FeishuBot()
    bot.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
