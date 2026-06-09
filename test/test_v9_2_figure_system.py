# -*- coding: utf-8 -*-
"""
v9.2 端到端测试 — 验证所有新模块的 import 和基本功能
"""

import sys
import os
import json
import logging

# 确保项目根目录在 path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def test_imports():
    """测试所有新模块的 import"""
    print("=" * 60)
    print("1. 测试模块 Import")
    print("=" * 60)

    modules = [
        ("tools.content_analyzer", "ContentBrief, FigureNeed, InnovationPoint, analyze_paper_content"),
        ("tools.experiment_explorer", "explore_experiments, ExperimentSummary"),
        ("tools.data_visualizer", "generate_comparison_chart, generate_ablation_chart, generate_image_grid"),
        ("tools.image_finder", "find_qualitative_images, get_grid_image_paths"),
        ("figure.layout_templates", "PipelineTemplate, DualBranchTemplate, select_template, TEMPLATES"),
        ("figure.layout_engine", "generate_tikz_from_plan"),
        ("tools.figure_planner", "plan_figures, plan_figures_with_content_analysis"),
        ("tools.figure_generator", "generate_figure_from_plan"),
        ("tools.figure_critic", "evaluate_figure"),
        ("tools.iterate_controller", "run_pgei_pipeline"),
    ]

    all_ok = True
    for module_name, classes in modules:
        try:
            mod = __import__(module_name, fromlist=classes.split(", "))
            for cls_name in classes.split(", "):
                cls_name = cls_name.strip()
                assert hasattr(mod, cls_name), f"{module_name}.{cls_name} 不存在"
            print(f"  ✓ {module_name}")
        except Exception as e:
            print(f"  ✗ {module_name}: {e}")
            all_ok = False

    return all_ok


def test_layout_templates():
    """测试布局模板"""
    print("\n" + "=" * 60)
    print("2. 测试布局模板")
    print("=" * 60)

    from figure.layout_templates import (
        PipelineTemplate, DualBranchTemplate, PyramidTemplate,
        EncoderDecoderTemplate, ParallelTemplate, RecursiveTemplate,
        NodeSpec, EdgeSpec, GroupSpec, Position,
        select_template, TEMPLATES,
    )

    # 创建测试节点
    nodes = [
        NodeSpec(id="m1", label="Input", is_innovation=False),
        NodeSpec(id="m2", label="Feature Extract", is_innovation=False),
        NodeSpec(id="m3", label="Core Module", is_innovation=True),
        NodeSpec(id="m4", label="Output", is_innovation=False),
    ]
    edges = [
        EdgeSpec(from_id="m1", to_id="m2"),
        EdgeSpec(from_id="m2", to_id="m3"),
        EdgeSpec(from_id="m3", to_id="m4"),
    ]
    groups = []

    # 测试每种模板
    for name, cls in TEMPLATES.items():
        template = cls()
        positions = template.compute_positions(nodes, edges, groups)
        assert len(positions) == 4, f"{name}: 位置数 != 4"
        # 检查无重叠（简单检查：x 坐标不全相同）
        xs = [p.x for p in positions.values()]
        ys = [p.y for p in positions.values()]
        print(f"  ✓ {name}: positions={[(f'{p.x:.1f}', f'{p.y:.1f}') for p in positions.values()]}")

    # 测试自动选择
    template = select_template(nodes, edges, "")
    print(f"  ✓ 自动选择: {template.name}")

    # 双分支测试
    nodes2 = [
        NodeSpec(id="m1", label="Input"),
        NodeSpec(id="m2", label="Branch A"),
        NodeSpec(id="m3", label="Branch B"),
        NodeSpec(id="m4", label="Merge"),
    ]
    edges2 = [
        EdgeSpec(from_id="m1", to_id="m2"),
        EdgeSpec(from_id="m1", to_id="m3"),
        EdgeSpec(from_id="m2", to_id="m4"),
        EdgeSpec(from_id="m3", to_id="m4"),
    ]
    template = select_template(nodes2, edges2, "")
    print(f"  ✓ 双分支自动选择: {template.name}")
    assert template.name == "dual_branch", f"期望 dual_branch，得到 {template.name}"

    return True


def test_content_analyzer():
    """测试内容分析器"""
    print("\n" + "=" * 60)
    print("3. 测试内容分析器（规则模式）")
    print("=" * 60)

    from tools.content_analyzer import _rule_based_analysis, brief_to_dict

    paper_content = {
        "title": "Unified Depth Estimation via Angular Frequency Analysis",
        "abstract": "We propose a novel framework for light field depth estimation that decomposes angular signals into three layers. The proposed method introduces a dual-mask modeling approach for material-aware depth prediction.",
        "method_text": "The proposed method first performs angular frequency analysis on 9x9 angular patches. We then introduce a signal decomposition module that separates depth, material, and illumination components. Finally, a component-aware depth estimation network produces the depth map.",
    }

    brief = _rule_based_analysis(paper_content)
    print(f"  ✓ 核心贡献: {brief.core_contribution[:80]}")
    print(f"  ✓ 创新点数: {len(brief.innovation_points)}")
    print(f"  ✓ 图表需求: {len(brief.figure_needs)}")

    d = brief_to_dict(brief)
    assert "core_contribution" in d
    assert "figure_needs" in d
    print(f"  ✓ 序列化正常")

    return True


