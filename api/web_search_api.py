# -*- coding: utf-8 -*-
"""
智谱 Web Search API 直接封装

端点: POST /paas/v4/web_search
认证: Bearer {API_KEY}（Coding Plan key 兼容）
文档: https://docs.bigmodel.cn/cn/guide/tools/web-search

与 MCP web-search-prime 的区别:
- MCP: StreamableHTTP 协议（JSON-RPC over HTTP + SSE），共享 MCP 每周配额
- Web Search API: 标准 REST，独立配额，MCP 配额耗尽时仍可用

v11.9 设计:
1. 搜索降级链中的第二通道（MCP 之后、OpenAlex 之前）
2. 搜索结果通过 LLM 提取/验证为结构化学术信息
3. LLM 提取后的结果与 S2/OpenAlex 格式完全兼容
"""

import json
import logging
import re
import time
import threading
from typing import Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

# API 端点
_API_URL = "https://open.bigmodel.cn/api/paas/v4/web_search"

# 请求缓存
_cache: Dict[str, tuple] = {}
_CACHE_TTL = 1800  # 30 分钟
_cache_lock = threading.Lock()

# LLM 客户端单例（延迟初始化）
_light_orch = None
_orch_lock = threading.Lock()


def _get_light_orch():
    """获取 BaseOrchestrator 单例（用于 call_light 快速 LLM 调用）"""
    global _light_orch
    if _light_orch is not None:
        return _light_orch
    with _orch_lock:
        if _light_orch is not None:
            return _light_orch
        from agent.base_orchestrator import BaseOrchestrator
        from config.project_config import OUTPUT_DIR
        _light_orch = BaseOrchestrator(output_dir=OUTPUT_DIR)
        return _light_orch


def _cleanup_cache():
    """清理过期缓存条目"""
    global _cache
    now = time.time()
    expired = [k for k, (_, ts) in _cache.items() if now - ts > _CACHE_TTL]
    for k in expired:
        del _cache[k]
    if expired:
        logger.debug(f"[WebSearch] 清理 {len(expired)} 条过期缓存")


def _get_api_key() -> str:
    from config.api_config import GLM_CODING_PLAN_API_KEY, ZHIPU_GLM_API_KEY
    return GLM_CODING_PLAN_API_KEY or ZHIPU_GLM_API_KEY


def web_search(
    query: str,
    engine: str = "search_std",
    count: int = 10,
    search_intent: bool = False,
    domain_filter: str = "",
    recency_filter: str = "noLimit",
    content_size: str = "high",
    timeout: int = 30,
) -> Optional[Dict]:
    """
    调用智谱 Web Search API

    Returns:
        API 原始响应字典，失败返回 None
    """
    api_key = _get_api_key()
    if not api_key:
        logger.debug("[WebSearch] API Key 未配置")
        return None

    cache_key = f"{query}|{engine}|{domain_filter}|{recency_filter}|{content_size}"
    with _cache_lock:
        if cache_key in _cache:
            result, ts = _cache[cache_key]
            if time.time() - ts < _CACHE_TTL:
                logger.debug(f"[WebSearch] 缓存命中: {query[:40]}")
                return result
        # 顺便清理过期条目
        if len(_cache) > 100:
            expired = [k for k, (_, ts) in _cache.items() if time.time() - ts > _CACHE_TTL]
            for k in expired:
                del _cache[k]

    query = query[:70] if len(query) > 70 else query

    payload = {
        "search_query": query,
        "search_engine": engine,
        "search_intent": search_intent,
        "count": count,
    }
    if domain_filter:
        payload["search_domain_filter"] = domain_filter
    if recency_filter != "noLimit":
        payload["search_recency_filter"] = recency_filter
    if content_size != "medium":
        payload["content_size"] = content_size

    try:
        resp = requests.post(
            _API_URL,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            json=payload,
            timeout=timeout,
        )
        if resp.status_code == 200:
            data = resp.json()
            results = data.get("search_result", [])
            logger.info(f"[WebSearch] 成功: {len(results)} 条 ({query[:50]})")
            _cache[cache_key] = (data, time.time())
            return data
        elif resp.status_code == 429:
            logger.warning("[WebSearch] 429 限速")
            return None
        else:
            logger.warning(f"[WebSearch] HTTP {resp.status_code}: {resp.text[:200]}")
            return None
    except requests.exceptions.Timeout:
        logger.warning(f"[WebSearch] 超时 ({timeout}s)")
        return None
    except Exception as e:
        logger.warning(f"[WebSearch] 失败: {e}")
        return None


