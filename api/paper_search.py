# -*- coding: utf-8 -*-
"""
论文搜索API

v8.1: 统一多源降级链重构
    - 修复 URL-as-paperId 导致 S2 404 的问题
    - 新增百度学术搜索（MCP 域名限定 + HTTP 直连）
    - 增强 S2 429 限速退避
    - get_paper_details_semantic 支持 URL 识别 + MCP web-reader 回退

检索优先级（统一降级链）：
1. 智谱MCP (web-search-prime) - 利用大模型理解检索意图
2. 百度学术 - 中文论文覆盖广，通过MCP域名限定搜索
3. Semantic Scholar API - 英文学术论文覆盖广，免费
4. AMiner API - 备选（需API key）

MCP服务说明（需在 ~/.codebuddy/mcp.json 中配置，或设置 GLM_CODING_PLAN_API_KEY 环境变量）:
- web-search-prime: 智谱MCP网络搜索
- web-reader: 智谱MCP网页读取
- zread: 智谱MCP文档读取
"""

import json
import logging
import re
import time
from pathlib import Path
from typing import List, Dict, Optional, Any

import requests

project_root = Path(__file__).parent.parent

logger = logging.getLogger(__name__)

# ====== 搜索缓存 ======
_search_cache: Dict[str, tuple] = {}  # query -> (result, timestamp)
_cache_ttl = 3600  # 缓存1小时
_rate_limit_last_call = 0.0  # 上次 API 调用时间
_rate_limit_interval = 2.0   # 最小调用间隔（秒）
_backoff_until = 0.0          # 429 退避截止时间


def _rate_limit():
    """API 调用限速（含 429 退避）"""
    global _rate_limit_last_call
    # 429 退避期检查
    if time.time() < _backoff_until:
        wait = _backoff_until - time.time()
        logger.debug(f"S2 429 退避中，等待 {wait:.0f}s")
        time.sleep(wait)
    elapsed = time.time() - _rate_limit_last_call
    if elapsed < _rate_limit_interval:
        time.sleep(_rate_limit_interval - elapsed)
    _rate_limit_last_call = time.time()


def _get_cache(query: str) -> Optional[List[Dict]]:
    """检查搜索缓存"""
    if query in _search_cache:
        result, ts = _search_cache[query]
        if time.time() - ts < _cache_ttl:
            return result
    return None


def _set_cache(query: str, result: List[Dict]):
    """设置搜索缓存"""
    _search_cache[query] = (result, time.time())

# ========== 智谱MCP增强检索 ==========

_mcp_available = None  # MCP可用性缓存
_mcp_mode = None       # MCP调用模式: "http" | "ide" | None


def _check_mcp_available() -> bool:
    """
    检查MCP服务是否可用
    优先使用独立 HTTP 客户端（api.mcp_http_client），回退到 IDE 注入模块
    """
    global _mcp_available, _mcp_mode
    if _mcp_available is not None:
        return _mcp_available

    # 方式1：尝试独立 HTTP 客户端（通过 GLM_CODING_PLAN_API_KEY）
    try:
        from api.mcp_http_client import get_mcp_client
        client = get_mcp_client()
        if client.api_key:
            logger.info("MCP 使用独立 HTTP 客户端模式 (GLM_CODING_PLAN_API_KEY)")
            _mcp_mode = "http"
            _mcp_available = True
            return True
    except Exception:
        pass

    # 方式2：尝试 IDE 注入的 MCP 模块（CodeBuddy 环境）
    try:
        from mcp_get_tool_description import mcp__get__tool__description
        result = mcp__get__tool__description([{"serverName": "web-search-prime", "toolName": "web_search_prime"}])
        if result is not None:
            logger.info("MCP 使用 IDE 注入模块模式")
            _mcp_mode = "ide"
            _mcp_available = True
            return True
    except ImportError:
        pass
    except Exception as e:
        logger.debug(f"MCP IDE注入模块检查失败: {e}")

    _mcp_available = False
    logger.info("MCP 服务不可用，文献检索将使用 Semantic Scholar + AMiner")
    return False


def search_with_zhipu_mcp(query: str, max_results: int = 10) -> List[Dict]:
    """
    使用智谱MCP进行网络搜索增强检索

    Args:
        query: 搜索查询
        max_results: 最大结果数

    Returns:
        搜索结果列表
    """
    if not _check_mcp_available():
        logger.debug("智谱MCP不可用，回退到Semantic Scholar")
        return []

    # 方式1：独立 HTTP 客户端
    if _mcp_mode == "http":
        try:
            from api.mcp_http_client import mcp_web_search
            raw_result = mcp_web_search(
                search_query=query,
                content_size="high",
                location="us",  # 学术论文以英文为主，使用 us 区域
            )
            if raw_result:
                return _parse_mcp_search_result(raw_result, query)
        except Exception as e:
            logger.debug(f"MCP HTTP客户端搜索失败: {e}")
        return []

    # 方式2：IDE 注入模块
    try:
        from mcp_call_tool import mcp__call__tool
        result = mcp__call__tool(
            arguments=json.dumps({"query": query, "max_results": max_results}),
            serverName="web-search-prime",
            toolName="web_search_prime"
        )
        if result and isinstance(result, str):
            return _parse_mcp_search_result(result, query)
    except Exception as e:
        logger.debug(f"智谱MCP IDE搜索失败: {e}")
    return []


