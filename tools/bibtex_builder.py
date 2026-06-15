# -*- coding: utf-8 -*-
"""
BibTeX 引用构建器（v14 精简版）

v14 后 LLM 直出 \\cite{key}，本模块职责简化为：
  - build_from_cite_key_map: 从 _cite_key_map（单一真相源）生成 references.bib
  - _extract_cited_keys: 从 main.tex 提取被 \\cite{} 引用的 key
  - _create_bib_entry[_with_doi]: 生成单条 @article{...}

已删除（v14 不再需要）：
  build_from_verified_citations / replace_numeric_with_cite / _load_* /
  _build_from_phase71_map / _generate_cite_key / _parse_reference_text /
  _get_domain_refs_from_pool / run_bibtex_builder
"""

import os
import re
import json
import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class BibTeXBuilder:
    """BibTeX 引用构建器"""

    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        self.latex_dir = os.path.join(output_dir, "latex")
        self._citation_map: Dict[int, str] = {}  # {1: "zhang2024dual", ...}
        self._bib_entries: Dict[str, str] = {}   # {key: "@article{...}"}


    def build_from_cite_key_map(self, cite_key_map: Dict[str, Dict]) -> Tuple[str, Dict[int, str]]:
        """
        v14.0: 从全局 _cite_key_map 构建 BibTeX（单一真相源）。
        确保生成的 bib entry key 与 prompt 注入的 key 完全一致。
        """
        # v14: 先过滤再编号——只为 tex 中实际 \cite{} 引用的 key 生成条目，
        # 消除孤儿条目 + citation_map.json 断号问题。
        cited_keys = self._extract_cited_keys()
        if cited_keys:
            filtered_map = {k: v for k, v in cite_key_map.items() if k in cited_keys}
            logger.info(f"[BibTeXBuilder] 过滤: pool {len(cite_key_map)} → cited {len(filtered_map)} key")
        else:
            # tex 尚未生成或无 \cite{}：保留全部（兜底）
            filtered_map = cite_key_map

        bib_entries = []
        citation_num_map = {}  # int → key（连续 1..N，无断号）

        for num, (key, paper) in enumerate(filtered_map.items(), 1):
            entry = self._create_bib_entry_with_doi(paper, key)
            if not entry:
                entry = self._create_bib_entry(paper, key)
            if entry:
                self._bib_entries[key] = entry
                citation_num_map[num] = key  # 连续编号
                bib_entries.append(entry)

        bib_content = "\n\n".join(bib_entries)

        # 保存
        os.makedirs(self.latex_dir, exist_ok=True)
        bib_path = os.path.join(self.latex_dir, "references.bib")
        with open(bib_path, "w", encoding="utf-8") as f:
            f.write(bib_content + "\n")

        map_path = os.path.join(self.output_dir, "citation_map.json")
        with open(map_path, "w", encoding="utf-8") as f:
            json.dump(citation_num_map, f, ensure_ascii=False, indent=2)

        self._citation_map = citation_num_map
        logger.info(f"[BibTeXBuilder] key_map 构建: {len(bib_entries)} 条 BibTeX")
        return bib_content, citation_num_map


    def _extract_cited_keys(self) -> set:
        """从 tex 文件中提取所有 \\cite{key} 引用的 key 集合"""
        cited = set()
        tex_path = os.path.join(self.latex_dir, "main.tex")
        if not os.path.exists(tex_path):
            return cited
        try:
            with open(tex_path, "r", encoding="utf-8") as f:
                tex = f.read()
            for m in re.finditer(r'\\cite\{([^}]+)\}', tex):
                for key in m.group(1).split(','):
                    cited.add(key.strip())
        except Exception as e:
            logger.debug(f"[BibTeXBuilder] 读取 tex 失败: {e}")
        return cited


    def _create_bib_entry(self, cite_info: Dict, key: str) -> Optional[str]:
        """创建 BibTeX 条目（v11.1: 补全 volume/number/pages/doi）"""
        title = cite_info.get("title", "")
        if not title:
            return None

        # 清理标题中的 LaTeX 命令
        title = re.sub(r'[{}\\]', '', title)
        title = title.strip()

        # 确定类型
        venue = cite_info.get("venue", cite_info.get("journal", ""))
        if isinstance(venue, dict):
            venue = venue.get("raw", "")
        entry_type = "inproceedings" if any(
            kw in str(venue).lower() for kw in ["cvpr", "iccv", "eccv", "neurips", "icml", "aaai", "iclr"]
        ) else "article"

        # 作者
        authors = cite_info.get("authors", [])
        if isinstance(authors, list):
            author_names = []
            for a in authors:
                if isinstance(a, dict):
                    author_names.append(a.get("name", ""))
                else:
                    author_names.append(str(a))
            author_str = " and ".join(a for a in author_names if a)
        else:
            author_str = str(authors)

        year = cite_info.get("year", "")
        if isinstance(year, int):
            year = str(year)

        # DOI
        doi = cite_info.get("doi", cite_info.get("externalIds", {}).get("DOI", ""))
        if isinstance(doi, dict):
            doi = ""

        # pages/volume/number (IEEE 必需)
        volume = cite_info.get("volume", "")
        number = cite_info.get("number", "")
        pages = cite_info.get("pages", "")

        # 构建条目
        lines = [f"@{entry_type}{{{key},"]
        lines.append(f"  title={{{title}}},")
        if author_str:
            lines.append(f"  author={{{author_str}}},")
        if year:
            lines.append(f"  year={{{year}}},")
        if venue:
            if entry_type == "article":
                lines.append(f"  journal={{{venue}}},")
            else:
                lines.append(f"  booktitle={{{venue}}},")
        if volume:
            lines.append(f"  volume={{{volume}}},")
        if number:
            lines.append(f"  number={{{number}}},")
        if pages:
            lines.append(f"  pages={{{pages}}},")
        if doi:
            lines.append(f"  doi={{{doi}}},")
        lines.append("}")

        return "\n".join(lines)


    def _create_bib_entry_with_doi(self, cite_info: Dict, key: str) -> Optional[str]:
        """
        v11.6: 跳过在线 DOI 获取（境内全超时），直接用 metadata 模板生成
        """
        # doi2bib 已移除（境内不可用），直接走模板组装

        # 降级：原有 _create_bib_entry
        return self._create_bib_entry(cite_info, key)

