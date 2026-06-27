# 飞书 Bot 接入完全指南（长连接模式）

本文档总结了「小说AI 飞书 Bot」接入飞书的完整流程，包含**所有踩过的坑和解决方案**。适用于任何想用飞书 Bot 接入自己应用的场景，不限于本项目。

---

## 一、方案选型

飞书 Bot 有两种接收消息的方式：

| 方式 | 需要公网IP | 复杂度 | 适用场景 |
|------|-----------|--------|---------|
| **长连接模式（推荐）** | ❌ 不需要 | 低 | 本地开发、个人应用、无服务器 |
| Webhook 回调 | ✅ 需要 | 高 | 生产环境、已有公网服务 |

**本指南使用长连接模式**——不需要公网 IP / 域名 / 服务器，只需一个 App ID + App Secret。

---

## 二、飞书开放平台配置（一次性）

### 步骤 1：创建应用

1. 访问 https://open.feishu.cn/app
2. 点击「创建企业自建应用」
3. 填写应用名称和描述
4. 创建后，在「凭证与基础信息」页面记下：
   - **App ID**（形如 `cli_xxxxxxxxxxxx`）
   - **App Secret**（一串字符）

### 步骤 2：开通权限（关键！）

进入「权限管理」→ 搜索并开通以下权限：

| 权限名 | 权限标识 | 用途 |
|--------|---------|------|
| 获取与发送单聊、群组消息 | `im:message` | 收发消息（核心） |
| 以应用身份发消息 | `im:message:send_as_bot` | Bot 主动发消息 |
| 获取群组信息 | `im:chat` | 列出/管理会话 |
| 获取通讯录用户信息 | `contact:user` 或 `contact:user.base:readonly` | 查用户 open_id（主动发消息需要） |
| 读取用户发给机器人的单聊消息 | `im:message:send_as_bot` | 同上，必须开 |

> ⚠️ **权限审批**：部分权限需要管理员审批。企业自建应用通常即审即过，但如果是租户应用可能要等。

### 步骤 3：配置事件订阅（最容易出错的一步！）

进入「事件与回调」页面：

1. **切换为长连接模式**：
   - 找到「事件配置」区域
   - 把「事件订阅方式」改为 **「使用长连接接收事件」**
   - （不是 Webhook 模式！不需要填回调 URL）

2. **添加事件订阅**（必须手动添加，否则收不到消息！）：

   点击「添加事件」，搜索并添加以下事件：

   | 事件名 | 事件标识 | 必要性 |
   |--------|---------|--------|
   | **接收消息 v2.0** | `im.message.receive_v1` | ✅ 必须，否则收不到用户消息 |
   | 消息已读 v1.0 | `im.message.message_read_v1` | 可选，消除日志噪音 |

   > ⚠️ **这是最容易漏的一步！** 长连接建立成功 ≠ 能收到消息。必须**显式订阅了 `im.message.receive_v1`**，飞书服务器才会通过长连接把消息推送给你。
   >
   > **如何验证订阅成功**：在事件列表里能看到 `im.message.receive_v1`。如果只看到 `message_read_v1`，说明漏加了。

3. **机器人能力**（确认已开启）：
   - 进入「应用能力」→「机器人」
   - 确认机器人功能已启用

### 步骤 4：发布应用

1. 进入「版本管理与发布」
2. 点击「创建版本」
3. 填写版本号和更新说明
4. 点击「发布」
5. 企业自建应用通常**即审即过**，状态变为「已发布」即可使用

> ⚠️ **未发布的应用收不到消息！** 每次修改权限或事件订阅后，可能需要重新发布版本。

### 步骤 5：获取用户 open_id（用于主动发消息）

Bot 主动给用户发消息需要 `open_id`（或 `chat_id`）。获取方式：

```python
import lark_oapi as lark
from lark_oapi.api.contact.v3 import ListUserRequest

client = lark.Client.builder().app_id(APP_ID).app_secret(APP_SECRET).build()
req = ListUserRequest.builder().page_size(10).build()
resp = client.contact.v3.user.list(req)
if resp.success():
    for u in resp.data.items:
        print(f"open_id={u.open_id}, name={u.name}")
```

> 需要 `contact:user` 权限才能调通。

---

## 三、代码实现（Python + lark-oapi）

### 安装 SDK

```bash
pip install lark-oapi
```

### 最小可用 Bot（长连接）

