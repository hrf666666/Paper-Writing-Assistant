# -*- coding: utf-8 -*-
"""
RefSearchStrategist — 参考论文搜索策略规划器 (v10.1)

核心原则：精准收束，逐层放宽
1. 从项目创新点提取核心方向
2. LLM 规划逐层搜索策略（Level 1 精准 → Level 4 大领域兜底）
3. 每层搜索后检查是否达到目标，够了就停
4. 优先近 2 年论文，找不到再逐步放宽年份和范围

代码 = 裁判（逐层搜索、计数、判断是否停止）
LLM = 运动员（提取核心方向、规划搜索词）
MD = 规则书（搜索策略引导）
"""

from __future__ import annotations

import json
import os
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

_SKILL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "skills", "journal_style")


class RefSearchStrategist:
    """LLM 驱动的参考论文精准搜索策略规划"""

    def __init__(self, api_client):
        self.api_client = api_client

    def plan_search_strategy(
        self,
        project_data: Dict,
        innovation_points: List[Dict],
        venue: str,
        existing_dois: Optional[List[str]] = None,
        existing_count: int = 0,
    ) -> Dict:
        """
        规划逐层收束的搜索策略。

        Args:
            project_data: 项目数据
            innovation_points: 创新点列表
            venue: 目标期刊名
            existing_dois: 已有论文 DOI（避免重复）
            existing_count: 已有论文数量

        Returns:
            {
                "core_direction": str,
                "search_layers": [
                    {
                        "level": 1-4,
                        "description": str,
                        "queries": [{"keywords": str, "year_from": int, ...}],
                        "target_count": int,
                        "stop_if_found": int,  # 累计达到此数停止后续层
                    },
                    ...
                ],
                "must_include_dois": [str],
                "excluded_keywords": [str],
            }
        """
        # 加载策略引导
        guide = self._load_guide("ref_search_strategy_guide.md")

        # 构建创新点摘要
        innovation_summary = self._summarize_innovations(innovation_points)

        # 构建项目领域信息
        project_info = project_data.get("project_info", {})
        report_content = project_info.get("report_content", "")[:2000]

        # 已有论文信息
        existing_info = ""
        if existing_count > 0:
            existing_info = f"已有 {existing_count} 篇参考论文在 ref_pdf/ 中，请避免重复搜索。"

        prompt = f"""Plan a layered reference paper search strategy for this research project targeting {venue}.

## Search Strategy Guide
{guide}

## Project Innovation Points
{innovation_summary}

## Project Description
{report_content}

## Existing Papers
{existing_info}

## Task
Based on the project's core innovation direction, plan a PRECISE, LAYERED search strategy.
Start from the most specific search (Level 1) and progressively broaden (Level 4).
Level 5 is ALWAYS included for survey papers (separate category).

Rules:
1. Extract 2-3 core technical keyword combinations from the innovation points
2. Level 1: exact core direction + last 2 years (2024-2026)
3. Level 2: core direction + key techniques from each innovation point (2023-2026)
4. Level 3: broaden sub-domain, remove finest granularity qualifier (2021-2026)
5. Level 4: broad domain + classic papers (2020-2026, NO surveys)
6. Level 5: survey/review papers ONLY (is_survey=true, 1-3 papers, for Related Work only)
7. Target: 15-30 research papers + 1-3 surveys. STOP if cumulative target reached.
8. All search keywords must be in ENGLISH academic terms.
9. Level 5 MUST be included even if Level 1-4 found enough papers.
10. Survey papers are marked with "is_survey": true — they do NOT participate in style learning.

Output ONLY valid JSON (no markdown code blocks):
{{
  "core_direction": "one sentence describing the project's core research direction",
  "is_survey_paper": false,
  "search_layers": [
    {{
      "level": 1,
      "description": "core innovation direction search",
      "is_survey": false,
      "queries": [
        {{"keywords": "exact English search phrase", "year_from": 2024, "year_to": 2026, "venue": "{venue}"}}
      ],
      "target_count": 10,
      "stop_if_found": 8
    }},
    {{
      "level": 2,
      "description": "core direction + key techniques",
      "is_survey": false,
      "queries": [
        {{"keywords": "combined search phrase", "year_from": 2023, "year_to": 2026, "venue": ""}},
        {{"keywords": "another combination", "year_from": 2023, "year_to": 2026, "venue": ""}}
      ],
      "target_count": 10,
      "stop_if_found": 15
    }},
    {{
      "level": 3,
      "description": "sub-domain expansion",
      "is_survey": false,
      "queries": [
        {{"keywords": "broader search phrase", "year_from": 2021, "year_to": 2026, "venue": ""}}
      ],
      "target_count": 5,
      "stop_if_found": 20
    }},
    {{
      "level": 4,
      "description": "broad domain + classics (NO surveys)",
      "is_survey": false,
      "queries": [
        {{"keywords": "broad domain search", "year_from": 2020, "year_to": 2026, "venue": ""}}
      ],
      "target_count": 5,
      "stop_if_found": 25
    }},
    {{
      "level": 5,
      "description": "survey papers for Related Work (NOT for style learning)",
      "is_survey": true,
      "queries": [
        {{"keywords": "survey OR review OR taxonomy + domain keyword", "year_from": 2020, "year_to": 2026, "venue": ""}}
      ],
      "target_count": 3,
      "stop_if_found": 3
    }}
  ],
  "must_include_dois": ["DOIs of essential papers that must be downloaded"],
  "excluded_keywords": ["keywords to exclude as they are too broad or irrelevant"]
}}"""

        try:
            response = self.api_client.call_generation(prompt)
            strategy = self._parse_strategy(response)

            # 验证策略完整性
            strategy = self._validate_strategy(strategy)

            logger.info(
                f"[RefSearchStrategist] 策略规划完成: "
                f"核心方向='{strategy.get('core_direction', '')[:60]}', "
                f"{len(strategy.get('search_layers', []))} 层搜索"
            )
            return strategy

        except Exception as e:
            logger.error(f"[RefSearchStrategist] 策略规划失败: {e}")
            return self._fallback_strategy(innovation_points, venue)

    def _summarize_innovations(self, innovation_points: List[Dict]) -> str:
        """构建创新点英文摘要"""
        if not innovation_points:
            return "No innovation points available"

        lines = []
        for i, ip in enumerate(innovation_points, 1):
            name = ip.get("创新点名称", ip.get("name", f"Innovation {i}"))
            content = ip.get("创新点工作内容", ip.get("content", []))
            value = ip.get("创新点价值", ip.get("value", ""))

            # 如果有英文贡献声明，优先使用
            anchor = ip.get("anchor", {})
            contribution = anchor.get("contribution_statement", "")

            lines.append(f"Innovation {i}: {name}")
            if contribution:
                lines.append(f"  Contribution: {contribution}")
            if isinstance(content, list):
                for c in content[:2]:
                    lines.append(f"  - {str(c)[:120]}")
            else:
                lines.append(f"  - {str(content)[:120]}")
            lines.append(f"  Value: {str(value)[:120]}")

        return "\n".join(lines)

    def _parse_strategy(self, response: str) -> Dict:
        """解析 LLM 输出的搜索策略"""
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
            return json.loads(text)
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
                                return json.loads(text[start:i + 1])
                            except json.JSONDecodeError:
                                pass
                            break
            return {}

    def _validate_strategy(self, strategy: Dict) -> Dict:
        """验证策略完整性"""
        if "core_direction" not in strategy:
            strategy["core_direction"] = "unknown direction"

        if "search_layers" not in strategy or not strategy["search_layers"]:
            strategy["search_layers"] = self._default_layers()

        # 确保每层都有必要字段
        for layer in strategy["search_layers"]:
            if "level" not in layer:
                continue
            if "queries" not in layer:
                layer["queries"] = []
            if "target_count" not in layer:
                layer["target_count"] = 5
            if "stop_if_found" not in layer:
                layer["stop_if_found"] = 15

        if "must_include_dois" not in strategy:
            strategy["must_include_dois"] = []
        if "excluded_keywords" not in strategy:
            strategy["excluded_keywords"] = []

        return strategy

    def _default_layers(self) -> List[Dict]:
        """默认搜索层级"""
        return [
            {
                "level": 1,
                "description": "core direction search",
                "queries": [{"keywords": "depth estimation", "year_from": 2024, "year_to": 2026, "venue": ""}],
                "target_count": 10,
                "stop_if_found": 8,
            },
            {
                "level": 2,
                "description": "sub-field search",
                "queries": [{"keywords": "depth estimation survey", "year_from": 2022, "year_to": 2026, "venue": ""}],
                "target_count": 10,
                "stop_if_found": 15,
            },
            {
                "level": 3,
                "description": "broad domain",
                "queries": [{"keywords": "3D reconstruction OR scene understanding", "year_from": 2020, "year_to": 2026, "venue": ""}],
                "target_count": 5,
                "stop_if_found": 20,
            },
        ]

    def _fallback_strategy(
        self,
        innovation_points: List[Dict],
        venue: str,
    ) -> Dict:
        """降级策略（LLM 不可用时）"""
        # 从创新点名称中提取关键词
        keywords = set()
        for ip in innovation_points[:3]:
            name = ip.get("创新点名称", "")
            anchor = ip.get("anchor", {})
            contrib = anchor.get("contribution_statement", "")
            if contrib:
                # 从英文贡献声明中提取关键词
                words = contrib.lower().split()
                ngrams = []
                for i in range(len(words) - 1):
                    bigram = f"{words[i]} {words[i+1]}"
                    ngrams.append(bigram)
                keywords.update(ngrams[:3])

        core_kw = " OR ".join(list(keywords)[:3]) if keywords else "depth estimation"

        return {
            "core_direction": "automated from innovation points",
            "is_survey_paper": False,
            "search_layers": [
                {
                    "level": 1,
                    "description": "core keywords from innovation points",
                    "is_survey": False,
                    "queries": [{"keywords": core_kw, "year_from": 2024, "year_to": 2026, "venue": venue}],
                    "target_count": 10,
                    "stop_if_found": 8,
                },
                {
                    "level": 2,
                    "description": "broadened search",
                    "is_survey": False,
                    "queries": [{"keywords": core_kw, "year_from": 2022, "year_to": 2026, "venue": ""}],
                    "target_count": 10,
                    "stop_if_found": 18,
                },
                {
                    "level": 3,
                    "description": "domain-level search",
                    "is_survey": False,
                    "queries": [{"keywords": "depth estimation", "year_from": 2020, "year_to": 2026, "venue": ""}],
                    "target_count": 5,
                    "stop_if_found": 25,
                },
                {
                    "level": 5,
                    "description": "survey papers for Related Work",
                    "is_survey": True,
                    "queries": [{"keywords": f"survey OR review {core_kw}", "year_from": 2020, "year_to": 2026, "venue": ""}],
                    "target_count": 3,
                    "stop_if_found": 3,
                },
            ],
            "must_include_dois": [],
            "excluded_keywords": [],
        }

    def _load_guide(self, filename: str) -> str:
        """加载引导文件"""
        path = os.path.join(_SKILL_DIR, filename)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        return "Plan a layered search strategy: specific first, then broaden."
