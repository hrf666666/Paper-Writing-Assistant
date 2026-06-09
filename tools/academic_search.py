# -*- coding: utf-8 -*-
"""
Tool: 学术搜索工具 — 集成 academic-search (ustc-ai4science) 策略

API Cookbook 来源: https://github.com/ustc-ai4science/academic-search
- arXiv REST API
- Semantic Scholar REST API
- CrossRef REST API
- BibTeX 导出 (arXiv / DOI Content Negotiation)

v11.1 设计:
1. 直接 HTTP (网络好时): 直接调用各平台 API
2. MCP 代理 (境内网络差时): 通过智谱 MCP web-reader 代理请求
3. 离线数据包兜底: 以上都失败时用预构建数据包
"""

import json
import logging
import re
import time
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

# ====== API 端点 ======
ARXIV_API = "https://export.arxiv.org/api/query"
S2_API = "https://api.semanticscholar.org/graph/v1"
CROSSREF_API = "https://api.crossref.org/works"
ARXIV_BIBTEX = "https://arxiv.org/bibtex"

# ====== MCP 代理 ======
def _try_mcp_fetch(url: str) -> Optional[str]:
    """通过智谱 MCP web-reader 代理请求（境内可用）"""
    try:
        from api.mcp_http_client import mcp_web_reader
        result = mcp_web_reader(url, return_format="text", retain_images=False)
        if result and "MCP error" not in result[:100]:
            return result
    except Exception:
        pass
    return None


# ====== arXiv 搜索 ======
def search_arxiv(query: str, limit: int = 10, sort_by: str = "submittedDate",
                 use_mcp: bool = True) -> List[Dict]:
    """
    搜索 arXiv 论文 (REST API, 无需鉴权)

    Args:
        query: 搜索关键词 (支持 ti: au: abs: cat: 前缀)
        limit: 最大结果数
        sort_by: 排序 (submittedDate / relevance)
        use_mcp: 网络不通时是否尝试 MCP 代理
    """
    params = {
        "search_query": f"all:{query}" if ":" not in query else query,
        "max_results": limit,
        "sortBy": sort_by,
        "sortOrder": "descending",
    }

    # 构造 URL
    url = f"{ARXIV_API}?search_query={params['search_query']}&max_results={params['max_results']}&sortBy={params['sortBy']}&sortOrder={params['sortOrder']}"

    # 1. 直接 HTTP
    try:
        r = requests.get(url, timeout=20)
        if r.status_code == 200:
            return _parse_arxiv_xml(r.text)
    except Exception:
        pass

    # 2. MCP 代理
    if use_mcp:
        content = _try_mcp_fetch(url)
        if content:
            return _parse_arxiv_xml(content)

    return []


def _parse_arxiv_xml(xml_text: str) -> List[Dict]:
    """解析 arXiv Atom XML 响应"""
    results = []
    try:
        # 清理可能的 markdown 包裹
        if "```" in xml_text[:20]:
            xml_text = re.sub(r'^```(?:xml)?\s*', '', xml_text)
            xml_text = re.sub(r'\s*```$', '', xml_text)

        root = ET.fromstring(xml_text)
        ns = {"atom": "http://www.w3.org/2005/Atom",
              "arxiv": "http://arxiv.org/schemas/atom"}

        for entry in root.findall("atom:entry", ns):
            title = entry.find("atom:title", ns).text.strip().replace("\n", " ")
            title = re.sub(r'\s+', ' ', title)

            # 作者
            authors = [a.find("atom:name", ns).text
                       for a in entry.findall("atom:author", ns)]

            # arXiv ID
            entry_id = entry.find("atom:id", ns).text
            arxiv_id = entry_id.split("/abs/")[-1]

            # DOI
            doi_elem = entry.find("arxiv:doi", ns)
            doi = doi_elem.text if doi_elem is not None else ""

            # 年份
            published = entry.find("atom:published", ns).text[:4]

            # 摘要
            abstract = entry.find("atom:summary", ns).text
            if abstract:
                abstract = abstract.strip().replace("\n", " ")[:500]

            # PDF
            pdf_url = f"https://arxiv.org/pdf/{arxiv_id}"

            # 类别
            categories = [c.get("term") for c in entry.findall("atom:category", ns)]

            results.append({
                "title": title,
                "authors": authors,
                "year": int(published),
                "venue": ", ".join(categories[:2]) if categories else "arXiv",
                "doi": doi,
                "arxiv_id": arxiv_id,
                "abstract": abstract,
                "citation_count": None,  # arXiv 不提供
                "pdf_url": pdf_url,
                "source": "arxiv",
            })
    except ET.ParseError as e:
        logger.debug(f"[ArxivSearch] XML 解析失败: {e}")
    except Exception as e:
        logger.debug(f"[ArxivSearch] 解析异常: {e}")

    return results