```python
import json
import time
import lark_oapi as lark
from lark_oapi.api.im.v1 import (
    P2ImMessageReceiveV1,
    P2ImMessageMessageReadV1,
    CreateMessageRequest,
    CreateMessageRequestBody,
)

APP_ID = "cli_xxxxxxxxxxxx"
APP_SECRET = "你的secret"
TARGET_OPEN_ID = "ou_xxxxxxxxxxxx"  # 你的 open_id


def on_message(data: P2ImMessageReceiveV1) -> None:
    """收到用户消息的回调"""
    msg = data.event.message
    chat_id = msg.chat_id
    msg_type = msg.message_type

    if msg_type != "text":
        send_text(chat_id, "目前只支持文本消息")
        return

    # ⚠️ 关键坑：飞书 text 消息的 content 是 JSON 字符串，格式是 {"text": "..."}
    # 不是 {"content": "..."}！取错 key 会拿到空字符串，静默失败。
    content = json.loads(msg.content)
    text = content.get("text", "").strip()  # ← key 是 "text"，不是 "content"！

    print(f"[收到] {text}")
    send_text(chat_id, f"你说的是：{text}")


def on_read(data) -> None:
    """消息已读回调（仅记录）"""
    print(f"[已读] {time.strftime('%H:%M:%S')}")


def send_text(chat_id: str, text: str) -> bool:
    """发送文本消息"""
    client = lark.Client.builder().app_id(APP_ID).app_secret(APP_SECRET).build()
    req = (
        CreateMessageRequest.builder()
        .receive_id_type("chat_id")
        .request_body(
            CreateMessageRequestBody.builder()
            .receive_id(chat_id)
            .msg_type("text")
            .content(json.dumps({"text": text}))  # ← 同样，key 是 "text"
            .build()
        )
        .build()
    )
    resp = client.im.v1.message.create(req)
    return resp.success()


# ===== 启动长连接 =====
handler = (
    lark.EventDispatcherHandler.builder("", "")
    .register_p2_im_message_receive_v1(on_message)        # 接收消息事件
    .register_p2_im_message_message_read_v1(on_read)      # 消息已读事件
    .build()
)

cli = lark.ws.Client(
    APP_ID,
    APP_SECRET,
    event_handler=handler,
    log_level=lark.LogLevel.DEBUG,  # 调试时用 DEBUG，生产用 INFO
)
cli.start()
```

### 主动给用户发消息（不等用户先发）

```python
def send_to_user(open_id: str, text: str) -> bool:
    """用 open_id 主动发消息（不需要先收到 chat_id）"""
    client = lark.Client.builder().app_id(APP_ID).app_secret(APP_SECRET).build()
    req = (
        CreateMessageRequest.builder()
        .receive_id_type("open_id")          # ← 用 open_id 而非 chat_id
        .request_body(
            CreateMessageRequestBody.builder()
            .receive_id(open_id)
            .msg_type("text")
            .content(json.dumps({"text": text}, ensure_ascii=False))
            .build()
        )
        .build()
    )
    resp = client.im.v1.message.create(req)
    return resp.success()
```

---

## 四、踩坑记录与解决方案

### 坑 1：content 的 key 是 `text` 不是 `content`

**症状**：收到消息但没有回复，日志里没有任何错误。

**原因**：飞书的文本消息 content 字段格式是 `{"text": "用户发的消息"}`，不是 `{"content": "..."}`。

```python
# ❌ 错误——拿到空字符串，静默 return
text = content.get("content", "")

# ✅ 正确
text = content.get("text", "")
```

**这是最隐蔽的坑**——不报错、不抛异常，就是取到空字符串然后什么都不发生。一定要检查解析后的文本是否为空。

### 坑 2：未订阅 `im.message.receive_v1` 事件

**症状**：长连接建立成功（日志显示 `connected to wss://...`），但发消息后 bot 完全无反应。日志里只有 ping/pong，没有任何 `receive message`。

**原因**：长连接建立 ≠ 能收到消息。必须在飞书后台「事件订阅」里**显式添加 `im.message.receive_v1`** 事件。

**诊断方法**：看日志里有没有类似这行：
```
[DEBUG] receive message, message_type: event, ..., payload: {"...event_type":"im.message.receive_v1"...}
```
如果没有 → 事件订阅没配好。
如果有但后面跟着 `processor not found` → 注册的处理器类型不匹配。

### 坑 3：`processor not found` 错误

**症状**：日志里收到事件了，但报：
```
handle message failed, err: processor not found, type: im.message.message_read_v1
```

**原因**：收到了事件但代码里没注册对应类型的处理器。比如只注册了 `receive_v1` 但飞书也推了 `message_read_v1`。

**解决**：把 `message_read_v1` 也注册一个空处理器：

