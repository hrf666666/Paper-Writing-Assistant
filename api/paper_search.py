# -*- coding: utf-8 -*-
"""
论文搜索API

v5.0: 新增Semantic Scholar API（更稳定、更学术）
     新增智谱MCP增强检索（web-search-prime, zread）
保留AMiner API作为备选

检索优先级：
1. 智谱MCP (web-search-prime) - 利用大模型理解检索意图
2. Semantic Scholar API - 学术论文覆盖广，免费
3. AMiner API - 中文论文覆盖好（需API key）

MCP服务说明（需在 ~/.codebuddy/mcp.json 中配置，或设置 GLM_CODING_PLAN_API_KEY 环境变量）:
- web-search-prime: 智谱MCP网络搜索
- web-reader: 智谱MCP网页读取
- zread: 智谱MCP文档读取
"""

import json
import logging
import re
from pathlib import Path
from typing import List, Dict, Optional, Any

import requests

project_root = Path(__file__).parent.parent

logger = logging.getLogger(__name__)

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
    
    # 回退到Semantic Scholar API
    if fields is None:
        fields = "title,year,authors,abstract,venue,externalIds,citationCount"

    params = {
        "query": query,
        "limit": min(limit, 100),
        "fields": fields,
    }

    try:
        response = requests.get(S2_SEARCH_URL, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()

        papers = data.get("data", [])
        return [
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
    使用智谱MCP验证引用真实性 - 在网络上搜索确认论文存在
    
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
        "method": "mcp_enhanced",
    }
    
    # 1. 使用智谱MCP搜索
    search_query = paper_title
    if author_hint:
        search_query = f"{author_hint} {paper_title}"
    
    mcp_results = search_with_zhipu_mcp(search_query, max_results=5)
    
    if mcp_results:
        # 检查是否有学术来源
        academic_urls = []
        for r in mcp_results:
            url = r.get("url", "")
            if any(domain in url.lower() for domain in [
                "arxiv.org", "ieee.org", "acm.org", "springer.com",
                "sciencedirect.com", "nature.com", "cvpr", "iccv", "eccv"
            ]):
                academic_urls.append(url)
        
        if academic_urls:
            result["verified"] = True
            result["found_urls"] = academic_urls
            result["confidence"] = 0.9 if len(academic_urls) > 1 else 0.7
            return result
    
    # 2. 回退到Semantic Scholar
    papers = search_papers_semantic(paper_title, limit=3)
    if papers:
        result["verified"] = True
        result["confidence"] = 0.95  # Semantic Scholar结果可信度更高
        result["method"] = "semantic_scholar"
        result["matched_paper"] = papers[0] if papers else None
    
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


def get_paper_details_semantic(paper_id: str,
                                fields: str = None) -> Optional[Dict]:
    """
    使用Semantic Scholar API获取论文详情

    Args:
        paper_id: 论文ID（Semantic Scholar ID, DOI, 或 ArXiv ID）
        fields: 要返回的字段

    Returns:
        Dict: 论文详情
    """
    if fields is None:
        fields = "title,year,authors,abstract,venue,externalIds,citationCount,references,citations"

    # 检测ID类型并构造URL
    if paper_id.startswith("arXiv:"):
        url = f"{S2_PAPER_URL}/ArXiv:{paper_id.replace('arXiv:', '')}"
    elif paper_id.startswith("DOI:"):
        url = f"{S2_PAPER_URL}/DOI:{paper_id.replace('DOI:', '')}"
    elif paper_id.startswith("CORPUSID:"):
        url = f"{S2_PAPER_URL}/CORPUSID:{paper_id.replace('CORPUSID:', '')}"
    else:
        url = f"{S2_PAPER_URL}/{paper_id}"

    params = {"fields": fields}

    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.warning(f"Semantic Scholar获取论文详情失败: {e}")
        return None


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


# ========== 兼容旧接口 ==========

def search_papers(query, size):
    """
    搜索论文（兼容旧接口，优先使用Semantic Scholar）

    Args:
        query: 嵌套关键词列表 [["kw1", "kw2"], ["kw3"]] 或搜索字符串
        size: 返回结果数量

    Returns:
        搜索结果（保持AMiner格式兼容）
    """
    # 构建查询字符串
    if isinstance(query, list):
        # 从嵌套列表构建查询
        query_parts = []
        for group in query:
            if isinstance(group, list):
                query_parts.extend(group)
            else:
                query_parts.append(str(group))
        query_str = " ".join(query_parts)
    else:
        query_str = str(query)

    # 优先使用Semantic Scholar
    papers = search_papers_semantic(query_str, limit=size)

    if papers:
        # 转换为AMiner兼容格式
        return {
            "data": [
                {
                    "id": p.get("paperId", ""),
                    "title": p.get("title", ""),
                    "year": p.get("year"),
                    "authors": p.get("authors", []),
                    "venue": {"raw": p.get("venue", "")},
                    "abstract": p.get("abstract", ""),
                    "n_citation": p.get("citationCount", 0),
                }
                for p in papers
            ]
        }

    # 回退到AMiner
    return search_papers_aminer(query, size)


def get_paper_details(paper_id):
    """
    获取论文详情（兼容旧接口，优先使用Semantic Scholar）

    Args:
        paper_id: 论文ID

    Returns:
        论文详情（保持AMiner格式兼容）
    """
    # 优先使用Semantic Scholar
    details = get_paper_details_semantic(paper_id)

    if details and details.get("paperId"):
        return {
            "data": [{
                "id": details.get("paperId", ""),
                "title": details.get("title", ""),
                "year": details.get("year"),
                "authors": details.get("authors", []),
                "venue": {"raw": details.get("venue", "")},
                "abstract": details.get("abstract", ""),
                "n_citation": details.get("citationCount", 0),
            }]
        }

    # 回退到AMiner
    return get_paper_details_aminer(paper_id)


if __name__ == "__main__":
    # 测试Semantic Scholar搜索
    print("=== Semantic Scholar 搜索测试 ===")
    results = search_papers_semantic("light field depth estimation dual mask", limit=5)
    for r in results:
        print(f"  - [{r.get('year', 'N/A')}] {r.get('title', 'N/A')[:80]}")
        print(f"    Authors: {', '.join(a.get('name', '') for a in r.get('authors', [])[:3])}")
        print(f"    Citations: {r.get('citationCount', 0)}")
        print()

    # 测试兼容接口
    print("=== 兼容接口测试 ===")
    compat_results = search_papers([['light field', 'depth estimation'], ['physical model']], 3)
    if compat_results.get("data"):
        for r in compat_results["data"][:3]:
            print(f"  - {r.get('title', 'N/A')[:80]}")