# ====== Semantic Scholar 搜索 ======
def search_semantic_scholar(query: str, limit: int = 10,
                            api_key: str = None,
                            use_mcp: bool = True) -> List[Dict]:
    """
    搜索 Semantic Scholar

    v12.0: 境内永久 429，直接返回空。保留接口向后兼容。
    """
    logger.debug("[S2Search] 境内永久 429，跳过 Semantic Scholar")
    return []
    fields = "title,authors,year,abstract,citationCount,externalIds,openAccessPdf,venue"
    url = f"{S2_API}/paper/search?query={query.replace(' ', '+')}&limit={limit}&fields={fields}"

    headers = {}
    if api_key:
        headers["x-api-key"] = api_key

    # 1. 直接 HTTP
    try:
        r = requests.get(url, headers=headers, timeout=20)
        if r.status_code == 200:
            return _parse_s2_json(r.text)
        elif r.status_code == 429:
            logger.warning("[S2Search] 429 限速")
    except Exception:
        pass

    # 2. MCP 代理
    if use_mcp:
        content = _try_mcp_fetch(url)
        if content:
            return _parse_s2_json(content)

    return []


def get_s2_paper_by_doi(doi: str, api_key: str = None,
                        use_mcp: bool = True) -> Optional[Dict]:
    """通过 DOI 获取 S2 论文元数据"""
    fields = "title,authors,year,abstract,citationCount,externalIds,openAccessPdf,venue"
    url = f"{S2_API}/paper/DOI:{doi}?fields={fields}"

    headers = {}
    if api_key:
        headers["x-api-key"] = api_key

    try:
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code == 200:
            data = r.json()
            return _normalize_s2_paper(data)
    except Exception:
        pass

    if use_mcp:
        content = _try_mcp_fetch(url)
        if content:
            try:
                data = json.loads(content)
                return _normalize_s2_paper(data)
            except Exception:
                pass

    return None


def _parse_s2_json(json_text: str) -> List[Dict]:
    """解析 S2 搜索 JSON"""
    results = []
    try:
        data = json.loads(json_text)
        for p in data.get("data", []):
            results.append(_normalize_s2_paper(p))
    except Exception as e:
        logger.debug(f"[S2Search] JSON 解析失败: {e}")
    return results


def _normalize_s2_paper(p: Dict) -> Dict:
    """标准化 S2 论文格式"""
    ext_ids = p.get("externalIds", {})
    authors = [a.get("name", "") for a in (p.get("authors") or [])]
    pdf_info = p.get("openAccessPdf") or {}

    return {
        "title": p.get("title", ""),
        "authors": authors,
        "year": p.get("year"),
        "venue": p.get("venue", ""),
        "doi": ext_ids.get("DOI", ""),
        "arxiv_id": ext_ids.get("ArXiv", ""),
        "abstract": (p.get("abstract") or "")[:500],
        "citation_count": p.get("citationCount", 0),
        "pdf_url": pdf_info.get("url", ""),
        "source": "semantic_scholar",
    }


# ====== BibTeX 获取 ======
def get_bibtex_arxiv(arxiv_id: str, use_mcp: bool = True) -> Optional[str]:
    """从 arXiv 获取 BibTeX"""
    url = f"{ARXIV_BIBTEX}/{arxiv_id}"

    try:
        r = requests.get(url, timeout=15)
        if r.status_code == 200 and "@" in r.text:
            return r.text
    except Exception:
        pass

    if use_mcp:
        content = _try_mcp_fetch(url)
        if content and "@" in content:
            return content

    return None


