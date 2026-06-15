# -*- coding: utf-8 -*-
"""
Skill: 参考文献审查器 (v13.0)
验证所有参考文献的可检索性和出处真实性。

v13.0 重写要点：
- 核心格式从 <citation> 迁移到 \cite{key}
- extract_all_references() 现在能提取 \cite{key} 格式
- 与 ReferenceStore 协同工作，不再依赖旧的 citation tag 解析
"""

import os
import json
import re
import time

from config.project_config import (
    PAPER_TITLE, OUTPUT_DIR
)
from agent.base_orchestrator import BaseOrchestrator
from api.paper_search import search_papers, get_paper_details

import logging
logger = logging.getLogger(__name__)

# 基类实例：统一 LLM 调用
_orch = BaseOrchestrator(output_dir=OUTPUT_DIR)


def extract_all_references(full_paper_content):
    """
    从全文中提取所有引用标记。

    支持三种格式：
    1. \\cite{key} 或 \\cite{key1,key2} (新格式，主要)
    2. [N] 数字引用 (旧格式，兼容)
    3. <citation>...</citation> (已弃用，兼容)
    """
    # 提取 \cite{key} 引用
    cite_pattern = r'\\cite\{([^}]+)\}'
    cite_matches = re.findall(cite_pattern, full_paper_content)
    cite_keys = set()
    for match in cite_matches:
        for key in match.split(','):
            cite_keys.add(key.strip())

    # 兼容：提取 [N] 数字引用
    numeric_pattern = r'\[(\d+)\]'
    numeric_refs = [int(n) for n in re.findall(numeric_pattern, full_paper_content)]

    # 兼容：提取 <citation> 标记
    citation_pattern = r'<citation>(.*?)</citation>'
    raw_citations = re.findall(citation_pattern, full_paper_content, re.DOTALL)

    return {
        "cite_keys": sorted(cite_keys),
        "numeric_refs": sorted(set(numeric_refs)),
        "citation_tags": raw_citations,
    }


def verify_reference_by_search(ref_entry):
    """通过多源搜索API验证参考文献是否存在"""

    content = ref_entry.get("content", "")
    title = ref_entry.get("title", "")

    # 优先使用 MCP 多源验证
    try:
        from api.paper_search import verify_citation_with_mcp, _extract_title_from_bibliography
        search_title = title or _extract_title_from_bibliography(content)
        if search_title:
            mcp_result = verify_citation_with_mcp(search_title)
            if mcp_result.get("verified"):
                matched = mcp_result.get("matched_paper", {})
                return {
                    "verified": True,
                    "matched_paper": {
                        "title": matched.get("title", search_title),
                        "year": matched.get("year", ""),
                        "venue": matched.get("venue", ""),
                        "authors": [a.get("name", "") for a in matched.get("authors", [])]
                                   if isinstance(matched.get("authors"), list) else [],
                        "id": matched.get("paperId", ""),
                    },
                    "method": mcp_result.get("method", "mcp"),
                }
    except Exception as e:
        logger.debug(f"[reference_checker] MCP验证失败: {e}")

    # 回退：传统搜索
    search_text = title or content[:80]
    try:
        keywords = [[search_text]]
        search_result = search_papers(keywords, 3)
        if "data" in search_result and search_result["data"]:
            for paper in search_result["data"][:3]:
                details = get_paper_details(paper["id"])
                if "data" in details and details["data"]:
                    paper_info = details["data"][0]
                    paper_title = paper_info.get("title", "")
                    if _titles_similar(paper_title, search_text):
                        return {
                            "verified": True,
                            "matched_paper": {
                                "title": paper_title,
                                "year": paper_info.get("year", ""),
                                "venue": paper_info.get("venue", {}).get("raw", ""),
                                "authors": [a.get("name", "") for a in paper_info.get("authors", [])],
                                "id": paper.get("id", ""),
                            },
                        }
        return {"verified": False, "reason": "未找到匹配的论文记录"}
    except Exception as e:
        return {"verified": False, "reason": f"搜索失败: {e}"}


def _titles_similar(title, ref_content):
    """检查标题是否与参考文献条目相似"""
    title_words = set(title.lower().split())
    ref_words = set(ref_content.lower().split())
    if not title_words:
        return False
    overlap = len(title_words & ref_words) / len(title_words)
    return overlap > 0.4


