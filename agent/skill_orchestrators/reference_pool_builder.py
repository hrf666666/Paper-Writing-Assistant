# -*- coding: utf-8 -*-
"""
参考文献池构建器 - Phase 0.5

核心策略：
1. 在写论文之前，根据论文主题和项目代码提取搜索关键词
2. 通过 Semantic Scholar 批量检索，构建真实参考文献池
3. LLM 只能从参考池中选择引用，不能自由编造

解决问题：
- References 中 75%+ 是 LLM 编造的问题
- 虚假作者 "A. B. Smith and C. D. Jones" 的问题
- 核心领域文献缺失的问题
"""

import json
import time
import logging
from typing import Dict, List, Optional

from agent.base_orchestrator import BaseOrchestrator

logger = logging.getLogger(__name__)


class ReferencePoolBuilder(BaseOrchestrator):
    """
    参考文献池构建器

    工作流程：
    1. 从 project_data 和 ref_data 提取搜索关键词
    2. 生成多组搜索查询（按主题、方法、数据集等分类）
    3. 通过 Semantic Scholar 批量检索
    4. 去重并构建参考文献池
    5. 保存到 output/reference_pool.json
    """

    def __init__(self, api_client=None):
        super().__init__()
        self.api_client = api_client
        self._pool: List[Dict] = []
        self._seen_ids = set()
        self._seen_titles = set()

    def build(self, project_data: Dict, ref_data: Dict,
              max_papers: int = 80) -> List[Dict]:
        """
        构建参考文献池

        Args:
            project_data: 项目分析数据
            ref_data: 参考 PDF 分析数据
            max_papers: 最大论文数量

        Returns:
            参考文献池列表
        """
        self._pool = []
        self._seen_ids = set()
        self._seen_titles = set()

        # 1. 提取搜索关键词组
        try:
            keyword_groups = self._extract_keyword_groups(project_data, ref_data)
        except Exception as e:
            logger.error(f"[RefPool] 提取关键词失败: {e}")
            keyword_groups = {}
        logger.info(f"[RefPool] 提取到 {len(keyword_groups)} 组搜索关键词")

        # 2. 逐组检索（增加限速保护）
        for group_name, queries in keyword_groups.items():
            for query in queries:
                if len(self._pool) >= max_papers:
                    break
                self._search_and_add(query, group_name)
                time.sleep(3)  # 增加到 3 秒，避免 API 限速

        # 3. 按相关度排序
        try:
            self._pool.sort(key=lambda p: p.get("_relevance_score", 0), reverse=True)
        except Exception as e:
            logger.error(f"[RefPool] 排序失败: {e}")

        # 4. 截取
        self._pool = self._pool[:max_papers]

        logger.info(f"[RefPool] 参考文献池构建完成: {len(self._pool)} 篇论文")
        return self._pool

    def _extract_keyword_groups(self, project_data: Dict, ref_data: Dict) -> Dict[str, List]:
        """
        从项目数据中提取多组搜索关键词

        返回:
            {
                "core_topic": [["keyword1", "keyword2"]],
                "methods": [["method1", "method2"]],
                "datasets": [["dataset1"]],
                "baselines": [["baseline1", "baseline2"]],
            }
        """
        groups = {}

        # 1. 核心主题关键词
        innovation_points = project_data.get("innovation_points", [])
        core_terms = set()
        for ip in innovation_points:
            name = ip.get("创新点名称", "")
            if name:
                core_terms.add(name)
            # 从工作内容中提取术语
            for work in ip.get("创新点工作内容", []):
                # 提取英文术语（简单策略：取每个工作描述的关键名词）
                words = work.split()
                english_words = [w for w in words if w.isascii() and len(w) > 3]
                core_terms.update(english_words[:3])

        if core_terms:
            groups["core_topic"] = [list(core_terms)[:5]]

        # 2. 方法关键词
        model_arch = project_data.get("model_architecture", {})
        if model_arch:
            overall = model_arch.get("总体架构", "")
            modules = model_arch.get("模块详情", [])
            method_terms = []
            if overall:
                # 提取关键方法术语
                method_terms.append(overall[:100])
            for mod in modules[:3]:
                mod_name = mod.get("模块名", "")
                if mod_name:
                    method_terms.append(mod_name)
            if method_terms:
                groups["methods"] = [[t] for t in method_terms[:5]]

        # 3. 数据集关键词
        exp_design = project_data.get("experiment_design", {})
        datasets = exp_design.get("数据集", [])
        if datasets:
            dataset_queries = []
            for ds in datasets[:3]:
                if isinstance(ds, str):
                    dataset_queries.append([ds])
                elif isinstance(ds, dict):
                    ds_name = ds.get("名称", ds.get("name", ""))
                    if ds_name:
                        dataset_queries.append([ds_name])
            if dataset_queries:
                groups["datasets"] = dataset_queries

        # 4. 基线方法关键词
        baselines = exp_design.get("对比方法", exp_design.get("baselines", []))
        if baselines:
            baseline_queries = []
            for bl in baselines[:5]:
                if isinstance(bl, str):
                    baseline_queries.append([bl])
                elif isinstance(bl, dict):
                    bl_name = bl.get("名称", bl.get("name", ""))
                    if bl_name:
                        baseline_queries.append([bl_name])
            if baseline_queries:
                groups["baselines"] = baseline_queries

        # 5. 使用 LLM 扩展关键词（如果有 API client）
        if self.api_client:
            try:
                expanded = self._expand_keywords_with_llm(project_data)
                if expanded:
                    groups["llm_expanded"] = expanded
            except Exception as e:
                logger.warning(f"[RefPool] LLM 关键词扩展失败: {e}")

        return groups

    def _expand_keywords_with_llm(self, project_data: Dict) -> List[List[str]]:
        """使用 LLM 生成更多搜索关键词"""
        innovation = project_data.get("innovation_points", [])
        arch = project_data.get("model_architecture", {})

        prompt = f"""Based on the following research project, generate 5 search queries for finding relevant academic papers on Semantic Scholar.
Each query should be a list of 2-4 keywords in AND relationship.

Project innovation points: {json.dumps(innovation[:3], ensure_ascii=False)[:500]}
Model architecture: {json.dumps(arch, ensure_ascii=False)[:500]}

Return ONLY a JSON array of arrays, e.g.: [["keyword1", "keyword2"], ["keyword3", "keyword4"]]
No explanation needed."""

        response = self.api_client.call_light(prompt)
        try:
            cleaned = response.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[len("```json"):]
            if cleaned.startswith("```"):
                cleaned = cleaned[len("```"):]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-len("```")]
            cleaned = cleaned.strip()
            result = json.loads(cleaned)
            if isinstance(result, list):
                return [q for q in result if isinstance(q, list)][:5]
        except (json.JSONDecodeError, ValueError):
            pass

        return []

    def _search_and_add(self, keywords: List[str], group: str):
        """执行搜索并添加到池中"""
        try:
            from api.paper_search import search_papers, get_paper_details
            time.sleep(2)  # 每次搜索前额外等待
            result = search_papers(keywords, 5)

            if "data" not in result or not result["data"]:
                return

            for paper_brief in result["data"]:
                paper_id = paper_brief.get("paperId", paper_brief.get("id", ""))

                # 去重
                if paper_id in self._seen_ids:
                    continue

                # 获取详情
                try:
                    details = get_paper_details(paper_id)
                    if "data" not in details or not details["data"]:
                        continue
                    paper = details["data"][0]
                except Exception:
                    continue

                title = paper.get("title", "")
                title_lower = title.lower().strip()
                if title_lower in self._seen_titles:
                    continue

                self._seen_ids.add(paper_id)
                self._seen_titles.add(title_lower)

                # 提取作者
                authors = []
                if isinstance(paper.get("authors"), list):
                    authors = [a.get("name", "") for a in paper["authors"] if a.get("name")]

                self._pool.append({
                    "paperId": paper_id,
                    "title": title,
                    "year": paper.get("year"),
                    "authors": authors,
                    "venue": paper.get("venue", {}).get("raw", "") if isinstance(paper.get("venue"), dict) else str(paper.get("venue", "")),
                    "abstract": paper.get("abstract", "")[:300],
                    "citationCount": paper.get("citationCount", 0),
                    "group": group,
                    "_relevance_score": paper.get("citationCount", 0) * 0.3 + len(group) * 10,  # 综合引用数和搜索组相关度
                })

        except Exception as e:
            logger.warning(f"[RefPool] 搜索失败 ({keywords}): {e}")

    def save(self, output_dir: str):
        """保存参考文献池到磁盘"""
        import os
        try:
            pool_data = {
                "total": len(self._pool),
                "papers": self._pool,
            }
            filepath = os.path.join(output_dir, "reference_pool.json")
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(pool_data, f, ensure_ascii=False, indent=2)
            logger.info(f"[RefPool] 参考文献池已保存到 {filepath}")
        except Exception as e:
            logger.error(f"[RefPool] 保存参考文献池失败: {e}")

    def load(self, output_dir: str) -> List[Dict]:
        """从磁盘加载参考文献池"""
        import os
        filepath = os.path.join(output_dir, "reference_pool.json")
        if not os.path.exists(filepath):
            return []
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self._pool = data.get("papers", [])
            logger.info(f"[RefPool] 从 {filepath} 加载 {len(self._pool)} 篇论文")
        except Exception as e:
            logger.error(f"[RefPool] 加载参考文献池失败: {e}")
            self._pool = []
        return self._pool


def run_reference_pool_builder(project_data: Dict, ref_data: Dict,
                                api_client=None, max_papers: int = 80) -> List[Dict]:
    """
    主入口：构建参考文献池

    Args:
        project_data: 项目分析数据
        ref_data: 参考 PDF 分析数据
        api_client: API 客户端
        max_papers: 最大论文数量

    Returns:
        参考文献池列表
    """
    from config.project_config import OUTPUT_DIR

    builder = ReferencePoolBuilder(api_client)
    try:
        pool = builder.build(project_data, ref_data, max_papers)
    except Exception as e:
        logger.error(f"[RefPool] 参考文献池构建失败: {e}")
        pool = []
    
    try:
        builder.save(OUTPUT_DIR)
    except Exception as e:
        logger.error(f"[RefPool] 保存参考文献池失败: {e}")

    return pool