def get_bibtex_doi(doi: str, use_mcp: bool = True) -> Optional[str]:
    """通过 DOI Content Negotiation 获取 BibTeX"""
    url = f"https://doi.org/{doi}"

    try:
        r = requests.get(url, headers={"Accept": "application/x-bibtex"},
                         timeout=20, allow_redirects=True)
        if r.status_code == 200 and "@" in r.text:
            return r.text
    except Exception:
        pass

    if use_mcp:
        content = _try_mcp_fetch(url)
        if content and "@" in content:
            return content

    return None


# ====== 统一搜索入口 ======
def academic_search(query: str, limit: int = 20,
                    sources: List[str] = None,
                    use_mcp: bool = True) -> List[Dict]:
    """
    统一学术搜索入口 — v11.9: offline → MCP → Web Search API → openalex

    arXiv/S2/CrossRef/DBLP 直连在境内全超时，已禁用。
    MCP (智谱 web-search-prime) 是第一外网通道。
    Web Search API (/paas/v4/web_search) 独立配额，MCP 耗尽时降级。
    """
    # v11.9: 四级降级
    sources = sources or ["offline", "web_search_api", "openalex"]
    all_results = []
    seen_titles = set()

    for source in sources:
        if len(all_results) >= limit:
            break

        remaining = limit - len(all_results)

        if source == "arxiv":
            results = search_arxiv(query, limit=remaining, use_mcp=use_mcp)
        elif source == "s2":
            results = search_semantic_scholar(query, limit=remaining, use_mcp=use_mcp)
        elif source == "offline":
            try:
                from tools.reference_pack_manager import search_offline_papers
                offline = search_offline_papers(query, limit=remaining)
                results = [{
                    "title": p.get("title", ""),
                    "authors": p.get("authors", []),
                    "year": p.get("year"),
                    "venue": p.get("venue_abbr", p.get("venue", "")),
                    "doi": p.get("doi", ""),
                    "arxiv_id": "",
                    "abstract": p.get("abstract", ""),
                    "citation_count": p.get("citation_count", 0),
                    "pdf_url": "",
                    "source": "offline_pack",
                } for p in offline]
            except Exception:
                results = []
        elif source == "web_search_api":
            try:
                from api.web_search_api import search_papers_web
                # 互补模式：Web Search + LLM 找论文，内部自动用 OpenAlex 补全
                ws_results = search_papers_web(query, limit=remaining, enrich=True)
                results = [{
                    "title": p.get("title", ""),
                    "authors": p.get("authors", []),
                    "year": p.get("year"),
                    "venue": p.get("venue", ""),
                    "doi": p.get("externalIds", {}).get("DOI", ""),
                    "arxiv_id": p.get("externalIds", {}).get("ArXiv", ""),
                    "abstract": p.get("abstract", ""),
                    "citation_count": p.get("citationCount", 0),
                    "pdf_url": "",
                    "source": p.get("source", "web_search_api"),
                } for p in ws_results]
            except Exception:
                results = []
        elif source == "openalex":
            try:
                from api.paper_search import search_papers_openalex
                oa_results = search_papers_openalex(query, limit=remaining)
                results = [{
                    "title": p.get("title", ""),
                    "authors": p.get("authors", []),
                    "year": p.get("year"),
                    "venue": p.get("venue", {}).get("raw", "") if isinstance(p.get("venue"), dict) else str(p.get("venue", "")),
                    "doi": p.get("externalIds", {}).get("DOI", ""),
                    "arxiv_id": "",
                    "abstract": p.get("abstract", ""),
                    "citation_count": p.get("citationCount", 0),
                    "pdf_url": "",
                    "source": "openalex",
                } for p in oa_results]
            except Exception:
                results = []
        else:
            continue

        # 去重
        for r in results:
            title_key = r.get("title", "").lower()[:40]
            if title_key not in seen_titles and title_key:
                seen_titles.add(title_key)
                all_results.append(r)

        logger.info(f"[AcademicSearch] {source}: +{len(results)} 条 (总 {len(all_results)})")

    # 按引用数排序
    all_results.sort(key=lambda p: p.get("citation_count") or 0, reverse=True)
    return all_results[:limit]
