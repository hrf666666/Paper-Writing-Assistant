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
        验证引用 — 多源降级链

        优先级：
        1. reference_pool 预构建池匹配
        2. verify_citation_with_mcp() 多源在线验证（MCP → 百度学术 → S2）
        3. search_papers() + get_paper_details() 统一搜索（兜底）

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

            # 2. 多源在线验证（MCP → 百度学术 → Semantic Scholar）
            if not result["verified"]:
                try:
                    from api.paper_search import verify_citation_with_mcp
                    # 从 keywords 构造搜索标题
                    search_title = self._keywords_to_title(cite["keywords"])
                    if search_title:
                        mcp_result = verify_citation_with_mcp(search_title)
                        if mcp_result.get("verified"):
                            result["verified"] = True
                            result["paper_id"] = mcp_result.get("found_urls", [""])[0] if mcp_result.get("found_urls") else ""
                            matched = mcp_result.get("matched_paper")
                            if matched:
                                result["matched_paper"] = matched
                            else:
                                # MCP 验证通过但无结构化数据，构造最小匹配
                                result["matched_paper"] = {
                                    "title": mcp_result.get("title", search_title),
                                    "year": None,
                                    "authors": [],
                                    "venue": "",
                                    "paperId": result["paper_id"],
                                }
                            logger.debug(f"  MCP验证通过: {search_title[:50]} ({mcp_result.get('method')})")
                except Exception as e:
                    logger.debug(f"[CitationManager] MCP验证失败: {e}")

            # 3. 兜底：统一搜索接口
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

    def _keywords_to_title(self, keywords: List[List[str]]) -> str:
        """从嵌套关键词列表中提取搜索标题"""
        if not keywords:
            return ""
        parts = []
        for group in keywords:
            if isinstance(group, list):
                parts.append(" ".join(group))
            elif isinstance(group, str):
                parts.append(group)
        return " ".join(parts)[:120]

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

        对于未验证的引用，使用 reference_pool 中最相关的论文做最佳匹配
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

        # 对未验证的引用尝试兜底匹配
        unverified_tags = []
        for cite in verified_citations:
            if not cite.get("verified"):
                unverified_tags.append(cite)

        if unverified_tags and self._ref_entries:
            # 使用已有的参考文献中最相关的做兜底
            for cite in unverified_tags:
                keywords = cite.get("keywords", [])
                best_idx = self._find_best_fallback(keywords)
                if best_idx is not None:
                    tag_to_index[cite["raw_tag"]] = best_idx
                    logger.debug(f"兜底匹配: {cite['raw_tag'][:40]} -> [{best_idx}]")

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

    def _find_best_fallback(self, keywords: List[List[str]]) -> Optional[int]:
        """从已有的参考文献条目中找到最佳兜底匹配"""
        if not keywords or not self._ref_entries:
            return None

        all_terms = set()
        for group in keywords:
            if isinstance(group, list):
                for term in group:
                    all_terms.add(term.lower().strip())
            elif isinstance(group, str):
                all_terms.add(group.lower().strip())

        if not all_terms:
            return None

        best_idx = None
        best_score = 0
        for entry in self._ref_entries:
            title = entry.get("title", "").lower()
            overlap = sum(1 for t in all_terms if t in title)
            score = overlap / max(len(all_terms), 1)
            if score > best_score and score > 0.2:
                best_score = score
                best_idx = entry["index"]

        return best_idx

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

    def build_citation_bank(self, reference_pool: List[Dict],
                            project_data: Dict, output_dir: str = None) -> Dict:
        """
        基于 reference_pool 构建引用支撑库（claim 级映射）

        为每篇参考论文提取可支撑的 claim（论断/观点），
        建立从 claim 到参考文献的映射表，供章节生成时使用。

        Args:
            reference_pool: 参考文献池（来自 reference_pool_builder）
            project_data: 项目分析数据
            output_dir: 输出目录（用于保存中间结果）

        Returns:
            {"claims": [...], "pool_size": int}
        """
        claims = []
        innovation_points = project_data.get("innovation_points", [])
        model_arch = project_data.get("model_architecture", {})

        for paper in reference_pool[:50]:  # 限制处理量
            title = paper.get("title", "")
            abstract = paper.get("abstract", "")
            if not abstract:
                continue

            # 使用 LLM 提取该论文的可支撑 claim
            if self.api_client:
                try:
                    prompt = f"""Given this paper, list 3-5 key claims/findings that could support a research paper.
Each claim should be a concise statement (one sentence).

Paper title: {title}
Abstract: {abstract[:500]}

Innovation points of our paper: {json.dumps(innovation_points[:3], ensure_ascii=False)[:500]}

Return ONLY a JSON array of strings. No explanation needed."""
                    response = self.api_client.call_light(prompt)
                    if response:
                        response = response.strip()
                        if response.startswith("```"):
                            response = "\n".join(response.split("\n")[1:-1])
                        paper_claims = json.loads(response)
                        if isinstance(paper_claims, list):
                            for claim in paper_claims[:5]:
                                if isinstance(claim, str) and len(claim) > 10:
                                    claims.append({
                                        "claim": claim,
                                        "paper_id": paper.get("paperId", ""),
                                        "title": title,
                                        "year": paper.get("year"),
                                    })
                except (json.JSONDecodeError, Exception) as e:
                    logger.debug(f"提取 claim 失败 ({title[:30]}): {e}")
                    continue

        result = {"claims": claims, "pool_size": len(reference_pool)}
        logger.info(f"[CitationManager] 引用支撑库: {len(claims)} 个 claim, 来自 {len(reference_pool)} 篇论文")

        if output_dir:
            try:
                import os
                os.makedirs(output_dir, exist_ok=True)
                filepath = os.path.join(output_dir, "citation_bank.json")
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
            except Exception as e:
                logger.warning(f"保存 citation_bank 失败: {e}")

        return result

    def _match_in_pool(self, keywords: List[List[str]], pool: List[Dict]) -> Optional[Dict]:
        """在预构建的 reference_pool 中查找匹配（增强版）"""
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
            abstract = (paper.get("abstract", "") or "").lower()

            # 计算关键词与标题的重叠度（标题匹配权重更高）
            title_words = set(title.split())
            title_overlap = sum(1 for t in all_terms if t in title or any(t in w for w in title_words))
            title_score = title_overlap / max(len(all_terms), 1)

            # 计算关键词与摘要的重叠度
            abstract_overlap = sum(1 for t in all_terms if t in abstract)
            abstract_score = abstract_overlap / max(len(all_terms), 1) * 0.5

            # 综合评分：标题匹配为主，摘要匹配为辅
            score = max(title_score, abstract_score)

            # 额外加分：匹配到了 group 中的关键词（词组匹配）
            for group in keywords:
                if isinstance(group, list):
                    group_text = " ".join(group).lower()
                    if group_text in title:
                        score += 0.3

            if score > best_score and score > 0.2:  # 降低初始阈值
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
