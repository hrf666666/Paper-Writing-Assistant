# -*- coding: utf-8 -*-
"""
Tool: 论文图表生成器 v9.0

用 matplotlib 生成论文所需的：
1. 总体架构图（Architecture Diagram）
2. 模块设计图（Module Diagram）
3. 实验结果表格图（Comparison Table）
4. 消融实验柱状图（Ablation Bar Chart）
5. 性能对比图（Performance Comparison）

保存为 PDF 格式（LaTeX 可用 \\includegraphics 嵌入）
"""

import os
import re
import json
import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# 全局 matplotlib 配置
_MPL_CONFIGURED = False


def _setup_matplotlib():
    global _MPL_CONFIGURED
    if _MPL_CONFIGURED:
        return
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        plt.rcParams.update({
            'font.family': 'serif',
            'font.serif': ['Times New Roman', 'DejaVu Serif'],
            'font.size': 9,
            'axes.labelsize': 10,
            'axes.titlesize': 11,
            'xtick.labelsize': 8,
            'ytick.labelsize': 8,
            'legend.fontsize': 8,
            'figure.dpi': 300,
            'savefig.dpi': 300,
            'savefig.bbox': 'tight',
            'savefig.pad_inches': 0.05,
        })
        _MPL_CONFIGURED = True
    except Exception as e:
        logger.warning(f"[FigureGen] matplotlib 配置失败: {e}")


def generate_architecture_diagram(output_dir: str,
                                   innovation_points: List[Dict] = None) -> str:
    """
    生成总体架构图

    Returns:
        保存的 PDF 文件路径
    """
    _setup_matplotlib()
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

    fig, ax = plt.subplots(1, 1, figsize=(7, 3.5))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 5)
    ax.axis('off')
    ax.set_title('Overall Architecture of the Proposed Method', fontsize=11, fontweight='bold', pad=10)

    # ── 定义模块 ──
    modules = [
        # (x, y, w, h, label, color)
        (0.3, 1.5, 1.8, 1.2, 'Light Field\nInput\n(9×9 Angular)', '#E3F2FD'),
        (2.5, 3.0, 1.8, 1.2, 'Angular\nFrequency\nAnalysis', '#FFF3E0'),
        (2.5, 0.5, 1.8, 1.2, 'Dual-Mask\nModeling\n(Med+Ang)', '#E8F5E9'),
        (4.8, 1.5, 1.8, 1.2, 'Material\nClassification\n(Diff/Spec/Sct)', '#FCE4EC'),
        (7.1, 3.0, 2.5, 1.2, 'Component-Aware\nDepth Estimation\n(EPI/Photo/Scatter)', '#F3E5F5'),
        (7.1, 0.5, 2.5, 1.2, 'Weighted\nFusion &\nRefinement', '#E0F7FA'),
    ]

    for x, y, w, h, label, color in modules:
        box = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.1",
                              facecolor=color, edgecolor='#333333', linewidth=1.0)
        ax.add_patch(box)
        ax.text(x + w/2, y + h/2, label, ha='center', va='center',
                fontsize=7, fontweight='bold', color='#333333')

    # ── 箭头连接 ──
    arrows = [
        ((2.1, 2.1), (2.5, 3.3)),   # Input → Freq Analysis
        ((2.1, 2.1), (2.5, 1.1)),   # Input → Dual Mask
        ((4.3, 3.6), (4.8, 2.1)),   # Freq Analysis → Material
        ((4.3, 1.1), (4.8, 2.1)),   # Dual Mask → Material
        ((6.6, 2.1), (7.1, 3.6)),   # Material → Depth
        ((6.6, 2.1), (7.1, 1.1)),   # Material → Fusion
        ((8.35, 3.0), (8.35, 1.7)), # Depth → Fusion
    ]

    for (x1, y1), (x2, y2) in arrows:
        ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                     arrowprops=dict(arrowstyle='->', color='#666666', lw=1.2))

    # 保存
    figures_dir = os.path.join(output_dir, "figures")
    os.makedirs(figures_dir, exist_ok=True)
    pdf_path = os.path.join(figures_dir, "architecture.pdf")
    fig.savefig(pdf_path, format='pdf', bbox_inches='tight')
    plt.close(fig)

    logger.info(f"[FigureGen] 架构图已保存: {pdf_path}")
    return pdf_path