# ====== LLM 辅助提取 ======

def _llm_extract_papers(query: str, raw_results: List[Dict]) -> List[Dict]:
    """
    用 LLM 从网页搜索结果中提取结构化学术论文信息

    搜索结果可能是博客、知乎、GitHub 等，但内容中往往引用了真实论文。
    LLM 的任务是从这些内容中识别并提取出真正的学术论文信息。

    Args:
        query: 原始搜索查询
        raw_results: Web Search API 返回的 search_result 列表

    Returns:
        LLM 提取出的论文列表，格式与 paper_search.py 兼容
    """
    if not raw_results:
        return []

    # 拼接搜索结果给 LLM
    snippets = ""
    for i, r in enumerate(raw_results[:8]):
        title = r.get("title", "")
        content = r.get("content", "")[:600]
        link = r.get("link", "")
        media = r.get("media", "")
        snippets += f"\n--- Result {i+1} ---\n"
        snippets += f"Title: {title}\n"
        snippets += f"Source: {media} | URL: {link}\n"
        snippets += f"Content: {content}\n"

    prompt = f"""Search query: "{query}"

Below are web search results. Your task: extract ALL real academic papers mentioned or discussed in these results.

For each paper found, output a JSON array. Each element:
{{
  "title": "exact paper title in English",
  "authors": ["Firstname Lastname", "Firstname Lastname"] (max 3, use FULL names not just surname),
  "year": 2024 or null,
  "venue": "full venue name, e.g. IEEE/CVF Conference on Computer Vision and Pattern Recognition" or "",
  "arxiv_id": "2312.10175" or "",
  "doi": "10.xxxx/..." or "",
  "url": "the original paper URL if found in search results"
}}

Rules:
- ONLY extract real academic papers (journal/conference papers, arXiv preprints)
- Do NOT include blog posts, tutorials, GitHub repos, or survey articles
- Authors: use FULL names (e.g. "Ben Mildenhall" not "Mildenhall"). If only surname is known, still include it.
- Venue: use full name when possible (e.g. "IEEE/CVF Conference on Computer Vision and Pattern Recognition" not "CVPR")
- If a result discusses a paper but you're unsure it's real, include it anyway with best info
- Output ONLY the JSON array, no other text
- If no papers found, output []

Search results:
{snippets}"""

    try:
        orch = _get_light_orch()
        response = orch.call_light(prompt)

        if not response:
            return []

        papers = _parse_llm_json(response)
        if papers:
            logger.info(f"[WebSearch] LLM 从 {len(raw_results)} 条网页中提取出 {len(papers)} 篇论文")
        return papers

    except Exception as e:
        logger.warning(f"[WebSearch] LLM 提取失败: {e}")
        return []


def _parse_llm_json(text: str) -> List[Dict]:
    """解析 LLM 返回的 JSON 数组"""
    # 去掉 markdown 代码块
    text = text.strip()
    text = re.sub(r'^```(?:json)?\s*', '', text)
    text = re.sub(r'\s*```$', '', text)

    # 尝试直接解析
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        pass

    # 尝试提取 JSON 数组
    m = re.search(r'\[.*\]', text, re.DOTALL)
    if m:
        try:
            data = json.loads(m.group())
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            pass

    return []


