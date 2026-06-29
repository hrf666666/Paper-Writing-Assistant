# -*- coding: utf-8 -*-
"""
CitationBase —— 引用子系统唯一边界（照 FactBase 范式）

取代散落 16 文件 / 40 函数 / 8 份 \\cite{} 正则副本 / 10 处 min_cites 硬编码的旧状。
所有引用数据与逻辑只在 CitationBase 内部；外部模块只能通过本模块的 API 调用，
不再自己碰 \\cite{} 正则、_cite_key_map、min_cites。

设计（与 FactBase 对称）：
- dataclass + 明确字段，构建一次落盘，多处只读
- 真相源：cite_key_map / title_to_key / author_year_to_key
- 正向链：LLM 输出占位符 <cite title=".." author=".."/> → inject() 多级回退注入 \\cite{key}
- 反向链：audit_chapter() 数引用数 + 池外检测 → critical finding 走 FindingBus rerun
            coverage_report() 统计池子采用率

key 生成规则从 tools/text_utils.generate_bib_key 迁入（唯一权威实现）。
\\cite{} 提取正则唯一一份，消除旧 8 份副本（[^}]+ / [^}]* 行为不一致）。
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# 持久化文件名（全系统约定）
CITATIONBASE_FILENAME = "citation_base.json"

# ── 占位符契约（LLM ↔ 系统的硬接口）──────────────────────────
# LLM 在 LaTeX 正文里写：
#   ResNet~<cite title="Deep Residual Learning for Image Recognition" author="he"/> ...
# author 可选（第一作者姓，小写）。title 必填（论文标题原文）。
PLACEHOLDER_TAG = "cite"  # <cite .../>
_PLACEHOLDER_RE = re.compile(
    r'<cite\s+title="([^"]*)"(?:\s+author="([^"]*)")?\s*/>'
)

# ── 唯一的 \\cite{key} 提取正则（消除旧 8 份副本）─────────────
# 统一用 [^}]+（拒绝空 key）；空 key 检测由 extract_empty_cites 单独提供
_CITE_RE = re.compile(r"\\cite\{([^}]+)\}")
_EMPTY_CITE_RE = re.compile(r"\\cite\{\s*\}")


@dataclass
class CitationBase:
    """引用子系统唯一边界。构建一次，多处只读。

    所有验证/注入/审计/计数都读这里。cite key 的合法性、引用数是否达标、
    池子采用率，全部由本 dataclass 权威判定。
    """

    # ── 真相源（构建一次）──
    cite_key_map: Dict[str, dict] = field(default_factory=dict)
    # key -> paper dict（含 title/authors/year/venue/doi，reference_pool_builder 产出）
    title_to_key: Dict[str, str] = field(default_factory=dict)
    # title.lower().strip() -> key（正向注入第一锚）
    author_year_to_key: Dict[str, str] = field(default_factory=dict)
    # f"{surname_lower}{year}" -> key（双保险第二锚，与 _gen_key 同形）

    # ── 引用契约（每章预期，集中化取代 10 处硬编码）──
    chapter_contract: Dict[str, dict] = field(default_factory=dict)
    # {"ch1": {"min_cites": 8, "must_cite": ["he2016", ...]}, ...}

    # ──────────────────────────────────────────────────────────
    # key 生成（迁自 tools/text_utils.generate_bib_key，唯一权威实现）
    # ──────────────────────────────────────────────────────────

    @staticmethod
    def _gen_key(authors: list, year: Any, title: str) -> str:
        """生成确定性 BibTeX cite key: surname + year。

        同一篇论文无论在哪调用，始终生成相同 key。冲突消解由 build() 处理。
        （逻辑原样迁自 tools/text_utils.py:15-46，含 v15.6 E2 修复。）
        """
        surname = ""
        if authors:
            first = authors[0]
            name = first.get("name", "") if isinstance(first, dict) else str(first)
            # PaperFetch 常把整串作者塞进单元素，需先取首作者（第一个逗号前）
            # 再取其姓（该片段末词）
            _first_author = name.split(",")[0].strip() if name else ""
            surname = _first_author.split()[-1].lower() if _first_author else ""
            surname = re.sub(r'[^a-z]', '', surname)

        if not surname or len(surname) < 2:
            words = re.findall(r'[a-zA-Z]+', title)
            stopwords = {'the', 'a', 'an', 'of', 'for', 'and', 'in', 'on', 'to',
                         'from', 'with', 'by', 'using', 'based'}
            meaningful = [w.lower() for w in words
                          if w.lower() not in stopwords and len(w) > 2]
            surname = (meaningful[0][:6] + meaningful[1][:4]) if len(meaningful) >= 2 \
                else meaningful[0][:10] if meaningful else "ref"

        _yr_raw = str(year) if year is not None else ""
        yr = _yr_raw if _yr_raw.isdigit() else ""
        key = f"{surname}{yr}"
        return key[:20]

    @staticmethod
    def _author_surname(authors: list) -> str:
        """提取首作者姓（小写、去非字母），用于占位符 author 锚匹配。"""
        if not authors:
            return ""
        first = authors[0]
        name = first.get("name", "") if isinstance(first, dict) else str(first)
        _first_author = name.split(",")[0].strip() if name else ""
        surname = _first_author.split()[-1].lower() if _first_author else ""
        return re.sub(r'[^a-z]', '', surname)

    @staticmethod
    def _norm_year(year: Any) -> str:
        _yr_raw = str(year) if year is not None else ""
        return _yr_raw if _yr_raw.isdigit() else ""

    # ──────────────────────────────────────────────────────────
    # 构建 API
    # ──────────────────────────────────────────────────────────

    @classmethod
    def build(cls, reference_pool: List[Dict],
              citation_bank: Optional[Dict] = None,
              chapter_plans: Optional[Dict] = None) -> "CitationBase":
        """从 reference_pool + citation_bank 构建真相源（构建一次）。

        Args:
            reference_pool: reference_pool_builder 产出的论文池
            citation_bank: citation_manager 产出的 claims（含 title/year/authors）
            chapter_plans: 可选，{chapter: {min_cites, must_cite}}；缺省用默认契约

        Returns:
            CitationBase 实例（已去重、已冲突消解）
        """
        cb = cls()
        # 合并去重（按 title.lower().strip()）
        seen = set()
        all_sources: List[dict] = []
        for p in (reference_pool or []):
            if not isinstance(p, dict):
                continue
            t = p.get("title", "").lower().strip()
            if t and t not in seen:
                all_sources.append(p)
                seen.add(t)
        if citation_bank and citation_bank.get("claims"):
            for c in citation_bank["claims"]:
                if not isinstance(c, dict):
                    continue
                t = c.get("title", "").lower().strip()
                if t and t not in seen:
                    all_sources.append(c)
                    seen.add(t)

        for p in all_sources:
            title = p.get("title", "")
            if not title:
                continue
            authors = p.get("authors", []) or []
            year = cls._norm_year(p.get("year"))
            base_key = cls._gen_key(authors, year, title)

            # 冲突消解：同 key 但不同 title → 加 _2/_3 后缀
            key = base_key
            suffix = 2
            while key in cb.cite_key_map:
                existing = cb.cite_key_map[key]
                if existing.get("title", "").lower().strip() == title.lower().strip():
                    break  # 同一篇（重复），跳过
                key = f"{base_key}_{suffix}"
                suffix += 1

            if key not in cb.cite_key_map:
                cb.cite_key_map[key] = p
                cb.title_to_key[title.lower().strip()] = key
                # 双保险第二锚：surname+year（与 _gen_key 同形）
                surname = cls._author_surname(authors)
                if surname and year:
                    cb.author_year_to_key[f"{surname}{year}"] = key

        cb.chapter_contract = chapter_plans or cls._default_contract()
        logger.info(f"[CitationBase] 构建: {len(cb.cite_key_map)} 篇可引论文, "
                    f"{len(cb.chapter_contract)} 章契约")
        return cb

    @staticmethod
    def _default_contract() -> Dict[str, dict]:
        """默认每章引用契约（迁自 ch1/ch2/ch3/ch4 的 10 处硬编码 + 补 ch5 孤儿）。

        min_cites 取各章子节的较大值（按整章计）；must_cite 留空由后续填充。
        """
        return {
            "ch1": {"min_cites": 8, "must_cite": []},   # ch1 §1.1=8 最大
            "ch2": {"min_cites": 5, "must_cite": []},   # ch2 §2.1=5
            "ch3": {"min_cites": 3, "must_cite": []},   # ch3 §3.1=3
            "ch4": {"min_cites": 5, "must_cite": []},   # ch4 §4.1=5
            "ch5": {"min_cites": 3, "must_cite": []},   # ch5 孤儿补齐
        }

    # ── 池外论文登记（堵 ch2 裂缝：在线搜到的论文进 map）──
    def add_papers(self, papers: List[Dict]) -> int:
        """把外部搜到的论文（如 ch2 在线检索结果）登记为合法可引目标。

        Returns: 新增的论文数（去重后）
        """
        added = 0
        for p in (papers or []):
            if not isinstance(p, dict):
                continue
            title = p.get("title", "")
            if not title or title.lower().strip() in self.title_to_key:
                continue
            authors = p.get("authors", []) or []
            year = self._norm_year(p.get("year"))
            base_key = self._gen_key(authors, year, title)
            key = base_key
            suffix = 2
            while key in self.cite_key_map:
                key = f"{base_key}_{suffix}"
                suffix += 1
            self.cite_key_map[key] = p
            self.title_to_key[title.lower().strip()] = key
            surname = self._author_surname(authors)
            if surname and year:
                self.author_year_to_key[f"{surname}{year}"] = key
            added += 1
        if added:
            logger.info(f"[CitationBase] 池外登记: +{added} 篇")
        return added

    # ──────────────────────────────────────────────────────────
    # 唯一 \\cite{} 提取 API（消除旧 8 份副本）
    # ──────────────────────────────────────────────────────────

    @staticmethod
    def extract_cites(text: str) -> List[str]:
        """提取 text 里所有 \\cite{...} 的 key（展开多 key 逗号分隔，去空去重保序）。"""
        keys: List[str] = []
        for m in _CITE_RE.finditer(text or ""):
            for k in m.group(1).split(","):
                k = k.strip()
                if k and k not in keys:
                    keys.append(k)
        return keys

    @staticmethod
    def extract_empty_cites(text: str) -> List[str]:
        """检测空 \\cite{} 残留（旧 [^}]* 变体的职责，单列避免污染主提取）。"""
        return [m.group(0) for m in _EMPTY_CITE_RE.finditer(text or "")]

    # ──────────────────────────────────────────────────────────
    # prompt 注入 API（喂 LLM，取代散落的 build_citation_instruction）
    # ──────────────────────────────────────────────────────────

    def citation_block(self, chapter: Optional[str] = None) -> str:
        """返回喂给 LLM 的 prompt 片段：占位符用法 + 该章可引论文清单(不给 key)。

        清单只给 [序号] title — 作者 et al., year，绝不给 cite key。
        LLM 因此无法编造 key，只能用 title/author 指认。
        """
        lines = [
            "**引用方式（强制，违反将导致返工）**：",
            f"不要写 \\cite{{key}}。引用时必须写占位符：",
            f'  <cite title="论文标题原文" author="第一作者姓"/>',
            f"（author 可选但建议写，用作双保险匹配；title 必填，必须与下方清单一致）",
            "",
            "**可引论文清单（只能引用清单内的论文，按 title/author 指认）**：",
        ]
        for i, (key, p) in enumerate(self.cite_key_map.items(), 1):
            if i > 60:
                break
            title = (p.get("title", "") or "")[:80]
            year = self._norm_year(p.get("year"))
            surname = self._author_surname(p.get("authors", []))
            au = f"{surname} et al.," if surname else ""
            lines.append(f"  [{i}] {title} — {au} {year}".rstrip())

        contract = self.chapter_contract.get(chapter, {}) if chapter else {}
        min_cites = contract.get("min_cites", 5)
        lines.append("")
        lines.append(f"本节至少引用 {min_cites} 篇不同的参考文献（少引将触发返工）。")
        return "\n".join(lines)

    # ──────────────────────────────────────────────────────────
    # 占位符注入 API（正向链核心）
    # ──────────────────────────────────────────────────────────

    def _resolve_placeholder(self, title: str, author: str) -> Optional[str]:
        """多级回退查 key：title 精确 → title fuzzy → author+year。

        Returns: 命中的 key，或 None（交由调用方留痕/回填/返工）。
        """
        if not title:
            return None
        t = title.strip()

        # 1) title 精确匹配
        k = self.title_to_key.get(t.lower().strip())
        if k:
            return k

        # 2) title fuzzy：归一化 token 重合（去掉冒号/破折号后的大小写/标点差异）
        t_norm = self._normalize_title(t)
        best, best_score = None, 0.0
        for map_title, mk in self.title_to_key.items():
            mt_norm = self._normalize_title(map_title)
            if not mt_norm:
                continue
            score = self._token_overlap(t_norm, mt_norm)
            if score > best_score:
                best, best_score = mk, score
        if best and best_score >= 0.6:
            return best

        # 3) author+year 锚：占位符 author 形如 "he2016" 或 "he"(无年份则需配合上下文)
        if author:
            a = re.sub(r'[^a-z0-9]', '', author.lower())
            # 精确 surname+year
            if a in self.author_year_to_key:
                return self.author_year_to_key[a]
            # 仅 surname：找该 surname 的任一年份（取第一个，罕见歧义）
            if len(a) >= 2:
                for ak, mk in self.author_year_to_key.items():
                    if ak.startswith(a) or a.startswith(ak[:len(a)]):
                        # 要求 author 锚与 map 锚 surname 部分一致
                        if re.sub(r'\d', '', ak) == re.sub(r'\d', '', a):
                            return mk
        return None

    @staticmethod
    def _normalize_title(t: str) -> List[str]:
        """归一化标题为小写 token 序列（去标点、去停用词）。"""
        words = re.findall(r'[a-z0-9]+', (t or "").lower())
        stopwords = {'the', 'a', 'an', 'of', 'for', 'and', 'in', 'on', 'to',
                     'from', 'with', 'by', 'using', 'based', 'via'}
        return [w for w in words if w not in stopwords and len(w) > 1]

    @staticmethod
    def _token_overlap(a: List[str], b: List[str]) -> float:
        """两 token 序列的重合度（Jaccard-ish，按较短序列计）。"""
        if not a or not b:
            return 0.0
        sa, sb = set(a), set(b)
        inter = len(sa & sb)
        shorter = min(len(sa), len(sb))
        return inter / shorter if shorter else 0.0

    def inject(self, tex: str) -> Tuple[str, List[dict]]:
        """把所有 <cite .../> 占位符替换为 \\cite{key}（多级回退）。

        同一段落里相邻的同 key 占位符自动合并为 \\cite{k1,k2}。
        未解析的占位符降级为留痕 \\textbf{[REF?-title]} 并计入返回的 unresolved 列表
        （由 audit/回填/返工接管，不静默放过）。

        Returns: (注入后 tex, 未解析占位符列表 [{title, author, span}])
        """
        if not tex:
            return tex, []
        unresolved: List[dict] = []

        def _replace(m: "re.Match") -> str:
            title, author = m.group(1), (m.group(2) or "")
            key = self._resolve_placeholder(title, author)
            if key:
                return f"\\cite{{{key}}}"
            unresolved.append({"title": title, "author": author,
                               "span": (m.start(), m.end())})
            # 留痕（可见化降级，非静默删）
            return f"\\textbf{{[REF?-{title[:40]}]}}"

        new_tex = _PLACEHOLDER_RE.sub(_replace, tex)
        if unresolved:
            logger.warning(f"[CitationBase] 注入: {len(unresolved)} 个占位符未解析"
                           f"（待回填/返工）: {[u['title'][:30] for u in unresolved[:5]]}")
        else:
            n = len(_PLACEHOLDER_RE.findall(tex))
            if n:
                logger.info(f"[CitationBase] 注入: {n} 个占位符全部解析成功")
        return new_tex, unresolved

    # ──────────────────────────────────────────────────────────
    # 池外回填 API（Semantic Scholar 查未解析占位符）
    # ──────────────────────────────────────────────────────────

    def resolve_offline(self, unresolved: List[dict],
                        api_client=None, timeout: float = 15.0) -> List[dict]:
        """未解析占位符 → Semantic Scholar 查 title/author → 命中则回填 map。

        失败/超时/查无的不阻塞，返回仍解析不了的列表（由 audit/rerun 兜底）。
        """
        if not unresolved:
            return []
        still_missing: List[dict] = []
        for u in unresolved:
            title = u.get("title", "")
            if not title or len(title) < 4:
                still_missing.append(u)
                continue
            found = None
            try:
                if api_client:
                    from api.paper_search import search_papers
                    hits = search_papers(title, limit=3)
                    if hits:
                        found = hits[0]
            except Exception as e:
                logger.debug(f"[CitationBase] 回填查询失败 ({title[:30]}): {e}")
            if found and isinstance(found, dict) and found.get("title"):
                added = self.add_papers([found])
                if added:
                    key = self._resolve_placeholder(title, u.get("author", ""))
                    if key:
                        logger.info(f"[CitationBase] 回填成功: {title[:30]} → {key}")
                        continue
            still_missing.append(u)
        if still_missing:
            logger.warning(f"[CitationBase] 回填后仍 {len(still_missing)} 个未解析"
                           f"（触发返工）")
        return still_missing

    # ──────────────────────────────────────────────────────────
    # 审计 API（反向闭环：少引 / 池外残留 → critical finding → rerun）
    # ──────────────────────────────────────────────────────────

    def audit_chapter(self, chapter: str, content: str) -> List[dict]:
        """检查单章引用合规性，返回 findings 列表（同时支持占位符与 \\cite{} 形态）。

        章节内容在 phase5.6 时是占位符 <cite .../>，在 phase7 后是 \\cite{key}。
        本方法两种形态都数：
        - 占位符形态：数 <cite .../> 个数 + 检测 title 不在清单（池外指认）
        - \\cite{} 形态：数 key 个数 + 检测 key ∉ map（幻觉残留）

        - 引用数 < min_cites → CRITICAL（少引，该引不引）
        - 池外指认/残留 → CRITICAL（指认清单外论文）
        - must_cite 缺失 → WARNING
        - 空 \\cite{} 残留 → CRITICAL

        findings 形如 {"severity","chapter","type","detail"}，
        由 audit_to_findings 转 Finding 塞进 FindingBus 走 rerun（与 FactBase 对称）。
        """
        findings: List[dict] = []
        contract = self.chapter_contract.get(chapter, {})
        min_cites = contract.get("min_cites", 0)

        # 占位符形态（phase5.6 审计时）
        placeholders = list(_PLACEHOLDER_RE.finditer(content or ""))
        n_placeholder = len(placeholders)
        offpool_titles = []
        for m in placeholders:
            title = (m.group(1) or "").strip()
            # title 在清单里？（精确或可解析）
            if title and not self._resolve_placeholder(title, m.group(2) or ""):
                offpool_titles.append(title)

        # \cite{} 形态（phase7 后审计时）
        cited = self.extract_cites(content)
        valid = set(self.cite_key_map.keys())
        offpool_keys = [k for k in cited if k not in valid]

        # 引用总数 = 占位符 + 已注入 cite（同一内容通常只有一种形态，相加即总数）
        total = n_placeholder + len(cited)
        if min_cites and total < min_cites:
            findings.append({
                "severity": "CRITICAL", "chapter": chapter,
                "type": "undercited",
                "detail": f"引用 {total} 篇 < 预期 {min_cites} 篇（占位符{n_placeholder} + cite{len(cited)}）",
            })

        # 池外指认（占位符 title 不在清单 → 这是该引但池子没有的，需回填/返工）
        for t in offpool_titles:
            findings.append({
                "severity": "CRITICAL", "chapter": chapter,
                "type": "offpool_cite",
                "detail": f"占位符指认清单外论文: '{t[:50]}'（需回填或为池子补充）",
            })

        # 幻觉残留（\cite{} key ∉ map，注入遗漏或旧路径残留）
        for k in offpool_keys:
            findings.append({
                "severity": "CRITICAL", "chapter": chapter,
                "type": "offpool_key",
                "detail": f"引用 key '{k}' 不在引用池（幻觉或注入遗漏）",
            })

        # 空 cite 残留
        for ec in self.extract_empty_cites(content):
            findings.append({
                "severity": "CRITICAL", "chapter": chapter,
                "type": "empty_cite",
                "detail": f"空引用残留 {ec}",
            })

        # must_cite 缺失（按 key 计，仅 \cite{} 形态有 key）
        for must in contract.get("must_cite", []):
            if must not in cited:
                findings.append({
                    "severity": "WARNING", "chapter": chapter,
                    "type": "missing_must",
                    "detail": f"必引 key '{must}' 未出现",
                })
        return findings

    def audit_to_findings(self, chapter: str, content: str) -> List["object"]:
        """把 audit_chapter 的 dict findings 转 FindingBus 可消费的 Finding 列表。

        延迟 import finding 模块，避免循环依赖。返回 List[Finding]。
        """
        from agent.core.finding import Finding, Severity, Location
        out = []
        for f in self.audit_chapter(chapter, content):
            out.append(Finding(
                source="citation_base",
                kind=f"citation:{f['type']}",
                severity=Severity(f["severity"].lower()),
                description=f["detail"],
                location=Location(chapter=f.get("chapter")),
            ))
        return out

    def coverage_report(self, all_content: str) -> dict:
        """统计池子采用率：pool N 篇 / 被引 Y 篇 / 浪费 Z 篇（哪些 key 没被引）。

        同时认占位符与 \\cite{} 形态（章节在 phase5.6 是占位符、phase7 后是 cite）。
        浪费比例过高告警——引用不只防"乱引"，也防"该引不引"。
        """
        cited_keys = set(self.extract_cites(all_content))
        # 占位符形态：把 title 解析成 key 一并计入被引
        for m in _PLACEHOLDER_RE.finditer(all_content or ""):
            k = self._resolve_placeholder(m.group(1) or "", m.group(2) or "")
            if k:
                cited_keys.add(k)
        pool_keys = set(self.cite_key_map.keys())
        used = cited_keys & pool_keys
        wasted = pool_keys - cited_keys
        n_pool = len(pool_keys)
        rate = (len(used) / n_pool) if n_pool else 0.0
        return {
            "pool_total": n_pool,
            "cited_in_pool": len(used),
            "cited_offpool": len(cited_keys - pool_keys),
            "wasted_count": len(wasted),
            "coverage_rate": round(rate, 3),
            "wasted_keys": sorted(wasted),
            "wasted_high": rate < 0.4 and n_pool > 0,  # 采用率过低告警
        }

    # ──────────────────────────────────────────────────────────
    # bib 生成 API（迁自 bibtex_builder.build_from_cite_key_map）
    # ──────────────────────────────────────────────────────────

    def build_bib(self, tex: str) -> Tuple[str, Dict[int, str]]:
        """从 cite_key_map 生成 references.bib，只为 tex 实际 cite 的 key 生成条目。

        Returns: (bib 内容, {序号: key} 编号映射)
        """
        cited_keys = self.extract_cites(tex)
        cited_set = set(cited_keys)
        # tex 无 cite 时兜底保留全部 map（与旧 bibtex_builder 一致）
        target = {k: v for k, v in self.cite_key_map.items()
                  if (not cited_set) or (k in cited_set)}

        entries: List[str] = []
        num_map: Dict[int, str] = {}
        for i, (key, paper) in enumerate(target.items(), 1):
            entry = self._create_bib_entry(paper, key)
            if entry:
                entries.append(entry)
                num_map[i] = key
        bib_content = "\n\n".join(entries)
        return bib_content, num_map

    @staticmethod
    def _create_bib_entry(paper: dict, key: str) -> Optional[str]:
        """创建单条 BibTeX 条目（迁自 bibtex_builder._create_bib_entry）。"""
        title = (paper.get("title", "") or "").strip()
        if not title:
            return None
        title = re.sub(r'[{}\\]', '', title).strip()

        venue = paper.get("venue", paper.get("journal", ""))
        if isinstance(venue, dict):
            venue = venue.get("raw", "")
        entry_type = "inproceedings" if any(
            kw in str(venue).lower()
            for kw in ["cvpr", "iccv", "eccv", "neurips", "icml", "aaai", "iclr"]
        ) else "article"

        authors = paper.get("authors", [])
        if isinstance(authors, list):
            names = []
            for a in authors:
                names.append(a.get("name", "") if isinstance(a, dict) else str(a))
            author_str = " and ".join(a for a in names if a)
        else:
            author_str = str(authors)

        year = CitationBase._norm_year(paper.get("year"))
        doi = paper.get("doi", "")
        if isinstance(doi, dict):
            doi = ""

        lines = [f"@{entry_type}{{{key},"]
        lines.append(f"  title={{{title}}},")
        if author_str:
            lines.append(f"  author={{{author_str}}},")
        if year:
            lines.append(f"  year={{{year}}},")
        if venue:
            lines.append(f"  {'booktitle' if entry_type == 'inproceedings' else 'journal'}={{{venue}}},")
        if doi:
            lines.append(f"  doi={{{doi}}},")
        lines.append("}")
        return "\n".join(lines)

    # ──────────────────────────────────────────────────────────
    # 序列化 / 持久化（照 FactBase.save/load 范式）
    # ──────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "cite_key_map": self.cite_key_map,
            "title_to_key": self.title_to_key,
            "author_year_to_key": self.author_year_to_key,
            "chapter_contract": self.chapter_contract,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "CitationBase":
        return cls(
            cite_key_map=d.get("cite_key_map", {}),
            title_to_key=d.get("title_to_key", {}),
            author_year_to_key=d.get("author_year_to_key", {}),
            chapter_contract=d.get("chapter_contract", cls._default_contract()),
        )

    def is_empty(self) -> bool:
        return not self.cite_key_map


# ──────────────────────────────────────────────────────────────
# 持久化（保证落盘，失败抛错而非静默）——照 factbase.py 范式
# ──────────────────────────────────────────────────────────────

def save(cb: CitationBase, output_dir: str) -> str:
    """持久化到 {output_dir}/citation_base.json。"""
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, CITATIONBASE_FILENAME)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cb.to_dict(), f, ensure_ascii=False, indent=2)
    logger.info(f"[CitationBase] 已落盘: {path} ({len(cb.cite_key_map)} 篇)")
    return path


def load(output_dir: str) -> Optional[CitationBase]:
    """从磁盘加载。不存在返回 None。"""
    path = os.path.join(output_dir, CITATIONBASE_FILENAME)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return CitationBase.from_dict(json.load(f))
    except Exception as e:
        logger.warning(f"[CitationBase] 加载失败 {path}: {e}")
        return None