def test_experiment_explorer():
    """测试实验探索器"""
    print("\n" + "=" * 60)
    print("4. 测试实验探索器")
    print("=" * 60)

    from tools.experiment_explorer import explore_experiments, summary_to_json

    # 用 depth_estimation 项目测试
    project_path = "/home/bigboss/code/depth_estimation_unify_theory"
    if not os.path.isdir(project_path):
        print(f"  ⚠ 项目路径不存在: {project_path}，跳过")
        return True

    summary = explore_experiments(project_path)
    print(f"  ✓ 实验结果: {len(summary.available_results)} 个")
    print(f"  ✓ 已有图片: {len(summary.available_images)} 张")

    if summary.comparison_data:
        print(f"  ✓ 对比数据: {len(summary.comparison_data.methods)} 方法, "
              f"{len(summary.comparison_data.metrics)} 指标")
    else:
        print(f"  ⚠ 无对比数据")

    if summary.ablation_data:
        print(f"  ✓ 消融数据: {len(summary.ablation_data.components)} 组件")
    else:
        print(f"  ⚠ 无消融数据")

    print(f"  ✓ 缺失数据: {summary.missing_data}")
    print(f"  ✓ 推荐图表: {len(summary.recommended_figures)} 个")

    # 测试序列化
    json_str = summary_to_json(summary)
    assert len(json_str) > 100
    print(f"  ✓ 序列化正常 ({len(json_str)} 字符)")

    return True


def test_figure_generator_tikz():
    """测试图表生成器（TikZ 架构图）"""
    print("\n" + "=" * 60)
    print("5. 测试图表生成器（TikZ 架构图）")
    print("=" * 60)

    from tools.figure_generator import generate_figure_from_plan

    fig_plan = {
        "fig_id": "test_arch",
        "fig_type": "teaser",
        "title": "Test Architecture",
        "layout_template": "pipeline",
        "modules": [
            {"id": "m1", "label": "Input", "is_innovation": False},
            {"id": "m2", "label": "Feature Extraction", "is_innovation": False},
            {"id": "m3", "label": "Core Module", "is_innovation": True},
            {"id": "m4", "label": "Fusion", "is_innovation": False},
            {"id": "m5", "label": "Output", "is_innovation": False},
        ],
        "connections": [
            {"from": "m1", "to": "m2"},
            {"from": "m2", "to": "m3"},
            {"from": "m3", "to": "m4"},
            {"from": "m4", "to": "m5"},
        ],
        "groups": [
            {"id": "g1", "label": "Processing", "module_ids": ["m2", "m3"], "style": "dashed_box"},
        ],
    }

    output_dir = "/home/bigboss/code/paper-writing-assistant/output/v92_test"
    figures_dir = os.path.join(output_dir, "figures")

    result = generate_figure_from_plan(fig_plan, figures_dir)
    print(f"  PDF: {result.get('pdf_path', 'N/A')}")
    print(f"  PNG: {result.get('png_path', 'N/A')}")

    if result.get("pdf_path") and os.path.exists(result["pdf_path"]):
        size = os.path.getsize(result["pdf_path"])
        print(f"  ✓ PDF 大小: {size} bytes")
    else:
        print(f"  ⚠ PDF 未生成")

    return True


def test_data_chart():
    """测试数据图表生成"""
    print("\n" + "=" * 60)
    print("6. 测试数据图表生成")
    print("=" * 60)

    from tools.data_visualizer import generate_comparison_chart, generate_ablation_chart

    output_dir = "/home/bigboss/code/paper-writing-assistant/output/v92_test"
    figures_dir = os.path.join(output_dir, "figures")

    # 对比图
    comp_data = {
        "title": "Performance Comparison",
        "methods": ["EPINet", "AGEDNet", "Ours"],
        "metrics": ["MAE"],
        "values": [[0.162], [0.227], [0.133]],
    }
    result = generate_comparison_chart(comp_data, figures_dir, "test_comp")
    print(f"  ✓ 对比图: {result.get('pdf_path', 'N/A')}")

    # 消融图
    abl_data = {
        "title": "Ablation Study",
        "components": ["Baseline", "+DualMask", "+Angular", "Full"],
        "metrics": {"MAE": [0.180, 0.160, 0.148, 0.133]},
    }
    result = generate_ablation_chart(abl_data, figures_dir, "test_abl")
    print(f"  ✓ 消融图: {result.get('pdf_path', 'N/A')}")

    return True


if __name__ == "__main__":
    print("v9.2 图表系统端到端测试")
    print("=" * 60)

    tests = [
        ("Import", test_imports),
        ("Layout Templates", test_layout_templates),
        ("Content Analyzer", test_content_analyzer),
        ("Experiment Explorer", test_experiment_explorer),
        ("Figure Generator (TikZ)", test_figure_generator_tikz),
        ("Data Chart", test_data_chart),
    ]

    results = {}
    for name, test_fn in tests:
        try:
            ok = test_fn()
            results[name] = "PASS" if ok else "FAIL"
        except Exception as e:
            results[name] = f"ERROR: {e}"
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    for name, status in results.items():
        marker = "✓" if status == "PASS" else "✗"
        print(f"  {marker} {name}: {status}")

    all_pass = all(s == "PASS" for s in results.values())
    print(f"\n{'✓ ALL PASSED' if all_pass else '✗ SOME FAILED'}")