def _llm_verify_citation(paper_title: str, search_results: List[Dict]) -> Dict:
    """
    用 LLM 判断搜索结果中是否包含目标论文

    Args:
        paper_title: 待验证的论文标题
        search_results: Web Search API 结果列表

    Returns:
        验证结果字典
    """
    if not search_results:
        return {"verified": False, "confidence": 0.0, "method": "none"}

    snippets = ""
    for i, r in enumerate(search_results[:5]):
        snippets += f"\n[{i+1}] {r.get('title', '')}\n"
        snippets += f"    URL: {r.get('link', '')}\n"
        snippets += f"    Content: {(r.get('content', '') or '')[:400]}\n"

    prompt = f"""Is the following academic paper real? Check if any of these search results mention or discuss it.

Paper to verify: "{paper_title}"

Search results:
{snippets}

Answer in JSON only:
{{"verified": true/false, "confidence": 0.0-1.0, "matched_url": "the best matching URL or null, must be from search results", "reason": "brief explanation"}}"""

    try:
        orch = _get_light_orch()
        response = orch.call_light(prompt)

        if not response:
            return {"verified": False, "confidence": 0.0, "method": "none"}

        result = _parse_llm_json(response)
        if isinstance(result, dict):
            pass
        elif isinstance(result, list) and result:
            result = result[0] if isinstance(result[0], dict) else {}
        else:
            # 尝试从文本中提取 JSON 对象
            m = re.search(r'\{.*\}', response, re.DOTALL)
            if m:
                try:
                    result = json.loads(m.group())
                except json.JSONDecodeError:
                    result = {}
            else:
                result = {}

        verified = result.get("verified", False)
        confidence = result.get("confidence", 0.0)
        matched_url = result.get("matched_url")

        ret = {
            "verified": bool(verified),
            "title": paper_title,
            "found_urls": [matched_url] if matched_url else [],
            "confidence": float(confidence),
            "method": "web_search_api_llm" if verified else "none",
        }
        logger.info(f"[WebSearch] LLM 验证 '{paper_title[:40]}': verified={verified}, conf={confidence:.2f}")
        return ret

    except Exception as e:
        logger.warning(f"[WebSearch] LLM 验证失败: {e}")
        return {"verified": False, "confidence": 0.0, "method": "none"}


# ====== 公开接口 ======

def search_papers_web(query: str, limit: int = 10, enrich: bool = True) -> List[Dict]:
    """
    使用 Web Search API 搜索学术论文，LLM 提取，OpenAlex 补全

    互补流程：Web Search → LLM 提取论文 → OpenAlex 补全结构化信息 → 标准化输出

    Args:
        query: 搜索查询
        limit: 最大结果数
        enrich: 是否用 OpenAlex 补全结构化信息（venue/DOI/abstract/citationCount）

    Returns:
        标准论文格式列表（兼容 paper_search.py）
    """
    data = web_search(query, engine="search_std", count=min(limit * 2, 20), content_size="high")
    if not data:
        return []

    raw_results = data.get("search_result", [])

    # ---- Step 1: 用 LLM 从网页搜索结果中提取论文 ----
    extracted = _llm_extract_papers(query, raw_results)

    if not extracted:
        logger.debug("[WebSearch] LLM 未提取到论文，使用正则兜底")
        return _fallback_parse(raw_results, limit)

    # 标准化 LLM 输出
    papers = _normalize_llm_papers(extracted, limit)

    # ---- Step 2: 用 OpenAlex 补全结构化信息 ----
    if enrich and papers:
        papers = _enrich_with_openalex(papers)

    return papers[:limit]


def _normalize_llm_papers(extracted: List[Dict], limit: int) -> List[Dict]:
    """将 LLM 输出标准化为项目统一格式"""
    papers = []
    seen_titles = set()

    for p in extracted[:limit]:
        title = (p.get("title") or "").strip()
        if not title or len(title) < 10:
            continue

        title_key = title.lower()[:40]
        if title_key in seen_titles:
            continue
        seen_titles.add(title_key)

        arxiv_id = p.get("arxiv_id", "")
        doi = p.get("doi", "")
        url = p.get("url", "")

        if arxiv_id and not url:
            url = f"https://arxiv.org/abs/{arxiv_id}"

        paper_id = ""
        if arxiv_id:
            paper_id = f"ArXiv:{arxiv_id}"
        elif doi:
            paper_id = f"DOI:{doi}"
        elif url:
            paper_id = url

        raw_authors = p.get("authors", [])
        authors = []
        for a in raw_authors:
            if isinstance(a, str):
                authors.append({"name": a})
            elif isinstance(a, dict) and a.get("name"):
                authors.append({"name": a["name"]})

        papers.append({
            "paperId": paper_id,
            "title": title,
            "year": p.get("year"),
            "authors": authors[:5],
            "abstract": "",
            "venue": p.get("venue", ""),
            "citationCount": 0,
            "externalIds": {
                **({"ArXiv": arxiv_id} if arxiv_id else {}),
                **({"DOI": doi} if doi else {}),
                **({"url": url} if url else {}),
            },
            "url": url,
            "source": "web_search_api",
        })

    return papers


