# -*- coding: utf-8 -*-
"""
Tool: 创新点验证器

三阶段验证：
Stage 1: 新颖性验证 — MCP/百度学术/S2 搜索确认候选创新点是否已被提出
Stage 2: 递进关系设计 — 确保 3 个创新点形成逻辑递进链
Stage 3: 章节锚定 — 每个创新点映射到 Methodology/Experiments 的具体子节
"""

import os
import re
import json
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class InnovationVerifier:
    """创新点三阶段验证器"""

    def __init__(self, output_dir: str, api_client=None):
        self.output_dir = output_dir
        self.api_client = api_client
        self.result_path = os.path.join(output_dir, "innovation_verified.json")

    def verify_all(self, innovation_points: List[Dict]) -> Dict:
        """
        执行完整的三阶段验证

        Returns:
            {
                "innovation_points": [...],  # 增强后的创新点
                "novelty_scores": [...],
                "progression": {...},
                "anchor_map": {...},
            }
        """
        result = {
            "innovation_points": innovation_points,
            "novelty_scores": [],
            "progression": {},
            "anchor_map": {},
        }

        # Stage 1: 新颖性验证
        novelty_scores = self.verify_novelty(innovation_points)
        result["novelty_scores"] = novelty_scores

        # Stage 2: 递进关系设计
        progression = self.design_progression(innovation_points, novelty_scores)
        result["progression"] = progression

        # Stage 3: 章节锚定
        outline = self._load_outline()
        anchor_map = self.anchor_to_sections(innovation_points, outline, progression)
        result["anchor_map"] = anchor_map

        # 保存
        with open(self.result_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        # 更新 innovation_points.json（增加验证信息）
        enhanced = self._enhance_innovation_points(innovation_points, result)
        ip_path = os.path.join(self.output_dir, "innovation_points.json")
        with open(ip_path, "w", encoding="utf-8") as f:
            json.dump(enhanced, f, ensure_ascii=False, indent=2)

        avg_novelty = sum(n.get("score", 0.5) for n in novelty_scores) / max(len(novelty_scores), 1)
        logger.info(f"[InnovationVerify] 新颖性均分={avg_novelty:.2f}, "
                     f"递进={progression.get('type', 'unknown')}, "
                     f"锚定={len(anchor_map)} 个创新点")
        return result

    def verify_novelty(self, innovation_points: List[Dict]) -> List[Dict]:
        """
        Stage 1: 对每个创新点进行新颖性搜索

        通过 MCP/百度学术/Semantic Scholar 搜索，判断候选创新点是否已被提出。
        """
        scores = []

        for i, ip in enumerate(innovation_points):
            name = ip.get("创新点名称", ip.get("name", ""))
            content_list = ip.get("创新点工作内容", ip.get("content", []))
            search_query = name
            if isinstance(content_list, list) and content_list:
                search_query = f"{name} {' '.join(str(c) for c in content_list[:2])}"
            search_query = search_query[:120]

            novelty = {
                "index": i,
                "name": name,
                "score": 0.5,  # 默认中等
                "overlapping_works": [],
                "verdict": "unverified",
            }

            # 尝试 MCP/多源搜索
            try:
                from api.paper_search import verify_citation_with_mcp
                mcp_result = verify_citation_with_mcp(search_query)
                if mcp_result.get("verified"):
                    # 找到了相关工作，需要评估重叠程度
                    novelty["overlapping_works"] = mcp_result.get("found_urls", [])
                    if mcp_result.get("matched_paper"):
                        novelty["overlapping_works"].append(
                            mcp_result["matched_paper"].get("title", ""))
                    # LLM 评估重叠度
                    if self.api_client:
                        overlap_score = self._evaluate_overlap(
                            ip, mcp_result.get("matched_paper", {}))
                        novelty["score"] = 1.0 - overlap_score  # 重叠越高，新颖性越低
                    else:
                        novelty["score"] = 0.3  # 保守估计
                    novelty["verdict"] = "partially_novel"
                else:
                    novelty["score"] = 0.8  # 搜索不到相关工作，可能是新颖的
                    novelty["verdict"] = "likely_novel"
            except Exception as e:
                logger.debug(f"[InnovationVerify] 搜索失败 ({name}): {e}")
                novelty["verdict"] = "search_failed"
                novelty["score"] = 0.5

            scores.append(novelty)
            logger.info(f"  [{novelty['verdict']}] {name}: novelty={novelty['score']:.2f}")

        return scores

    def design_progression(self, innovation_points: List[Dict],
                            novelty_scores: List[Dict]) -> Dict:
        """
        Stage 2: 设计创新点的递进关系

        理想递进: 问题定义 → 方法创新 → 验证应用
        """
        names = [ip.get("创新点名称", ip.get("name", f"创新点{i+1}"))
                 for i, ip in enumerate(innovation_points)]

        progression = {
            "type": "unknown",
            "chain": [],
            "story_line": "",
            "contribution_statements": [],
        }

        if not self.api_client or len(innovation_points) < 2:
            # 降级：基于启发式推断
            progression["type"] = "heuristic"
            progression["chain"] = names
            progression["story_line"] = " → ".join(names)
            return progression

        # LLM 设计递进关系
        prompt = f"""You are a senior research advisor. Given these 2-3 innovation points of a paper, design their logical progression.

Innovation points:
{json.dumps(names, ensure_ascii=False)}

Ideal progression patterns:
- Pattern A: Problem definition → Method innovation → Validation/Application
- Pattern B: Observation → Analysis → Solution
- Pattern C: Component 1 → Component 2 → Integration

For each innovation point, provide:
1. Its role in the progression (problem/analysis/solution/validation)
2. A one-sentence contribution statement
3. How it connects to the next point

Also provide a 2-sentence story line that ties all innovations together.

Output JSON:
{{
    "progression_type": "A|B|C|custom",
    "chain": [
        {{"name": "innovation name", "role": "problem|analysis|method|validation", "contribution": "one sentence", "connects_to_next": "how"}}
    ],
    "story_line": "2 sentences",
    "contribution_statements": ["We identify that...", "We propose...", "We demonstrate..."]
}}

```json ... ``` only."""

        try:
            response = self.api_client.call_evaluation(prompt)
            result = self.api_client.parse_json_response(response, default={})
            if isinstance(result, dict) and "chain" in result:
                progression.update(result)
        except Exception as e:
            logger.warning(f"[InnovationVerify] 递进设计失败: {e}")
            progression["type"] = "fallback"
            progression["chain"] = names
            progression["story_line"] = " → ".join(names)

        return progression

    def anchor_to_sections(self, innovation_points: List[Dict],
                            outline: Dict = None,
                            progression: Dict = None) -> Dict:
        """
        Stage 3: 将创新点锚定到具体章节

        输出 anchor_map: {innovation_N: {related_work, methodology, experiment}}
        """
        anchor_map = {}
        outline = outline or self._load_outline()

        # 章节子节默认映射（如果 outline 不可用）
        default_sections = {
            1: {  # 创新点1
                "related_work_section": "2.1 Traditional Methods",
                "methodology_section": "3.2",
                "experiment_section": "4.3",
            },
            2: {
                "related_work_section": "2.2 Deep Learning Methods",
                "methodology_section": "3.3",
                "experiment_section": "4.4",
            },
            3: {
                "related_work_section": "2.2 Deep Learning Methods",
                "methodology_section": "3.4",
                "experiment_section": "4.5",
            },
        }

        for i, ip in enumerate(innovation_points):
            name = ip.get("创新点名称", ip.get("name", f"Innovation_{i+1}"))
            key = f"innovation_{i+1}"

            # 尝试从 outline 匹配子节
            anchor = default_sections.get(i + 1, {}).copy()
            anchor["name"] = name

            # 从 outline 查找匹配的子节
            if outline:
                for chapter_name, chapter_info in outline.items():
                    if isinstance(chapter_info, dict):
                        subsections = chapter_info.get("subsections", [])
                        for sub in subsections:
                            sub_name = sub if isinstance(sub, str) else sub.get("name", "")
                            # 简单匹配：创新点关键词是否出现在子节名中
                            name_words = set(re.findall(r'[a-zA-Z]+', name.lower()))
                            sub_words = set(re.findall(r'[a-zA-Z]+', sub_name.lower()))
                            if name_words & sub_words:
                                chapter_lower = chapter_name.lower()
                                if "method" in chapter_lower:
                                    anchor["methodology_section"] = sub_name
                                elif "experiment" in chapter_lower:
                                    anchor["experiment_section"] = sub_name
                                elif "related" in chapter_lower:
                                    anchor["related_work_section"] = sub_name

            # 生成贡献声明
            contribution = ""
            if progression and progression.get("contribution_statements"):
                statements = progression["contribution_statements"]
                if i < len(statements):
                    contribution = statements[i]
            anchor["contribution_statement"] = contribution

            anchor_map[key] = anchor

        # 保存
        anchor_path = os.path.join(self.output_dir, "anchor_map.json")
        with open(anchor_path, "w", encoding="utf-8") as f:
            json.dump(anchor_map, f, ensure_ascii=False, indent=2)

        return anchor_map

    def _evaluate_overlap(self, innovation: Dict, matched_paper: Dict) -> float:
        """用 LLM 评估创新点与匹配论文的重叠度 (0-1)"""
        if not self.api_client or not matched_paper:
            return 0.3

        ip_name = innovation.get("创新点名称", "")
        ip_content = innovation.get("创新点工作内容", [])
        mp_title = matched_paper.get("title", "")
        mp_abstract = matched_paper.get("abstract", "")[:500]

        prompt = f"""Rate the conceptual overlap between these two research contributions (0.0 = completely different, 1.0 = essentially identical):

Our innovation: {ip_name}
Our content: {json.dumps(ip_content, ensure_ascii=False)[:300]}

Published paper: {mp_title}
Abstract: {mp_abstract}

Output only a single float number between 0.0 and 1.0:"""

        try:
            response = self.api_client.call_light(prompt)
            score = float(re.search(r'[\d.]+', response).group())
            return min(max(score, 0.0), 1.0)
        except Exception:
            return 0.3

    def _load_outline(self) -> Dict:
        path = os.path.join(self.output_dir, "outline.json")
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _enhance_innovation_points(self, points: List[Dict], result: Dict) -> List[Dict]:
        """增强创新点数据（添加验证信息）"""
        enhanced = []
        for i, ip in enumerate(points):
            e = dict(ip)
            if i < len(result.get("novelty_scores", [])):
                e["novelty_score"] = result["novelty_scores"][i]["score"]
                e["novelty_verdict"] = result["novelty_scores"][i]["verdict"]
            key = f"innovation_{i+1}"
            if key in result.get("anchor_map", {}):
                e["anchor"] = result["anchor_map"][key]
            enhanced.append(e)
        return enhanced


def run_innovation_verifier(output_dir: str, innovation_points: List[Dict],
                             api_client=None) -> Dict:
    """创新点验证入口"""
    verifier = InnovationVerifier(output_dir, api_client)
    return verifier.verify_all(innovation_points)
