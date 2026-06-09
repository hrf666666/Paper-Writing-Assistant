# -*- coding: utf-8 -*-
"""
Tool: 数据可视化器 v9.2 (Data Visualizer)

基于真实实验数据生成 matplotlib 图表。
接收 ExperimentSummary 的数据，自动选择可视化类型。

支持：
- 分组柱状图（SOTA 对比）
- 单柱状图（消融实验）
- 图片网格（定性对比）
"""

import json
import logging
import os
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def generate_comparison_chart(
    comparison_data: Dict,
    figures_dir: str,
    fig_id: str = "fig_comparison",
    venue: str = "IEEE TCSVT",
) -> Dict:
    """
    生成 SOTA 对比分组柱状图。

    Args:
        comparison_data: ComparisonData 的 dict 形式
        figures_dir: 输出目录
        fig_id: 图表 ID
        venue: 目标 venue

    Returns:
        {"pdf_path": "...", "png_path": "..."}
    """
    from figure.style_templates import get_style, get_figure_size

    style = get_style(venue)
    fig_size = get_figure_size(style, "double")

    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np

    methods = comparison_data.get("methods", [])
    metrics = comparison_data.get("metrics", ["MAE"])
    values = comparison_data.get("values", [])

    if not methods or not values:
        logger.warning(f"[DataViz] 无对比数据，跳过: {fig_id}")
        return _empty_result(figures_dir, fig_id)

    n_methods = len(methods)
    n_metrics = len(metrics)
    x = np.arange(n_methods)
    width = 0.8 / max(n_metrics, 1)

    fig, ax = plt.subplots(figsize=fig_size)

    colors_list = style["colors"]["comparison"]
    for m_idx, metric in enumerate(metrics):
        vals = []
        for row in values:
            if m_idx < len(row):
                vals.append(row[m_idx])
            else:
                vals.append(0)

        offset = (m_idx - n_metrics / 2 + 0.5) * width
        color = colors_list[m_idx % len(colors_list)]
        bars = ax.bar(x + offset, vals, width, label=metric,
                      color=color, edgecolor=style["colors"]["border"], linewidth=0.3)

        # 柱顶标注
        for bar, val in zip(bars, vals):
            if val > 0:
                ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(),
                        f'{val:.3f}', ha='center', va='bottom',
                        fontsize=style["font_sizes"]["annotation"] - 1, rotation=45)

    # 高亮最佳方法
    if n_metrics > 0:
        main_vals = [row[0] if row else 999 for row in values]
        best_idx = main_vals.index(min(main_vals))
        ax.axvspan(best_idx - 0.4, best_idx + 0.4, alpha=0.08,
                    color=style["colors"]["accent"], zorder=0)

    ax.set_xticks(x)
    short_methods = [m[:15] + "..." if len(m) > 15 else m for m in methods]
    ax.set_xticklabels(short_methods, rotation=30, ha='right',
                        fontsize=style["font_sizes"]["tick_label"])
    ax.set_ylabel(metrics[0] if metrics else "Score",
                  fontsize=style["font_sizes"]["axis_label"])
    ax.legend(fontsize=style["font_sizes"]["legend"], loc='upper right')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    title = comparison_data.get("title", "Performance Comparison")
    ax.set_title(title, fontsize=style["font_sizes"]["title"],
                 fontweight='bold', pad=10)

    fig.tight_layout(pad=0.3)

    return _save_figure(fig, figures_dir, fig_id)