def _parse_mcp_search_result(raw_result: str, query: str) -> List[Dict]:
    """解析智谱MCP搜索结果（处理多层JSON转义）"""
    results = []

    try:
        data = None
        text = raw_result

        # 反复 json.loads 直到得到非字符串类型（最多5层）
        for _ in range(5):
            if not isinstance(text, str):
                data = text
                break
            text = text.strip()
            if not text:
                break
            try:
                parsed = json.loads(text)
                if isinstance(parsed, (list, dict)):
                    data = parsed
                    break
                elif isinstance(parsed, str):
                    text = parsed  # 继续解析下一层
                else:
                    data = parsed
                    break
            except (json.JSONDecodeError, ValueError):
                # 如果不是合法JSON，尝试正则提取数组
                json_match = re.search(r'\[.*\]', text, re.DOTALL)
                if json_match:
                    try:
                        data = json.loads(json_match.group())
                    except (json.JSONDecodeError, ValueError):
                        pass
                break

        if isinstance(data, list):
            for item in data[:10]:
                if isinstance(item, dict):
                    results.append({
                        "title": item.get("title", item.get("name", "")),
                        "url": item.get("url", item.get("link", "")),
                        "snippet": item.get("snippet", item.get("description", item.get("content", ""))),
                        "source": "zhipu_mcp",
                    })
        elif isinstance(data, dict):
            results.append({
                "title": data.get("title", data.get("name", "")),
                "url": data.get("url", data.get("link", "")),
                "snippet": data.get("snippet", data.get("description", data.get("content", ""))),
                "source": "zhipu_mcp",
            })
    except Exception as e:
        logger.debug(f"解析MCP结果失败: {e}")

    return results


def fetch_page_content(url: str) -> Optional[str]:
    """
    使用智谱MCP读取网页内容

    Args:
        url: 网页URL

    Returns:
        网页文本内容
    """
    if not _check_mcp_available():
        return None

    # 方式1：独立 HTTP 客户端
    if _mcp_mode == "http":
        try:
            from api.mcp_http_client import mcp_web_reader
            return mcp_web_reader(url, return_format="markdown", retain_images=False)
        except Exception as e:
            logger.debug(f"MCP HTTP客户端读取网页失败: {e}")
        return None

    # 方式2：IDE 注入模块
    try:
        from mcp_call_tool import mcp__call__tool
        result = mcp__call__tool(
            arguments=json.dumps({"url": url}),
            serverName="web-reader",
            toolName="webReader"
        )
        if result and isinstance(result, str):
            return result
    except Exception as e:
        logger.debug(f"智谱MCP读取网页失败: {e}")
    return None


def extract_paper_from_url(url: str) -> Optional[Dict]:
    """
    从URL提取论文信息（用于验证引用真实性）
    
    Args:
        url: 论文页面URL（如arXiv, IEEE Xplore, ACM DL等）
        
    Returns:
        论文信息字典
    """
    if not _check_mcp_available():
        return None
    
    content = fetch_page_content(url)
    if not content:
        return None
    
    # 尝试提取论文信息
    paper_info = {
        "title": "",
        "authors": [],
        "abstract": "",
        "url": url,
    }
    
    # 提取标题
    title_match = re.search(r'<title>(.*?)</title>', content, re.IGNORECASE)
    if title_match:
        paper_info["title"] = title_match.group(1).strip()
    
    # 提取摘要
    abstract_patterns = [
        r'abstract[^>]*>(.*?)</abstract>',
        r'Abstract[^>]*>(.*?)</abstract>',
        r'"abstract":\s*"(.*?)"',
    ]
    for pattern in abstract_patterns:
        match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
        if match:
            paper_info["abstract"] = match.group(1).strip()
            break
    
    return paper_info if paper_info.get("title") else None


# ========== 百度学术搜索 ==========