def _enrich_with_openalex(papers: List[Dict]) -> List[Dict]:
    """
    用 OpenAlex 补全 Web Search API 论文的结构化信息

    对每篇论文用标题搜索 OpenAlex，如果匹配则补全：
    - venue (完整期刊/会议名)
    - DOI
    - abstract
    - citationCount
    - year (如果原来缺失)
    """
    try:
        from api.paper_search import search_papers_openalex
    except ImportError:
        return papers

    enriched_count = 0
    # 只补全前 3 篇（控制总延迟 <60s）
    for paper in papers[:3]:
        title = paper.get("title", "")
        if not title or len(title) < 15:
            continue

        try:
            # 用标题的前 80 字符搜索 OpenAlex，按相关性排序
            oa_results = search_papers_openalex(title[:80], limit=3, sort="relevance_score:desc")
            if not oa_results:
                continue

            # 找最佳匹配（标题词重叠率 > 60%）
            best = _best_title_match(title, oa_results)
            if not best:
                continue

            # 补全缺失字段（不覆盖已有值）
            if not paper.get("year") and best.get("year"):
                paper["year"] = best["year"]

            if not paper.get("abstract") and best.get("abstract"):
                paper["abstract"] = best["abstract"][:500]

            if not paper.get("venue") or paper["venue"] in ("", "arXiv"):
                oa_venue = best.get("venue", "")
                if isinstance(oa_venue, dict):
                    oa_venue = oa_venue.get("raw", "")
                if oa_venue and len(oa_venue) > 2:
                    paper["venue"] = oa_venue
                    updated = True
            else:
                # OpenAlex 有完整 venue 名时，覆盖缩写（如 "CVPR" → "IEEE/CVF Conference on..."）
                oa_venue = best.get("venue", "")
                if isinstance(oa_venue, dict):
                    oa_venue = oa_venue.get("raw", "")
                if oa_venue and len(oa_venue) > len(str(paper.get("venue", ""))) + 5:
                    paper["venue"] = oa_venue
                    updated = True

            if not paper.get("citationCount"):
                paper["citationCount"] = best.get("citationCount", 0)

            # 补全 pages/volume/number (IEEE BibTeX 必需)
            if not paper.get("pages") and best.get("pages"):
                paper["pages"] = best["pages"]
                updated = True
            if not paper.get("volume") and best.get("volume"):
                paper["volume"] = best["volume"]
                updated = True
            if not paper.get("number") and best.get("number"):
                paper["number"] = best["number"]
                updated = True

            # 补全 DOI
            ext = paper.get("externalIds", {})
            if not ext.get("DOI"):
                oa_doi = best.get("externalIds", {}).get("DOI", "")
                if oa_doi:
                    ext["DOI"] = oa_doi
                    if not paper["paperId"].startswith("DOI:"):
                        paper["paperId"] = f"DOI:{oa_doi}"

            # 补全 paperId（如果原来只有 URL）
            if not paper["paperId"]:
                oa_arxiv = best.get("externalIds", {}).get("ArXiv", "")
                if oa_arxiv:
                    paper["paperId"] = f"ArXiv:{oa_arxiv}"
                    ext["ArXiv"] = oa_arxiv
                elif oa_doi:
                    paper["paperId"] = f"DOI:{oa_doi}"

            paper["source"] = "web_search_api+openalex"
            enriched_count += 1

        except Exception:
            continue

    if enriched_count:
        logger.info(f"[WebSearch] OpenAlex 补全 {enriched_count}/{len(papers)} 篇")
    return papers


def _best_title_match(target: str, candidates: List[Dict], threshold: float = 0.6) -> Optional[Dict]:
    """在候选列表中找到标题最匹配的论文"""
    target_words = set(target.lower().split())
    if not target_words:
        return None

    best_paper = None
    best_score = 0.0

    for c in candidates:
        c_title = c.get("title", "")
        c_words = set(c_title.lower().split())
        if not c_words:
            continue

        # 双向重叠率取平均
        overlap_forward = len(target_words & c_words) / len(target_words)
        overlap_backward = len(target_words & c_words) / len(c_words)
        score = (overlap_forward + overlap_backward) / 2

        if score > best_score:
            best_score = score
            best_paper = c

    return best_paper if best_score >= threshold else None