def generate_ablation_chart(
    ablation_data: Dict,
    figures_dir: str,
    fig_id: str = "fig_ablation",
    venue: str = "IEEE TCSVT",
) -> Dict:
    """
    生成消融实验柱状图。

    Args:
        ablation_data: AblationData 的 dict 形式
        figures_dir: 输出目录
        fig_id: 图表 ID
        venue: 目标 venue

    Returns:
        {"pdf_path": "...", "png_path": "..."}
    """
    from figure.style_templates import get_style, get_figure_size

    style = get_style(venue)
    fig_size = get_figure_size(style, "single")

    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np

    components = ablation_data.get("components", [])
    metrics = ablation_data.get("metrics", {})

    if not components or not metrics:
        logger.warning(f"[DataViz] 无消融数据，跳过: {fig_id}")
        return _empty_result(figures_dir, fig_id)

    metric_name = next(iter(metrics))
    values = metrics[metric_name]

    n = len(components)
    x = np.arange(n)

    fig, ax = plt.subplots(figsize=fig_size)

    best_idx = values.index(min(values)) if values else -1
    colors = []
    for i in range(n):
        if i == best_idx:
            colors.append(style["colors"]["accent"])
        else:
            alpha_frac = 0.3 + 0.5 * (i / max(n - 1, 1))
            colors.append(style["colors"]["primary"] if i > 0 else style["colors"]["primary_light"])

    bars = ax.bar(x, values, color=colors,
                  edgecolor=style["colors"]["border"], linewidth=0.5,
                  width=style["chart"]["bar_width"])

    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.001,
                f'{val:.4f}', ha='center', va='bottom',
                fontsize=style["font_sizes"]["annotation"])

    if best_idx >= 0:
        ax.annotate('Best', xy=(x[best_idx], values[best_idx]),
                     xytext=(x[best_idx], values[best_idx] + max(values) * 0.1),
                     ha='center', fontsize=style["font_sizes"]["annotation"],
                     color=style["colors"]["accent"], fontweight='bold',
                     arrowprops=dict(arrowstyle='->', color=style["colors"]["accent"]))

    ax.set_xticks(x)
    short_labels = [c[:20] + "..." if len(c) > 20 else c for c in components]
    ax.set_xticklabels(short_labels, rotation=30, ha='right',
                        fontsize=style["font_sizes"]["tick_label"])
    ax.set_ylabel(metric_name, fontsize=style["font_sizes"]["axis_label"])
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    title = ablation_data.get("title", "Ablation Study")
    ax.set_title(title, fontsize=style["font_sizes"]["title"],
                 fontweight='bold', pad=10)

    fig.tight_layout(pad=0.3)

    return _save_figure(fig, figures_dir, fig_id)


def generate_image_grid(
    image_paths: List[str],
    figures_dir: str,
    fig_id: str = "fig_qualitative",
    venue: str = "IEEE TCSVT",
    n_cols: int = 3,
    titles: List[str] = None,
) -> Dict:
    """
    将多张图片组合成对比网格图。

    Args:
        image_paths: 图片路径列表
        figures_dir: 输出目录
        fig_id: 图表 ID
        venue: 目标 venue
        n_cols: 列数
        titles: 每张子图的标题

    Returns:
        {"pdf_path": "...", "png_path": "..."}
    """
    from figure.style_templates import get_style, get_figure_size

    style = get_style(venue)
    fig_size = get_figure_size(style, "double")

    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.image as mpimg

    valid_paths = [p for p in image_paths if os.path.isfile(p)]
    if not valid_paths:
        logger.warning(f"[DataViz] 无有效图片，跳过: {fig_id}")
        return _empty_result(figures_dir, fig_id)

    n_images = len(valid_paths)
    n_rows = (n_images + n_cols - 1) // n_cols

    fig, axes = plt.subplots(n_rows, n_cols,
                              figsize=(fig_size[0], fig_size[0] * n_rows / n_cols * 0.8))

    if n_rows == 1 and n_cols == 1:
        axes = [[axes]]
    elif n_rows == 1:
        axes = [axes]
    elif n_cols == 1:
        axes = [[ax] for ax in axes]

    for idx in range(n_rows * n_cols):
        row = idx // n_cols
        col = idx % n_cols
        ax = axes[row][col]

        if idx < n_images:
            try:
                img = mpimg.imread(valid_paths[idx])
                ax.imshow(img)
            except Exception as e:
                logger.warning(f"[DataViz] 图片读取失败 {valid_paths[idx]}: {e}")
                ax.text(0.5, 0.5, "Image\nNot Found", ha='center', va='center',
                        fontsize=9, color='gray', transform=ax.transAxes)

            if titles and idx < len(titles):
                ax.set_title(titles[idx], fontsize=style["font_sizes"]["tick_label"],
                             fontweight='bold', pad=3)

        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_edgecolor(style["colors"]["border"])
            spine.set_linewidth(0.3)

    fig.tight_layout(pad=0.3, h_pad=0.3, w_pad=0.3)

    return _save_figure(fig, figures_dir, fig_id)


# ═══════════════════════════════════════════════════════════════
# 内部工具
# ═══════════════════════════════════════════════════════════════

def _save_figure(fig, figures_dir: str, fig_id: str) -> Dict:
    """保存图表为 PDF + PNG"""
    import matplotlib.pyplot as _plt
    os.makedirs(figures_dir, exist_ok=True)

    pdf_path = os.path.join(figures_dir, f"{fig_id}.pdf")
    png_path = os.path.join(figures_dir, f"{fig_id}.png")

    fig.savefig(pdf_path, format='pdf', bbox_inches='tight', pad_inches=0.05,
                facecolor='white')
    fig.savefig(png_path, format='png', bbox_inches='tight', pad_inches=0.05,
                dpi=200, facecolor='white')
    _plt.close(fig)

    logger.info(f"[DataViz] 图表已保存: {pdf_path}")
    return {"pdf_path": pdf_path, "png_path": png_path}


def _empty_result(figures_dir: str, fig_id: str) -> Dict:
    """空结果"""
    return {"pdf_path": "", "png_path": ""}
