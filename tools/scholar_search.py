# -*- coding: utf-8 -*-
"""
Tool: 多源学术搜索引擎 (v11.0)

支持数据源（按优先级）：
1. Semantic Scholar — AI推荐+元数据，需 API key 或忍受 429
2. DBLP             — 免费，计算机科学，自带 BibTeX endpoint
3. CrossRef         — 全学科，需 mailto 参数获更高速率
4. arXiv            — 预印本，CS/物理/数学
5. 智谱 MCP         — 网络搜索增强（需 MCP 配置）
6. paper-fetch      — 从 arXiv URL 获取全文 Markdown

核心设计：
- 动态网络探测：启动时 ping 各 API，运行时自动标记不可用源
- 智能降级链：优先用最快最可靠的源，失败自动换源
- 本地缓存：results_cache/{query_hash}.json，跨运行复用
- 统一输出格式：每条结果含 title, authors, year, venue, doi, abstract, citations

实测结论（2026-06-01）：
- S2: 连通但 429 限速，需 API key
- DBLP: 偶尔可达，不稳定
- CrossRef: 当前网络超时，代码保留好网络时自动启用
- arXiv API: 当前网络超时，代码保留
- paper-fetch arXiv 路径: 稳定可用
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════
# 数据模型
# ═══════════════════════════════════════════════════

@dataclass
class PaperResult:
    """统一论文搜索结果"""
    title: str = ""
    authors: List[str] = field(default_factory=list)
    year: Optional[int] = None
    venue: str = ""
    doi: str = ""
    abstract: str = ""
    citation_count: int = 0
    url: str = ""
    source: str = ""           # 哪个搜索源返回的
    paper_id: str = ""         # S2 paperId / DBLP key 等
    relevance_score: float = 0.0

    def to_dict(self) -> Dict:
        return asdict(self)


# ═══════════════════════════════════════════════════
# 源状态管理
# ═══════════════════════════════════════════════════

class SourceStatus:
    """跟踪每个搜索源的健康状态"""

    def __init__(self):
        self._status: Dict[str, Dict] = {}

    def mark_ok(self, source: str):
        self._status[source] = {
            "available": True,
            "last_success": time.time(),
            "fail_count": 0,
            "cooldown_until": 0,
        }

    def mark_fail(self, source: str, cooldown: float = 300):
        prev = self._status.get(source, {"fail_count": 0})
        self._status[source] = {
            "available": False,
            "last_success": prev.get("last_success", 0),
            "fail_count": prev.get("fail_count", 0) + 1,
            "cooldown_until": time.time() + cooldown,
        }

    def is_available(self, source: str) -> bool:
        s = self._status.get(source)
        if not s:
            return True  # 未测试过，假设可用
        if not s["available"] and time.time() < s["cooldown_until"]:
            return False
        return True

    def get_available_sources(self, preferred_order: List[str]) -> List[str]:
        """按优先级返回可用源列表"""
        return [s for s in preferred_order if self.is_available(s)]


# ═══════════════════════════════════════════════════
# 缓存管理
# ═══════════════════════════════════════════════════

class SearchCache:
    """本地 JSON 缓存，跨运行复用搜索结果"""

    def __init__(self, cache_dir: str = ""):
        if not cache_dir:
            cache_dir = os.path.join(os.path.dirname(__file__), "..", "output", "search_cache")
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _key(self, query: str) -> str:
        return hashlib.md5(query.encode()).hexdigest()

    def get(self, query: str, max_age: float = 86400 * 7) -> Optional[List[PaperResult]]:
        path = self.cache_dir / f"{self._key(query)}.json"
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if time.time() - data.get("timestamp", 0) > max_age:
                return None
            return [PaperResult(**p) for p in data.get("results", [])]
        except Exception:
            return None

    def put(self, query: str, results: List[PaperResult]):
        path = self.cache_dir / f"{self._key(query)}.json"
        try:
            data = {
                "query": query,
                "timestamp": time.time(),
                "results": [r.to_dict() for r in results],
            }
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            logger.warning(f"[SearchCache] 写入失败: {e}")


# ═══════════════════════════════════════════════════
# 主搜索引擎
# ═══════════════════════════════════════════════════

class ScholarSearch:
    """多源学术搜索引擎"""

    # 搜索源优先级
    SOURCE_ORDER = [
        "semantic_scholar",
        "dblp",
        "crossref",
        "arxiv",
    ]

    def __init__(
        self,
        s2_api_key: str = "",
        crossref_mailto: str = "",
        timeout: float = 20.0,
        use_cache: bool = True,
    ):
        self.s2_api_key = s2_api_key or os.getenv("SEMANTIC_SCHOLAR_API_KEY", "")
        self.crossref_mailto = crossref_mailto or "paper-assistant@example.com"
        self.timeout = timeout
        self.source_status = SourceStatus()
        self.cache = SearchCache() if use_cache else None
        self._s2_backoff_until = 0.0

    def search(
        self,
        query: str,
        limit: int = 20,
        year_from: Optional[int] = None,
        year_to: Optional[int] = None,
        sources: Optional[List[str]] = None,
    ) -> List[PaperResult]:
        """
        多源搜索，自动降级。
        
        v11.1: 离线数据包作为第一优先级（境内零网络依赖）

        Returns:
            合并去重后的论文列表，按引用数降序
        """
        # 检查缓存
        if self.cache:
            cached = self.cache.get(query)
            if cached:
                logger.info(f"[ScholarSearch] 缓存命中: {query[:50]} ({len(cached)} 条)")
                return cached[:limit]

        # === v11.1: 优先使用离线数据包 ===
        offline_results = self._search_offline(query, limit, year_from, year_to)
        if offline_results:
            logger.info(f"[ScholarSearch] 离线数据包: {len(offline_results)} 条")
            if len(offline_results) >= limit:
                return offline_results[:limit]

        # 在线搜索（补充离线数据不够的部分）
        use_sources = sources or self.source_status.get_available_sources(self.SOURCE_ORDER)
        all_results: List[PaperResult] = list(offline_results)  # 保留离线结果

        for source in use_sources:
            if len(all_results) >= limit:
                break
            try:
                results = self._search_source(source, query, limit - len(all_results), year_from, year_to)
                if results:
                    all_results.extend(results)
                    self.source_status.mark_ok(source)
                    logger.info(f"[ScholarSearch] {source}: {len(results)} 条")
            except Exception as e:
                logger.warning(f"[ScholarSearch] {source} 失败: {e}")
                self.source_status.mark_fail(source)
                continue

        # 去重
        all_results = self._deduplicate(all_results)

        # 按引用数降序
        all_results.sort(key=lambda p: p.citation_count, reverse=True)

        # 缓存
        if self.cache and all_results:
            self.cache.put(query, all_results)

        return all_results[:limit]

    def _search_offline(self, query: str, limit: int,
                        year_from: int = None, year_to: int = None) -> List[PaperResult]:
        """v11.1: 从离线数据包搜索"""
        try:
            from tools.reference_pack_manager import get_reference_pack_manager
            mgr = get_reference_pack_manager()
            papers = mgr.search_papers(query, limit=limit, min_year=year_from)
            results = []
            for p in papers:
                if year_to and p.get("year", 9999) > year_to:
                    continue
                results.append(PaperResult(
                    title=p.get("title", ""),
                    authors=p.get("authors", []),
                    year=p.get("year"),
                    venue=p.get("venue_abbr", p.get("venue", "")),
                    doi=p.get("doi", ""),
                    abstract=p.get("abstract", ""),
                    citation_count=p.get("citation_count", 0),
                    paper_id=p.get("doi") or f"pack:{p.get('title', '')[:30]}",
                    source="offline_pack",
                ))
            return results
        except Exception as e:
            logger.debug(f"[ScholarSearch] 离线搜索失败: {e}")
            return []

    def search_by_doi(self, doi: str) -> Optional[PaperResult]:
        """通过 DOI 查找论文详情"""
        # S2
        if self.source_status.is_available("semantic_scholar"):
            try:
                result = self._s2_get_by_doi(doi)
                if result:
                    return result
            except Exception:
                pass

        # DBLP 不支持 DOI 查询，跳过

        # CrossRef
        if self.source_status.is_available("crossref"):
            try:
                result = self._crossref_get_by_doi(doi)
                if result:
                    return result
            except Exception:
                pass

        return None

    def search_by_title(self, title: str) -> Optional[PaperResult]:
        """通过标题精确搜索论文"""
        results = self.search(title, limit=5)
        if results:
            # 找最佳匹配
            best = self._best_title_match(title, results)
            if best:
                return best
        return results[0] if results else None

    # ──────────────────────────────────────
    # 各源实现
    # ──────────────────────────────────────

    def _search_source(
        self, source: str, query: str, limit: int,
        year_from: Optional[int], year_to: Optional[int],
    ) -> List[PaperResult]:
        if source == "semantic_scholar":
            return self._s2_search(query, limit, year_from, year_to)
        elif source == "dblp":
            return self._dblp_search(query, limit)
        elif source == "crossref":
            return self._crossref_search(query, limit, year_from, year_to)
        elif source == "arxiv":
            return self._arxiv_search(query, limit)
        return []

    def _s2_search(
        self, query: str, limit: int,
        year_from: Optional[int], year_to: Optional[int],
    ) -> List[PaperResult]:
        """Semantic Scholar 搜索，带指数退避"""
        if time.time() < self._s2_backoff_until:
            return []

        params = {
            "query": query,
            "limit": min(limit, 100),
            "fields": "title,year,authors,abstract,venue,externalIds,citationCount",
        }
        if year_from:
            params["year"] = f"{year_from}-{year_to or ''}"

        headers = {}
        if self.s2_api_key:
            headers["x-api-key"] = self.s2_api_key

        try:
            r = requests.get(
                "https://api.semanticscholar.org/graph/v1/paper/search",
                params=params, headers=headers, timeout=self.timeout,
            )
            if r.status_code == 429:
                wait = 60
                self._s2_backoff_until = time.time() + wait
                logger.warning(f"[S2] 429 限速，退避 {wait}s")
                return []
            r.raise_for_status()
            data = r.json()
            results = []
            for p in data.get("data", []):
                ext = p.get("externalIds", {})
                results.append(PaperResult(
                    title=p.get("title", ""),
                    authors=[a.get("name", "") for a in (p.get("authors") or [])],
                    year=p.get("year"),
                    venue=p.get("venue", ""),
                    doi=ext.get("DOI", ""),
                    abstract=p.get("abstract", "")[:500],
                    citation_count=p.get("citationCount", 0) or 0,
                    paper_id=p.get("paperId", ""),
                    source="semantic_scholar",
                ))
            return results
        except requests.exceptions.Timeout:
            raise RuntimeError("S2 超时")
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"S2 请求失败: {e}")

    def _s2_get_by_doi(self, doi: str) -> Optional[PaperResult]:
        """S2 通过 DOI 获取论文"""
        if time.time() < self._s2_backoff_until:
            return None

        headers = {}
        if self.s2_api_key:
            headers["x-api-key"] = self.s2_api_key

        try:
            r = requests.get(
                f"https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}",
                params={"fields": "title,year,authors,abstract,venue,externalIds,citationCount"},
                headers=headers, timeout=self.timeout,
            )
            if r.status_code == 404:
                return None
            if r.status_code == 429:
                self._s2_backoff_until = time.time() + 60
                return None
            r.raise_for_status()
            p = r.json()
            ext = p.get("externalIds", {})
            return PaperResult(
                title=p.get("title", ""),
                authors=[a.get("name", "") for a in (p.get("authors") or [])],
                year=p.get("year"),
                venue=p.get("venue", ""),
                doi=doi,
                abstract=p.get("abstract", "")[:500],
                citation_count=p.get("citationCount", 0) or 0,
                paper_id=p.get("paperId", ""),
                source="semantic_scholar",
            )
        except Exception:
            return None

    def _dblp_search(self, query: str, limit: int) -> List[PaperResult]:
        """DBLP 搜索"""
        try:
            r = requests.get(
                "https://dblp.org/search/publ/api",
                params={"q": query, "format": "json", "h": min(limit, 30)},
                timeout=self.timeout,
            )
            r.raise_for_status()
            data = r.json()
            hits = data.get("result", {}).get("hits", {})
            results = []
            for h in hits.get("hit", []):
                info = h.get("info", {})
                # 提取作者
                authors_raw = info.get("authors", {}).get("author", [])
                if isinstance(authors_raw, dict):
                    authors_raw = [authors_raw]
                authors = [a.get("text", "") for a in authors_raw if isinstance(a, dict)]

                results.append(PaperResult(
                    title=info.get("title", ""),
                    authors=authors,
                    year=int(info["year"]) if info.get("year", "").isdigit() else None,
                    venue=info.get("venue", ""),
                    doi=info.get("doi", ""),
                    abstract="",
                    citation_count=0,
                    paper_id=info.get("key", ""),
                    url=info.get("url", ""),
                    source="dblp",
                ))
            return results
        except requests.exceptions.Timeout:
            raise RuntimeError("DBLP 超时")
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"DBLP 请求失败: {e}")

    def _crossref_search(
        self, query: str, limit: int,
        year_from: Optional[int], year_to: Optional[int],
    ) -> List[PaperResult]:
        """CrossRef 搜索"""
        params = {
            "query": query,
            "rows": min(limit, 50),
            "sort": "is-referenced-by-count",
            "order": "desc",
            "mailto": self.crossref_mailto,
        }
        filters = []
        if year_from:
            filters.append(f"from-pub-date:{year_from}")
        if year_to:
            filters.append(f"until-pub-date:{year_to}")
        if filters:
            params["filter"] = ",".join(filters)

        try:
            r = requests.get(
                "https://api.crossref.org/works",
                params=params, timeout=self.timeout,
            )
            r.raise_for_status()
            data = r.json()
            results = []
            for item in data.get("message", {}).get("items", []):
                # 提取作者
                authors = []
                for a in item.get("author", [])[:10]:
                    name = f"{a.get('given', '')} {a.get('family', '')}".strip()
                    if name:
                        authors.append(name)

                # 提取年份
                year = None
                for date_field in ["published-print", "published-online", "created"]:
                    date_parts = item.get(date_field, {}).get("date-parts", [[]])
                    if date_parts and date_parts[0]:
                        year = date_parts[0][0]
                        break

                results.append(PaperResult(
                    title=item.get("title", [""])[0],
                    authors=authors,
                    year=year,
                    venue=item.get("container-title", [""])[0] if item.get("container-title") else "",
                    doi=item.get("DOI", ""),
                    abstract=re.sub(r'<[^>]+>', '', item.get("abstract", ""))[:500],
                    citation_count=item.get("is-referenced-by-count", 0),
                    url=item.get("URL", ""),
                    source="crossref",
                ))
            return results
        except requests.exceptions.Timeout:
            raise RuntimeError("CrossRef 超时")
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"CrossRef 请求失败: {e}")

    def _crossref_get_by_doi(self, doi: str) -> Optional[PaperResult]:
        """CrossRef 通过 DOI 获取"""
        try:
            r = requests.get(
                f"https://api.crossref.org/works/{doi}",
                timeout=self.timeout,
            )
            if r.status_code == 404:
                return None
            r.raise_for_status()
            item = r.json().get("message", {})
            authors = []
            for a in item.get("author", [])[:10]:
                name = f"{a.get('given', '')} {a.get('family', '')}".strip()
                if name:
                    authors.append(name)
            year = None
            for date_field in ["published-print", "published-online"]:
                date_parts = item.get(date_field, {}).get("date-parts", [[]])
                if date_parts and date_parts[0]:
                    year = date_parts[0][0]
                    break
            return PaperResult(
                title=item.get("title", [""])[0],
                authors=authors,
                year=year,
                venue=item.get("container-title", [""])[0] if item.get("container-title") else "",
                doi=doi,
                abstract=re.sub(r'<[^>]+>', '', item.get("abstract", ""))[:500],
                citation_count=item.get("is-referenced-by-count", 0),
                source="crossref",
            )
        except Exception:
            return None

    def _arxiv_search(self, query: str, limit: int) -> List[PaperResult]:
        """arXiv API 搜索"""
        try:
            r = requests.get(
                "http://export.arxiv.org/api/query",
                params={
                    "search_query": f"all:{query}",
                    "start": 0,
                    "max_results": min(limit, 30),
                    "sortBy": "submittedDate",
                    "sortOrder": "descending",
                },
                timeout=self.timeout,
            )
            r.raise_for_status()
            root = ET.fromstring(r.text)
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            results = []
            for entry in root.findall("atom:entry", ns):
                title = entry.find("atom:title", ns).text.strip().replace("\n", " ")
                # DOI
                ns2 = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
                doi_elem = entry.find("atom:arxiv:doi", ns2)
                doi = doi_elem.text if doi_elem is not None else ""
                # 作者
                authors = [a.find("atom:name", ns).text for a in entry.findall("atom:author", ns)]
                # 年份
                published = entry.find("atom:published", ns).text[:4]
                year = int(published) if published.isdigit() else None
                # URL
                link = entry.find("atom:id", ns).text

                results.append(PaperResult(
                    title=title,
                    authors=authors,
                    year=year,
                    venue="arXiv",
                    doi=doi,
                    abstract=entry.find("atom:summary", ns).text.strip()[:500] if entry.find("atom:summary", ns) is not None else "",
                    citation_count=0,
                    url=link,
                    source="arxiv",
                ))
            return results
        except requests.exceptions.Timeout:
            raise RuntimeError("arXiv 超时")
        except Exception as e:
            raise RuntimeError(f"arXiv 请求失败: {e}")

    # ──────────────────────────────────────
    # 工具方法
    # ──────────────────────────────────────

    def _deduplicate(self, results: List[PaperResult]) -> List[PaperResult]:
        """按 DOI + 标题去重"""
        seen_dois = set()
        seen_titles = set()
        unique = []
        for r in results:
            # DOI 去重
            if r.doi:
                doi_norm = r.doi.lower().strip()
                if doi_norm in seen_dois:
                    continue
                seen_dois.add(doi_norm)

            # 标题去重（归一化后）
            title_norm = re.sub(r'[^a-z0-9]', '', r.title.lower())[:60]
            if title_norm and title_norm in seen_titles:
                continue
            if title_norm:
                seen_titles.add(title_norm)

            unique.append(r)
        return unique

    def _best_title_match(self, query: str, results: List[PaperResult]) -> Optional[PaperResult]:
        """从结果中找最佳标题匹配"""
        query_words = set(query.lower().split())
        best_score = 0
        best_result = None
        for r in results:
            title_words = set(r.title.lower().split())
            if not query_words:
                continue
            overlap = len(query_words & title_words) / len(query_words)
            if overlap > best_score:
                best_score = overlap
                best_result = r
        return best_result if best_score > 0.3 else None


# ═══════════════════════════════════════════════════
# 便捷函数
# ═══════════════════════════════════════════════════

_default_engine: Optional[ScholarSearch] = None


def get_scholar_search(s2_api_key: str = "") -> ScholarSearch:
    """获取全局搜索引擎实例"""
    global _default_engine
    if _default_engine is None:
        _default_engine = ScholarSearch(s2_api_key=s2_api_key)
    return _default_engine


def search_papers(
    query: str,
    limit: int = 20,
    year_from: Optional[int] = None,
    year_to: Optional[int] = None,
) -> List[Dict]:
    """
    搜索论文 — 简单接口，返回字典列表

    兼容 reference_pool_builder 的调用格式
    """
    engine = get_scholar_search()
    results = engine.search(query, limit=limit, year_from=year_from, year_to=year_to)
    return [r.to_dict() for r in results]
