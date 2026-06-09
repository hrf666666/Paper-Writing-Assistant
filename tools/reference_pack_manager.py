# -*- coding: utf-8 -*-
"""
离线参考文献数据包管理器 (v11.1 — 境内可用)

解决境内无法稳定访问国际学术 API 的问题。
提供预构建的、经过人工验证的参考文献数据包。

使用方式:
  from tools.reference_pack_manager import ReferencePackManager
  mgr = ReferencePackManager()
  papers = mgr.get_papers_for_domain("light_field_depth_estimation")
  papers = mgr.search_papers("depth estimation", limit=10)

数据包位置: data/reference_packs/*.json
"""
import json
import logging
import os
import re
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

PACKS_DIR = Path(__file__).parent.parent / "data" / "reference_packs"


class ReferencePackManager:
    """离线参考文献数据包管理器"""

    def __init__(self, packs_dir: str = None):
        self.packs_dir = Path(packs_dir) if packs_dir else PACKS_DIR
        self._packs: Dict[str, dict] = {}  # domain -> pack_data
        self._all_papers: List[dict] = []   # flat list of all papers
        self._loaded = False

    def _load_packs(self):
        """加载所有数据包"""
        if self._loaded:
            return

        if not self.packs_dir.exists():
            logger.warning(f"[RefPack] 数据包目录不存在: {self.packs_dir}")
            self._loaded = True
            return

        for f in self.packs_dir.glob("*.json"):
            try:
                with open(f, "r", encoding="utf-8") as fh:
                    pack = json.load(fh)
                domain = pack.get("domain", f.stem)
                self._packs[domain] = pack
                for paper in pack.get("papers", []):
                    paper["_pack_domain"] = domain
                    paper["_source"] = "reference_pack"
                    self._all_papers.append(paper)
                logger.debug(f"[RefPack] 加载 {domain}: {len(pack.get('papers', []))} 篇")
            except Exception as e:
                logger.warning(f"[RefPack] 加载失败 {f.name}: {e}")

        self._loaded = True
        logger.info(f"[RefPack] 共加载 {len(self._packs)} 个数据包, {len(self._all_papers)} 篇论文")

    def get_papers_for_domain(self, domain: str) -> List[Dict]:
        """获取指定领域的所有论文"""
        self._load_packs()
        pack = self._packs.get(domain)
        if not pack:
            # 模糊匹配
            for k, v in self._packs.items():
                if domain.replace("_", " ") in k.replace("_", " "):
                    return v.get("papers", [])
            return []
        return pack.get("papers", [])

    def search_papers(self, query: str, limit: int = 20,
                      tags: List[str] = None,
                      min_year: int = None) -> List[Dict]:
        """
        在所有数据包中搜索论文

        Args:
            query: 搜索关键词（空格分隔，AND 逻辑）
            limit: 最大返回数
            tags: 标签过滤
            min_year: 最低年份
        """
        self._load_packs()

        if not self._all_papers:
            return []

        query_words = set(query.lower().split()) if query else set()
        scored = []

        for paper in self._all_papers:
            score = 0
            title = paper.get("title", "").lower()
            abstract = paper.get("abstract", "").lower()
            paper_tags = [t.lower() for t in paper.get("tags", [])]

            # 关键词匹配
            if query_words:
                title_words = set(title.split())
                title_overlap = len(query_words & title_words)
                tag_overlap = sum(1 for t in paper_tags if any(w in t for w in query_words))

                score = title_overlap * 3 + tag_overlap * 2

                # 如果标题中没有任何关键词，跳过
                if score == 0 and not any(w in abstract for w in query_words):
                    continue

            # 标签过滤
            if tags:
                if not any(t.lower() in paper_tags for t in tags):
                    continue

            # 年份过滤
            if min_year and paper.get("year", 0) < min_year:
                continue

            # 引用数加权
            score += min(paper.get("citation_count", 0), 1000) / 1000
            scored.append((score, paper))

        # 按分数降序排序
        scored.sort(key=lambda x: x[0], reverse=True)
        return [p for _, p in scored[:limit]]

    def get_all_papers(self) -> List[Dict]:
        """获取所有论文（去重）"""
        self._load_packs()
        # 按 title 去重
        seen = set()
        unique = []
        for p in self._all_papers:
            key = p.get("title", "").lower()[:40]
            if key not in seen:
                seen.add(key)
                unique.append(p)
        return unique

    def get_domain_list(self) -> List[str]:
        """获取所有可用的领域"""
        self._load_packs()
        return list(self._packs.keys())

    def to_reference_pool_format(self, papers: List[Dict]) -> List[Dict]:
        """
        转换为 reference_pool_builder 兼容的格式
        """
        result = []
        for p in papers:
            authors = p.get("authors", [])
            if isinstance(authors, list) and authors and isinstance(authors[0], str):
                authors = [{"name": a} for a in authors]

            result.append({
                "paperId": p.get("doi", f"pack:{p.get('title', '')[:30]}"),
                "title": p.get("title", ""),
                "year": p.get("year"),
                "authors": authors,
                "venue": p.get("venue_abbr", p.get("venue", "")),
                "abstract": p.get("abstract", ""),
                "citationCount": p.get("citation_count", 0),
                "doi": p.get("doi", ""),
                "externalIds": {"DOI": p.get("doi", "")} if p.get("doi") else {},
                "group": p.get("_pack_domain", "reference_pack"),
                "_relevance_score": p.get("citation_count", 0) * 0.3,
                "_source": "reference_pack",
            })
        return result

    def stats(self) -> Dict:
        """返回数据包统计信息"""
        self._load_packs()
        return {
            "packs": len(self._packs),
            "total_papers": len(self._all_papers),
            "domains": list(self._packs.keys()),
        }


# 全局单例
_manager: Optional[ReferencePackManager] = None


def get_reference_pack_manager() -> ReferencePackManager:
    global _manager
    if _manager is None:
        _manager = ReferencePackManager()
    return _manager


def search_offline_papers(query: str, limit: int = 20) -> List[Dict]:
    """快捷函数：离线搜索论文"""
    mgr = get_reference_pack_manager()
    return mgr.search_papers(query, limit=limit)


def get_offline_reference_pool(domain: str = None) -> List[Dict]:
    """快捷函数：获取离线论文（reference_pool 格式）"""
    mgr = get_reference_pack_manager()
    if domain:
        papers = mgr.get_papers_for_domain(domain)
    else:
        papers = mgr.get_all_papers()
    return mgr.to_reference_pool_format(papers)
