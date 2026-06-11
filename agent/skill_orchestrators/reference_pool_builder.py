# -*- coding: utf-8 -*-
"""
参考文献池构建器 - Phase 0.5 (v12.2)

核心策略：
1. 在写论文之前，根据论文主题和项目代码提取搜索关键词
2. 通过 ScholarSearch 多源检索（S2/DBLP/CrossRef/arXiv），构建真实参考文献池
3. LLM 只能从参考池中选择引用，不能自由编造

v12.2 重构：
- 使用 ReferenceStore (SQLite) 替代内存 _pool / JSON 文件
- 并行搜索：多组关键词 ThreadPool 并行 → 统一入库（SQLite 去重）
- 并行全文获取：_enrich_pool_with_fulltext ThreadPool 并行
- 子 Agent 边界：Searcher 写 papers + search_log，Fetcher 更新 fulltext_*
"""

import json
import os
import time
import logging
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from agent.base_orchestrator import BaseOrchestrator

logger = logging.getLogger(__name__)


class ReferencePoolBuilder(BaseOrchestrator):
    """
    参考文献池构建器 (v12.2)

    工作流程：
    1. 初始化 ReferenceStore，导入离线数据包
    2. 提取搜索关键词组
    3. 并行搜索（ThreadPool），结果统一写入 ReferenceStore
    4. 并行全文获取（ThreadPool）
    """

    def __init__(self, api_client=None, store=None):
        super().__init__()
        self.api_client = api_client
        self._store = store  # ReferenceStore instance

    def _get_store(self):
        """懒加载 ReferenceStore"""
        if self._store is None:
            from tools.reference_store import get_reference_store
            self._store = get_reference_store()
        return self._store

    def build(self, project_data: Dict, ref_data: Dict,
              max_papers: int = 80) -> List[Dict]:
        """
        构建参考文献池

        Args:
            project_data: 项目分析数据
            ref_data: 参考 PDF 分析数据
            max_papers: 最大论文数量

        Returns:
            参考文献池列表（兼容旧接口）
        """
        store = self._get_store()

        # === 1. 离线数据包作为基础 ===
        offline_count = self._load_offline_packs(project_data)
        logger.info(f"[RefPool] 离线数据包加载: {offline_count} 篇")

        current_count = store.get_paper_count()

        # === 2. 提取搜索关键词组 ===
        try:
            keyword_groups = self._extract_keyword_groups(project_data, ref_data)
        except Exception as e:
            logger.error(f"[RefPool] 提取关键词失败: {e}")
            keyword_groups = {}
        logger.info(f"[RefPool] 提取到 {len(keyword_groups)} 组搜索关键词")

        # === 3. 并行搜索（v12.2） ===
        if current_count < max_papers * 0.6:
            all_queries = []
            for group_name, queries in keyword_groups.items():
                for query in queries:
                    all_queries.append((query, group_name))

            if all_queries:
                # 先检查缓存，过滤已有搜索
                uncached = []
                for query, group in all_queries:
                    cache = store.search_cache_hit(
                        " ".join(query) if isinstance(query, list) else str(query),
                        "academic_search"
                    )
                    if cache is not None:
                        logger.debug(f"[RefPool] 缓存命中: {str(query)[:50]}")
                    else:
                        uncached.append((query, group))

                if uncached:
                    logger.info(f"[RefPool] 并行搜索 {len(uncached)} 组关键词...")
                    with ThreadPoolExecutor(max_workers=3) as executor:
                        futures = {}
                        for query, group in uncached:
                            future = executor.submit(
                                self._search_and_add, query, group
                            )
                            futures[future] = (query, group)

                        for future in as_completed(futures):
                            query, group = futures[future]
                            try:
                                future.result()
                            except Exception as e:
                                logger.warning(f"[RefPool] 搜索异常 ({query}): {e}")

                    new_count = store.get_paper_count()
                    logger.info(f"[RefPool] 搜索完成: {current_count} → {new_count}")
        else:
            logger.info(f"[RefPool] 离线数据充足 ({current_count} 篇)，跳过在线搜索")

        # === 4. 返回结果（兼容旧接口） ===
        pool = store.get_all_papers(limit=max_papers)
        logger.info(f"[RefPool] 参考文献池构建完成: {len(pool)} 篇论文")
        return pool

    def _load_offline_packs(self, project_data: Dict) -> int:
        """
        v12.2: 从离线数据包导入 ReferenceStore
        """
        store = self._get_store()

        # 如果已有数据，跳过
        if store.get_paper_count() > 0:
            logger.info(f"[RefPool] ReferenceStore 已有 {store.get_paper_count()} 篇，跳过离线导入")
            return store.get_paper_count()

        try:
            from tools.reference_pack_manager import get_reference_pack_manager
            mgr = get_reference_pack_manager()

            target_domains = self._detect_domains(project_data)
            all_offline = []
            for domain in target_domains:
                papers = mgr.get_papers_for_domain(domain)
                all_offline.extend(papers)

            if not all_offline:
                paper_title = project_data.get("paper_title", "")
                all_offline = mgr.search_papers(paper_title, limit=40)

            pool_papers = mgr.to_reference_pool_format(all_offline)
            count = store.upsert_papers_batch(pool_papers)
            return count
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
        """
        执行搜索并写入 ReferenceStore（v12.2: SQLite 去重，无需内存 set）
        """
        store = self._get_store()
        query = " ".join(keywords) if isinstance(keywords, list) else str(keywords)

        # 查缓存
        cached = store.search_cache_hit(query, "academic_search")
        if cached is not None:
            logger.debug(f"[RefPool] 搜索缓存命中: {query[:50]}")
            store.upsert_papers_batch(cached)
            return

        results_raw = []
        try:
            from tools.academic_search import academic_search
            results = academic_search(query, limit=10, use_mcp=True)

            if results:
                for paper in results:
                    if hasattr(paper, 'to_dict'):
                        paper = paper.to_dict()
                    authors = paper.get("authors", [])
                    if isinstance(authors, list) and authors and isinstance(authors[0], str):
                        authors = [{"name": a} for a in authors]

                    results_raw.append({
                        "title": paper.get("title", ""),
                        "year": paper.get("year"),
                        "authors": authors,
                        "venue": paper.get("venue", ""),
                        "abstract": (paper.get("abstract", "") or "")[:300],
                        "citationCount": paper.get("citation_count",
                                                    paper.get("citationCount", 0)),
                        "doi": paper.get("doi", ""),
                        "group": group,
                        "_source": "web_search",
                        "search_query": query,
                        "_relevance_score": (paper.get("citation_count",
                                                    paper.get("citationCount", 0)) or 0) * 0.3,
                    })
            else:
                logger.debug(f"[RefPool] 无结果，降级: {query[:50]}")
                results_raw = self._search_fallback_raw(keywords, group)

        except ImportError:
            logger.warning("[RefPool] academic_search 不可用，降级")
            results_raw = self._search_fallback_raw(keywords, group)
        except Exception as e:
            logger.warning(f"[RefPool] 搜索失败 ({keywords}): {e}")
            results_raw = self._search_fallback_raw(keywords, group)

        # 写入 ReferenceStore（upsert 自动去重）
        if results_raw:
            count = store.upsert_papers_batch(results_raw)
            # 缓存搜索结果
            store.log_search(query, "academic_search", results_raw)
            logger.debug(f"[RefPool] {query[:50]}: +{count} 篇")

    def _search_fallback_raw(self, keywords: List[str], group: str) -> List[Dict]:
        """降级搜索，返回原始结果列表"""
        try:
            from api.paper_search import search_papers, get_paper_details
            time.sleep(2)
            result = search_papers(keywords, 5)

            if "data" not in result or not result["data"]:
                return []

            papers = []
            for paper_brief in result["data"]:
                try:
                    details = get_paper_details(
                        paper_brief.get("paperId", paper_brief.get("id", ""))
                    )
                    if "data" not in details or not details["data"]:
                        continue
                    paper = details["data"][0]
                except Exception:
                    continue

                authors = []
                if isinstance(paper.get("authors"), list):
                    authors = [a.get("name", "") for a in paper["authors"]
                               if a.get("name")]

                venue = paper.get("venue", "")
                if isinstance(venue, dict):
                    venue = venue.get("raw", "")

                papers.append({
                    "title": paper.get("title", ""),
                    "year": paper.get("year"),
                    "authors": authors,
                    "venue": venue,
                    "abstract": (paper.get("abstract", "") or "")[:300],
                    "citationCount": paper.get("citationCount", 0),
                    "group": group,
                    "_source": "paper_search",
                    "_relevance_score": paper.get("citationCount", 0) * 0.3,
                    "search_query": " ".join(keywords) if isinstance(keywords, list) else str(keywords),
                })
            return papers

        except Exception as e:
            logger.warning(f"[RefPool] 降级搜索失败 ({keywords}): {e}")
            return []

    def save(self, output_dir: str):
        """v12.2: 兼容旧接口，数据已存入 SQLite，额外导出一份 JSON 供旧代码降级"""
        store = self._get_store()
        try:
            pool_data = store.export_reference_pool()
            filepath = os.path.join(output_dir, "reference_pool.json")
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(pool_data, f, ensure_ascii=False, indent=2)
            logger.info(f"[RefPool] 兼容导出: {filepath} ({pool_data['total']} 篇)")
        except Exception as e:
            logger.error(f"[RefPool] 导出失败: {e}")

    def load(self, output_dir: str) -> List[Dict]:
        """v12.2: 从 ReferenceStore 加载"""
        store = self._get_store()
        pool = store.get_all_papers(limit=200)
        logger.info(f"[RefPool] 从 ReferenceStore 加载 {len(pool)} 篇论文")
        return pool


