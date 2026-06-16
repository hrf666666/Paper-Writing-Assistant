# -*- coding: utf-8 -*-
"""
章节生成公共工具集（v14 第3步）

设计原则：工具集 + 轻量上下文对象，非强制继承的 ABC。
理由：5 章差异远大于共性（ch2 动态子节/ch3 架构图+tuple/ch4 文件扫描+写文件），
强制模板方法会让子类充满 override，比现在更乱。

4 个工具：
- ChapterContext: 从 project_data/ref_data 一次性提取所有公共字段
- generate_section: 统一 try/except call_generation 安全调用
- assemble_chapter: 章节 \section 拼接（平铺 / 带 \subsection）
- run_chapter_template: run_chapterN 外壳模板（makedirs+try/except+fallback+save+log）

顺带统一修复：
- innovation_summary 3 种格式归一
- ch4 漏注入 style/citation 的隐患（工具统一注入）
"""
from __future__ import annotations

import logging
import os
from typing import Any, Callable, Dict, List, Optional

from config.project_config import OUTPUT_DIR, get_article_type_info
from agent.base_orchestrator import BaseOrchestrator

logger = logging.getLogger(__name__)

# 模块级单例（5 章共用，避免各自 new BaseOrchestrator）
_orch: Optional[BaseOrchestrator] = None


def get_orchestrator() -> BaseOrchestrator:
    """获取共享的 BaseOrchestrator 单例。"""
    global _orch
    if _orch is None:
        _orch = BaseOrchestrator(output_dir=OUTPUT_DIR)
    return _orch


class ChapterContext:
    """从 project_data/ref_data 一次性提取章节生成所需的公共字段。

    用法：ctx = ChapterContext(project_data, ref_data, "Introduction", venue_adapter)
    消除每章重复的字段提取 + innovation_summary 构建（当前有 3 种格式变体）。
    """

    def __init__(self, project_data: Dict, ref_data: Dict, chapter_name: str,
                 venue_adapter=None, citation_context: str = "",
                 previous_chapters: Optional[Dict] = None,
                 motivation_thread: str = ""):
        self.chapter_name = chapter_name
        self.project_data = project_data or {}
        self.ref_data = ref_data or {}
        self.venue_adapter = venue_adapter
        self.citation_context = citation_context or ""
        self.previous_chapters = previous_chapters or {}

        # 公共字段提取
        self.innovation_points: List = self.project_data.get("innovation_points", []) or []
        self.experiment_design: Dict = self.project_data.get("experiment_design", {}) or {}
        self.model_architecture: Dict = self.project_data.get("model_architecture", {}) or {}
        self.project_info: Dict = self.project_data.get("project_info", {}) or {}
        self.style_guide: Dict = self.ref_data.get("style_guide", {}) or {}
        self.chapter_org: Dict = self.ref_data.get("chapter_organizations", {}).get(chapter_name, {}) or {}
        self.article_info: Dict = get_article_type_info()
        self.motivation_thread: str = motivation_thread or self.project_data.get("motivation_thread", "") or ""
        self.outline: Dict = self.project_data.get("outline", {}) or {}
        self.content_strategy: Dict = self.project_data.get("content_strategy", {}) or {}

    @property
    def innovation_summary(self) -> str:
        """统一格式的创新点摘要（归一 3 种变体）。

        格式：'1. 创新点名称: 工作内容 — 价值'
        """
        if not self.innovation_points:
            return ""
        lines = []
        for i, inn in enumerate(self.innovation_points, 1):
            if not isinstance(inn, dict):
                continue
            name = inn.get("创新点名称", inn.get("name", ""))
            # v14 修正: 覆盖真实 key 集（创新点工作内容 list / 创新点价值）
            work_raw = inn.get("创新点工作内容", inn.get("工作内容",
                          inn.get("what_it_does", inn.get("description", ""))))
            work = "; ".join(str(w) for w in work_raw) if isinstance(work_raw, list) else (str(work_raw) if work_raw else "")
            value = inn.get("创新点价值", inn.get("价值",
                       inn.get("value", inn.get("why_it_matters", ""))))
            parts = [f"{i}. {name}"]
            if work:
                parts.append(f": {work}")
            if value:
                parts.append(f" — {value}")
            lines.append("".join(parts))
        return "\n".join(lines)

    def style_instruction(self, **kwargs) -> str:
        """构建风格指令（统一入口，避免 ch4 漏传 venue_adapter）。"""
        from agent.base_orchestrator import build_style_instruction
        kw = dict(style_guide=self.style_guide, chapter_org=self.chapter_org,
                  chapter_name=self.chapter_name, venue_adapter=self.venue_adapter)
        kw.update(kwargs)
        return build_style_instruction(**kw)

    def citation_block(self, min_cites: int) -> str:
        """引用上下文 + 引用指令拼接（统一注入，避免 ch4 4.1/4.2 漏注入）。"""
        from agent.base_orchestrator import build_citation_instruction
        parts = []
        if self.citation_context:
            parts.append(self.citation_context)
        parts.append(build_citation_instruction(min_cites=min_cites))
        return "\n".join(parts)

    def prev_content(self, sections: List[str], idx: int, n: int = 1500) -> str:
        """取前一节内容的截断（统一 <previous_content> 逻辑）。"""
        if idx > 0 and idx - 1 < len(sections):
            return (sections[idx - 1] or "")[:n]
        return ""

    # —— 规划产物注入（根治"ch1-5 不读规划"）——

    def planning_block(self) -> str:
        """把已有规划产物（motivation/outline/content_strategy）注入 prompt。

        v14 核心修复：之前 ch2-5 完全不读这些字段，现在 ChapterContext 统一提供。
        各章 generate_* 在 prompt 里加 {ctx.planning_block()} 即可消费。
        """
        blocks = []
        if self.motivation_thread:
            blocks.append(f"<motivation_thread>\n{self.motivation_thread[:2000]}\n</motivation_thread>")
        # outline 的该章契约（若有）
        ch_outline = self.outline.get(str(self._chapter_num()), {})
        if ch_outline and isinstance(ch_outline, dict):
            must_include = ch_outline.get("must_include", [])
            if must_include:
                blocks.append(f"<chapter_focus>必须覆盖: {', '.join(must_include[:5])}</chapter_focus>")
        # content_strategy 的该章策略
        ch_strategy = self.content_strategy.get(str(self._chapter_num()))
        if ch_strategy and isinstance(ch_strategy, dict):
            focus = ch_strategy.get("focus", "")
            avoid = ch_strategy.get("avoid", [])
            if focus:
                blocks.append(f"<content_focus>{focus}</content_focus>")
            if avoid:
                blocks.append(f"<content_avoid>避免: {', '.join(str(a) for a in avoid[:3])}</content_avoid>")
        return "\n".join(blocks) if blocks else ""

    def _chapter_num(self) -> int:
        m = {"Introduction": 1, "Related Work": 2, "Methodology": 3,
             "Experiments": 4, "Conclusion": 5}
        return m.get(self.chapter_name, 0)


