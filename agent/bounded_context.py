# -*- coding: utf-8 -*-
"""
恒定大小上下文管理器 — 3层记忆，固定字符预算

借鉴 auto_research_agent 的 constant-size context 设计：
- 无论论文多长，注入到 LLM 的上下文始终在预算范围内
- 3层记忆：工作记忆 + 短期记忆 + 长期记忆（磁盘）
- 自动压缩：超出预算时按优先级压缩（保留关键数据，丢弃冗余描述）

解决的问题：
- 长论文后半段质量退化（上下文爆炸）
- API Token 浪费（传递过多重复内容）
- 关键信息被淹没在大量文本中

用法:
    ctx = BoundedContextManager(budget=5000)
    ctx.set_working_memory(current_chapter_outline)
    ctx.update_short_term(previous_chapter_summary, key_data_table)
    prompt_context = ctx.build_prompt_context()  # 保证 <= budget 字符
"""

import re
import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from collections import OrderedDict

logger = logging.getLogger(__name__)


class BoundedContextManager:
    """
    3层恒定大小上下文管理器

    层级：
    1. 工作记忆（~30% 预算）：当前章节的大纲 + 关键公式 + 生成策略
    2. 短期记忆（~40% 预算）：前一章节的摘要 + 关键数据表 + 符号定义
    3. 长期记忆（~30% 预算）：项目简报 + 创新点 + 核心术语表

    总预算默认 5000 字符（~1500 tokens），保证在任何阶段都恒定。
    """

    def __init__(self, budget: int = 5000):
        self.budget = budget

        # 3层记忆
        self._working: Dict[str, str] = {}      # 当前章节的工作上下文
        self._short_term: Dict[str, str] = {}   # 前序章节的摘要
        self._long_term: Dict[str, str] = {}    # 项目级固定信息

        # 章节摘要缓存（不放入 prompt，仅用于跨章节传递）
        self._chapter_summaries: Dict[str, str] = {}

        # 符号表（跨章节传递，保证一致性）
        self._symbol_table: Dict[str, str] = {}  # symbol -> definition

    @property
    def working_memory(self) -> str:
        return self._concat_dict(self._working)

    @property
    def short_term_memory(self) -> str:
        return self._concat_dict(self._short_term)

    @property
    def long_term_memory(self) -> str:
        return self._concat_dict(self._long_term)

    # ──────────── 工作记忆 ────────────

    def set_working(self, key: str, value: str):
        """设置工作记忆项"""
        self._working[key] = value

    def clear_working(self):
        """清空工作记忆（新章节开始时调用）"""
        self._working.clear()

    def set_chapter_outline(self, outline: str):
        """设置当前章节大纲到工作记忆"""
        self.set_working("chapter_outline", outline)

    def set_generation_strategy(self, strategy: str):
        """设置生成策略到工作记忆"""
        self.set_working("strategy", strategy)

    # ──────────── 短期记忆 ────────────

    def update_short_term(self, chapter_summaries: Dict[str, str],
                          key_data: str = ""):
        """
        更新短期记忆

        Args:
            chapter_summaries: {chapter_name: summary_text}
            key_data: 关键数据表（如实验结果表格的提取）
        """
        self._short_term.clear()

        for ch_name, summary in chapter_summaries.items():
            self._short_term[f"prev_{ch_name}"] = summary

        if key_data:
            self._short_term["key_data"] = key_data

        # 符号表
        if self._symbol_table:
            symbols_text = self._format_symbol_table()
            self._short_term["symbols"] = symbols_text

    def update_chapter_summary(self, chapter_key: str, content: str):
        """
        更新章节摘要缓存

        从完整内容中提取结构化摘要（不放入 prompt，仅传递给下一章节）
        """
        summary = self._extract_structured_summary(content)
        self._chapter_summaries[chapter_key] = summary
        logger.debug(f"[BoundedContext] 章节 {chapter_key} 摘要: {len(summary)} 字符")

    def get_chapter_summary(self, chapter_key: str) -> str:
        """获取章节摘要"""
        return self._chapter_summaries.get(chapter_key, "")

    def get_previous_summaries(self, current_chapter_num: int,
                                max_chars_per: int = 1000) -> Dict[str, str]:
        """
        获取前序章节摘要（用于传递给章节生成器）

        Args:
            current_chapter_num: 当前章节号
            max_chars_per: 每个章节摘要的最大字符数

        Returns:
            {chapter_num: summary_text}
        """
        result = {}
        for i in range(1, current_chapter_num):
            key = str(i)
            summary = self._chapter_summaries.get(key, "")
            if summary:
                result[key] = summary[:max_chars_per]
        return result

    # ──────────── 长期记忆 ────────────

    def set_project_brief(self, brief: str):
        """设置项目简报（固定，不频繁更新）"""
        self._long_term["project_brief"] = brief

    def set_innovation_points(self, points: List[Dict]):
        """设置创新点（固定）"""
        text = "\n".join(
            f"{i + 1}. {p.get('创新点名称', p.get('name', 'N/A'))}: "
            f"{p.get('创新点价值', p.get('value', ''))[:100]}"
            for i, p in enumerate(points[:5])
        )
        self._long_term["innovations"] = text

    def set_key_terms(self, terms: Dict[str, str]):
        """设置关键术语表"""
        lines = [f"- {k}: {v}" for k, v in list(terms.items())[:15]]
        self._long_term["terms"] = "\n".join(lines)

    # ──────────── 符号表 ────────────

    def register_symbol(self, symbol: str, definition: str):
        """注册一个符号定义"""
        self._symbol_table[symbol] = definition

    def extract_symbols_from_content(self, content: str):
        """从内容中提取符号定义并存入符号表"""
        # 模式1: "$symbol$ (description)" 或 "$symbol$ — description"
        patterns = [
            r'\$([^$]+)\$\s*[\(（]([^)）]{3,50})[\)）]',
            r'\$([^$]+)\$\s*[—\-–]\s*([^\n]{3,50})',
            r'where \$([^$]+)\$ is ([^\n]{3,50})',
        ]
        for pattern in patterns:
            for m in re.finditer(pattern, content):
                symbol = m.group(1).strip()
                definition = m.group(2).strip()
                if len(symbol) <= 20:  # 过滤掉太长的公式
                    self._symbol_table[symbol] = definition

    # ──────────── 上下文构建 ────────────

    def build_prompt_context(self) -> str:
        """
        构建注入到 LLM 的上下文（保证 <= budget 字符）

        优先级：长期记忆 > 工作记忆 > 短期记忆
        高优先级的先占满，低优先级的填充剩余空间
        """
        budget_allocation = {
            "long_term": int(self.budget * 0.30),
            "working": int(self.budget * 0.30),
            "short_term": int(self.budget * 0.40),
        }

        parts = []

        # 1. 长期记忆（项目简报、创新点）
        long_text = self._format_section(
            "Project Context", self._long_term, budget_allocation["long_term"]
        )
        parts.append(long_text)

        remaining = self.budget - len(long_text)

        # 2. 工作记忆（当前章节大纲、策略）
        work_text = self._format_section(
            "Current Task", self._working, budget_allocation["working"]
        )
        parts.append(work_text)

        remaining -= len(work_text)

        # 3. 短期记忆（前序章节摘要，弹性使用剩余空间）
        short_budget = max(budget_allocation["short_term"], remaining)
        short_text = self._format_section(
            "Previous Chapters", self._short_term, short_budget
        )
        parts.append(short_text)

        result = "\n\n".join(p for p in parts if p)

        # 最终保障：绝对不超过预算
        if len(result) > self.budget:
            result = result[:self.budget - 50] + "\n\n[context truncated to budget]"

        logger.debug(f"[BoundedContext] prompt context: {len(result)}/{self.budget} chars")
        return result

    # ──────────── 内部方法 ────────────

    def _format_section(self, title: str, data: Dict[str, str],
                         budget: int) -> str:
        """格式化一个记忆层级，保证在预算内"""
        if not data:
            return ""

        lines = [f"## {title}"]
        used = len(lines[0]) + 1

        for key, value in data.items():
            entry = f"**{key}**: {value}"
            if used + len(entry) + 1 > budget:
                # 空间不够了，压缩当前条目
                remaining = budget - used - 20
                if remaining > 50:
                    entry = f"**{key}**: {value[:remaining]}..."
                    lines.append(entry)
                break
            lines.append(entry)
            used += len(entry) + 1

        return "\n".join(lines)

    def _format_symbol_table(self) -> str:
        """格式化符号表"""
        if not self._symbol_table:
            return ""
        lines = ["Symbol definitions:"]
        for symbol, definition in list(self._symbol_table.items())[:10]:
            lines.append(f"  ${symbol}$: {definition}")
        return "\n".join(lines)

    @staticmethod
    def _concat_dict(data: Dict[str, str]) -> str:
        """拼接字典值"""
        return "\n".join(f"{k}: {v}" for k, v in data.items())

    @staticmethod
    def _extract_structured_summary(content: str) -> str:
        """
        从章节内容中提取结构化摘要

        提取：
        1. 标题和子标题
        2. 关键数值（实验结果）
        3. 关键术语定义
        4. 去除冗余描述
        """
        if not content:
            return ""

        parts = []

        # 1. 提取标题
        headings = re.findall(r'^(#{1,3}\s+.+)$', content, re.MULTILINE)
        if headings:
            parts.append("Structure: " + " > ".join(
                h.strip().lstrip('#').strip() for h in headings[:6]
            ))

        # 2. 提取关键数值
        numbers = re.findall(
            r'(?:accuracy|error|score|performance|MAE|RMSE|PSNR|SSIM)[\s:=]+\(?([\d.]+)',
            content, re.IGNORECASE
        )
        if numbers:
            parts.append("Key metrics: " + ", ".join(numbers[:8]))

        # 3. 首段摘要（截取前300字）
        paragraphs = [p.strip() for p in content.split('\n\n') if len(p.strip()) > 30]
        if paragraphs:
            first_para = paragraphs[0]
            if first_para.startswith('#'):
                first_para = paragraphs[1] if len(paragraphs) > 1 else ""
            if first_para:
                parts.append(first_para[:300])

        return "\n".join(parts)

    def get_stats(self) -> Dict[str, Any]:
        """获取上下文使用统计"""
        ctx = self.build_prompt_context()
        return {
            "total_budget": self.budget,
            "actual_size": len(ctx),
            "usage_pct": round(len(ctx) / self.budget * 100, 1) if self.budget else 0,
            "working_items": len(self._working),
            "short_term_items": len(self._short_term),
            "long_term_items": len(self._long_term),
            "chapter_summaries": len(self._chapter_summaries),
            "symbol_table_size": len(self._symbol_table),
        }