def search_papers_baidu(query: str, limit: int = 10) -> List[Dict]:
    """
    通过百度学术搜索论文

    优先使用 MCP web-search-prime 限定 xueshu.baidu.com 域名搜索，
    MCP 不可用时回退到直接 HTTP 请求百度学术搜索页面。

    Args:
        query: 搜索查询
        limit: 最大结果数

    Returns:
        标准论文格式列表
    """
    # 方式1：通过 MCP web-search-prime 限定域名搜索
    if _check_mcp_available():
        mcp_results = _search_baidu_via_mcp(query, limit)
        if mcp_results:
            logger.debug(f"百度学术(MCP)搜索到 {len(mcp_results)} 条结果")
            return mcp_results

    # 方式2：直接 HTTP 请求百度学术
    http_results = _search_baidu_via_http(query, limit)
    if http_results:
        logger.debug(f"百度学术(HTTP)搜索到 {len(http_results)} 条结果")
    return http_results


def _search_baidu_via_mcp(query: str, limit: int = 10) -> List[Dict]:
    """通过 MCP web-search-prime 限定 xueshu.baidu.com 域名搜索"""
    if _mcp_mode != "http":
        return []

    try:
        from api.mcp_http_client import mcp_web_search
        raw_result = mcp_web_search(
            search_query=query,
            search_domain_filter="xueshu.baidu.com",
            content_size="high",
            location="cn",
        )
        if not raw_result:
            return []
        return _parse_baidu_mcp_results(raw_result, query)
    except Exception as e:
        logger.debug(f"百度学术 MCP 搜索失败: {e}")
        return []


def _parse_baidu_mcp_results(raw_result: str, query: str) -> List[Dict]:
    """解析百度学术 MCP 搜索结果"""
    results = []

    try:
        data = None
        text = raw_result

        # 反复 json.loads 直到得到非字符串类型
        for _ in range(5):
            if not isinstance(text, str):
                data = text
                break
            text = text.strip()
            if not text:
                break
            try:
                parsed = json.loads(text)
                if isinstance(parsed, (list, dict)):
                    data = parsed
                    break
                elif isinstance(parsed, str):
                    text = parsed
                else:
                    data = parsed
                    break
            except (json.JSONDecodeError, ValueError):
                break

        items = []
        if isinstance(data, list):
            items = data[:10]
        elif isinstance(data, dict):
            items = [data]

        for item in items:
            if not isinstance(item, dict):
                continue
            title = item.get("title", item.get("name", "")).strip()
            url = item.get("url", item.get("link", "")).strip()
            snippet = item.get("snippet", item.get("description", item.get("content", "")))

            if not title:
                continue

            # 清理 HTML 标签
            title = re.sub(r'<[^>]+>', '', title)
            snippet = re.sub(r'<[^>]+>', '', snippet) if snippet else ""

            results.append({
                "paperId": url or f"baidu:{title[:50]}",
                "title": title,
                "year": _extract_year_from_text(snippet),
                "authors": _extract_authors_from_text(snippet),
                "abstract": snippet,
                "venue": "",
                "citationCount": 0,
                "externalIds": {"url": url} if url else {},
                "url": url,
                "source": "baidu_scholar",
            })
    except Exception as e:
        logger.debug(f"解析百度学术 MCP 结果失败: {e}")

    return results


def _search_baidu_via_http(query: str, limit: int = 10) -> List[Dict]:
    """直接 HTTP 请求百度学术搜索页面并解析 HTML"""
    results = []
    url = "https://xueshu.baidu.com/s"
    params = {
        "wd": query,
        "pn": 0,
        "filter": "sc_type%3D%7B1%7D",  # 仅学术论文
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }

    try:
        _rate_limit()
        response = requests.get(url, params=params, headers=headers, timeout=15)
        response.raise_for_status()
        html = response.text

        # 解析搜索结果条目
        # 百度学术的 HTML 结构：每个结果在 <div class="result"> 中
        result_blocks = re.findall(
            r'<div class="result".*?<h3 class="t".*?<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>.*?</div>',
            html, re.DOTALL
        )

        for link, title_html in result_blocks[:limit]:
            title = re.sub(r'<[^>]+>', '', title_html).strip()
            if not title:
                continue

            # 尝试提取年份和摘要
            snippet = ""
            abs_match = re.search(
                r'<div class="c_abstract">(.*?)</div>',
                html[html.find(title):html.find(title) + 2000] if title in html else "",
                re.DOTALL
            )
            if abs_match:
                snippet = re.sub(r'<[^>]+>', '', abs_match.group(1)).strip()

            results.append({
                "paperId": link if link.startswith("http") else f"baidu:{title[:50]}",
                "title": title,
                "year": _extract_year_from_text(snippet),
                "authors": [],
                "abstract": snippet,
                "venue": "",
                "citationCount": 0,
                "externalIds": {"url": link} if link.startswith("http") else {},
                "url": link,
                "source": "baidu_scholar",
            })

    except Exception as e:
        logger.debug(f"百度学术 HTTP 搜索失败: {e}")

    return results


# Semantic Scholar API 基础URL
S2_BASE_URL = "https://api.semanticscholar.org/graph/v1"
S2_SEARCH_URL = f"{S2_BASE_URL}/paper/search"
S2_PAPER_URL = f"{S2_BASE_URL}/paper"