# —— 模块级工具函数 ——

def generate_section(prompt: str, log_tag: str = "", on_fail: str = "") -> str:
    """统一 try/except call_generation 安全调用（消除每章重复）。"""
    orch = get_orchestrator()
    try:
        return orch.call_generation(prompt)
    except Exception as e:
        logger.error(f"[{log_tag}] 生成失败: {e}")
        return on_fail


def assemble_chapter(section_title: str, sections: List[str],
                     subsection_titles: Optional[List[str]] = None) -> str:
    """拼接完整章节。

    - 无 subsection_titles：平铺（节之间 \\n\\n）
    - 有 subsection_titles：首节平铺，其余包 \\subsection{title}
    """
    if not sections:
        return f"\\section{{{section_title}}}\n\n(生成失败，请重新运行)"
    parts = [f"\\section{{{section_title}}}"]
    for i, sec in enumerate(sections):
        if subsection_titles and i > 0 and i - 1 < len(subsection_titles):
            parts.append(f"\\subsection{{{subsection_titles[i - 1]}}}")
        parts.append(sec or "")
    return "\n\n".join(parts)


def run_chapter_template(phase_num: int, chapter_name: str,
                          generate_fn: Callable, project_data: Dict, ref_data: Dict,
                          **kwargs) -> str:
    """run_chapterN 外壳模板（消除 5 个 run 函数的重复外壳）。

    makedirs → try generate_fn → except fallback 串 → save_output → log。
    保持 loop.py 契约：模块级函数名 run_chapterN + str 返回值。
    """
    chapter_dir = os.path.join(OUTPUT_DIR, f"chapter{phase_num}")
    os.makedirs(chapter_dir, exist_ok=True)
    try:
        content = generate_fn(project_data, ref_data, **kwargs)
        # ch3 返回 tuple (content, arch_pdf_path)，解包
        if isinstance(content, tuple):
            content = content[0] if content else ""
        if not content:
            content = f"\\section{{{chapter_name}}}\n\n(生成失败，请重新运行)"
    except Exception as e:
        logger.error(f"第{phase_num}章 {chapter_name} 生成失败: {e}", exc_info=True)
        content = f"\\section{{{chapter_name}}}\n\n(生成失败，请重新运行)"
    # 保存
    try:
        orch = get_orchestrator()
        orch.save_output(f"chapter{phase_num}_{chapter_name.lower().replace(' ', '_')}.md",
                         content, subdir=f"chapter{phase_num}")
    except Exception:
        pass
    logger.info(f"第{phase_num}章 {chapter_name} 生成完成")
    return content