def run_reference_pool_builder(project_data: Dict, ref_data: Dict,
                                api_client=None, max_papers: int = 80,
                                enrich_fulltext: bool = True,
                                max_fulltext: int = 15) -> List[Dict]:
    """
    主入口：构建参考文献池

    v12.2:
    - ReferenceStore (SQLite) 统一存储
    - 并行搜索 + 并行全文获取
    - 兼容导出 reference_pool.json
    """
    from config.project_config import OUTPUT_DIR

    # 初始化 ReferenceStore（自动导入旧数据）
    from tools.reference_store import init_reference_store_from_output
    store = init_reference_store_from_output(OUTPUT_DIR)

    builder = ReferencePoolBuilder(api_client, store=store)
    try:
        pool = builder.build(project_data, ref_data, max_papers)
    except Exception as e:
        logger.error(f"[RefPool] 参考文献池构建失败: {e}")
        pool = store.get_all_papers(limit=max_papers)

    # v12.2: 并行全文获取
    if enrich_fulltext and pool:
        try:
            _enrich_pool_parallel(store, max_fulltext)
        except Exception as e:
            logger.warning(f"[RefPool] 并行全文获取失败: {e}")

    # 兼容导出 JSON
    try:
        builder.save(OUTPUT_DIR)
    except Exception as e:
        logger.error(f"[RefPool] 保存参考文献池失败: {e}")

    return pool


