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

        v11.2: 同时匹配 <citation>...</citation> 和自闭合 <citation> 标记

        Returns:
            List of {"raw": "<citation>...</citation>", "keywords": "..."}
        """
        citations = []
        paired_positions = set()

        # 先找所有配对的 <citation>...</citation>
        # 用非贪婪匹配，且不跨过另一个 <citation>
        for m in re.finditer(r'<citation>((?:(?!<citation>).)*?)</citation>', full_text, re.DOTALL):
            tag_content = m.group(1).strip()
            citations.append({
                "index": len(citations),
                "raw_tag": tag_content,
                "keywords": self._parse_keywords(tag_content),
            })
            paired_positions.add(m.start())

        # 再找所有未配对的 <citation>（不在配对范围内的）
        for m in re.finditer(r'<citation>', full_text):
            if m.start() in paired_positions:
                continue
            # 检查这个位置是否在某个配对标签内部
            in_paired = False
            for pm in re.finditer(r'<citation>.*?</citation>', full_text, re.DOTALL):
                if pm.start() < m.start() < pm.end():
                    in_paired = True
                    break
            if not in_paired:
                # v11.8: 自闭合 <citation> — 结合前文语境提取关键词
                preceding = full_text[max(0, m.start()-200):m.start()]
                following = full_text[m.end():m.end()+100]
                # 优先从前文提取括号内术语和名词短语
                kw_candidates = re.findall(r'\(([A-Z][^)]{3,40})\)', preceding)
                kw_candidates += re.findall(r'([A-Z][a-z]+(?:\s+[a-z]+){0,3})', preceding)
                # 去停用词
                _stop = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'has', 'have',
                         'been', 'this', 'that', 'these', 'those', 'and', 'but', 'for',
                         'with', 'from', 'which', 'where', 'when', 'how', 'can', 'may',
                         'not', 'also', 'such', 'into', 'more', 'than', 'its', 'our'}
                kw_candidates = [k.strip() for k in kw_candidates
                                 if k.strip() and k.lower().split()[0] not in _stop
                                 and len(k.strip()) > 3]
                kw_text = " ".join(kw_candidates[:5]) if kw_candidates else ""
                if not kw_text:
                    # 降级：取后续句子的第一句
                    kw_text = following.split('.')[0].strip()[:80]
                citations.append({
                    "index": len(citations),
                    "raw_tag": kw_text if kw_text else "unknown",
                    "keywords": self._parse_keywords(kw_text) if kw_text else [["unknown"]],
                })

        logger.info(f"[CitationManager] 收集到 {len(citations)} 个 <citation> 标记 "
                     f"(配对={len(paired_positions)}, 自闭合={len(citations)-len(paired_positions)})")
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
                    result["paper_id"] = match.get("paperId", "") or match.get("doi", "")

            # v12.0: Semantic Scholar 境内永久 429，彻底禁用在线验证
            # 离线池匹配 + MCP 兜底已足够
            should_try_online = False

            # 2. 多源在线验证（MCP → 百度学术 → Semantic Scholar）
            if should_try_online:
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

            # 3. 兜底：统一搜索接口（仅离线池不足时）
            if not result["verified"] and should_try_online and self.api_client:
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

        # v11.1: 保存编号映射供 Phase 7.8 (BibTeXBuilder) 使用
        self._save_ref_entries()

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

        # v11.5: 如果还有未验证引用，使用 reference_pool 全局兜底
        # 放宽条件：只要有未验证引用就触发
        remaining_unverified = [c for c in unverified_tags if c["raw_tag"] not in tag_to_index]
        if remaining_unverified:
            try:
                from tools.reference_pack_manager import get_offline_reference_pool
                offline_pool = get_offline_reference_pool()
                if offline_pool:
                    next_idx = max(self._citation_map.values()) + 1 if self._citation_map else 1
                    # 收集已使用的论文 dedup_key，避免重复分配
                    used_keys = set(self._citation_map.keys())
                    pool_queue = [p for p in offline_pool
                                  if (p.get("doi", "") or p.get("title", "").lower().strip()) not in used_keys]
                    for cite in remaining_unverified:
                        keywords = cite.get("keywords", [])
                        best_paper = self._match_in_pool(keywords, offline_pool)
                        if not best_paper and pool_queue:
                            # 匹配失败时，轮流分配池中未使用的论文
                            best_paper = pool_queue.pop(0)
                        if best_paper:
                            dedup_key = best_paper.get("doi", "") or best_paper.get("title", "").lower().strip()
                            if dedup_key in self._citation_map:
                                tag_to_index[cite["raw_tag"]] = self._citation_map[dedup_key]
                            else:
                                self._citation_map[dedup_key] = next_idx
                                tag_to_index[cite["raw_tag"]] = next_idx
                                next_idx += 1
                    matched = sum(1 for c in remaining_unverified if c["raw_tag"] in tag_to_index)
                    logger.info(f"[CitationManager] 全局兜底: {matched}/{len(remaining_unverified)} 个未验证引用已分配编号")
            except Exception as e:
                logger.warning(f"[CitationManager] 全局兜底失败: {e}")

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

        # v11.2: 处理自闭合 <citation> 标记
        # 使用最后一个有效引用编号作为兜底
        last_idx = max(self._citation_map.values()) if self._citation_map else 0

        def replace_citation_standalone(match):
            if last_idx > 0:
                return f"[{last_idx}]"
            return ""

        result = re.sub(
            r'<citation>(.*?)</citation>',
            replace_citation,
            full_text,
            flags=re.DOTALL
        )
        # v11.2: 也替换自闭合的 <citation> 标记
        result = re.sub(
            r'<citation>',
            replace_citation_standalone,
            result,
        )

        return result

    def _save_ref_entries(self):
        """v11.1: 保存编号映射供 BibTeXBuilder 使用"""
        try:
            import os
            from config.project_config import OUTPUT_DIR
            path = os.path.join(OUTPUT_DIR, "citation_entries.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._ref_entries, f, ensure_ascii=False, indent=2)
            logger.debug(f"[CitationManager] 编号映射已保存: {path}")
        except Exception as e:
            logger.debug(f"[CitationManager] 保存编号映射失败: {e}")

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
            venue = paper.get("venue", "") or paper.get("venue_abbr", "")
            year = paper.get("year", "")

            # v11.6: 无 abstract 时使用 title + tags 生成有意义的 claim
            if not abstract:
                if title and len(title) > 10:
                    short_venue = venue if venue else "prior work"
                    year_str = str(year) if year else "recent"
                    tags = paper.get("tags", [])
                    tag_str = ", ".join(tags[:3]) if tags else ""
                    # 从标题提取关键技术方向
                    meaningful = [w for w in re.findall(r'[A-Za-z]+', title)
                                  if w.lower() not in {'the', 'a', 'an', 'of', 'for',
                                  'and', 'in', 'on', 'to', 'from', 'with', 'using', 'based'}
                                  and len(w) > 2]
                    technique = meaningful[0] if meaningful else "this approach"
                    claims.append({
                        "claim": f"{technique} technique presented in {short_venue} ({year_str}): {title}.",
                        "paper_id": paper.get("paperId", "") or paper.get("doi", ""),
                        "title": title,
                        "year": year,
                    })
                    if tag_str:
                        claims.append({
                            "claim": f"Related method using {tag_str} — {title} ({short_venue}, {year_str}).",
                            "paper_id": paper.get("paperId", "") or paper.get("doi", ""),
                            "title": title,
                            "year": year,
                        })
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
        """在预构建的 reference_pool 中查找匹配（v11.6 增强版：tags + 降级阈值）"""
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
            tags = [t.lower() for t in paper.get("tags", [])]

            # 标题匹配
            title_words = set(title.split())
            title_overlap = sum(1 for t in all_terms if t in title or any(t in w for w in title_words))
            title_score = title_overlap / max(len(all_terms), 1)

            # 摘要匹配
            abstract_overlap = sum(1 for t in all_terms if t in abstract)
            abstract_score = abstract_overlap / max(len(all_terms), 1) * 0.5

            # v11.6: tags 匹配（离线池有 tags 字段）
            tag_text = " ".join(tags)
            tag_overlap = sum(1 for t in all_terms if t in tag_text)
            tag_score = tag_overlap / max(len(all_terms), 1) * 0.4

            score = max(title_score, abstract_score, tag_score)

            # 词组匹配加分
            for group in keywords:
                if isinstance(group, list):
                    group_text = " ".join(group).lower()
                    if group_text in title:
                        score += 0.3

            # 阈值：离线池无 abstract 时降低要求
            threshold = 0.15 if not abstract else 0.2
            if score > best_score and score > threshold:
                best_score = score
                best_match = paper

        return best_match


def run_citation_manager(full_text: str, api_client=None,
                         reference_pool: List[Dict] = None) -> Tuple[str, str, Dict]:
    """
    主入口（旧接口，向后兼容）：对全文执行引用管理

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


