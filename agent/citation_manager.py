# -*- coding: utf-8 -*-
"""
引用支撑库构建器（v14 精简版）

v14 后 LLM 直出 \\cite{key}，<citation>->[N]->\\cite 流水线已废弃。
collect/verify/dedup/resolve/run_citation_manager* 已删除。

唯一存活方法 build_citation_bank -- 基于 reference_pool 构建 claim 级映射，
供 _build_citation_context / _build_cite_key_list 消费。Phase 0.8 调用。
"""

import json
import re
import logging
from typing import Dict, List

logger = logging.getLogger(__name__)


class CitationManager:
    """引用支撑库构建器（v14 精简版）。"""

    def __init__(self, api_client=None):
        self.api_client = api_client
        self._citation_pool: List[Dict] = []  # 验证后的参考文献池
        self._citation_map: Dict[str, int] = {}  # citation_key -> index
        self._ref_entries: List[Dict] = []  # 最终参考文献条目 [1], [2], ...



    def build_citation_bank(self, reference_pool: List[Dict],
                            project_data: Dict, output_dir: str = None) -> Dict:
        """
        基于 reference_pool 构建引用支撑库（claim 级映射）

        v12.2: claims 写入 ReferenceStore，兼容导出 JSON。

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

        # 尝试使用 ReferenceStore
        store = None
        try:
            from tools.reference_store import get_reference_store
            store = get_reference_store()
        except Exception:
            pass

        for paper in reference_pool[:50]:
            title = paper.get("title", "")
            abstract = paper.get("abstract", "")
            venue = paper.get("venue", "") or paper.get("venue_abbr", "")
            year = paper.get("year", "")

            paper_claims_data = []

            # v11.6: 无 abstract 时使用 title + tags 生成有意义的 claim
            if not abstract:
                if title and len(title) > 10:
                    short_venue = venue if venue else "prior work"
                    year_str = str(year) if year else "recent"
                    tags = paper.get("tags", [])
                    tag_str = ", ".join(tags[:3]) if tags else ""
                    meaningful = [w for w in re.findall(r'[A-Za-z]+', title)
                                  if w.lower() not in {'the', 'a', 'an', 'of', 'for',
                                  'and', 'in', 'on', 'to', 'from', 'with', 'using', 'based'}
                                  and len(w) > 2]
                    technique = meaningful[0] if meaningful else "this approach"
                    paper_claims_data.append({
                        "claim": f"{technique} technique presented in {short_venue} ({year_str}): {title}.",
                        "paper_id": paper.get("paperId", "") or paper.get("doi", ""),
                        "title": title,
                        "year": year,
                    })
                    if tag_str:
                        paper_claims_data.append({
                            "claim": f"Related method using {tag_str} — {title} ({short_venue}, {year_str}).",
                            "paper_id": paper.get("paperId", "") or paper.get("doi", ""),
                            "title": title,
                            "year": year,
                        })
            else:
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
                            parsed = json.loads(response)
                            if isinstance(parsed, list):
                                for claim in parsed[:5]:
                                    if isinstance(claim, str) and len(claim) > 10:
                                        paper_claims_data.append({
                                            "claim": claim,
                                            "paper_id": paper.get("paperId", ""),
                                            "title": title,
                                            "year": paper.get("year"),
                                        })
                    except (json.JSONDecodeError, Exception) as e:
                        logger.debug(f"提取 claim 失败 ({title[:30]}): {e}")

            # 写入 ReferenceStore
            if store and paper_claims_data:
                try:
                    db_paper = store.find_paper_by_title(title)
                    if db_paper:
                        existing = store.get_claims_for_paper(db_paper["id"])
                        if not existing:
                            store.add_claims(db_paper["id"], paper_claims_data)
                except Exception as e:
                    logger.debug(f"[CitationManager] ReferenceStore claims 写入失败: {e}")

            claims.extend(paper_claims_data)

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
