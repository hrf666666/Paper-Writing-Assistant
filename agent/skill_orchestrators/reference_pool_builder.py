# -*- coding: utf-8 -*-
"""
参考文献池构建器 - Phase 0.5 (v11.1)

核心策略：
1. 在写论文之前，根据论文主题和项目代码提取搜索关键词
2. 通过 ScholarSearch 多源检索（S2/DBLP/CrossRef/arXiv），构建真实参考文献池
3. LLM 只能从参考池中选择引用，不能自由编造

v11.1 增强：
- 使用 tools/scholar_search.py 替代单一 S2 搜索
- 多源搜索自动降级（S2 429 → DBLP → CrossRef → arXiv）
- 本地缓存跨运行复用
- 构建池后，通过 paper-fetch 获取高优先级论文的全文 Markdown
- 搜索策略规则书: skills/reference_management/search_strategy.md

解决问题：
- References 中 75%+ 是 LLM 编造的问题
- 虚假作者 "A. B. Smith and C. D. Jones" 的问题
- 核心领域文献缺失的问题
- S2 429 限速导致空池的问题
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

        # === v11.1: 离线数据包作为基础（境内可靠） ===
        offline_count = self._load_offline_packs(project_data)
        logger.info(f"[RefPool] 离线数据包加载: {offline_count} 篇")

        # 1. 提取搜索关键词组
        try:
            keyword_groups = self._extract_keyword_groups(project_data, ref_data)
        except Exception as e:
            logger.error(f"[RefPool] 提取关键词失败: {e}")
            keyword_groups = {}
        logger.info(f"[RefPool] 提取到 {len(keyword_groups)} 组搜索关键词")

        # 2. 在线检索补充（如果离线数据不够或网络可用）
        if len(self._pool) < max_papers * 0.6:  # 离线数据不足 60% 才触发在线搜索
            for group_name, queries in keyword_groups.items():
                for query in queries:
                    if len(self._pool) >= max_papers:
                        break
                    self._search_and_add(query, group_name)
                    time.sleep(3)
        else:
            logger.info(f"[RefPool] 离线数据充足 ({len(self._pool)} 篇)，跳过在线搜索")

        # 3. 按相关度排序
        try:
            self._pool.sort(key=lambda p: p.get("_relevance_score", 0), reverse=True)
        except Exception as e:
            logger.error(f"[RefPool] 排序失败: {e}")

        # 4. 截取
        self._pool = self._pool[:max_papers]

        logger.info(f"[RefPool] 参考文献池构建完成: {len(self._pool)} 篇论文")
        return self._pool

    def _load_offline_packs(self, project_data: Dict) -> int:
        """
        v11.1: 从离线数据包加载预构建的参考文献
        境内网络不可用时，这是最可靠的数据来源
        """
        try:
            from tools.reference_pack_manager import get_reference_pack_manager
            mgr = get_reference_pack_manager()

            # 1. 根据项目主题确定需要的领域
            target_domains = self._detect_domains(project_data)

            # 2. 加载对应领域的论文
            all_offline = []
            for domain in target_domains:
                papers = mgr.get_papers_for_domain(domain)
                all_offline.extend(papers)

            # 3. 如果没有精确匹配，搜索所有包
            if not all_offline:
                paper_title = project_data.get("paper_title", "")
                all_offline = mgr.search_papers(paper_title, limit=40)

            # 4. 转换格式并添加到 pool
            pool_papers = mgr.to_reference_pool_format(all_offline)
            added = 0
            for paper in pool_papers:
                title = paper.get("title", "")
                title_lower = title.lower().strip()
                if title_lower in self._seen_titles:
                    continue
                pid = paper.get("doi") or paper.get("paperId") or title_lower
                if pid in self._seen_ids:
                    continue
                self._seen_ids.add(pid)
                self._seen_titles.add(title_lower)
                self._pool.append(paper)
                added += 1

            return added
        except Exception as e:
            logger.warning(f"[RefPool] 离线数据包加载失败: {e}")
            return 0

    def _detect_domains(self, project_data: Dict) -> List[str]:
        """根据项目数据检测需要的参考领域"""
        domains = []
        # v11.2: 多来源获取标题（project_data 不一定有 paper_title）
        title = project_data.get("paper_title", "").lower()
        if not title:
            try:
                from config.project_config import PAPER_TITLE
                title = PAPER_TITLE.lower()
            except Exception as e:
                logger.debug(f"操作失败: {e}")
        venue = project_data.get("target_venue", "").lower()

        # 光场深度估计相关
        if any(kw in title for kw in ["light field", "depth estimation", "epipolar", "plenoptic"]):
            domains.append("light_field_depth_estimation")

        # 计算机视觉基础（几乎所有 CV 论文都需要）
        domains.append("computer_vision_foundations")

        return domains

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
        datasets_raw = exp_design.get("数据集", [])
        # 数据集可能是 dict（如 {"名称": [...], "规模": {...}}）或 list
        if isinstance(datasets_raw, dict):
            # 从 dict 中提取名称列表
            names = datasets_raw.get("名称", [])
            if isinstance(names, list):
                datasets = names
            else:
                datasets = [str(names)]
        elif isinstance(datasets_raw, list):
            datasets = datasets_raw
        else:
            datasets = []

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
        baselines_raw = exp_design.get("对比方法", exp_design.get("baselines", []))
        # 基线方法也可能是 dict
        if isinstance(baselines_raw, dict):
            names = baselines_raw.get("名称", baselines_raw.get("methods", []))
            if isinstance(names, list):
                baselines = names
            else:
                baselines = [str(names)]
        elif isinstance(baselines_raw, list):
            baselines = baselines_raw
        else:
            baselines = []

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
        """执行搜索并添加到池中（v11.1: 使用 academic_search 多源搜索 + MCP 代理）"""
        try:
            from tools.academic_search import academic_search
            query = " ".join(keywords) if isinstance(keywords, list) else str(keywords)
            results = academic_search(query, limit=10, use_mcp=True)

            if not results:
                # 降级到旧接口（paper_search.py 的 MCP + S2 + 百度学术）
                logger.debug(f"[RefPool] ScholarSearch 无结果，降级到 paper_search: {query[:50]}")
                self._search_and_add_fallback(keywords, group)
                return

            for paper in results:
                # paper 是 PaperResult 或 dict
                if hasattr(paper, 'to_dict'):
                    paper = paper.to_dict()

                title = paper.get("title", "")
                if not title:
                    continue

                title_lower = title.lower().strip()
                if title_lower in self._seen_titles:
                    continue

                # 用 DOI 或 paper_id 去重
                pid = paper.get("doi") or paper.get("paper_id") or title_lower
                if pid in self._seen_ids:
                    continue

                self._seen_ids.add(pid)
                self._seen_titles.add(title_lower)

                authors = paper.get("authors", [])
                if isinstance(authors, list) and authors and isinstance(authors[0], str):
                    authors = [{"name": a} for a in authors]

                self._pool.append({
                    "paperId": paper.get("paper_id", pid),
                    "title": title,
                    "year": paper.get("year"),
                    "authors": authors,
                    "venue": paper.get("venue", ""),
                    "abstract": (paper.get("abstract", "") or "")[:300],
                    "citationCount": paper.get("citation_count", paper.get("citationCount", 0)),
                    "doi": paper.get("doi", ""),
                    "externalIds": {"DOI": paper.get("doi", "")} if paper.get("doi") else {},
                    "group": group,
                    "_relevance_score": (paper.get("citation_count", paper.get("citationCount", 0)) or 0) * 0.3 + len(group) * 10,
                })

        except ImportError:
            logger.warning("[RefPool] academic_search 不可用，降级到 paper_search")
            self._search_and_add_fallback(keywords, group)
        except Exception as e:
            logger.warning(f"[RefPool] 搜索失败 ({keywords}): {e}")
            self._search_and_add_fallback(keywords, group)

    def _search_and_add_fallback(self, keywords: List[str], group: str):
        """降级搜索：使用原有 paper_search.py 的 MCP + S2 + 百度学术链"""
        try:
            from api.paper_search import search_papers, get_paper_details
            time.sleep(2)
            result = search_papers(keywords, 5)

            if "data" not in result or not result["data"]:
                return

            for paper_brief in result["data"]:
                paper_id = paper_brief.get("paperId", paper_brief.get("id", ""))

                if paper_id in self._seen_ids:
                    continue

                try:
                    details = get_paper_details(paper_id)
                    if "data" not in details or not details["data"]:
                        continue
                    paper = details["data"][0]
                except Exception as e:
                    logger.debug(f"论文处理失败: {e}")
                    continue

                title = paper.get("title", "")
                title_lower = title.lower().strip()
                if title_lower in self._seen_titles:
                    continue

                self._seen_ids.add(paper_id)
                self._seen_titles.add(title_lower)

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
                    "_relevance_score": paper.get("citationCount", 0) * 0.3 + len(group) * 10,
                })

        except Exception as e:
            logger.warning(f"[RefPool] 降级搜索失败 ({keywords}): {e}")

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
                                api_client=None, max_papers: int = 80,
                                enrich_fulltext: bool = True,
                                max_fulltext: int = 15) -> List[Dict]:
    """
    主入口：构建参考文献池

    v11.0: 新增 paper-fetch 全文增强
    - 构建池后，对高优先级论文通过 paper-fetch 获取 Markdown 全文
    - 全文保存到 ref_md/ 目录，供 ref_pdf_analyzer 使用

    Args:
        project_data: 项目分析数据
        ref_data: 参考 PDF 分析数据
        api_client: API 客户端
        max_papers: 最大论文数量
        enrich_fulltext: 是否用 paper-fetch 获取全文增强
        max_fulltext: 最多获取几篇全文

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

    # v11.0: paper-fetch 全文增强
    if enrich_fulltext and pool:
        try:
            _enrich_pool_with_fulltext(pool, max_fulltext)
        except Exception as e:
            logger.warning(f"[RefPool] paper-fetch 全文增强失败: {e}")

    try:
        builder.save(OUTPUT_DIR)
    except Exception as e:
        logger.error(f"[RefPool] 保存参考文献池失败: {e}")

    return pool