def generate_module_diagram(output_dir: str,
                             module_name: str,
                             sub_modules: List[str]) -> str:
    """
    生成单个模块的详细设计图

    Args:
        module_name: 模块名称
        sub_modules: 子模块列表

    Returns:
        保存的 PDF 文件路径
    """
    _setup_matplotlib()
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch

    n = len(sub_modules)
    fig_height = max(2.5, 1.0 + n * 0.8)
    fig, ax = plt.subplots(1, 1, figsize=(5, fig_height))
    ax.set_xlim(0, 5)
    ax.set_ylim(0, fig_height)
    ax.axis('off')

    # 标题
    ax.text(2.5, fig_height - 0.3, module_name, ha='center', va='center',
            fontsize=11, fontweight='bold')

    colors = ['#E3F2FD', '#FFF3E0', '#E8F5E9', '#FCE4EC', '#F3E5F5', '#E0F7FA']

    for i, sub in enumerate(sub_modules):
        y = fig_height - 1.0 - i * 0.8
        color = colors[i % len(colors)]
        box = FancyBboxPatch((0.5, y), 4.0, 0.6, boxstyle="round,pad=0.05",
                              facecolor=color, edgecolor='#555', linewidth=0.8)
        ax.add_patch(box)
        ax.text(2.5, y + 0.3, sub, ha='center', va='center', fontsize=8)

        if i > 0:
            ax.annotate('', xy=(2.5, y + 0.6), xytext=(2.5, y + 0.8),
                         arrowprops=dict(arrowstyle='->', color='#888', lw=1.0))

    figures_dir = os.path.join(output_dir, "figures")
    os.makedirs(figures_dir, exist_ok=True)
    safe_name = re.sub(r'[^a-zA-Z0-9]', '_', module_name).lower()
    pdf_path = os.path.join(figures_dir, f"module_{safe_name}.pdf")
    fig.savefig(pdf_path, format='pdf', bbox_inches='tight')
    plt.close(fig)

    logger.info(f"[FigureGen] 模块图已保存: {pdf_path}")
    return pdf_path


def generate_comparison_table(output_dir: str,
                               datasets: List[str],
                               methods: List[str],
                               metrics: List[str],
                               data: List[List[List[float]]],
                               best_method: str = "Ours",
                               caption: str = "Comparison with state-of-the-art methods.") -> str:
    """
    生成实验对比表格图（matplotlib 渲染的三线表）

    Args:
        datasets: 数据集名称列表
        methods: 方法名列表
        metrics: 指标名列表 (如 ["MAE", "RMSE", "BadPix"])
        data: [dataset][method][metric] 三维数组
        best_method: 最佳方法名称（加粗）
        caption: 表格标题

    Returns:
        保存的 PDF 文件路径
    """
    _setup_matplotlib()
    import matplotlib.pyplot as plt
    import numpy as np

    n_datasets = len(datasets)
    n_methods = len(methods)
    n_metrics = len(metrics)

    # 每个数据集一个子表
    fig, axes = plt.subplots(n_datasets, 1, figsize=(7, 1.0 + n_datasets * 1.5))
    if n_datasets == 1:
        axes = [axes]

    for d_idx, (ax, dataset) in enumerate(zip(axes, datasets)):
        ax.axis('off')

        # 构建表格数据
        cell_text = []
        for m_idx, method in enumerate(methods):
            row = []
            for metric_idx in range(n_metrics):
                val = data[d_idx][m_idx][metric_idx]
                if method == best_method:
                    row.append(f"\\textbf{{{val:.3f}}}")
                else:
                    row.append(f"{val:.3f}")
            cell_text.append([method] + row)

        col_labels = ["Method"] + metrics
        table = ax.table(cellText=cell_text, colLabels=col_labels,
                         loc='center', cellLoc='center')
        table.auto_set_font_size(False)
        table.set_fontsize(8)

        # 样式
        for (row, col), cell in table.get_celld().items():
            if row == 0:
                cell.set_facecolor('#E8E8E8')
                cell.set_text_props(fontweight='bold')
            cell.set_edgecolor('#CCCCCC')
            cell.set_height(0.3)

        ax.set_title(f"Dataset: {dataset}", fontsize=9, fontweight='bold', pad=5)

    fig.suptitle(caption, fontsize=10, y=0.98)

    figures_dir = os.path.join(output_dir, "figures")
    os.makedirs(figures_dir, exist_ok=True)
    pdf_path = os.path.join(figures_dir, "comparison_table.pdf")
    fig.savefig(pdf_path, format='pdf', bbox_inches='tight')
    plt.close(fig)

    logger.info(f"[FigureGen] 对比表格已保存: {pdf_path}")
    return pdf_path