```python
handler = (
    lark.EventDispatcherHandler.builder("", "")
    .register_p2_im_message_receive_v1(on_message)
    .register_p2_im_message_message_read_v1(on_read)  # ← 注册已读事件
    .build()
)
```

### 坑 4：应用未发布或版本过期

**症状**：配置都对了但依然收不到消息。

**原因**：每次修改权限或事件订阅后，**可能需要重新创建版本并发布**。未发布的应用不生效。

**解决**：去「版本管理与发布」→ 创建新版本 → 发布。

### 坑 5：权限不足导致发送失败

**症状**：发送消息返回错误码 `230002`（权限错误）或 `99991663`。

**解决**：确认开通了 `im:message` 和 `im:message:send_as_bot` 权限，且应用已发布。

### 坑 6：import 报循环导入

**症状**：`ImportError: cannot import name 'ws' from partially initialized module`

**原因**：直接 `import lark_oapi.ws` 在某些版本会触发循环导入。

**解决**：用以下方式导入：
```python
import lark_oapi as lark
# lark.ws.Client 自动可用，无需单独 import
cli = lark.ws.Client(APP_ID, APP_SECRET, ...)
```

### 坑 7：长连接断线重连

**症状**：日志出现 `keepalive ping timeout` 后断线。

**原因**：网络波动或飞书服务器维护，正常现象。

**解决**：`lark.ws.Client` 默认支持自动重连（`auto_reconnect`），一般不用处理。如果频繁断线，检查网络稳定性。

---

## 五、调试流程清单

按这个顺序排查，能定位 99% 的问题：

```
1. 长连接是否建立？
   → 日志有 "connected to wss://msg-frontier.feishu.cn" → ✅ 建立成功
   → 没有这行 → 检查 App ID/Secret 是否正确

2. 消息事件是否到达？
   → 发消息后日志有 "receive message" 且 payload 含 "im.message.receive_v1" → ✅ 到达
   → 只有 ping/pong → 飞书后台事件订阅没配（坑2）

3. 处理器是否触发？
   → 日志有你的 print（如 "[收到]"）→ ✅ 触发
   → 收到事件但报 "processor not found" → 处理器没注册或类型不对（坑3）

4. 文本是否解析正确？
   → print 出解析后的文本，不是空字符串 → ✅
   → 空字符串 → content key 取错了（坑1）

5. 回复是否发送成功？
   → API 返回 success()=True → ✅
   → 返回错误码 → 检查权限（坑5）或 content 格式（坑1）
```

---

## 六、常用 API 速查

| 功能 | API | 要点 |
|------|-----|------|
| 发送文本消息 | `im.v1.message.create` | content=`{"text":"..."}`, receive_id_type=`chat_id`或`open_id` |
| 主动发消息给用户 | 同上 | 用 `open_id` 作为 receive_id |
| 获取用户列表 | `contact.v3.user.list` | 需 `contact:user` 权限 |
| 获取 Bot 所在会话 | `im.v1.chat.list` | 需 `im:chat` 权限 |
| 接收消息事件 | `register_p2_im_message_receive_v1` | 必须 |
| 消息已读事件 | `register_p2_im_message_message_read_v1` | 可选 |

### 常见错误码

| 错误码 | 含义 | 解决 |
|--------|------|------|
| `230001` | content 格式错误 | key 用 `text` 不是 `content` |
| `230002` | 权限不足 | 开通 `im:message` 权限并发布 |
| `99991663` | token 无效 | App Secret 错误或过期 |
| `99991661` | 应用不存在 | App ID 错误 |

---

## 七、项目配置示例

本项目（小说AI）的飞书配置：

### .env
```
FEISHU_APP_ID=cli_aabfb2ecec341bd0
FEISHU_APP_SECRET=你的secret
```

### config.yaml
```yaml
feishu:
  app_id: ${FEISHU_APP_ID}
  app_secret: ${FEISHU_APP_SECRET}
  default_project: demo          # 默认操作的 NovelAI 项目
  max_msg_chars: 2800            # 单条消息最大字符（超长自动分段）
  task_timeout: 600              # 长任务超时秒数
```

### 启动
```bash
python feishu_bot.py
```

### 本项目的飞书命令

```
#帮助                    显示命令列表
#想法 <内容> #标签 @人物   记录灵感
#下一章                   写下一章（异步，完成后推送）
#进度                     查看写作进度
#预览 [章节id]            预览章节正文
#大纲 / #设定 / #连续性   查看项目信息
#搜索 <关键词>            全文搜索
#备份                     手动备份
（任意非#消息）            自由对话（写作教练模式）
```