def _enrich_pool_with_fulltext(pool: List[Dict], max_papers: int = 15):
    """
    通过 paper-fetch 为参考池中的高优先级论文获取全文 Markdown。

    优先级：引用数高的优先（更有参考价值）
    """
    try:
        from tools.paper_fetch_tool import is_available, fetch_and_save
    except ImportError:
        logger.info("[RefPool] paper_fetch_tool 不可用，跳过全文增强")
        return

    if not is_available():
        logger.info("[RefPool] paper-fetch 未安装，跳过全文增强")
        return

    # 计算保存目录
    from config.project_config import REF_PDF_PATH
    import os
    md_dir = os.path.join(os.path.dirname(REF_PDF_PATH), "ref_md")

    # 按引用数排序，取高优先级论文
    sorted_pool = sorted(
        pool,
        key=lambda p: p.get("citationCount", 0),
        reverse=True,
    )

    enriched = 0
    for entry in sorted_pool:
        if enriched >= max_papers:
            break

        # 跳过已获取的
        if entry.get("markdown_path"):
            continue

        # 优先 DOI
        query = entry.get("externalIds", {}).get("DOI", "")
        if not query:
            query = entry.get("title", "")
        if not query:
            continue

        content, md_path = fetch_and_save(query, md_dir)
        if md_path:
            entry["markdown_path"] = md_path
            entry["content_kind"] = content.content_kind
            entry["token_estimate"] = content.token_estimate
            enriched += 1

    logger.info(f"[RefPool] paper-fetch 全文增强: {enriched}/{min(len(pool), max_papers)}")