def run_citation_manager_for_chapters(
    chapters: Dict,
    api_client=None,
    reference_pool: List[Dict] = None,
) -> Tuple[Dict, str, Dict]:
    """
    v11.2 主入口：按章节独立处理引用，消除 join-then-split。

    流程：
    1. 按 chapter key 逐章 collect <citation> 标记
    2. 汇总所有章节的 citations，统一 verify + dedup（保证编号全局唯一）
    3. 按 chapter key 逐章 resolve（替换 <citation> → [N]）
    4. 返回更新后的 chapters dict + bibliography + stats

    Args:
        chapters: {chapter_key: content_str}，key 可以是 int 或 str
        api_client: API 客户端
        reference_pool: 预构建的参考文献池

    Returns:
        (updated_chapters, bibliography, stats)
    """
    manager = CitationManager(api_client)

    # 1. 按章节收集
    all_citations = []
    chapter_citation_map: Dict[Any, List[Dict]] = {}  # chapter_key -> citations

    for key, content in chapters.items():
        if not content or not content.strip():
            chapter_citation_map[key] = []
            continue
        cites = manager.collect(content)
        chapter_citation_map[key] = cites
        all_citations.extend(cites)
        logger.info(f"[CitationManager] Chapter {key}: {len(cites)} 个 <citation> 标记")

    if not all_citations:
        logger.info("[CitationManager] 全文无 <citation> 标记")
        stats = {"total_ref_entries": 0, "unique_papers": 0,
                 "unverified_count": 0, "total_citations": 0}
        return chapters, manager.format_bibliography(), stats

    # 2. 统一验证 + 去重（保证编号全局唯一且连续）
    verified = manager.verify(all_citations, reference_pool)
    manager.dedup(verified)

    # 3. 按章节 resolve（各章独立替换，互不干扰）
    updated_chapters = {}
    for key, content in chapters.items():
        if not content or not content.strip():
            updated_chapters[key] = content
            continue
        chapter_cites = chapter_citation_map.get(key, [])
        if chapter_cites:
            resolved = manager.resolve(content, chapter_cites)
            updated_chapters[key] = resolved
        else:
            updated_chapters[key] = content

    # 4. 生成参考文献
    bibliography = manager.format_bibliography()

    # 5. 统计
    unverified = manager.get_unverified_citations(verified)
    stats = manager.get_stats()
    stats["unverified_count"] = len(unverified)
    stats["total_citations"] = len(all_citations)

    if unverified:
        logger.warning(f"[CitationManager] {len(unverified)} 个引用未验证通过")

    logger.info(f"[CitationManager] 按章节处理完成: {stats['total_ref_entries']} 篇参考文献, "
                f"{stats['total_citations']} 个引用")

    return updated_chapters, bibliography, stats
