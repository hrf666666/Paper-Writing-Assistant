# -*- coding: utf-8 -*-
"""
引用管理器 - 统一引用去重、编号、格式化

解决问题：
1. 各章独立生成 <citation> 标记，最终没有统一的编号
2. <citation> 标记未被替换为 [n] 格式
3. 参考文献列表与正文引用不对应
4. 重复引用未去重

设计：
- 收集全文的 <citation> 标记
- 通过 Semantic Scholar 检索验证每个引用
- 去重并分配统一编号
- 将 <citation> 替换为 [n]
- 生成格式化的 References 列表
"""

import re
import json
import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class CitationManager:
    """
    统一引用管理器

    工作流程：
    1. collect(): 收集全文的 <citation> 标记和引用关键词
    2. verify(): 通过 Semantic Scholar 验证每个引用
    3. dedup(): 对重复引用去重，分配统一编号
    4. resolve(): 将 <citation> 替换为 [n]
    5. format_bibliography(): 生成格式化的参考文献列表
    """

    def __init__(self, api_client=None):
        self.api_client = api_client
        self._citation_pool: List[Dict] = []  # 验证后的参考文献池
        self._citation_map: Dict[str, int] = {}  # citation_key -> index
        self._ref_entries: List[Dict] = []  # 最终参考文献条目 [1], [2], ...

    def collect(self, full_text: str) -> List[Dict]:
        """
        从全文中收集所有 <citation> 标记

        Returns:
            List of {"raw": "<citation>...</citation>", "keywords": "..."}
        """
        pattern = r'<citation>(.*?)</citation>'
        matches = re.findall(pattern, full_text, re.DOTALL)

        citations = []
        for i, tag_content in enumerate(matches):
            citations.append({
                "index": i,
                "raw_tag": tag_content.strip(),
                "keywords": self._parse_keywords(tag_content.strip()),
            })

        logger.info(f"[CitationManager] 收集到 {len(citations)} 个 <citation> 标记")
        return citations

    def verify(self, citations: List[Dict], reference_pool: List[Dict] = None) -> List[Dict]:
        """
        验证引用，优先从预构建的 reference_pool 匹配

        Args:
            citations: collect() 的输出
            reference_pool: 预构建的真实参考文献池 (来自 reference_pool_builder)

        Returns:
            验证后的引用列表，每个包含 verified, matched_paper, paper_id
        """
        verified = []

        for cite in citations:
            result = {
                **cite,
                "verified": False,
                "matched_paper": None,
                "paper_id": None,
            }

            # 1. 优先从预构建的 reference_pool 匹配
            if reference_pool:
                match = self._match_in_pool(cite["keywords"], reference_pool)
                if match:
                    result["verified"] = True
                    result["matched_paper"] = match
                    result["paper_id"] = match.get("paperId", "")

            # 2. 如果 reference_pool 无匹配，尝试在线检索
            if not result["verified"] and self.api_client:
                try:
                    from api.paper_search import search_papers, get_paper_details
                    keywords = cite["keywords"]
                    if keywords:
                        search_result = search_papers(keywords, 3)
                        if "data" in search_result and search_result["data"]:
                            for paper_brief in search_result["data"][:2]:
                                details = get_paper_details(paper_brief["id"])
                                if "data" in details and details["data"]:
                                    paper = details["data"][0]
                                    result["verified"] = True
                                    result["matched_paper"] = paper
                                    result["paper_id"] = paper_brief.get("id", "")
                                    break
                except Exception as e:
                    logger.warning(f"[CitationManager] 在线检索失败: {e}")

            verified.append(result)
            status = "✓" if result["verified"] else "✗"
            logger.debug(f"  [{status}] {cite['raw_tag'][:60]}")

        verified_count = sum(1 for v in verified if v["verified"])
        logger.info(f"[CitationManager] 验证完成: {verified_count}/{len(verified)} 通过")

        return verified

    def dedup(self, verified_citations: List[Dict]) -> Dict[str, int]:
        """
        去重并分配统一编号

        Returns:
            citation_key -> [n] 映射
        """
        self._citation_pool = []
        self._citation_map = {}
        self._ref_entries = []

        index = 0
        for cite in verified_citations:
            if not cite.get("verified") or not cite.get("matched_paper"):
                continue

            paper = cite["matched_paper"]
            # 使用 paperId 或 title 作为去重 key
            dedup_key = cite.get("paper_id", "") or paper.get("title", "").lower().strip()

            if dedup_key in self._citation_map:
                # 已存在，复用编号
                continue

            index += 1
            self._citation_map[dedup_key] = index

            # 构建参考文献条目
            authors = []
            if isinstance(paper.get("authors"), list):
                authors = [a.get("name", "") for a in paper["authors"] if a.get("name")]
            author_str = ", ".join(authors[:3])
            if len(authors) > 3:
                author_str += " et al."

            title = paper.get("title", "")
            year = paper.get("year", "")
            venue = ""
            if isinstance(paper.get("venue"), dict):
                venue = paper["venue"].get("raw", "")
            elif isinstance(paper.get("venue"), str):
                venue = paper["venue"]

            entry_text = f"[{index}] {author_str}, \"{title},\" "
            if venue:
                entry_text += f"{venue}, "
            if year:
                entry_text += f"{year}."

            self._ref_entries.append({
                "index": index,
                "entry": entry_text,
                "paper_id": cite.get("paper_id", ""),
                "title": title,
                "dedup_key": dedup_key,
            })

        logger.info(f"[CitationManager] 去重后 {len(self._ref_entries)} 篇参考文献")
        return self._citation_map

    def resolve(self, full_text: str, verified_citations: List[Dict]) -> str:
        """
        将全文中的 <citation> 标记替换为 [n] 格式

        对于未验证的引用，使用 [?] 标记需要人工检查
        """
        # 构建 raw_tag -> [n] 的直接映射
        tag_to_index = {}
        for cite in verified_citations:
            if not cite.get("verified"):
                continue
            paper = cite.get("matched_paper", {})
            dedup_key = cite.get("paper_id", "") or paper.get("title", "").lower().strip()
            if dedup_key in self._citation_map:
                idx = self._citation_map[dedup_key]
                tag_to_index[cite["raw_tag"]] = idx

        def replace_citation(match):
            tag_content = match.group(1).strip()
            if tag_content in tag_to_index:
                return f"[{tag_to_index[tag_content]}]"
            # 尝试模糊匹配
            for key, idx in self._citation_map.items():
                if key in tag_content or tag_content in key:
                    return f"[{idx}]"
            # 未匹配的引用标记为需要检查
            return f"[?]"

        result = re.sub(
            r'<citation>(.*?)</citation>',
            replace_citation,
            full_text,
            flags=re.DOTALL
        )

        return result

    def format_bibliography(self) -> str:
        """生成格式化的参考文献列表 (Markdown)"""
        if not self._ref_entries:
            return "# References\n\n*No references verified.*\n"

        lines = ["# References\n"]
        for entry in sorted(self._ref_entries, key=lambda x: x["index"]):
            lines.append(entry["entry"])
            lines.append("")

        return "\n".join(lines)

    def get_unverified_citations(self, verified_citations: List[Dict]) -> List[Dict]:
        """获取未通过验证的引用列表"""
        return [c for c in verified_citations if not c.get("verified")]

    def get_stats(self) -> Dict:
        """获取引用统计"""
        return {
            "total_ref_entries": len(self._ref_entries),
            "unique_papers": len(set(e["dedup_key"] for e in self._ref_entries)),
        }

    def _parse_keywords(self, tag_content: str) -> List[List[str]]:
        """解析 <citation> 标记中的关键词"""
        try:
            import ast
            parsed = ast.literal_eval(tag_content)
            if isinstance(parsed, list):
                return parsed
        except (ValueError, SyntaxError):
            pass
        # 回退：将原始文本作为单个搜索词
        return [[tag_content[:80]]]

    def _match_in_pool(self, keywords: List[List[str]], pool: List[Dict]) -> Optional[Dict]:
        """在预构建的 reference_pool 中查找匹配"""
        if not keywords:
            return None

        # 提取所有关键词的扁平列表
        all_terms = set()
        for group in keywords:
            if isinstance(group, list):
                for term in group:
                    all_terms.add(term.lower().strip())
            elif isinstance(group, str):
                all_terms.add(group.lower().strip())

        if not all_terms:
            return None

        best_match = None
        best_score = 0

        for paper in pool:
            title = paper.get("title", "").lower()
            # 计算关键词与标题的重叠度
            title_words = set(title.split())
            overlap = sum(1 for t in all_terms if t in title or any(t in w for w in title_words))
            score = overlap / max(len(all_terms), 1)

            if score > best_score and score > 0.3:
                best_score = score
                best_match = paper

        return best_match


def run_citation_manager(full_text: str, api_client=None,
                         reference_pool: List[Dict] = None) -> Tuple[str, str, Dict]:
    """
    主入口：对全文执行引用管理

    Args:
        full_text: 完整的论文 Markdown 文本
        api_client: API 客户端（用于在线检索）
        reference_pool: 预构建的真实参考文献池

    Returns:
        (resolved_text, bibliography, stats)
    """
    manager = CitationManager(api_client)

    # 1. 收集
    citations = manager.collect(full_text)

    # 2. 验证
    verified = manager.verify(citations, reference_pool)

    # 3. 去重编号
    manager.dedup(verified)

    # 4. 替换
    resolved_text = manager.resolve(full_text, verified)

    # 5. 生成参考文献
    bibliography = manager.format_bibliography()

    # 6. 统计
    unverified = manager.get_unverified_citations(verified)
    stats = manager.get_stats()
    stats["unverified_count"] = len(unverified)
    stats["total_citations"] = len(citations)

    if unverified:
        logger.warning(f"[CitationManager] {len(unverified)} 个引用未验证通过，已标记为 [?]")

    return resolved_text, bibliography, stats