def search_papers_semantic(query: str, limit: int = 10,
                           fields: str = None) -> List[Dict]:
    """
    搜索论文 - 优先使用智谱MCP，fallback到Semantic Scholar

    Args:
        query: 搜索查询字符串
        limit: 返回结果数量
        fields: 要返回的字段（逗号分隔），默认包含title,year,authors,abstract,venue

    Returns:
        List[Dict]: 论文列表
    """
    # 优先使用智谱MCP增强搜索
    mcp_results = search_with_zhipu_mcp(query, max_results=limit)
    if mcp_results:
        logger.debug(f"智谱MCP搜索到 {len(mcp_results)} 条结果")
        # 尝试从MCP结果中提取可验证的论文信息
        return _convert_mcp_to_paper_format(mcp_results)

    # 检查缓存
    cached = _get_cache(query)
    if cached is not None:
        logger.debug(f"使用缓存结果: {query[:50]}")
        return cached

    # 回退到Semantic Scholar API
    if fields is None:
        fields = "title,year,authors,abstract,venue,externalIds,citationCount"

    params = {
        "query": query,
        "limit": min(limit, 100),
        "fields": fields,
    }

    # 如果 S2 处于 429 退避期，直接跳过
    if _is_rate_limited():
        logger.debug("S2 处于 429 退避期，跳过搜索")
        return []

    try:
        _rate_limit()  # API 调用限速
        response = requests.get(S2_SEARCH_URL, params=params, timeout=15)

        # 429 限速处理
        if response.status_code == 429:
            logger.warning("Semantic Scholar 搜索 429 限速")
            _handle_rate_limit_429(response)
            return []

        response.raise_for_status()
        data = response.json()

        papers = data.get("data", [])
        result = [
            {
                "paperId": p.get("paperId", ""),
                "title": p.get("title", ""),
                "year": p.get("year"),
                "authors": [
                    {"name": a.get("name", "")}
                    for a in (p.get("authors") or [])
                ],
                "abstract": p.get("abstract", ""),
                "venue": p.get("venue", ""),
                "citationCount": p.get("citationCount", 0),
                "externalIds": p.get("externalIds", {}),
                "source": "semantic_scholar",
            }
            for p in papers
        ]
        _set_cache(query, result)  # 缓存结果
        return result
    except requests.exceptions.Timeout:
        logger.warning("Semantic Scholar搜索超时")
        return []
    except requests.exceptions.RequestException as e:
        logger.warning(f"Semantic Scholar搜索失败: {e}")
        return []


def _convert_mcp_to_paper_format(mcp_results: List[Dict]) -> List[Dict]:
    """将智谱MCP结果转换为标准论文格式"""
    papers = []
    
    for item in mcp_results:
        # 尝试从URL推断论文信息
        url = item.get("url", "")
        
        # 识别学术论文URL
        is_academic = any(domain in url.lower() for domain in [
            "arxiv.org", "ieee.org", "acm.org", "springer.com",
            "sciencedirect.com", "nature.com", "pubmed.gov",
            "arxiv", "cvpr", "iccv", "eccv", "neurips"
        ])
        
        if is_academic or item.get("snippet"):
            papers.append({
                "paperId": url,  # 使用URL作为ID
                "title": item.get("title", ""),
                "year": _extract_year_from_text(item.get("snippet", "")),
                "authors": _extract_authors_from_text(item.get("snippet", "")),
                "abstract": item.get("snippet", ""),
                "venue": "",
                "citationCount": 0,
                "externalIds": {"url": url},
                "url": url,
                "source": "zhipu_mcp",
            })
    
    return papers


def _extract_year_from_text(text: str) -> Optional[int]:
    """从文本中提取年份"""
    year_match = re.search(r'\b(19|20)\d{2}\b', text)
    if year_match:
        return int(year_match.group())
    return None


def _extract_authors_from_text(text: str) -> List[Dict]:
    """从文本中提取作者（简化实现）"""
    # 尝试匹配 "Author Name et al." 或 "Author1, Author2, ..."
    authors = []
    author_pattern = r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)'
    matches = re.findall(author_pattern, text)
    for match in matches[:5]:  # 最多取5个
        authors.append({"name": match.strip()})
    return authors


# ========== 增强引用验证（使用MCP） ==========

