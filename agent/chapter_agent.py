# -*- coding: utf-8 -*-
"""chapter_agent — v16.3 分层治理第二批：章节级 agent（省级政府）。

管一章的全面事务：生成 → 内容审 → 元素审（按章区分）→ 质量闭环 → 审计内聚。
解决：无差别审查（B8，ch1也审图）、重复审计（C2，phase5_6+6_5各审一遍）、断链（B1）。

设计：
- 持有 loop 引用，复用现有 quality_gate/auditor/verify（不重写）
- run(ch_num) 内聚"生成→审→改→审计"全流程
- 按章区分审查：ch1无图跳过图审、ch3审公式、ch4审表格
- 审计内聚：每章生成后立即审（替代 phase6_5 批量重复审）

接入点：_execute line 588 `self._run_chapter_phase(ch_num)` → `self.chapter_agent.run(ch_num)`
"""
import logging

logger = logging.getLogger(__name__)


class ChapterAgent:
    """章节级 agent（省级政府）——管一章的生成+审+改+审计。

    职权：本章内容、本章的图/表/公式布局
    边界：只管自己这一章，不碰别章；只审+驱动改，最终决策权在 loop
    """

    # 每章实际包含的元素（用于按章区分审查）
    _CHAPTER_ELEMENTS = {
        1: {"has_figure": False, "has_formula": False, "has_table": False},   # Introduction
        2: {"has_figure": False, "has_formula": False, "has_table": False},   # Related Work
        3: {"has_figure": True,  "has_formula": True,  "has_table": False},   # Methodology
        4: {"has_figure": True,  "has_formula": False, "has_table": True},    # Experiments
        5: {"has_figure": False, "has_formula": False, "has_table": False},   # Conclusion
    }

    def _get_elements(self, ch_num: int) -> dict:
        """G1: 获取本章元素配置——venue_profile 驱动，fallback 用 _CHAPTER_ELEMENTS。

        优先读 venue_adapter.profile.content_patterns[章节名].chapter_elements
        （让不同期刊/会议的章节元素差异由 profile 决定，而非硬编码）。
        venue 未配 chapter_elements 时，fallback 到 _CHAPTER_ELEMENTS（保证总有值）。
        """
        loop = self.loop
        ch_name = loop._CHAPTER_CONFIGS.get(ch_num, ("", ""))[1]
        _va = getattr(loop, "venue_adapter", None)
        if _va and getattr(_va, "profile", None):
            cp = _va.profile.content_patterns.get(ch_name, {})
            ce = cp.get("chapter_elements", {})
            if ce:   # venue 配了就用 venue 的
                return ce
        # fallback：venue 未配 chapter_elements
        return self._CHAPTER_ELEMENTS.get(ch_num, {})

    def __init__(self, loop):
        """持有 loop 引用，复用其现有方法和状态。

        Args:
            loop: ResearchLoop 实例（提供 _project_data/_ref_data/_chapters/
                  quality_gate/auditor/venue_adapter 等共享状态）
        """
        self.loop = loop

    def run(self, ch_num: int) -> str:
        """章节生成全流程（省级政府管一章全面事务）。

        流程：构建kwargs → orchestrator生成 → 内容质量闭环 → 子节校验
              → 审计内聚（替代phase6_5）→ 存储 → 返回

        按章区分审查：根据 _get_elements（venue 驱动）跳过本章没有的元素审查。
        """
        loop = self.loop
        module_name, chapter_name = loop._CHAPTER_CONFIGS[ch_num]
        elements = self._get_elements(ch_num)   # G1: venue 驱动，fallback _CHAPTER_ELEMENTS

        logger.info(f"[ChapterAgent] ch{ch_num} ({chapter_name}) 开始 — "
                    f"元素: {elements}")

        # ── 1. 生成（复用现有 orchestrator 调用逻辑）──
        content = self._generate(ch_num, module_name, chapter_name)

        # ── 2. 内容质量闭环（复用 _quality_ensure，带 venue 规格）──
        content, _ = loop._quality_ensure(chapter_name, content)

        # ── 3. 子节校验（复用 _verify_chapter_subsections，按章区分 + numeric 短路）──
        content = self._verify_with_awareness(ch_num, content, elements)

        # ── 4. 审计内聚（本章生成后立即审，替代 phase6_5 批量重复审）──
        self._audit_chapter(ch_num, chapter_name, content)

        # ── 5. 存储 ──
        loop._chapters[ch_num] = content

        # ── 6. ch2 特有：收编在线论文 ──
        if ch_num == 2:
            self._ch2_collect_online_papers()

        logger.info(f"[ChapterAgent] ch{ch_num} ({chapter_name}) 完成")
        return content

    def _generate(self, ch_num: int, module_name: str, chapter_name: str) -> str:
        """调 orchestrator 生成章节内容（迁移自 _run_chapter_phase 前半段）。"""
        import importlib
        loop = self.loop
        mod = importlib.import_module(f"agent.skill_orchestrators.{module_name}")
        run_fn = getattr(mod, f"run_chapter{ch_num}")

        # 构建前序章节摘要
        previous_chapters = {}
        for i in range(1, ch_num):
            if i in loop._chapters:
                previous_chapters[i] = loop._chapters[i][:2000]

        # 注入 Phase 0.65 分析结果
        if hasattr(loop, '_content_strategy') and loop._content_strategy:
            loop._project_data['content_strategy'] = loop._content_strategy
        if hasattr(loop, '_motivation_thread') and loop._motivation_thread:
            loop._project_data['motivation_thread'] = loop._motivation_thread
        if hasattr(loop, '_outline') and loop._outline:
            _ol = loop._outline.get("outline", loop._outline) if isinstance(loop._outline, dict) else {}
            loop._project_data['outline'] = _ol

        kwargs = {"citation_context": loop._build_citation_context(f"ch{ch_num}"),
                  "venue_adapter": loop.venue_adapter}
        if ch_num > 1:
            kwargs["previous_chapters"] = previous_chapters
        if ch_num == 5:
            kwargs["skip_limitations"] = loop._has_extra_discussion()

        return run_fn(loop._project_data, loop._ref_data, **kwargs)

    def _verify_with_awareness(self, ch_num: int, content: str, elements: dict = None) -> str:
        """子节校验（按章区分审查）。

        G1 接通：把 elements 透传给 _verify_chapter_subsections，
        无数值章（has_formula=False 且非 Experiments）跳过 _judge_metric_attribution 的 LLM 调用，
        节省 ch1/ch2/ch5 的 LLM 成本 + 避免误判。
        """
        loop = self.loop
        return loop._verify_chapter_subsections(ch_num, content, elements=elements)

    def _audit_chapter(self, ch_num: int, chapter_name: str, content: str):
        """审计内聚——本章生成后立即审（替代 phase6_5 批量重复审）。

        v16.3 治理改革：审计从 phase5_6+phase6_5 两次批量审，
        改为 ChapterAgent 每章生成后立即审一次。
        - 解决 C2（重复审计）：只审一次
        - 解决 B1（断链）：findings 直接录入 FindingBus 供闭环消费
        """
        loop = self.loop
        if not getattr(loop, 'auditor', None):
            return
        # 确保 auditor 有 FactBase
        _fb = getattr(loop, '_factbase', None)
        if _fb and not _fb.is_empty():
            if not getattr(loop.auditor, '_factbase', None):
                loop.auditor.set_factbase(_fb)

        try:
            report = loop.auditor.audit_chapter(
                f"phase{ch_num}", chapter_name, content,
                loop._project_data, loop._ref_data
            )
            # 录入 FindingBus（供 rerun/闭环消费）
            from agent.core.finding import audit_report_to_findings as _a2f
            findings = _a2f(report, chapter_hint=f"ch{ch_num}")
            if findings:
                loop._findings.record_many(findings)
                _critical = sum(1 for f in findings if f.severity.value == "critical")
                if _critical:
                    logger.warning(f"[ChapterAgent] ch{ch_num} 审计发现 "
                                   f"{_critical} 条 critical（将触发 rerun）")
                else:
                    logger.info(f"[ChapterAgent] ch{ch_num} 审计完成: "
                                f"{len(findings)} 条 finding（{_critical} critical）")
        except Exception as e:
            logger.warning(f"[ChapterAgent] ch{ch_num} 审计失败（不阻塞）: {e}")

    def _ch2_collect_online_papers(self):
        """ch2 特有：收编在线搜到的论文进 CitationBase。"""
        loop = self.loop
        _online = loop._ref_data.pop("_ch2_online_papers", None)
        _cb = getattr(loop, '_citation_base', None)
        if _online and _cb:
            _added = _cb.add_papers(_online)
            if _added:
                loop._cite_key_map = _cb.cite_key_map
                loop._title_to_key = _cb.title_to_key
                logger.info(f"[ChapterAgent] ch2 收编 {_added} 篇在线论文进 CitationBase")
