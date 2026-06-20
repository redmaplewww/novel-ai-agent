# 小说AI —— 基于 LLM 的中文长篇小说写作 Agent

一个开源、全流程的中文小说写作助手。从「一句话简介」出发，自动完成 **设定集 → 世界观 → 故事线 → 大纲 → 分章正文 → 节奏分析 → 审校修订** 的完整闭环，并提供 **CLI / Web UI / 飞书 Bot** 三种使用方式。

## 特性

### 写作流程
- **设定 & 世界观**：自动生成人物（含动态状态追踪）、地点、势力、规则体系（含硬性约束）、历史、术语表
- **大纲 & 故事线**：卷→章层次大纲，主线/支线/人物线/悬念线的串联与 idea 自动安插
- **智能写作**：分章生成正文，每章前自动注入设定集、连续性约束、故事线脉络、相关 idea
- **上下文压缩**：长篇不崩的核心——用最近 N 章摘要代替全文，配合上章末尾衔接

### 质量控制
- **审校 & 偏离检测**：写完自动检查逻辑一致性、与大纲的偏离度、连续性违反
- **节奏曲线分析**：每章张力/情绪/信息密度打分，自动检测平淡谷、高潮过载、情绪单调、钩子缺失
- **文风一致性**：LLM 自动提取全书文风指纹 + 人物语言指纹，检测后续章节漂移
- **时间线校核**：检测时序矛盾、人物分身、因果关系倒置
- **多版本章节**：重写自动归档历史版本，支持回滚、diff 对比

### 知识管理
- **灵感库**：暂存的点子（场景/情节点/对话/反转），写作时按本章人物自动检索注入
- **连续性追踪**：自动记录伏笔（含回收状态）、持有物、承诺、既定事实——全部写成强制约束
- **全文 & 语义搜索**：跨章节关键词搜索 + 硅基流动 bge-m3 语义向量检索 + 伏笔反查
- **统一知识库**：bible / continuity / world / ideas / threads / pacing / style 全部持久化为 JSON

### 使用界面
- **CLI**：25+ 命令覆盖全流程，支持批量连写、管道脚本
- **Gradio Web UI**：可视化操作，多标签页管理
- **飞书 Bot**：长连接模式（无需公网 IP），通过 `#命令` 记录想法、查进度、写下一章、预览正文

### 成本 & 安全
- **Token 成本统计**：每次 LLM 调用自动记账，按操作/章节/天汇总费用
- **自动备份**：写完每章 zip 快照，保留最近 10 个
- **LLM 双后端**：OpenAI 兼容 API (DeepSeek / 硅基流动 / OpenAI) + Ollama 本地

## 快速开始

### 安装

```bash
pip install -r requirements.txt
```

### 配置

```bash
copy .env.example .env      # 填入 API key
copy config.example.yaml config.yaml
```

`.env`：
```
NOVEL_API_KEY=sk-你的DeepSeekKey
SILICONFLOW_API_KEY=sk-你的硅基流动Key    # 语义搜索用
FEISHU_APP_ID=cli_xxx                     # 飞书 Bot（可选）
FEISHU_APP_SECRET=xxx
```

`config.yaml` 常用服务商：

| 服务 | base_url | model |
|------|----------|-------|
| DeepSeek | `https://api.deepseek.com/v1` | `deepseek-chat` |
| 硅基流动 | `https://api.siliconflow.cn/v1` | `Qwen/Qwen2.5-72B-Instruct` |
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-mini` |
| Ollama 本地 | (改 `backend: ollama`) | `qwen2.5:7b-instruct` |

### 测试连通

```bash
python cli.py test
```

### 三步写第一章

```bash
# 1. 新建项目（自动生成设定 + 大纲）
python cli.py new mybook --title "书名" --genre 玄幻 --synopsis "故事简介..." --init --chapters 20

# 2. 搭建世界观（规则/历史/地理/术语，含硬性约束）
python cli.py kb mybook world --build

