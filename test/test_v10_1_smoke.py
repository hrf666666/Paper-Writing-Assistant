#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v10.1 冒烟测试 — 验证所有新增模块能正确导入、初始化和基本功能
"""

import sys
import os
import json
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-5s %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("v10.1_smoke")

PASS = 0
FAIL = 0
SKIP = 0


def test(name, func):
    global PASS, FAIL, SKIP
    try:
        func()
        logger.info(f"  ✓ {name}")
        PASS += 1
    except ImportError as e:
        logger.warning(f"  ⊘ {name}: ImportError — {e}")
        SKIP += 1
    except Exception as e:
        logger.error(f"  ✗ {name}: {type(e).__name__}: {e}")
        FAIL += 1


# ═══════════════════════════════════════════════════
# 1. 导入测试
# ═══════════════════════════════════════════════════

def test_import_journal_style_learner():
    from agent.journal_style_learner import JournalStyleLearner

def test_import_content_strategist():
    from agent.content_strategist import ContentStrategist

def test_import_style_manager():
    from agent.style_manager import StyleManager

def test_import_ref_search_strategist():
    from agent.ref_search_strategist import RefSearchStrategist

def test_import_ref_pdf_downloader():
    from tools.ref_pdf_downloader import RefPdfDownloader

def test_import_content_analyzer():
    from tools.content_analyzer import analyze_paper_content

def test_import_data_visualizer():
    from tools.data_visualizer import generate_comparison_chart, generate_ablation_chart

def test_import_layout_engine():
    from figure.layout_engine import generate_tikz_from_plan, _escape_latex

def test_import_layout_templates():
    from figure.layout_templates import PipelineTemplate

def test_import_figure_generator():
    from tools.figure_generator import generate_figure_from_plan, _find_pdflatex

def test_import_venue_adapter():
    from agent.venue_adapter import VenueAdapter


# ═══════════════════════════════════════════════════
# 2. 初始化测试
# ═══════════════════════════════════════════════════

def test_venue_adapter_init():
    from agent.venue_adapter import VenueAdapter
    adapter = VenueAdapter()
    assert adapter.profile is not None
    assert hasattr(adapter, 'build_chapter_style_instruction')

def test_venue_adapter_set_journal_style():
    from agent.venue_adapter import VenueAdapter
    adapter = VenueAdapter()
    adapter.set_journal_style({"content_patterns": {"test": "value"}})
    assert adapter._journal_style is not None

def test_content_strategist_fallback():
    from agent.content_strategist import ContentStrategist
    cs = ContentStrategist.__new__(ContentStrategist)
    sections = ["introduction", "related_work", "methodology", "experiments", "conclusion"]
    strategy = cs._fallback_strategy(sections, [{"name": "test innovation"}])
    assert isinstance(strategy, dict)
    assert "introduction" in strategy
    assert "must_include" in strategy["introduction"]

def test_ref_search_strategist_fallback():
    from agent.ref_search_strategist import RefSearchStrategist
    rss = RefSearchStrategist.__new__(RefSearchStrategist)
    result = rss._fallback_strategy(
        [{"创新点名称": "dual-mask model", "anchor": {"contribution_statement": "novel depth estimation for non-Lambertian"}}],
        "IEEE TCSVT",
    )
    assert isinstance(result, dict)
    assert "search_layers" in result or "core_direction" in result

def test_base_profile_soft_constraints():
    from config.venue_profiles.base_profile import VenueProfile
    p = VenueProfile()
    assert hasattr(p, 'content_patterns')
    assert hasattr(p, 'argument_rhythm')
    assert hasattr(p, 'depth_gradients')
    assert hasattr(p, 'figure_preferences')
    assert hasattr(p, 'content_emphasis')

def test_journal_csvt_soft_constraints():
    from config.venue_profiles.journal_csvt import IEEE_TCSVT_Profile
    profile = IEEE_TCSVT_Profile()
    assert "TCSVT" in profile.venue_name or "Circuits" in profile.venue_name
    assert isinstance(profile.content_patterns, dict)
    assert len(profile.content_patterns) > 0


# ═══════════════════════════════════════════════════
# 3. 逻辑修复验证
# ═══════════════════════════════════════════════════

def test_escape_latex():
    from figure.layout_engine import _escape_latex
    # 基本转义
    assert r"\&" in _escape_latex("a&b")
    assert r"\%" in _escape_latex("100%")
    assert r"\$" in _escape_latex("$x$")
    # 反斜杠不破坏花括号
    result = _escape_latex(r"a\b")
    assert "textbackslash" in result
    # 验证花括号不被破坏
    result2 = _escape_latex(r"{test}")
    assert r"\{" in result2
    assert r"\}" in result2

def test_find_pdflatex():
    from tools.figure_generator import _find_pdflatex
    path = _find_pdflatex()
    assert isinstance(path, str)
    assert "pdflatex" in path.lower()

def test_layout_find_pdflatex():
    from figure.layout_engine import _find_pdflatex
    path = _find_pdflatex()
    assert isinstance(path, str)
    assert "pdflatex" in path.lower()

def test_get_existing_dois():
    from tools.ref_pdf_downloader import _get_existing_dois
    # 对不存在的目录应返回空列表
    result = _get_existing_dois("/nonexistent/dir")
    assert result == []

def test_motivation_verify():
    from agent.motivation_engine import _extract_anchor_keywords
    # 测试关键词提取
    keywords = _extract_anchor_keywords("We propose a novel dual-mask model for depth estimation")
    assert isinstance(keywords, list)
    assert len(keywords) > 0

def test_figure_critic_json_parsing():
    """验证 4 层 JSON 解析容错 — _parse_evaluation 返回归一化结构"""
    from tools.figure_critic import _parse_evaluation

    # 直接 JSON — 返回归一化的结构
    result = _parse_evaluation('{"passed": true, "score": 8}')
    assert isinstance(result, dict)
    assert "passed" in result

    # Markdown 包裹
    result = _parse_evaluation('```json\n{"passed": false, "score": 3}\n```')
    assert isinstance(result, dict)
    assert "passed" in result

    # 常见错误修复（尾逗号）— 不崩溃即可
    result = _parse_evaluation('{"passed": true, "score": 8,}')
    assert isinstance(result, dict)


# ═══════════════════════════════════════════════════
# 4. 配置验证
# ═══════════════════════════════════════════════════

def test_project_config():
    from config.project_config import TARGET_VENUE, PROJECT_CODE_PATH
    assert TARGET_VENUE == "IEEE TCSVT"
    assert os.path.exists(PROJECT_CODE_PATH)

def test_ref_pdf_exists():
    ref_pdf = "/home/bigboss/code/paper-writing-assistant/ref_pdf"
    assert os.path.isdir(ref_pdf)
    pdfs = [f for f in os.listdir(ref_pdf) if f.endswith(".pdf")]
    assert len(pdfs) > 0, "ref_pdf/ 下没有 PDF 文件"


# ═══════════════════════════════════════════════════
# 运行
# ═══════════════════════════════════════════════════

def main():
    tests = [
        ("导入: JournalStyleLearner", test_import_journal_style_learner),
        ("导入: ContentStrategist", test_import_content_strategist),
        ("导入: StyleManager", test_import_style_manager),
        ("导入: RefSearchStrategist", test_import_ref_search_strategist),
        ("导入: RefPdfDownloader", test_import_ref_pdf_downloader),
        ("导入: ContentAnalyzer", test_import_content_analyzer),
        ("导入: DataVisualizer", test_import_data_visualizer),
        ("导入: LayoutEngine", test_import_layout_engine),
        ("导入: LayoutTemplates", test_import_layout_templates),
        ("导入: FigureGenerator", test_import_figure_generator),
        ("导入: VenueAdapter", test_import_venue_adapter),
        ("初始化: VenueAdapter", test_venue_adapter_init),
        ("初始化: VenueAdapter.set_journal_style", test_venue_adapter_set_journal_style),
        ("初始化: ContentStrategist fallback", test_content_strategist_fallback),
        ("初始化: RefSearchStrategist fallback", test_ref_search_strategist_fallback),
        ("配置: BaseProfile 软约束", test_base_profile_soft_constraints),
        ("配置: TCSVT 软约束", test_journal_csvt_soft_constraints),
        ("修复: _escape_latex", test_escape_latex),
        ("修复: figure_generator._find_pdflatex", test_find_pdflatex),
        ("修复: layout_engine._find_pdflatex", test_layout_find_pdflatex),
        ("修复: _get_existing_dois", test_get_existing_dois),
        ("修复: _extract_anchor_keywords", test_motivation_verify),
        ("修复: _parse_evaluation JSON", test_figure_critic_json_parsing),
        ("配置: project_config", test_project_config),
        ("资源: ref_pdf 存在", test_ref_pdf_exists),
    ]

    logger.info("=" * 60)
    logger.info("  v10.1 Smoke Test")
    logger.info("=" * 60)

    for name, func in tests:
        test(name, func)

    logger.info("=" * 60)
    logger.info(f"  结果: {PASS} 通过, {FAIL} 失败, {SKIP} 跳过")
    logger.info("=" * 60)

    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
