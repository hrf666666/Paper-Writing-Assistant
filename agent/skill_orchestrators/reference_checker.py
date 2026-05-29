# -*- coding: utf-8 -*-
"""
Skill: 参考文献审查器
验证所有参考文献的可检索性和出处真实性，不胡编乱造
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
    """从全文中提取所有引用标记和参考文献条目"""
    citations = []
    
    # 提取<citation>标记
    citation_pattern = r'<citation>(.*?)</citation>'
    raw_citations = re.findall(citation_pattern, full_paper_content, re.DOTALL)
    
    # 提取[n]引用标记
    numeric_pattern = r'\[(\d+)\]'
    numeric_refs = re.findall(numeric_pattern, full_paper_content)
    
    # 提取可能的参考文献列表（References / Bibliography部分）
    ref_section = ""
    ref_markers = ["# References", "# Bibliography", "# 参考文献", "## References", "## Bibliography"]
    for marker in ref_markers:
        idx = full_paper_content.find(marker)
        if idx != -1:
            ref_section = full_paper_content[idx:]
            break
    
    # 解析参考文献条目
    ref_entries = []
    if ref_section:
        # 尝试匹配 [n] Author. Title. Venue, Year. 格式
        entry_pattern = r'\[(\d+)\]\s*(.*?)(?=\n\[\d+\]|\Z)'
        entries = re.findall(entry_pattern, ref_section, re.DOTALL)
        for num, content in entries:
            ref_entries.append({
                "index": int(num),
                "content": content.strip(),
                "source": "bibliography_section",
            })
    
    return {
        "citation_tags": raw_citations,
        "numeric_refs": [int(n) for n in numeric_refs],
        "bibliography_entries": ref_entries,
    }


def verify_reference_by_search(ref_entry):
    """通过多源搜索API验证参考文献是否存在（MCP → 百度学术 → S2 → AMiner）"""

    content = ref_entry.get("content", "")

    # ── 优先使用 MCP 多源验证 ──
    try:
        from api.paper_search import verify_citation_with_mcp, _extract_title_from_bibliography
        title = _extract_title_from_bibliography(content)
        if title:
            mcp_result = verify_citation_with_mcp(title)
            if mcp_result.get("verified"):
                matched = mcp_result.get("matched_paper", {})
                return {
                    "verified": True,
                    "matched_paper": {
                        "title": matched.get("title", title),
                        "year": matched.get("year", ""),
                        "venue": matched.get("venue", ""),
                        "authors": [a.get("name", "") for a in matched.get("authors", [])] if isinstance(matched.get("authors"), list) else [],
                        "id": matched.get("paperId", ""),
                    },
                    "method": mcp_result.get("method", "mcp"),
                }
    except Exception as e:
        logger.debug(f"[reference_checker] MCP验证失败: {e}")

    # ── 回退：传统搜索 ──
    prompt = f"""
请从以下参考文献条目中提取用于论文搜索的关键词。返回一个嵌套数组格式的搜索词：
- 内层数组中的词是OR关系
- 外层数组中的词是AND关系

参考文献条目：{content}