# 3. 写第一章（自动审校 + 状态追踪 + 备份）
python cli.py write mybook c001 --full
```

## CLI 命令全览

### 项目管理
| 命令 | 说明 |
|------|------|
| `new <name> --synopsis "..." --init` | 新建项目并生成大纲设定 |
| `list` | 列出所有项目 |
| `init <project>` | 为已有项目重新生成大纲/设定 |
| `outline <project>` | 查看大纲 |
| `bible <project>` | 查看设定集 |
| `export <project>` | 导出全文 markdown |

### 写作执行
| 命令 | 说明 |
|------|------|
| `write <project> [cid]` | 写指定章节或下一章（含审校+追踪+备份） |
| `batch <project> <n>` | 连写 n 章 |
| `rewrite <project> <cid> --passage "原文" --to "指令"` | 局部重写（自动归档旧版） |
| `version <project> <cid> --list/--rollback/--diff` | 章节版本管理 |

### 知识库
| 命令 | 说明 |
|------|------|
| `kb <project> view` | 查看完整知识库 |
| `kb <project> idea --add "..."` | 记录灵感 |
| `kb <project> world --build` | 搭建/补全世界观 |
| `kb <project> threads --weave` | 串联故事线 |
| `kb <project> timeline` | 时间线校核 |
| `kb <project> place` | idea 安插建议 |

### 分析与质量
| 命令 | 说明 |
|------|------|
| `pacing <project> --analyze` | 节奏曲线分析 |
| `style <project> --analyze` | 提取文风指纹 |
| `style <project> --check c001` | 检测某章文风漂移 |
| `track <project> --all` | 补跑状态追踪 |
| `search <project> <关键词> [--semantic]` | 全文/语义搜索 |

### 进度与成本
| 命令 | 说明 |
|------|------|
| `stats <project>` | 写作进度仪表盘 |
| `cost <project>` | Token 用量与成本统计 |
| `backup <project>` | 手动备份 |
| `test` | 测试 LLM 后端连通性 |

## 飞书 Bot

飞书 Bot 是小说AI的移动端入口，非常适合随时记录灵感、查看进度。

### 启动

```bash
python feishu_bot.py
```

Bot 使用飞书**长连接模式**（无需公网 IP / 域名）。

### 前置配置（飞书开放平台后台，一次性）

1. 创建「企业自建应用」，记下 App ID / App Secret
2. 权限管理 → 开通：`im:message`、`im:message:send_as_bot`、`im:chat`、`contact:user`
3. 事件与回调 → 切换为**长连接模式**
4. 添加事件：`接收消息 v2.0` (im.message.receive_v1) 和 `消息已读` (im.message.message_read_v1)
5. 版本管理 → 创建版本并发布
6. 将 App ID/Secret 写入 `.env` 的 `FEISHU_APP_ID` / `FEISHU_APP_SECRET`

### 可用命令（飞书聊天里发送）

| 命令 | 功能 |
|------|------|
| `#帮助` | 显示命令列表 |
| `#想法 <内容> #标签 @人物` | 记录灵感 |
| `#想法列表` | 查看所有灵感 |
| `#进度` | 查看写作进度仪表盘 |
| `#下一章` | 写下一章（异步，完成后推送） |
| `#预览 [章节id]` | 预览章节（默认最新章节） |
| `#预览 下一章` | 预览下一个待写章节计划 |
| `#大纲` | 查看大纲 |
| `#设定` | 查看设定集 |
| `#连续性` | 查看连续性追踪表 |
| `#节奏` | 查看节奏曲线 |
| `#文风` | 查看文风指纹 |
| `#搜索 <关键词>` | 全文搜索 |
| `#知识库` | 查看完整知识库 |
| `#成本` | 查看成本统计 |
| `#备份` | 手动备份 |

长任务（写章节）约 1-3 分钟，完成后自动推送结果。

## 🧠 知识库架构

| 模块 | 文件 | 功能 |
|------|------|------|
| 设定集 | `bible.json` | 人物（含动态状态时间线）/地点/势力/物品/设定 |
| 连续性追踪 | `continuity.json` | 时间线/伏笔/持有物/承诺/既定事实 |
| 世界观 | `world.json` | 规则/历史/地理/文化/组织/术语，含硬约束 |
| 灵感库 | `ideas.json` | 场景/情节/对话/反转，按优先级标签管理 |
| 故事线 | `threads.json` | 主线/支线/人物线/悬念线节点串联 |
| 节奏曲线 | `pacing.json` | 每章张力/情绪/信息密度/节奏/钩子评分 |
| 文风指纹 | `style.json` | 全文文风特征 + 人物语言指纹 |
| 搜索索引 | `embeddings/` | 文本索引 + bge-m3 向量库（numpy） |