def verify_citation_with_mcp(paper_title: str, author_hint: str = "") -> Dict:
    """
    多源验证引用真实性 — 降级链：MCP → 百度学术 → Semantic Scholar

    Args:
        paper_title: 论文标题
        author_hint: 作者提示（可选）

    Returns:
        验证结果字典
    """
    result = {
        "verified": False,
        "title": paper_title,
        "found_urls": [],
        "confidence": 0.0,
        "method": "none",
    }

    search_query = paper_title
    if author_hint:
        search_query = f"{author_hint} {paper_title}"

    # ── 1. 智谱 MCP 搜索 ──
    mcp_results = search_with_zhipu_mcp(search_query, max_results=5)
    if mcp_results:
        academic_urls = []
        for r in mcp_results:
            url = r.get("url", "")
            if any(domain in url.lower() for domain in [
                "arxiv.org", "ieee.org", "acm.org", "springer.com",
                "sciencedirect.com", "nature.com", "cvpr", "iccv", "eccv",
                "xueshu.baidu.com", "cnki.net",
            ]):
                academic_urls.append(url)

        if academic_urls:
            result["verified"] = True
            result["found_urls"] = academic_urls
            result["confidence"] = 0.9 if len(academic_urls) > 1 else 0.7
            result["method"] = "mcp"
            return result

    # ── 2. 百度学术 ──
    baidu_papers = search_papers_baidu(paper_title, limit=3)
    if baidu_papers:
        best = baidu_papers[0]
        sim = _title_similarity(paper_title, best.get("title", ""))
        if sim > 0.4:
            result["verified"] = True
            result["confidence"] = 0.85
            result["method"] = "baidu_scholar"
            result["matched_paper"] = best
            if best.get("url"):
                result["found_urls"] = [best["url"]]
            return result

    # ── 3. Semantic Scholar ──
    if not _is_rate_limited():
        papers = search_papers_semantic(paper_title, limit=3)
        if papers:
            best = papers[0]
            sim = _title_similarity(paper_title, best.get("title", ""))
            if sim > 0.3:
                result["verified"] = True
                result["confidence"] = 0.95
                result["method"] = "semantic_scholar"
                result["matched_paper"] = best
                return result

    return result


def deep_verify_reference(citation_text: str) -> Dict:
    """
    深度验证参考文献 - 结合MCP和语义搜索
    
    这是最严格的验证方式，用于审计系统中的critical级别检查
    
    Args:
        citation_text: 参考文献完整文本
        
    Returns:
        验证结果
    """
    result = {
        "verified": False,
        "original_text": citation_text,
        "issues": [],
        "confidence": 0.0,
    }
    
    # 1. 提取引用标题
    title = _extract_title_from_bibliography(citation_text)
    if not title:
        result["issues"].append("无法提取论文标题")
        return result
    
    result["title"] = title
    
    # 2. 提取引用年份
    year = _extract_year_from_text(citation_text)
    if year:
        result["year"] = year
    
    # 3. 提取作者
    authors = _extract_authors_from_text(citation_text)
    if authors:
        result["authors"] = [a["name"] for a in authors]
        author_hint = ", ".join([a["name"] for a in authors[:2]])
    else:
        author_hint = ""
    
    # 4. 使用MCP验证
    verification = verify_citation_with_mcp(title, author_hint)
    
    result["verified"] = verification["verified"]
    result["confidence"] = verification["confidence"]
    result["found_urls"] = verification.get("found_urls", [])
    
    if not verification["verified"]:
        result["issues"].append("在网上未找到该论文，可能为虚构引用")
    
    return result


def _extract_title_from_bibliography(text: str) -> Optional[str]:
    """从参考文献条目中提取标题"""
    # 常见格式: [1] Author. Title. Venue, Year.
    # 或: Author. "Title". Venue, Year.
    
    # 尝试匹配引号中的标题
    quote_match = re.search(r'"([^"]+)"', text)
    if quote_match:
        title = quote_match.group(1).strip()
        # 验证是否像标题（长度、格式）
        if 10 < len(title) < 300 and not title.endswith("."):
            return title
    
    # 尝试匹配 "Author. Title." 格式
    # 标题通常是作者名之后、venue/年份之前的部分
    dot_parts = text.split(". ")
    if len(dot_parts) >= 2:
        # 跳过第一个部分（通常是编号+作者）
        for i, part in enumerate(dot_parts[1:], 1):
            part = part.strip()
            # 检查是否像标题
            if 10 < len(part) < 300:
                # 标题通常以大写字母开头，不以年份开头
                if part[0].isupper() and not re.match(r'^\d{4}', part):
                    return part
    
    return None