def run_reference_checker(full_paper_content, cite_key_map=None):
    """
    主入口：运行参考文献审查。

    v14.0: 接受 cite_key_map（全局映射），不再独立生成 key。

    1. 提取所有 \cite{key} 引用
    2. 与 cite_key_map / ReferenceStore 中的论文匹配
    3. 标记未匹配的引用为待验证
    4. 返回审查报告
    """
    logger.info("[reference_checker] 开始参考文献审查...")

    # 获取 ReferenceStore
    store = None
    try:
        from tools.reference_store import get_reference_store
        store = get_reference_store()
    except Exception:
        pass

    # 提取引用
    try:
        refs = extract_all_references(full_paper_content)
    except Exception as e:
        logger.error(f"[reference_checker] 提取引用失败: {e}")
        return {"cite_keys": [], "verified": [], "unverified": []}

    cite_keys = refs["cite_keys"]
    logger.info(f"[reference_checker] 发现 {len(cite_keys)} 个 \\cite{{key}} 引用")
    logger.info(f"[reference_checker] 发现 {len(refs['numeric_refs'])} 个数字引用")
    logger.info(f"[reference_checker] 发现 {len(refs['citation_tags'])} 个旧 citation 标记")

    if not cite_keys:
        logger.warning("[reference_checker] 未发现任何 \\cite{key} 引用！")
        return {"cite_keys": [], "verified": [], "unverified": cite_keys}

    # 离线模式：用 ReferenceStore 验证
    skip_online = os.environ.get("SKIP_ONLINE_VERIFICATION", "").lower() in ("1", "true", "yes")

    verified = []
    unverified = []

    # v14: 优先使用传入的 cite_key_map（单一真相源）
    pool_by_key = {}
    if cite_key_map:
        pool_by_key = {k: v for k, v in cite_key_map.items()}
        logger.info(f"[reference_checker] 使用 cite_key_map: {len(pool_by_key)} 个 key")
    elif store:
        # 降级：独立构建（不同模块可能产生不一致的 key）
        try:
            pool = store.get_all_papers(limit=200)
            from tools.text_utils import generate_bib_key
            for idx, paper in enumerate(pool, 1):
                authors = paper.get("authors", [])
                year = paper.get("year", "")
                title = paper.get("title", "")
                key = generate_bib_key(authors, year, title)
                pool_by_key[key] = paper
        except Exception as e:
            logger.debug(f"[reference_checker] 构建 pool_by_key 失败: {e}")

    for key in cite_keys:
        if key in pool_by_key:
            paper = pool_by_key[key]
            verified.append({
                "key": key,
                "title": paper.get("title", ""),
                "verified": True,
                "source": "reference_store",
            })
            # 标记 ReferenceStore
            if store and not paper.get("verified"):
                try:
                    store.mark_verified(paper["id"], True)
                except Exception:
                    pass
        else:
            unverified.append(key)

    # 在线验证未匹配的 key
    if not skip_online and unverified:
        for key in unverified:
            logger.info(f"[reference_checker] 在线验证 cite key: {key}")
            result = verify_reference_by_search({"content": key, "title": ""})
            if result.get("verified"):
                verified.append({
                    "key": key,
                    "verified": True,
                    "source": "online_search",
                    "matched_paper": result.get("matched_paper", {}),
                })
            else:
                verified.append({
                    "key": key,
                    "verified": False,
                    "reason": result.get("reason", "未找到"),
                })
            time.sleep(1)
    elif unverified:
        logger.info(f"[reference_checker] 离线模式，{len(unverified)} 个 key 跳过在线验证")

    # 保存结果
    verification_results = {
        "cite_keys": cite_keys,
        "verified": verified,
        "unverified": unverified,
        "total": len(cite_keys),
        "verified_count": sum(1 for v in verified if v.get("verified")),
    }

    try:
        _orch.save_output("reference_verification.json", verification_results)
    except Exception as e:
        logger.error(f"[reference_checker] 保存验证结果失败: {e}")

    logger.info(
        f"[reference_checker] 审查完成: "
        f"{verification_results['verified_count']}/{len(cite_keys)} 个引用验证通过"
    )

    return verification_results


if __name__ == "__main__":
    # 读取全文进行审查
    full_content = ""
    for chapter_num in range(1, 6):
        import glob
        files = glob.glob(f"{OUTPUT_DIR}/chapter{chapter_num}/chapter{chapter_num}_*.md")
        for f in files:
            with open(f, 'r', encoding='utf-8') as fh:
                full_content += fh.read() + "\n\n"

    if full_content:
        result = run_reference_checker(full_content)
