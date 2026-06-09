# -*- coding: utf-8 -*-
"""
ContentStrategist — 内容策略规划器 (v10.1)

基于创新点、目标期刊和动机线程，规划每章的内容策略：
- 写什么 / 不写什么
- 重点写什么 / 略写什么
- 创新点在哪章重点阐述
- 动机锚点是否被覆盖

核心原则：
- 代码 = 裁判（验证策略完整性、锚点覆盖）
- LLM = 运动员（基于上下文生成策略）
- 输出的 ContentStrategy 驱动 Phase 1-5 的内容生成
"""

from __future__ import annotations

import json
import os
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# 引导文件路径
_SKILL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "skills", "journal_style")


class ContentStrategist:
    """基于创新点和目标期刊，规划每章的内容策略"""

    def __init__(self, api_client):
        """
        Args:
            api_client: BaseOrchestrator 实例
        """
        self.api_client = api_client

    def plan(
        self,
        project_data: Dict,
        innovation_points: List[Dict],
        venue_name: str,
        journal_style: Dict,
        motivation_thread: Optional[Dict] = None,
        sections: Optional[List[str]] = None,
    ) -> Dict[str, Dict]:
        """
        规划每章的内容策略。

        Args:
            project_data: 项目数据（包含 model_architecture, experiment_design 等）
            innovation_points: 创新点列表
            venue_name: 目标期刊名
            journal_style: JournalStyleLearner 的输出
            motivation_thread: MotivationEngine 的输出
            sections: 章节列表

        Returns:
            {chapter_name: {focus_areas, depth_map, innovation_allocation,
                            must_include, should_avoid, target_emphasis}}
        """
        if sections is None:
            sections = ["Introduction", "Related Work", "Methodology",
                        "Experiments", "Conclusion"]

        logger.info(f"[ContentStrategist] 规划 {len(sections)} 章的内容策略")

        # 加载策略模板
        template = self._load_guide("content_strategy_template.md")

        # 构建创新点摘要
        innovation_summary = self._summarize_innovations(innovation_points)

        # 构建动机线程摘要
        motivation_summary = ""
        if motivation_thread:
            anchors = motivation_thread.get("anchors", [])
            motivation_summary = "\n".join(
                f"  - {a.get('chapter_name', '?')}: {a.get('anchor_type', '?')} — {a.get('anchor_text', '')[:100]}"
                for a in anchors
            )

        # 构建期刊风格摘要（截断避免太长）
        style_summary = json.dumps(journal_style, ensure_ascii=False, indent=2)[:3000]

        prompt = f"""You are planning the content strategy for a paper targeting {venue_name}.

## Innovation Points
{innovation_summary}

## Motivation Thread (anchors that must be covered)
{motivation_summary if motivation_summary else "No motivation thread specified"}

## Journal Style (learned from {venue_name} papers)
{style_summary}

## Strategy Template
{template}

## Task
For each chapter, create a detailed content strategy. Think about:
1. Which innovation points should be emphasized in which chapters?
2. What should be written in depth vs. briefly?
3. What must be included vs. avoided?
4. How should the motivation thread anchors be covered?

Output ONLY valid JSON (no markdown code blocks):
```json
{{
  "Introduction": {{
    "focus_areas": ["...", "..."],
    "depth_map": {{"subsection_name": "deep|moderate|brief|skip"}},
    "innovation_allocation": {{"创新点1": "primary|supporting|mention"}},
    "must_include": ["...", "..."],
    "should_avoid": ["...", "..."],
    "target_emphasis": "one sentence describing the chapter's primary goal"
  }},
  "Related Work": {{...}},
  "Methodology": {{...}},
  "Experiments": {{...}},
  "Conclusion": {{...}}
}}
```"""

        try:
            response = self.api_client.call_generation(prompt)
            strategy = self._parse_strategy(response, sections)

            # 验证策略完整性
            strategy = self._validate_strategy(strategy, sections, motivation_thread)

            return strategy

        except Exception as e:
            logger.error(f"[ContentStrategist] 策略规划失败: {e}")
            return self._fallback_strategy(sections, innovation_points)

    def _summarize_innovations(self, innovation_points: List[Dict]) -> str:
        """构建创新点摘要"""
        if not innovation_points:
            return "No innovation points specified"

        lines = []
        for i, ip in enumerate(innovation_points, 1):
            name = ip.get("创新点名称", ip.get("name", f"Innovation {i}"))
            content = ip.get("创新点工作内容", ip.get("content", []))
            value = ip.get("创新点价值", ip.get("value", "N/A"))
            lines.append(f"创新点{i}: {name}")
            if isinstance(content, list):
                lines.append(f"  内容: {'; '.join(str(c) for c in content)}")
            else:
                lines.append(f"  内容: {content}")
            lines.append(f"  价值: {value}")

        return "\n".join(lines)

    def _parse_strategy(self, response: str, sections: List[str]) -> Dict[str, Dict]:
        """解析 LLM 的策略输出"""
        text = response.strip()

        # 去掉 markdown 代码块
        if "```json" in text:
            start = text.index("```json") + 7
            end = text.find("```", start)
            if end == -1:
                end = len(text)
            text = text[start:end].strip()
        elif "```" in text:
            start = text.index("```") + 3
            first_nl = text.find("\n", start)
            if first_nl != -1:
                end = text.find("```", first_nl)
                if end == -1:
                    end = len(text)
                text = text[first_nl + 1:end].strip()

        try:
            result = json.loads(text)
        except json.JSONDecodeError:
            # 平衡括号匹配
            start = text.find("{")
            if start != -1:
                depth = 0
                in_str = False
                esc = False
                for i in range(start, len(text)):
                    c = text[i]
                    if esc:
                        esc = False
                        continue
                    if c == "\\":
                        esc = True
                        continue
                    if c == '"':
                        in_str = not in_str
                        continue
                    if in_str:
                        continue
                    if c == "{":
                        depth += 1
                    elif c == "}":
                        depth -= 1
                        if depth == 0:
                            try:
                                result = json.loads(text[start:i + 1])
                            except json.JSONDecodeError:
                                result = {}
                            break
                else:
                    result = {}
            else:
                result = {}

        # 确保所有章节都有策略
        for section in sections:
            if section not in result:
                result[section] = self._default_chapter_strategy(section)

        return result

    def _validate_strategy(
        self,
        strategy: Dict[str, Dict],
        sections: List[str],
        motivation_thread: Optional[Dict],
    ) -> Dict[str, Dict]:
        """验证策略完整性（代码做裁判）"""
        for section in sections:
            s = strategy.get(section, {})

            # 确保必要字段存在
            if "focus_areas" not in s:
                s["focus_areas"] = []
            if "depth_map" not in s:
                s["depth_map"] = {}
            if "innovation_allocation" not in s:
                s["innovation_allocation"] = {}
            if "must_include" not in s:
                s["must_include"] = []
            if "should_avoid" not in s:
                s["should_avoid"] = []
            if "target_emphasis" not in s:
                s["target_emphasis"] = f"Write a compelling {section}"

            strategy[section] = s

        # 验证动机锚点覆盖（如果有动机线程）
        if motivation_thread:
            anchors = motivation_thread.get("anchors", [])
            for anchor in anchors:
                chapter = anchor.get("chapter_name", "")
                if chapter in strategy:
                    anchor_text = anchor.get("anchor_text", "")[:80]
                    covered = any(
                        anchor_text.lower() in str(v).lower()
                        for s in [strategy[chapter].get("must_include", []),
                                  strategy[chapter].get("focus_areas", [])]
                        for v in (s if isinstance(s, list) else s.values())
                    )
                    if not covered:
                        # 自动将锚点加入 must_include
                        strategy[chapter]["must_include"].append(
                            f"[动机锚点] {anchor.get('anchor_text', '')[:100]}"
                        )
                        logger.info(f"[ContentStrategist] 自动补充锚点到 {chapter}: {anchor_text[:50]}...")

        return strategy

    def _fallback_strategy(
        self,
        sections: List[str],
        innovation_points: List[Dict],
    ) -> Dict[str, Dict]:
        """降级策略（LLM 不可用时）"""
        strategy = {}
        for section in sections:
            strategy[section] = self._default_chapter_strategy(section)
        return strategy

    def _default_chapter_strategy(self, section: str) -> Dict:
        """单章默认策略"""
        defaults = {
            "Introduction": {
                "focus_areas": ["问题重要性", "现有方法局限", "本文贡献"],
                "depth_map": {"背景": "brief", "局限分析": "moderate", "贡献": "deep"},
                "innovation_allocation": {},
                "must_include": ["清晰的 gap statement", "具体贡献列表"],
                "should_avoid": ["详细的方法描述"],
                "target_emphasis": "建立问题重要性和研究动机",
            },
            "Related Work": {
                "focus_areas": ["按方法分类综述", "指出各类方法局限"],
                "depth_map": {},
                "innovation_allocation": {},
                "must_include": ["与本文方法最相关的 5-10 篇工作详细讨论"],
                "should_avoid": ["纯时间顺序罗列"],
                "target_emphasis": "建立研究空白，为本文方法铺垫",
            },
            "Methodology": {
                "focus_areas": ["整体架构", "创新模块详细描述"],
                "depth_map": {},
                "innovation_allocation": {},
                "must_include": ["完整公式推导", "模块间数据流"],
                "should_avoid": ["不必要的已有方法推导细节"],
                "target_emphasis": "清晰呈现本文方法的设计思路和技术细节",
            },
            "Experiments": {
                "focus_areas": ["与SOTA对比", "消融实验"],
                "depth_map": {},
                "innovation_allocation": {},
                "must_include": ["完整的消融实验", "定量对比表格"],
                "should_avoid": ["过度吹嘘结果"],
                "target_emphasis": "全面验证方法有效性",
            },
            "Conclusion": {
                "focus_areas": ["核心贡献总结", "未来方向"],
                "depth_map": {},
                "innovation_allocation": {},
                "must_include": ["与 Introduction 贡献呼应"],
                "should_avoid": ["引入新信息"],
                "target_emphasis": "简洁有力的总结",
            },
        }
        return defaults.get(section, {
            "focus_areas": [],
            "depth_map": {},
            "innovation_allocation": {},
            "must_include": [],
            "should_avoid": [],
            "target_emphasis": f"写好 {section}",
        })

    def _load_guide(self, filename: str) -> str:
        """加载引导文件"""
        path = os.path.join(_SKILL_DIR, filename)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        return ""
