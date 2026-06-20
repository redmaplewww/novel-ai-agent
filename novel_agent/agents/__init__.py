"""Agent 编排：把 LLM 后端 + Prompt + 数据模型串起来。

四个 Agent：
  - PlannerAgent  : 生成主线/大纲/章节计划/设定集
  - WriterAgent   : 写章节正文 + 生成摘要
  - ReviewerAgent : 偏离大纲检测 + 一致性检查 + 修订
  - StateTracker  : 提取状态变化、回写设定集、更新连续性表

外加一个 NovelAgent 总管，封装项目级的高层操作。
"""

from .llm_helpers import call_json, extract_json_block
from .planner import PlannerAgent
from .writer import WriterAgent
from .reviewer import ReviewerAgent
from .tracker import StateTracker
from .novel import NovelAgent

__all__ = [
    "call_json",
    "extract_json_block",
    "PlannerAgent",
    "WriterAgent",
    "ReviewerAgent",
    "StateTracker",
    "NovelAgent",
]