def _enrich_pool_parallel(store, max_papers: int = 15, max_workers: int = 4):
    """
    v12.2: 并行全文获取 — ThreadPoolExecutor

    从 ReferenceStore 获取待获取全文的论文，并行调用 paper-fetch。
    """
    try:
        from tools.paper_fetch_tool import is_available, fetch_and_save
    except ImportError:
        logger.info("[RefPool] paper_fetch_tool 不可用，跳过全文增强")
        return

    if not is_available():
        logger.info("[RefPool] paper-fetch 未安装，跳过全文增强")
        return

    from config.project_config import REF_PDF_PATH
    md_dir = os.path.join(os.path.dirname(REF_PDF_PATH), "ref_md")

    # 从 ReferenceStore 获取候选
    candidates = store.get_papers_for_fetch(limit=max_papers * 2)
    if not candidates:
        logger.info("[RefPool] 无待获取全文的论文")
        return

    enriched = 0

    def _fetch_one(paper):
        """单个论文获取"""
        query = paper.get("doi", "") or paper.get("title", "")
        if not query:
            return None
        # 标记为 fetching（防并发重复）
        store.update_fulltext_status(paper["id"], "fetching")
        try:
            content, md_path = fetch_and_save(query, md_dir)
            if md_path:
                store.update_fulltext_status(
                    paper["id"], "fetched", md_path,
                    content.token_estimate if hasattr(content, 'token_estimate') else 0
                )
                return paper["id"]
            else:
                store.update_fulltext_status(paper["id"], "failed")
                return None
        except Exception as e:
            logger.debug(f"[RefPool] fetch 失败 ({query[:40]}): {e}")
            store.update_fulltext_status(paper["id"], "failed")
            return None

    # 预截断候选数量，避免提交过多任务
    submit_candidates = candidates[:max_papers]

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_fetch_one, paper): paper
            for paper in submit_candidates
        }

        for future in as_completed(futures):
            try:
                result = future.result()
                if result is not None:
                    enriched += 1
            except Exception as e:
                logger.debug(f"[RefPool] 全文获取异常: {e}")

    logger.info(f"[RefPool] 并行全文增强: {enriched}/{min(len(candidates), max_papers)}")