def verify_citation_web(paper_title: str, author_hint: str = "") -> Dict:
    """
    使用 Web Search API + LLM 验证引用真实性

    Args:
        paper_title: 论文标题
        author_hint: 作者提示

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

    query = paper_title
    if author_hint:
        query = f"{author_hint} {paper_title}"
    if len(query) > 70:
        # 去掉 author_hint，只用标题
        query = paper_title
        if len(query) > 70:
            # 保留开头 + 关键尾部词
            words = query.split()
            if len(words) > 10:
                head = " ".join(words[:6])
                tail = " ".join(words[-4:])
                query = f"{head} {tail}"
            query = query[:70]

    data = web_search(query, engine="search_std", count=8)
    if not data:
        return result

    raw_results = data.get("search_result", [])

    # ---- 核心：用 LLM 判断搜索结果是否包含目标论文 ----
    llm_result = _llm_verify_citation(paper_title, raw_results)

    if llm_result.get("verified"):
        result.update(llm_result)
        return result

    # LLM 说没找到，用正则兜底检查 URL 域名
    academic_domains = [
        "arxiv.org", "ieee.org", "acm.org", "springer.com",
        "sciencedirect.com", "nature.com", "openaccess.thecvf.com",
        "semanticscholar.org", "dblp.org", "aminer.cn",
    ]
    academic_urls = []
    for r in raw_results:
        url = r.get("link", "")
        if any(d in url.lower() for d in academic_domains):
            academic_urls.append(url)

    if academic_urls:
        result["verified"] = True
        result["found_urls"] = academic_urls
        result["confidence"] = 0.6  # URL 匹配但 LLM 未确认，低置信度
        result["method"] = "web_search_api_url"

    return result


def check_search_intent(query: str) -> Optional[str]:
    """检查搜索意图"""
    data = web_search(query, engine="search_std", count=1, search_intent=True)
    if not data:
        return None
    intents = data.get("search_intent", [])
    return intents[0].get("intent") if intents else None


# ====== 兜底：正则解析（LLM 不可用时） ======

def _fallback_parse(raw_results: List[Dict], limit: int) -> List[Dict]:
    """正则兜底解析搜索结果"""
    papers = []
    seen_titles = set()

    for r in raw_results:
        title = re.sub(r'<[^>]+>', '', (r.get("title") or "")).strip()
        link = (r.get("link") or "").strip()
        content = re.sub(r'<[^>]+>', '', r.get("content", "")) if r.get("content") else ""
        media = r.get("media", "")

        if not title or len(title) < 10:
            continue

        title_key = title.lower()[:40]
        if title_key in seen_titles:
            continue
        seen_titles.add(title_key)

        year = _extract_year(r.get("publish_date", "")) or _extract_year(content)
        authors = _extract_authors(content)

        arxiv_id = ""
        doi = ""
        if "arxiv.org" in link.lower():
            m = re.search(r'arxiv\.org/(?:abs|pdf|html)/(\d{4}\.\d{4,5})', link)
            if m:
                arxiv_id = m.group(1)
        if "doi.org" in link.lower():
            m = re.search(r'doi\.org/(10\.\d{4,}/[^\s?#]+)', link)
            if m:
                doi = m.group(1).rstrip('/')

        papers.append({
            "paperId": link or f"ws:{title[:50]}",
            "title": title,
            "year": year,
            "authors": authors,
            "abstract": content[:500],
            "venue": media,
            "citationCount": 0,
            "externalIds": {
                "url": link,
                **({"ArXiv": arxiv_id} if arxiv_id else {}),
                **({"DOI": doi} if doi else {}),
            },
            "url": link,
            "source": "web_search_api",
        })

        if len(papers) >= limit:
            break

    return papers


def _extract_year(text: str) -> Optional[int]:
    if not text:
        return None
    m = re.search(r'\b(19|20)\d{2}\b', text)
    return int(m.group()) if m else None


def _extract_authors(text: str) -> List[Dict]:
    if not text:
        return []
    authors = []
    for m in re.finditer(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)', text[:500]):
        name = m.group(1).strip()
        if len(name) > 5:
            authors.append({"name": name})
    return authors[:5]
