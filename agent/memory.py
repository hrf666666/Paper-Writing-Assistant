# -*- coding: utf-8 -*-
"""
记忆管理器 - 双层记忆系统

设计参考 auto-deep-researcher 的记忆架构：
- PROJECT_BRIEF: 固定大小的项目简报（自动压缩）
- MEMORY_LOG: 执行日志（自动滚动，保留最近N条）

特性：
1. 常量大小的记忆占用
2. 自动压缩过长的记忆条目
3. 支持关键词检索
4. 持久化到磁盘
"""

import json
import time
import os
import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field, asdict

from config.project_config import OUTPUT_DIR

logger = logging.getLogger(__name__)


@dataclass
class MemoryEntry:
    """记忆条目"""
    timestamp: float
    category: str       # "brief" | "log" | "decision" | "error" | "quality"
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "MemoryEntry":
        return cls(**d)


class MemoryManager:
    """
    双层记忆管理器

    PROJECT_BRIEF（项目简报层）:
    - 存储：项目核心信息、创新点、架构、实验设计
    - 大小：固定上限，超出自动摘要压缩
    - 用途：每次生成时作为上下文注入

    MEMORY_LOG（执行日志层）:
    - 存储：每步执行的结果、决策、错误、质量评估
    - 大小：滚动窗口，保留最近 MAX_LOG_ENTRIES 条
    - 用途：REFLECT 阶段回顾历史，发现模式
    """

    # 记忆大小限制
    MAX_BRIEF_CHARS = 8000       # 项目简报最大字符数
    MAX_LOG_ENTRIES = 50         # 执行日志最大条目数
    MAX_ENTRY_CHARS = 2000       # 单条日志最大字符数

    def __init__(self, output_dir: str = None):
        self.output_dir = output_dir or OUTPUT_DIR
        self._brief: str = ""
        self._log_entries: List[MemoryEntry] = []
        self._decisions: List[MemoryEntry] = []  # 关键决策记录
        self._dead_ends: List[str] = []           # 已确认的死路

    @property
    def brief(self) -> str:
        """获取项目简报"""
        return self._brief

    @brief.setter
    def brief(self, value: str):
        """设置项目简报（自动压缩）"""
        if len(value) > self.MAX_BRIEF_CHARS:
            logger.info(f"项目简报过长({len(value)}字符)，自动压缩")
            self._brief = self._compress_brief(value)
        else:
            self._brief = value

    def _compress_brief(self, text: str) -> str:
        """压缩过长的项目简报，按段落边界截断以保留完整结构"""
        budget = self.MAX_BRIEF_CHARS - 200
        # 按双换行分段，保留完整段落
        paragraphs = text.split('\n\n')
        compressed_parts = []
        current_len = 0
        for para in paragraphs:
            if current_len + len(para) + 2 > budget:
                break
            compressed_parts.append(para)
            current_len += len(para) + 2

        result = '\n\n'.join(compressed_parts)
        result += "\n\n[注意：项目简报已自动压缩，完整信息请查看 output/ 目录下的原始JSON文件]"
        return result

    def add_log(self, category: str, content: str, metadata: Dict = None):
        """
        添加执行日志

        Args:
            category: 日志类别 (brief/log/decision/error/quality)
            content: 日志内容
            metadata: 附加元数据
        """
        if len(content) > self.MAX_ENTRY_CHARS:
            content = content[:self.MAX_ENTRY_CHARS - 50] + "\n...[已截断]"

        entry = MemoryEntry(
            timestamp=time.time(),
            category=category,
            content=content,
            metadata=metadata or {}
        )

        self._log_entries.append(entry)

        # 如果是决策，也加入决策列表
        if category == "decision":
            self._decisions.append(entry)

        # 滚动窗口：超出上限时移除最旧的
        if len(self._log_entries) > self.MAX_LOG_ENTRIES:
            self._log_entries = self._log_entries[-self.MAX_LOG_ENTRIES:]

    def add_dead_end(self, description: str):
        """
        记录已确认的死路（避免重复尝试）

        在REFLECT阶段发现某策略无效时调用
        """
        if description not in self._dead_ends:
            self._dead_ends.append(description)
            self.add_log("decision", f"死路确认: {description}")

    def is_dead_end(self, description: str) -> bool:
        """检查某策略是否已被确认为死路"""
        return any(description in de for de in self._dead_ends)

    def get_recent_logs(self, n: int = 10, category: str = None) -> List[MemoryEntry]:
        """获取最近的N条日志"""
        entries = self._log_entries
        if category:
            entries = [e for e in entries if e.category == category]
        return entries[-n:]

    def get_decisions(self) -> List[MemoryEntry]:
        """获取所有决策记录"""
        return self._decisions.copy()

    def get_dead_ends(self) -> List[str]:
        """获取所有死路记录"""
        return self._dead_ends.copy()

    def build_context_for_prompt(self, max_chars: int = 4000) -> str:
        """
        构建注入到LLM prompt的上下文

        包含项目简报 + 最近日志摘要 + 死路警告
        """
        context_parts = []

        # 1. 项目简报
        if self._brief:
            brief_budget = int(max_chars * 0.5)
            context_parts.append(f"<project_brief>\n{self._brief[:brief_budget]}\n</project_brief>")

        # 2. 最近日志摘要
        recent = self.get_recent_logs(5)
        if recent:
            log_budget = int(max_chars * 0.3)
            log_text = ""
            for entry in reversed(recent):
                time_str = time.strftime("%H:%M:%S", time.localtime(entry.timestamp))
                log_text += f"[{time_str}][{entry.category}] {entry.content[:200]}\n"
                if len(log_text) > log_budget:
                    break
            context_parts.append(f"<recent_logs>\n{log_text}\n</recent_logs>")

        # 3. 死路警告
        if self._dead_ends:
            dead_end_text = "\n".join(f"- {de}" for de in self._dead_ends[-5:])
            context_parts.append(f"<dead_ends>\n以下策略已确认无效，请勿重复尝试：\n{dead_end_text}\n</dead_ends>")

        return "\n\n".join(context_parts)

    def save(self, filepath: str = None):
        """持久化记忆到磁盘"""
        if filepath is None:
            filepath = os.path.join(self.output_dir, "memory_state.json")

        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        state = {
            "brief": self._brief,
            "log_entries": [e.to_dict() for e in self._log_entries],
            "decisions": [e.to_dict() for e in self._decisions],
            "dead_ends": self._dead_ends,
        }

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False, indent=2)

        logger.info(f"记忆已保存至 {filepath}")

    def load(self, filepath: str = None) -> bool:
        """从磁盘加载记忆"""
        if filepath is None:
            filepath = os.path.join(self.output_dir, "memory_state.json")

        if not os.path.exists(filepath):
            return False

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                state = json.load(f)

            self._brief = state.get("brief", "")
            self._log_entries = [MemoryEntry.from_dict(e) for e in state.get("log_entries", [])]
            self._decisions = [MemoryEntry.from_dict(e) for e in state.get("decisions", [])]
            self._dead_ends = state.get("dead_ends", [])

            logger.info(f"记忆已从 {filepath} 加载，{len(self._log_entries)} 条日志")
            return True
        except Exception as e:
            logger.error(f"加载记忆失败: {e}")
            return False

    def clear(self):
        """清空所有记忆"""
        self._brief = ""
        self._log_entries.clear()
        self._decisions.clear()
        self._dead_ends.clear()