**写每章时，这些知识自动注入上下文**（设定 → 世界观约束 → 连续性约束 → 故事线 → 大纲 → 前情 → 灵感 idea），全部标注"务必遵守，不得违反"。

## 写作闭环

```
写章前： 世界观硬约束 + 连续性约束 + 故事线脉络 + 相关idea
         ↓
写章：   LLM 生成正文
         ↓
写完：   生成摘要 → 状态追踪回写bible → 更新continuity → 审校(偏离检测)
         ↓                                   [严重问题自动修订重写]
         └→ 自动备份 → 记录进度 → 记账token成本
```

## 项目结构

```
小说AI/
├── cli.py                        # 命令行入口（25+ 子命令）
├── webui.py                      # Gradio Web UI
├── feishu_bot.py                 # 飞书 Bot（长连接）
├── config.yaml                   # 你的配置文件
├── .env                          # API key
├── novel_agent/
│   ├── config.py                 # 配置加载
│   ├── kb.py                     # KnowledgeBase 统一接口
│   ├── llm/                      # LLM 后端
│   │   ├── openai_api.py         #   OpenAI 兼容 (DeepSeek/硅基/...)
│   │   ├── ollama.py             #   本地 Ollama
│   │   └── embedding.py          #   Embedding (硅基流动 bge-m3)
│   ├── core/                     # 数据模型（全部 JSON 持久化）
│   │   ├── project.py            #   项目元信息
│   │   ├── bible.py              #   设定集
│   │   ├── outline.py            #   大纲树
│   │   ├── chapter.py            #   章节 + 多版本管理
│   │   ├── continuity.py         #   连续性追踪
│   │   ├── world.py              #   世界观
│   │   ├── ideas.py              #   灵感库
│   │   ├── threads.py            #   故事线
│   │   ├── pacing.py             #   节奏数据
│   │   ├── style.py              #   文风指纹
│   │   ├── search.py             #   搜索引擎（关键词+向量）
│   │   ├── progress.py           #   写作进度
│   │   ├── usage.py              #   用量记账
│   │   ├── backup.py             #   自动备份
│   │   └── memory.py             #   记忆系统（上下文组装）
│   ├── agents/                   # Agent 编排
│   │   ├── novel.py              #   NovelAgent 总管
│   │   ├── planner.py            #   规划
│   │   ├── writer.py             #   写作
│   │   ├── reviewer.py           #   审校+偏离检测
│   │   ├── tracker.py            #   状态追踪
│   │   ├── kb_agent.py           #   知识库操作
│   │   ├── pacing_agent.py       #   节奏分析
│   │   ├── rewrite_agent.py      #   局部重写
│   │   ├── style_agent.py        #   文风分析
│   │   └── llm_helpers.py        #   LLM 调用工具
│   ├── prompts/                  # 所有 Prompt 模板
│   │   ├── planner.py / writer.py / reviewer.py / tracker.py
│   │   ├── kb.py / pacing.py / rewrite.py / style.py
│   └── feishu/                   # 飞书 Bot 模块
│       ├── commands.py           #   命令路由器（可独立测试）
│       └── bot.py                #   (占位，主逻辑在 feishu_bot.py)
├── projects/                     # 你的小说项目
│   └── mybook/                   #   一个项目
│       ├── project.json / bible.json / outline.json
│       ├── continuity.json / world.json / ideas.json
│       ├── threads.json / pacing.json / style.json
│       ├── progress.json / usage_log.json
│       ├── chapters/             #     章节正文 + 摘要表
│       │   └── versions/         #     历史版本
│       ├── backups/              #     自动备份 zip
│       └── embeddings/           #     向量库（可重建）
└── tests/
    └── test_offline.py           # 离线集成测试（mock LLM）
```

## 测试

```bash
python tests/test_offline.py      # 离线测试全数据流（不依赖网络）
```

## 使用建议

- **模型**：写长篇推荐 DeepSeek-V3（便宜 + 长文本好）；本地 7B 起步
- **省钱**：规划/摘要/审校用便宜模型，写作用强模型（writer_model 配置项）
- **人工把关**：自动生成后务必审阅大纲和设定；正文在 Web UI 里直接改后手动跑 `rewrite`
- **批量**：`batch` 适合无人值守，每 5-10 章用 `pacing --analyze` 检查一次节奏
- **飞书**：bot 适合碎片时间记录灵感、查看进度；大段写作建议用 CLI/WebUI