def generate_ablation_chart(output_dir: str,
                             ablation_name: str,
                             component_names: List[str],
                             metric_values: List[float],
                             metric_name: str = "MAE",
                             baseline_value: float = None) -> str:
    """
    生成消融实验柱状图

    Args:
        ablation_name: 消融实验名称
        component_names: 组件名称列表
        metric_values: 每个配置的指标值
        metric_name: 指标名称
        baseline_value: 基线值（虚线标注）

    Returns:
        保存的 PDF 文件路径
    """
    _setup_matplotlib()
    import matplotlib.pyplot as plt
    import numpy as np

    fig, ax = plt.subplots(1, 1, figsize=(4.5, 2.5))

    x = np.arange(len(component_names))
    bars = ax.bar(x, metric_values, color='#4A90D9', edgecolor='#333', linewidth=0.5, width=0.6)

    # 高亮最佳结果
    if metric_values:
        best_idx = metric_values.index(min(metric_values))
        bars[best_idx].set_color('#D94A4A')

    # 基线虚线
    if baseline_value is not None:
        ax.axhline(y=baseline_value, color='#888', linestyle='--', linewidth=0.8, label=f'Baseline ({baseline_value:.3f})')

    ax.set_xticks(x)
    ax.set_xticklabels(component_names, rotation=30, ha='right', fontsize=7)
    ax.set_ylabel(metric_name, fontsize=9)
    ax.set_title(f'Ablation: {ablation_name}', fontsize=10, fontweight='bold')

    # 在柱顶标注数值
    for bar, val in zip(bars, metric_values):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.002,
                f'{val:.3f}', ha='center', va='bottom', fontsize=6)

    if baseline_value is not None:
        ax.legend(fontsize=7, loc='upper right')

    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    figures_dir = os.path.join(output_dir, "figures")
    os.makedirs(figures_dir, exist_ok=True)
    safe_name = re.sub(r'[^a-zA-Z0-9]', '_', ablation_name).lower()
    pdf_path = os.path.join(figures_dir, f"ablation_{safe_name}.pdf")
    fig.savefig(pdf_path, format='pdf', bbox_inches='tight')
    plt.close(fig)

    logger.info(f"[FigureGen] 消融图已保存: {pdf_path}")
    return pdf_path


def generate_performance_chart(output_dir: str,
                                method_names: List[str],
                                dataset_names: List[str],
                                mae_values: List[List[float]],
                                title: str = "Performance Comparison") -> str:
    """
    生成多数据集性能对比分组柱状图

    Args:
        method_names: 方法名列表
        dataset_names: 数据集列表
        mae_values: [method][dataset] MAE 值
        title: 图标题

    Returns:
        保存的 PDF 文件路径
    """
    _setup_matplotlib()
    import matplotlib.pyplot as plt
    import numpy as np

    n_methods = len(method_names)
    n_datasets = len(dataset_names)

    fig, ax = plt.subplots(1, 1, figsize=(6, 3))

    x = np.arange(n_methods)
    width = 0.8 / n_datasets
    colors = plt.cm.Set2(np.linspace(0, 1, n_datasets))

    for d_idx, (dataset, color) in enumerate(zip(dataset_names, colors)):
        values = [mae_values[m][d_idx] for m in range(n_methods)]
        offset = (d_idx - n_datasets/2 + 0.5) * width
        bars = ax.bar(x + offset, values, width, label=dataset,
                       color=color, edgecolor='#333', linewidth=0.3)

    ax.set_xticks(x)
    ax.set_xticklabels(method_names, rotation=30, ha='right', fontsize=7)
    ax.set_ylabel('MAE', fontsize=9)
    ax.set_title(title, fontsize=10, fontweight='bold')
    ax.legend(fontsize=7, loc='upper left', ncol=2)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    figures_dir = os.path.join(output_dir, "figures")
    os.makedirs(figures_dir, exist_ok=True)
    pdf_path = os.path.join(figures_dir, "performance_comparison.pdf")
    fig.savefig(pdf_path, format='pdf', bbox_inches='tight')
    plt.close(fig)

    logger.info(f"[FigureGen] 性能对比图已保存: {pdf_path}")
    return pdf_path