def _extract_id_from_url(paper_id: str) -> Optional[str]:
    """
    从 URL 中提取标准论文 ID（ArXiv ID / DOI），转换为 S2 可识别格式。

    Returns:
        "ArXiv:XXXX.XXXXX" / "DOI:10.xxxx/xxxxx" 格式字符串，无法提取时返回 None
    """
    if not paper_id.startswith(("http://", "https://")):
        return None

    # ArXiv: https://arxiv.org/abs/2312.10175 或 arxiv.org/pdf/2312.10175
    arxiv_match = re.search(r'arxiv\.org/(?:abs|pdf|html)/(\d{4}\.\d{4,5}(?:v\d+)?)', paper_id)
    if arxiv_match:
        return f"ArXiv:{arxiv_match.group(1)}"

    # DOI: https://doi.org/10.1109/CVPR46437.2021.00123
    doi_match = re.search(r'doi\.org/(10\.\d{4,}/[^\s?#]+)', paper_id)
    if doi_match:
        return f"DOI:{doi_match.group(1).rstrip('/')}"

    # NeurIPS papers: papers.neurips.cc/paper_files/paper/YEAR/file/...
    # CVPR open-access: openaccess.thecvf.com/content/CVPR2021/...
    # 这些无法转为 S2 ID，返回 None
    return None


def _get_paper_details_from_url_via_mcp(paper_url: str) -> Optional[Dict]:
    """
    当 paper_id 是 URL 且无法提取标准 ID 时，使用 MCP web-reader 读取页面提取元数据。
    """
    content = fetch_page_content(paper_url)
    if not content:
        return None

    info = {"paperId": paper_url, "source": "mcp_web_reader"}

    # 提取标题：<title> 或 og:title 或 citation_title
    title = ""
    for pattern in [
        r'<meta\s+name="citation_title"\s+content="([^"]+)"',
        r'<meta\s+property="og:title"\s+content="([^"]+)"',
        r'<title>(.*?)</title>',
    ]:
        m = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
        if m:
            title = m.group(1).strip()
            break
    info["title"] = title

    # 提取年份
    year_match = re.search(r'<meta\s+name="citation_(?:publication_)?date"\s+content="(\d{4})', content)
    if year_match:
        info["year"] = int(year_match.group(1))
    else:
        info["year"] = _extract_year_from_text(content[:2000])

    # 提取作者
    authors = []
    for m in re.finditer(r'<meta\s+name="citation_author"\s+content="([^"]+)"', content):
        authors.append({"name": m.group(1).strip()})
    if not authors:
        authors = _extract_authors_from_text(content[:2000])
    info["authors"] = authors[:10]

    # 提取摘要
    abs_match = re.search(r'<meta\s+name="(?:citation_abstract|description)"\s+content="([^"]+)"', content, re.DOTALL)
    info["abstract"] = abs_match.group(1).strip()[:1000] if abs_match else ""
    info["venue"] = ""
    info["citationCount"] = 0
    info["externalIds"] = {"url": paper_url}

    return info if info.get("title") else None


def get_paper_details_semantic(paper_id: str,
                               fields: str = None) -> Optional[Dict]:
    """
    使用Semantic Scholar API获取论文详情

    增强版：
    - 识别 URL 格式的 paper_id，提取 ArXiv/DOI 标准 ID
    - 无法提取标准 ID 时，回退到 MCP web-reader 读取原始页面
    - 支持 429 限速自动退避

    Args:
        paper_id: 论文ID（Semantic Scholar ID, DOI, ArXiv ID, 或 URL）
        fields: 要返回的字段

    Returns:
        Dict: 论文详情
    """
    if fields is None:
        fields = "title,year,authors,abstract,venue,externalIds,citationCount,references,citations"

    # ── 处理 URL 格式的 paper_id ──
    if paper_id.startswith(("http://", "https://")):
        standard_id = _extract_id_from_url(paper_id)
        if standard_id:
            paper_id = standard_id  # 转为 ArXiv:xxx 或 DOI:xxx
            logger.debug(f"URL 提取标准ID: {paper_id}")
        else:
            # 无法提取标准 ID，使用 MCP web-reader 回退
            logger.debug(f"URL 无法提取标准ID，使用 MCP web-reader: {paper_id[:80]}")
            mcp_result = _get_paper_details_from_url_via_mcp(paper_id)
            if mcp_result:
                return mcp_result
            return None

    # 检测ID类型并构造URL
    if paper_id.startswith("ArXiv:") or paper_id.startswith("arXiv:"):
        arxiv_id = paper_id.split(":", 1)[1]
        url = f"{S2_PAPER_URL}/ArXiv:{arxiv_id}"
    elif paper_id.startswith("DOI:"):
        url = f"{S2_PAPER_URL}/DOI:{paper_id.replace('DOI:', '')}"
    elif paper_id.startswith("CORPUSID:"):
        url = f"{S2_PAPER_URL}/CORPUSID:{paper_id.replace('CORPUSID:', '')}"
    else:
        url = f"{S2_PAPER_URL}/{paper_id}"

    params = {"fields": fields}

    try:
        _rate_limit()
        response = requests.get(url, params=params, timeout=15)

        # 429 限速处理
        if response.status_code == 429:
            logger.warning("Semantic Scholar 429 限速，等待退避")
            _handle_rate_limit_429(response)
            return None

        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.warning(f"Semantic Scholar获取论文详情失败: {e}")
        return None


