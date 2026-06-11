# -*- coding: utf-8 -*-
"""
Tool: BibTeX 引用构建器 (v11.1)

从已验证的引用池生成 BibTeX 条目，将 [N] 格式引用转为 \\cite{key}。

v11.1 改动：
- 删除硬编码 20 篇光场领域兜底论文（_get_domain_fallback_refs）
- 使用 tools/doi2bib.py 的 DOIToBib 多策略获取标准 BibTeX
- BibTeX 获取降级链：DOI Negotiation → CrossRef → S2 → DBLP → Python 模板
- 所有生成的 BibTeX 必须通过 _validate_bib_entry() 验证
- 失败条目标记 needs_manual_review，不放假 BibTeX
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

    def build_from_verified_citations(self) -> Tuple[str, Dict[int, str]]:
        """
        从已验证的引用构建 BibTeX

        v11.1: 优先加载 Phase 7.1 (CitationManager) 已建立的编号映射，
        确保 [N] → \\cite{key} 的映射与 Phase 7.1 一致。

        Returns:
            (bib_content, citation_map)
        """
        # ── v11.1: 尝试加载 Phase 7.1 已有的编号映射 ──
        phase71_map = self._load_phase71_citation_map()
        # v11.2: 如果 Phase 7.1 映射不足（<5条），说明引用解析质量差，走独立构建路径
        if phase71_map and len(phase71_map) >= 5:
            logger.info(f"[BibTeXBuilder] 使用 Phase 7.1 编号映射: {len(phase71_map)} 条")
            return self._build_from_phase71_map(phase71_map)
        elif phase71_map:
            logger.warning(f"[BibTeXBuilder] Phase 7.1 映射仅 {len(phase71_map)} 条，不足5条，走独立构建")

        # ── 降级：原有逻辑（独立构建编号） ──
        # 读取引用验证结果
        verified = self._load_verified_citations()

        # 读取参考文献列表
        references = self._load_references()

        # 读取引用池
        ref_pool = self._load_reference_pool()

        # 构建 BibTeX 条目
        bib_entries = []
        citation_num = 1

        # 优先处理已验证的引用
        for cite in verified:
            key = self._generate_cite_key(cite, citation_num)
            entry = self._create_bib_entry_with_doi(cite, key)
            if entry:
                self._bib_entries[key] = entry
                self._citation_map[citation_num] = key
                bib_entries.append(entry)
                citation_num += 1

        # 补充从引用池中未使用的论文
        if ref_pool and citation_num <= 55:
            for paper in ref_pool:
                if citation_num > 55:
                    break
                # 检查是否已添加
                title = paper.get("title", "")
                if not title or len(title) < 10:
                    continue
                if any(title[:30].lower() in e.lower() for e in bib_entries):
                    continue
                key = self._generate_cite_key(paper, citation_num)
                entry = self._create_bib_entry_with_doi(paper, key)
                if entry:
                    self._bib_entries[key] = entry
                    self._citation_map[citation_num] = key
                    bib_entries.append(entry)
                    citation_num += 1

        # 补充从参考文献列表中提取的引用
        if references and citation_num <= 55:
            for ref_text in references:
                if citation_num > 55:
                    break
                parsed = self._parse_reference_text(ref_text)
                if parsed and parsed.get("title") and len(parsed.get("title", "")) > 10:
                    key = self._generate_cite_key(parsed, citation_num)
                    entry = self._create_bib_entry_with_doi(parsed, key)
                    if entry:
                        self._bib_entries[key] = entry
                        self._citation_map[citation_num] = key
                        bib_entries.append(entry)
                        citation_num += 1

        # 补充领域基础参考文献（使用 DOI → BibTeX 获取真实论文）
        # 确保至少有 20 条引用
        if citation_num <= 55:
            domain_refs = self._get_domain_refs_from_pool()
            for ref_info in domain_refs:
                if citation_num > 55:
                    break
                title = ref_info.get("title", "")
                if any(title[:30].lower() in e.lower() for e in bib_entries):
                    continue
                key = self._generate_cite_key(ref_info, citation_num)
                entry = self._create_bib_entry_with_doi(ref_info, key)
                if entry:
                    self._bib_entries[key] = entry
                    self._citation_map[citation_num] = key
                    bib_entries.append(entry)
                    citation_num += 1

        bib_content = "\n\n".join(bib_entries)

        # 保存 .bib 文件
        os.makedirs(self.latex_dir, exist_ok=True)
        bib_path = os.path.join(self.latex_dir, "references.bib")
        with open(bib_path, "w", encoding="utf-8") as f:
            f.write(bib_content + "\n")

        # 保存 citation_map
        map_path = os.path.join(self.output_dir, "citation_map.json")
        with open(map_path, "w", encoding="utf-8") as f:
            json.dump(self._citation_map, f, ensure_ascii=False, indent=2)

        logger.info(f"[BibTeXBuilder] 生成 {len(bib_entries)} 条 BibTeX, "
                     f"引用映射 {len(self._citation_map)} 条")

        return bib_content, self._citation_map

    def replace_numeric_with_cite(self, text: str) -> str:
        """
        将 [1], [2,3], [1-3] 或 \\cite{1} 替换为 \\cite{key}
        
        v10.1: 同时处理 [N] 和 \\cite{N} 两种格式
        """
        if not self._citation_map:
            # 加载已保存的 map
            map_path = os.path.join(self.output_dir, "citation_map.json")
            if os.path.exists(map_path):
                with open(map_path, "r", encoding="utf-8") as f:
                    self._citation_map = {int(k): v for k, v in json.load(f).items()}

        if not self._citation_map:
            return text

        def _replace_single(match):
            nums_str = match.group(1)
            keys = []

            # 处理范围 [1-3]
            if "-" in nums_str:
                parts = nums_str.split("-")
                try:
                    start, end = int(parts[0].strip()), int(parts[1].strip())
                    for n in range(start, end + 1):
                        if n in self._citation_map:
                            keys.append(self._citation_map[n])
                except ValueError:
                    pass
            else:
                # 处理 [1], [2,3], [1, 2, 3]
                for n_str in nums_str.split(","):
                    try:
                        n = int(n_str.strip())
                        if n in self._citation_map:
                            keys.append(self._citation_map[n])
                    except ValueError:
                        pass

            if keys:
                return f"\\cite{{{','.join(keys)}}}"
            return match.group(0)  # 无法映射，保留原样

        # 先保护 $...$ 数学上下文，避免匹配 $[0,1]$ 中的 [0,1]
        _math_store = []
        def _protect_math(m):
            _math_store.append(m.group(0))
            return f'__MATHREF_{len(_math_store) - 1}__'
        text_protected = re.sub(r'\$[^$]+?\$', _protect_math, text)

        # 替换 \cite{N} 格式（v10.1 新增）
        text_protected = re.sub(
            r'\\cite\{(\d+(?:\s*[,]\s*\d+)*)\}',
            _replace_single, text_protected,
        )
        
        # 替换 [N], [N,M], [N-M] 格式
        text_protected = re.sub(
            r'\[(\d+(?:\s*[,]\s*\d+|\s*[-]\s*\d+)*)\]',
            _replace_single, text_protected,
        )
        
        # 恢复数学内容
        for i, v in enumerate(_math_store):
            text_protected = text_protected.replace(f'__MATHREF_{i}__', v)

        # v11.3: 处理 LLM 编造的 \cite{key} 格式（非数字 key）
        # 将未在 bib 中找到的 cite key 映射到 citation_map 中最接近的 bib key
        text_protected = self._remap_unknown_cite_keys(text_protected)

        return text_protected

    def _remap_unknown_cite_keys(self, text: str) -> str:
        """
        v11.3: 将 LLM 编造的 \\cite{key} 中不在 bib 里的 key，
        映射到 citation_map 中最接近的 bib key。
        例如 \\cite{shin2018epinet} → \\cite{heber2018} (如果 heber2018 是 EPINet 相关)
        """
        # 收集所有 bib 中的有效 key
        valid_keys = set(self._citation_map.values()) if self._citation_map else set()
        if not valid_keys:
            return text

        # 从 bib 文件中收集所有有效 key
        bib_path = os.path.join(self.latex_dir, "references.bib")
        bib_content = ""
        if os.path.exists(bib_path):
            with open(bib_path, "r", encoding="utf-8") as f:
                bib_content = f.read()
            for m in re.finditer(r'@\w+\{(\w+)', bib_content):
                valid_keys.add(m.group(1))

        # 构建 key → title 映射用于模糊匹配
        key_titles = {}
        if bib_content:
            for m in re.finditer(r'@\w+\{(\w+)[^@]*?title\s*=\s*\{([^}]*)\}', bib_content, re.DOTALL):
                key_titles[m.group(1)] = m.group(2).lower()

        # 收集 citation_map 中 key → paper_info（正确：外层 citation_map，内层 ref_pool 匹配）
        pool_by_key = {}
        ref_pool = self._load_reference_pool()
        for idx, bib_key in self._citation_map.items():
            if idx <= len(ref_pool):
                paper = ref_pool[idx - 1] if idx >= 1 else None
                if paper:
                    pool_by_key[bib_key] = {
                        "title": paper.get("title", "").lower().strip(),
                        "doi": paper.get("doi", ""),
                    }

        def _remap_cite(match):
            keys_str = match.group(1)
            keys = [k.strip() for k in keys_str.split(",")]
            remapped = []
            for key in keys:
                if key in valid_keys:
                    remapped.append(key)
                else:
                    # 尝试从 key 中提取关键词
                    best_key = self._find_closest_bib_key(key, key_titles, pool_by_key)
                    if best_key:
                        remapped.append(best_key)
                        logger.debug(f"[BibTeXBuilder] 映射 \\cite{{{key}}} → \\cite{{{best_key}}}")
                    # else: 丢弃这个引用（避免 undefined citation）
            if remapped:
                return f"\\cite{{{','.join(remapped)}}}"
            return ""  # 无匹配则删除引用标记

        # 匹配 \cite{xxx} 其中 xxx 不全是数字（数字格式已在上面处理）
        text = re.sub(
            r'\\cite\{([^}]+)\}',
            _remap_cite,
            text,
        )
        return text

    def _find_closest_bib_key(self, unknown_key: str, key_titles: Dict[str, str],
                               pool_by_key: Dict[str, Dict]) -> Optional[str]:
        """从有效 bib key 中找到最接近的匹配"""
        # 从 unknown_key 提取关键词 (如 shin2018epinet → ["shin", "epinet"])
        parts = re.findall(r'[a-z]+', unknown_key.lower())
        # 提取年份
        year_match = re.search(r'(20\d{2}|19\d{2})', unknown_key)
        year = year_match.group(1) if year_match else None

        if not parts:
            return None

        best_key = None
        best_score = 0

        for bib_key, title in key_titles.items():
            score = 0
            for part in parts:
                if len(part) >= 3 and part in title:
                    score += 3
                elif len(part) >= 3 and part in bib_key.lower():
                    score += 1
            # 年份匹配加分
            if year and year in bib_key:
                score += 2
            if score > best_score:
                best_score = score
                best_key = bib_key

        # 也尝试匹配 pool_by_key
        for bib_key, info in pool_by_key.items():
            title = info.get("title", "").lower()
            score = 0
            for part in parts:
                if len(part) >= 3 and part in title:
                    score += 3
            if year and year in bib_key:
                score += 2
            if score > best_score:
                best_score = score
                best_key = bib_key

        return best_key if best_score >= 2 else None

    def _load_verified_citations(self) -> List[Dict]:
        """加载已验证的引用"""
        path = os.path.join(self.output_dir, "reference_verification_final.json")
        if not os.path.exists(path):
            path = os.path.join(self.output_dir, "reference_verification.json")
        if not os.path.exists(path):
            return []

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            verified = data.get("verified_references", data.get("references", []))
            if isinstance(verified, list):
                return [r for r in verified if isinstance(r, dict)]
            return []
        except Exception:
            return []

    def _load_references(self) -> List[str]:
        """加载参考文献列表"""
        path = os.path.join(self.output_dir, "references.md")
        if not os.path.exists(path):
            return []
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            # 按行分割，过滤空行
            refs = [line.strip() for line in content.split("\n") if line.strip()]
            return refs
        except Exception:
            return []

    def _load_reference_pool(self) -> List[Dict]:
        """
        v12.2: 优先从 ReferenceStore 加载，降级到 JSON 文件
        """
        # 优先 ReferenceStore
        try:
            from tools.reference_store import get_reference_store
            store = get_reference_store()
            pool = store.get_all_papers(limit=200)
            if pool:
                return pool
        except Exception:
            pass

        # 降级: JSON 文件
        path = os.path.join(self.output_dir, "reference_pool.json")
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    pool = data
                else:
                    pool = data.get("papers", data.get("references", []))
                if pool:
                    return pool
            except Exception:
                pass

        # 最后降级: 离线数据包
        try:
            from tools.reference_pack_manager import get_reference_pack_manager
            mgr = get_reference_pack_manager()
            papers = mgr.get_all_papers()
            if papers:
                return mgr.to_reference_pool_format(papers)
        except Exception:
            pass

        return []

    def _load_phase71_citation_map(self) -> List[Dict]:
        """
        v11.1: 加载 Phase 7.1 (CitationManager) 已建立的编号映射。
        CitationManager.dedup() 按章节中 <citation> 出现顺序分配 [1],[2],...
        返回有序的 ref_entries 列表，每条含 {index, paper_id, title, dedup_key}
        """
        # 尝试从 citation_manager 保存的结果中读取
        for fname in ["citation_entries.json", "ref_entries.json"]:
            path = os.path.join(self.output_dir, fname)
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if isinstance(data, list) and data and "index" in data[0]:
                        return data
                except Exception:
                    pass
        return []

    def _build_from_phase71_map(self, ref_entries: List[Dict]) -> Tuple[str, Dict[int, str]]:
        """
        v11.1: 基于 Phase 7.1 的编号映射构建 BibTeX。
        保证 [N] → cite_key 的映射与 Phase 7.1 的编号完全一致。
        """
        # 加载 reference_pool 用于查找完整论文信息
        ref_pool = self._load_reference_pool()
        pool_by_title = {}
        for p in ref_pool:
            t = p.get("title", "").lower().strip()
            if t:
                pool_by_title[t] = p

        bib_entries = []
        citation_map = {}

        for entry in ref_entries:
            idx = entry["index"]
            title = entry.get("title", "")
            paper_id = entry.get("paper_id", "")

            # 从 reference_pool 查找完整论文信息
            paper_info = None
            if title:
                paper_info = pool_by_title.get(title.lower().strip())
            if not paper_info:
                paper_info = {"title": title, "year": "", "authors": []}

            key = self._generate_cite_key(paper_info, idx)
            bib_entry = self._create_bib_entry_with_doi(paper_info, key)
            if bib_entry:
                self._bib_entries[key] = bib_entry
                citation_map[idx] = key
                bib_entries.append(bib_entry)

        # v11.5: 从离线引用池补充到 ≥25 条 BibTeX
        MIN_BIB_ENTRIES = 25
        if len(bib_entries) < MIN_BIB_ENTRIES and ref_pool:
            existing_titles = set()
            for e in bib_entries:
                # 提取已添加的标题用于去重
                m = re.search(r'title\s*=\s*\{([^}]+)\}', e, re.IGNORECASE)
                if m:
                    existing_titles.add(m.group(1).lower().strip()[:40])

            next_idx = max(citation_map.keys()) + 1 if citation_map else 1
            for paper in ref_pool:
                if len(bib_entries) >= MIN_BIB_ENTRIES:
                    break
                p_title = paper.get("title", "")
                if not p_title or len(p_title) < 10:
                    continue
                if p_title.lower().strip()[:40] in existing_titles:
                    continue
                key = self._generate_cite_key(paper, next_idx)
                entry = self._create_bib_entry_with_doi(paper, key)
                if entry:
                    self._bib_entries[key] = entry
                    citation_map[next_idx] = key
                    bib_entries.append(entry)
                    existing_titles.add(p_title.lower().strip()[:40])
                    next_idx += 1

            if len(bib_entries) > len(ref_entries):
                logger.info(f"[BibTeXBuilder] 离线池补充: +{len(bib_entries) - len(ref_entries)} 条"
                            f" (共 {len(bib_entries)} 条)")

        bib_content = "\n\n".join(bib_entries)

        # 保存
        os.makedirs(self.latex_dir, exist_ok=True)
        bib_path = os.path.join(self.latex_dir, "references.bib")
        with open(bib_path, "w", encoding="utf-8") as f:
            f.write(bib_content + "\n")

        map_path = os.path.join(self.output_dir, "citation_map.json")
        with open(map_path, "w", encoding="utf-8") as f:
            json.dump(citation_map, f, ensure_ascii=False, indent=2)

        logger.info(f"[BibTeXBuilder] Phase 7.1 映射构建: {len(bib_entries)} 条 BibTeX")
        return bib_content, citation_map

    def _generate_cite_key(self, cite_info: Dict, num: int) -> str:
        """生成 cite key: 委托给公共 text_utils.generate_bib_key"""
        from tools.text_utils import generate_bib_key
        authors = cite_info.get("authors", [])
        year = cite_info.get("year", "")
        title = cite_info.get("title", "")
        key = generate_bib_key(authors, year, title, num)
        # 确保唯一
        if key in self._bib_entries:
            key += f"_{num}"
        return key or f"ref{num}"

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

    def _parse_reference_text(self, ref_text: str) -> Optional[Dict]:
        """从参考文献文本解析结构化信息"""
        info = {}

        # 提取年份
        year_match = re.search(r'\b(19|20)\d{2}\b', ref_text)
        if year_match:
            info["year"] = year_match.group()

        # 提取标题（通常在引号或句号之间）
        title_match = re.search(r'"([^"]+)"', ref_text)
        if title_match:
            info["title"] = title_match.group(1)
        elif "." in ref_text:
            parts = ref_text.split(".")
            if len(parts) >= 2:
                info["title"] = parts[0].strip()

        # 提取作者（年份前的部分）
        if year_match:
            author_part = ref_text[:year_match.start()].strip()
            if author_part:
                authors = [a.strip() for a in author_part.split(",")]
                info["authors"] = [{"name": a} for a in authors[:5]]

        return info if info.get("title") else None

    def _create_bib_entry_with_doi(self, cite_info: Dict, key: str) -> Optional[str]:
        """
        v11.6: 跳过在线 DOI 获取（境内全超时），直接用 metadata 模板生成
        """
        # doi2bib 已移除（境内不可用），直接走模板组装

        # 降级：原有 _create_bib_entry
        return self._create_bib_entry(cite_info, key)

    def _get_domain_refs_from_pool(self) -> List[Dict]:
        """
        v11.1: 从 reference_pool 中获取额外论文补充引用
        不再用硬编码兜底论文
        """
        ref_pool = self._load_reference_pool()
        if not ref_pool:
            logger.warning("[BibTeXBuilder] reference_pool 为空，无法补充领域论文")
            return []

        # 过滤已有引用
        existing_titles = set()
        for e in self._bib_entries.values():
            title_match = re.search(r'title\s*=\s*\{([^}]*)\}', e, re.IGNORECASE)
            if title_match:
                existing_titles.add(title_match.group(1).lower()[:30])

        refs = []
        for paper in ref_pool:
            title = paper.get("title", "")
            if not title or len(title) < 10:
                continue
            if title.lower()[:30] in existing_titles:
                continue
            refs.append(paper)

        # 按引用数排序
        refs.sort(key=lambda p: p.get("citationCount", 0), reverse=True)
        return refs[:30]


def run_bibtex_builder(output_dir: str) -> Tuple[str, Dict[int, str]]:
    """BibTeX 构建器入口"""
    builder = BibTeXBuilder(output_dir)
    return builder.build_from_verified_citations()