# ═══════════════════════════════════════════════════════════════
# 主入口：从项目数据自动生成所有图表
# ═══════════════════════════════════════════════════════════════
def run_figure_generator(output_dir: str,
                          project_data: Dict = None,
                          experiment_data: Dict = None) -> Dict:
    """
    自动生成论文所需的所有图表

    Args:
        output_dir: 输出目录
        project_data: 项目数据（含创新点、架构等）
        experiment_data: 实验数据（含消融结果等）

    Returns:
        生成的图表路径映射
    """
    results = {}

    # 1. 总体架构图
    try:
        innovations = []
        if project_data:
            innovations = project_data.get("innovation_points", [])
        arch_path = generate_architecture_diagram(output_dir, innovations)
        results["architecture"] = arch_path
    except Exception as e:
        logger.warning(f"[FigureGen] 架构图生成失败: {e}")

    # 2. 模块设计图
    if project_data:
        arch = project_data.get("model_architecture", {})
        modules = arch.get("modules", arch.get("核心模块", []))
        if isinstance(modules, list):
            for i, mod in enumerate(modules[:3]):
                try:
                    if isinstance(mod, dict):
                        name = mod.get("name", mod.get("模块名", f"Module_{i+1}"))
                        subs = mod.get("sub_modules", mod.get("子模块", []))
                        if isinstance(subs, list) and subs:
                            path = generate_module_diagram(output_dir, name, subs)
                            results[f"module_{i+1}"] = path
                except Exception as e:
                    logger.warning(f"[FigureGen] 模块图 {i+1} 生成失败: {e}")

    # 3. 性能对比图
    try:
        # 尝试从实验数据生成
        if experiment_data:
            datasets = experiment_data.get("datasets", ["HCI", "Stanford", "Urban"])
            methods = experiment_data.get("methods", ["EPINet", "LFNet", "Ours"])
            mae_data = experiment_data.get("mae_values", None)
            if mae_data:
                perf_path = generate_performance_chart(
                    output_dir, methods, datasets, mae_data)
                results["performance"] = perf_path
    except Exception as e:
        logger.warning(f"[FigureGen] 性能对比图生成失败: {e}")

    # 4. 消融实验图
    try:
        ablation_path = os.path.join(output_dir, "ablation_results.json")
        if os.path.exists(ablation_path):
            with open(ablation_path, "r", encoding="utf-8") as f:
                abl_data = json.load(f)
            experiments = abl_data.get("experiments", [])
            for i, exp in enumerate(experiments[:3]):
                name = exp.get("name", f"Ablation_{i+1}")
                configs = exp.get("configs", [])
                values = exp.get("values", [])
                baseline = exp.get("baseline_value", None)
                if configs and values:
                    path = generate_ablation_chart(
                        output_dir, name, configs, values,
                        metric_name=exp.get("metric", "MAE"),
                        baseline_value=baseline,
                    )
                    results[f"ablation_{i+1}"] = path
    except Exception as e:
        logger.warning(f"[FigureGen] 消融图生成失败: {e}")

    logger.info(f"[FigureGen] 生成完成: {len(results)} 个图表")
    return results


def generate_latex_figure_includes(output_dir: str) -> str:
    """
    生成所有图表的 LaTeX \\includegraphics 代码片段

    Returns:
        LaTeX 代码字符串
    """
    figures_dir = os.path.join(output_dir, "figures")
    if not os.path.exists(figures_dir):
        return ""

    latex_parts = []
    fig_counter = 0

    for fname in sorted(os.listdir(figures_dir)):
        if not fname.endswith('.pdf'):
            continue
        fig_counter += 1
        name = fname.replace('.pdf', '').replace('_', ' ').title()

        if 'architecture' in fname.lower():
            latex_parts.append(f"""
\\begin{{figure}}[!t]
\\centering
\\includegraphics[width=\\columnwidth]{{figures/{fname.replace('.pdf', '')}}}
\\caption{{Overall architecture of the proposed dual-mask unified light field depth estimation framework. The system integrates angular frequency analysis with dual-mask modeling for component-aware depth estimation.}}
\\label{{fig:architecture}}
\\end{{figure}}
""")
        elif 'module' in fname.lower():
            latex_parts.append(f"""
\\begin{{figure}}[!t]
\\centering
\\includegraphics[width=0.9\\columnwidth]{{figures/{fname.replace('.pdf', '')}}}
\\caption{{Detailed design of the {name} module.}}
\\label{{fig:{fname.replace('.pdf', '')}}}
\\end{{figure}}
""")
        elif 'ablation' in fname.lower():
            latex_parts.append(f"""
\\begin{{figure}}[!t]
\\centering
\\includegraphics[width=0.85\\columnwidth]{{figures/{fname.replace('.pdf', '')}}}
\\caption{{Ablation study results: {name}.}}
\\label{{fig:{fname.replace('.pdf', '')}}}
\\end{{figure}}
""")
        elif 'comparison' in fname.lower() or 'performance' in fname.lower():
            latex_parts.append(f"""
\\begin{{figure}}[!t]
\\centering
\\includegraphics[width=\\columnwidth]{{figures/{fname.replace('.pdf', '')}}}
\\caption{{Performance comparison across datasets.}}
\\label{{fig:{fname.replace('.pdf', '')}}}
\\end{{figure}}
""")

    return '\n'.join(latex_parts)