# ── 429 限速退避 ──

def _handle_rate_limit_429(response=None):
    """处理 Semantic Scholar 429 限速，指数退避"""
    global _backoff_until, _rate_limit_interval
    retry_after = 60  # 默认退避 60 秒
    if response is not None:
        ra_header = response.headers.get("Retry-After")
        if ra_header:
            try:
                retry_after = int(ra_header)
            except ValueError:
                pass
    _backoff_until = time.time() + retry_after
    # 增加基础限速间隔
    _rate_limit_interval = min(_rate_limit_interval * 1.5, 10.0)
    logger.info(f"S2 限速退避 {retry_after}s，新间隔 {_rate_limit_interval:.1f}s")


def _is_rate_limited() -> bool:
    """检查是否处于 429 退避期"""
    return time.time() < _backoff_until


def search_papers_by_keywords(keywords: List[List[str]],
                               limit: int = 5) -> List[Dict]:
    """
    使用嵌套关键词搜索论文

    Args:
        keywords: 嵌套关键词列表，内层OR，外层AND
                  如 [["deep learning", "neural network"], ["depth estimation"]]
        limit: 返回结果数量

    Returns:
        List[Dict]: 论文列表
    """
    # 将嵌套关键词组合为查询字符串
    query_parts = []
    for group in keywords:
        if isinstance(group, list):
            # OR关系用空格分隔
            query_parts.append(" ".join(group))
        else:
            query_parts.append(str(group))

    # AND关系用空格分隔
    query = " ".join(query_parts)
    return search_papers_semantic(query, limit=limit)


def batch_verify_references(ref_entries: List[Dict],
                             max_concurrent: int = 5) -> List[Dict]:
    """
    批量验证参考文献是否存在

    Args:
        ref_entries: 参考文献条目列表，每个包含 "content" 或 "title" 字段
        max_concurrent: 最大并发数（控制API频率）

    Returns:
        List[Dict]: 验证结果列表
    """
    import time

    results = []
    for i, entry in enumerate(ref_entries):
        # 提取标题
        title = entry.get("title", "")
        if not title:
            content = entry.get("content", "")
            # 尝试从引号中提取标题
            import re
            title_match = re.search(r'"(.+?)"', content)
            if title_match:
                title = title_match.group(1)
            else:
                title = content.split(".")[0] if content else ""

        if not title:
            results.append({
                "verified": False,
                "reason": "无法提取标题",
                "original": entry,
            })
            continue

        # 搜索验证
        papers = search_papers_semantic(title, limit=3)

        if papers:
            # 检查标题相似度
            best_match = papers[0]
            best_title = best_match.get("title", "")
            similarity = _title_similarity(title, best_title)

            results.append({
                "verified": True,
                "similarity": similarity,
                "matched_paper": best_match,
                "original": entry,
            })
        else:
            results.append({
                "verified": False,
                "reason": "未找到匹配论文",
                "original": entry,
            })

        # 控制API频率
        if i < len(ref_entries) - 1:
            time.sleep(1)

    return results


def _title_similarity(title1: str, title2: str) -> float:
    """计算两个标题的相似度（词重叠率）"""
    if not title1 or not title2:
        return 0.0
    words1 = set(title1.lower().split())
    words2 = set(title2.lower().split())
    if not words1:
        return 0.0
    # Jaccard-like: 重叠词 / 查询词
    overlap = len(words1 & words2) / len(words1)
    return round(overlap, 3)


# ========== AMiner API (备选) ==========

def _get_aminer_api_key():
    """获取AMiner API Key"""
    try:
        from config.api_config import AMINER_API_KEY
        return AMINER_API_KEY
    except ImportError:
        return None


def search_papers_aminer(query, size):
    """
    使用AMiner API搜索论文（备选方案）

    Args:
        query: 嵌套关键词列表 [["kw1", "kw2"], ["kw3"]] 或字符串
        size: 返回结果数量
    """
    api_key = _get_aminer_api_key()
    if not api_key:
        logger.warning("AMiner API key未配置，请使用search_papers_semantic")
        return {"data": []}

    url = "https://datacenter.aminer.cn/gateway/open_platform/api/paper/qa/search"

    headers = {
        "Content-Type": "application/json;charset=utf-8",
        "Authorization": api_key
    }

    data = {
        "topic_high": json.dumps(query, ensure_ascii=False) if isinstance(query, list) else query,
        "n_citation_flag": False,
        "force_citation_sort": False,
        "force_year_sort": False,
        "use_topic": isinstance(query, list),
        "size": size,
    }

    try:
        response = requests.post(url, headers=headers, json=data, timeout=15)
        return response.json()
    except Exception as e:
        logger.warning(f"AMiner搜索失败: {e}")
        return {"data": []}