请直接返回嵌套数组，如[["keyword1", "keyword2"], ["keyword3"]]，无需其他解释。
"""

    try:
        response = _orch.call_light(prompt)
        keywords = _orch.parse_json(response.strip(), default=None)
        if keywords is None:
            import ast
            try:
                keywords = ast.literal_eval(response.strip())
            except (ValueError, SyntaxError):
                keywords = None
        if not isinstance(keywords, list):
            keywords = [[content[:50]]]
    except Exception:
        keywords = [[content[:80]]]

    try:
        search_result = search_papers(keywords, 3)
        if "data" in search_result and search_result["data"]:
            for paper in search_result["data"][:3]:
                details = get_paper_details(paper["id"])
                if "data" in details and details["data"]:
                    paper_info = details["data"][0]
                    title = paper_info.get("title", "")
                    if _titles_similar(title, content):
                        return {
                            "verified": True,
                            "matched_paper": {
                                "title": title,
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
    # 简单的关键词重叠度检查
    title_words = set(title.lower().split())
    ref_words = set(ref_content.lower().split())
    if not title_words:
        return False
    overlap = len(title_words & ref_words) / len(title_words)
    return overlap > 0.4


def verify_citation_keywords(citation_tag):
    """验证<citation>标记中的搜索关键词是否有效（多源降级）"""
    try:
        import ast
        keywords = ast.literal_eval(citation_tag)
        if not isinstance(keywords, list):
            return {"verified": False, "reason": "格式不是列表"}

        # 构造搜索标题
        search_title = ""
        for group in keywords:
            if isinstance(group, list):
                search_title += " ".join(group) + " "
            elif isinstance(group, str):
                search_title += group + " "
        search_title = search_title.strip()[:120]

        # 优先 MCP 多源验证
        if search_title:
            try:
                from api.paper_search import verify_citation_with_mcp
                mcp_result = verify_citation_with_mcp(search_title)
                if mcp_result.get("verified"):
                    return {
                        "verified": True,
                        "found_papers": 1,
                        "method": mcp_result.get("method", "mcp"),
                    }
            except Exception:
                pass

        # 回退：统一搜索
        result = search_papers(keywords, 1)
        if "data" in result and result["data"]:
            return {"verified": True, "found_papers": len(result["data"])}
        else:
            return {"verified": False, "reason": "未检索到相关论文"}
    except Exception as e:
        return {"verified": False, "reason": f"关键词解析或搜索失败: {e}"}


def generate_bibliography_from_citations(full_paper_content, verified_citations):
    """根据验证通过的<citation>标记生成完整的参考文献列表"""
    
    all_bib_entries = []
    index = 0
    
    for citation in verified_citations:
        if not citation.get("verified", False):
            continue
        
        keywords = citation.get("keywords", "")
        matched = citation.get("search_result", {})
        
        if matched and "data" in matched and matched["data"]:
            for paper_brief in matched["data"][:2]:  # 每个引用位置最多2篇
                try:
                    details = get_paper_details(paper_brief["id"])
                    if "data" in details and details["data"]:
                        paper = details["data"][0]
                        index += 1
                        
                        # 构建参考文献条目
                        authors = [a.get("name", "") for a in paper.get("authors", []) if a.get("name")]
                        author_str = ", ".join(authors[:3])
                        if len(authors) > 3:
                            author_str += " et al."
                        
                        title = paper.get("title", "")
                        year = paper.get("year", "")
                        venue = paper.get("venue", {}).get("raw", "") if paper.get("venue") else ""
                        
                        entry = f"[{index}] {author_str}, \"{title},\" "
                        if venue:
                            entry += f"{venue}, "
                        if year:
                            entry += f"{year}."
                        
                        all_bib_entries.append({
                            "index": index,
                            "entry": entry,
                            "citation_tag": keywords,
                            "paper_id": paper_brief.get("id", ""),
                        })
                except Exception:
                    continue
    
    return all_bib_entries


def run_reference_checker(full_paper_content):
    """
    主入口：运行参考文献审查
    
    1. 提取所有引用标记
    2. 逐一验证引用的可检索性
    3. 生成验证通过的参考文献列表
    4. 返回审查报告和修正后的参考文献
    """
    logger.info("[reference_checker] 开始参考文献审查...")
    
    # 提取引用
    try:
        refs = extract_all_references(full_paper_content)
    except Exception as e:
        logger.error(f"[reference_checker] 提取引用失败: {e}")
        return {"citation_tags": [], "bibliography_entries": []}
    
    logger.info(f"[reference_checker] 发现 {len(refs['citation_tags'])} 个citation标记")
    logger.info(f"[reference_checker] 发现 {len(refs['numeric_refs'])} 个数字引用")
    logger.info(f"[reference_checker] 发现 {len(refs['bibliography_entries'])} 条参考文献条目")
    
    verification_results = {
        "citation_tags": [],
        "bibliography_entries": [],
    }
    
    # 验证<citation>标记
    for i, tag in enumerate(refs["citation_tags"]):
        logger.info(f"[reference_checker] 验证citation标记 {i+1}/{len(refs['citation_tags'])}...")
        try:
            result = verify_citation_keywords(tag)
        except Exception as e:
            logger.error(f"[reference_checker] citation标记验证失败: {e}")
            result = {"verified": False, "reason": f"验证异常: {e}"}
        result["keywords"] = tag
        verification_results["citation_tags"].append(result)
        time.sleep(2)  # 避免API频率限制
    
    # 验证参考文献条目
    for i, entry in enumerate(refs["bibliography_entries"]):
        logger.info(f"[reference_checker] 验证参考文献条目 {i+1}/{len(refs['bibliography_entries'])}...")
        try:
            result = verify_reference_by_search(entry)
        except Exception as e:
            logger.error(f"[reference_checker] 参考文献条目验证失败: {e}")
            result = {"verified": False, "reason": f"验证异常: {e}"}
        result["original_entry"] = entry
        verification_results["bibliography_entries"].append(result)
        time.sleep(2)
    
    # 保存验证结果
    try:
        _orch.save_output("reference_verification.json", verification_results)
    except Exception as e:
        logger.error(f"[reference_checker] 保存验证结果失败: {e}")
    
    # 统计
    verified_count = sum(1 for r in verification_results["citation_tags"] if r.get("verified"))
    total_count = len(verification_results["citation_tags"])
    logger.info(f"[reference_checker] 审查完成: {verified_count}/{total_count} 个引用验证通过")
    
    # 生成修正建议
    unverified = [
        r for r in verification_results["citation_tags"] 
        if not r.get("verified")
    ]
    
    if unverified:
        logger.warning(f"[reference_checker] 警告: {len(unverified)} 个引用未验证通过，需要人工检查")
        for uv in unverified:
            logger.warning(f"  - 关键词: {uv.get('keywords', 'N/A')}, 原因: {uv.get('reason', 'N/A')}")
    
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
