# -*- coding: utf-8 -*-
"""
图表风格模板库 (Style Templates)

为不同 venue 提供统一的图表风格。
"""

from __future__ import annotations
from typing import Dict


# IEEE 风格
IEEE_STYLE = {
    "font_family": "serif",
    "font_size": 10,
    "figure_dpi": 300,
    "figure_width_inches": 3.5,   # 单栏宽度
    "figure_height_inches": 2.5,
    "color_palette": ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"],
    "grid": True,
    "grid_alpha": 0.3,
    "linewidth": 1.5,
    "marker_size": 5,
}

# 会议论文风格 (更宽)
CONFERENCE_STYLE = {
    "font_family": "serif",
    "font_size": 9,
    "figure_dpi": 300,
    "figure_width_inches": 7.0,   # 双栏宽度
    "figure_height_inches": 3.0,
    "color_palette": ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"],
    "grid": True,
    "grid_alpha": 0.2,
    "linewidth": 2.0,
    "marker_size": 6,
}

# NeurIPS 风格
NEURIPS_STYLE = {
    "font_family": "sans-serif",
    "font_size": 10,
    "figure_dpi": 300,
    "figure_width_inches": 6.0,
    "figure_height_inches": 3.5,
    "color_palette": ["#4c72b0", "#dd8452", "#55a868", "#c44e52", "#8172b3"],
    "grid": False,
    "grid_alpha": 0.0,
    "linewidth": 2.0,
    "marker_size": 6,
}


VENUE_STYLES = {
    "IEEE TIP": IEEE_STYLE,
    "IEEE TCSVT": IEEE_STYLE,
    "IEEE TPAMI": IEEE_STYLE,
    "IEEE Trans": IEEE_STYLE,
    "CVPR": CONFERENCE_STYLE,
    "NeurIPS": NEURIPS_STYLE,
}


def get_style(venue_name: str) -> Dict:
    """获取 venue 对应的图表风格"""
    return VENUE_STYLES.get(venue_name, IEEE_STYLE)


def apply_style(style: Dict):
    """将风格应用到 matplotlib 全局配置"""
    import matplotlib.pyplot as plt

    plt.rcParams.update({
        "font.family": style.get("font_family", "serif"),
        "font.size": style.get("font_size", 10),
        "figure.dpi": style.get("figure_dpi", 300),
        "axes.grid": style.get("grid", True),
        "grid.alpha": style.get("grid_alpha", 0.3),
        "lines.linewidth": style.get("linewidth", 1.5),
        "lines.markersize": style.get("marker_size", 5),
    })