def get_paper_details_aminer(paper_id):
    """使用AMiner API获取论文详情（备选方案）"""
    api_key = _get_aminer_api_key()
    if not api_key:
        return {}

    url = f"https://datacenter.aminer.cn/gateway/open_platform/api/paper/detail?id={paper_id}"
    headers = {"Authorization": api_key}

    try:
        response = requests.get(url, headers=headers, timeout=15)
        return response.json()
    except Exception as e:
        logger.warning(f"AMiner获取详情失败: {e}")
        return {}


# ========== 统一多源搜索入口（兼容旧接口） ==========

def _build_query_string(query) -> str:
    """将嵌套关键词列表或字符串转为查询字符串"""
    if isinstance(query, list):
        query_parts = []
        for group in query:
            if isinstance(group, list):
                query_parts.extend(group)
            else:
                query_parts.append(str(group))
        return " ".join(query_parts)
    return str(query)


def _to_aminer_format(papers: List[Dict]) -> Dict:
    """将标准论文格式转为 AMiner 兼容格式"""
    return {
        "data": [
            {
                "id": p.get("paperId", ""),
                "title": p.get("title", ""),
                "year": p.get("year"),
                "authors": p.get("authors", []),
                "venue": {"raw": p.get("venue", "") if isinstance(p.get("venue"), str)
                          else p.get("venue", {}).get("raw", "")},
                "abstract": p.get("abstract", ""),
                "n_citation": p.get("citationCount", 0),
                "source": p.get("source", ""),
            }
            for p in papers
        ]
    }


def search_papers(query, size):
    """
    搜索论文 — 统一多源降级链

    优先级：MCP (web-search-prime) → 百度学术 → Semantic Scholar → AMiner

    Args:
        query: 嵌套关键词列表 [["kw1", "kw2"], ["kw3"]] 或搜索字符串
        size: 返回结果数量

    Returns:
        搜索结果（保持AMiner格式兼容）
    """
    query_str = _build_query_string(query)

    # 检查缓存
    cached = _get_cache(query_str)
    if cached is not None:
        logger.debug(f"使用缓存结果: {query_str[:50]}")
        return _to_aminer_format(cached)

    # 1. MCP web-search-prime（search_papers_semantic 内部已先尝试 MCP）
    papers = search_papers_semantic(query_str, limit=size)
    if papers:
        _set_cache(query_str, papers)
        return _to_aminer_format(papers)

    # 2. 百度学术
    papers = search_papers_baidu(query_str, limit=size)
    if papers:
        _set_cache(query_str, papers)
        return _to_aminer_format(papers)

    # 3. Semantic Scholar 已在 step 1 中尝试（MCP 不可用时自动回退到 S2）
    #    此处无需重复

    # 4. AMiner（最终回退）
    return search_papers_aminer(query, size)


def get_paper_details(paper_id):
    """
    获取论文详情 — 统一多源降级链

    优先级：Semantic Scholar（含 URL 识别 + MCP web-reader 回退）→ AMiner

    Args:
        paper_id: 论文ID（S2 ID, DOI, ArXiv ID, 或 URL）

    Returns:
        论文详情（保持AMiner格式兼容）
    """
    # 1. Semantic Scholar（已增强：URL 识别 + MCP web-reader 回退）
    details = get_paper_details_semantic(paper_id)

    if details and details.get("paperId"):
        venue = details.get("venue", "")
        if isinstance(venue, str):
            venue_dict = {"raw": venue}
        elif isinstance(venue, dict):
            venue_dict = venue
        else:
            venue_dict = {"raw": str(venue)}

        return {
            "data": [{
                "id": details.get("paperId", ""),
                "title": details.get("title", ""),
                "year": details.get("year"),
                "authors": details.get("authors", []),
                "venue": venue_dict,
                "abstract": details.get("abstract", ""),
                "n_citation": details.get("citationCount", 0),
                "source": details.get("source", "semantic_scholar"),
            }]
        }

    # 2. AMiner（最终回退）
    return get_paper_details_aminer(paper_id)


if __name__ == "__main__":
    # 测试Semantic Scholar搜索
    logger.info("=== Semantic Scholar 搜索测试 ===")
    results = search_papers_semantic("light field depth estimation dual mask", limit=5)
    for r in results:
        logger.info(f"  - [{r.get('year', 'N/A')}] {r.get('title', 'N/A')[:80]}")
        logger.info(f"    Authors: {', '.join(a.get('name', '') for a in r.get('authors', [])[:3])}")
        logger.info(f"    Citations: {r.get('citationCount', 0)}")

    # 测试兼容接口
    logger.info("=== 兼容接口测试 ===")
    compat_results = search_papers([['light field', 'depth estimation'], ['physical model']], 3)
    if compat_results.get("data"):
        for r in compat_results["data"][:3]:
            logger.info(f"  - {r.get('title', 'N/A')[:80]}")
