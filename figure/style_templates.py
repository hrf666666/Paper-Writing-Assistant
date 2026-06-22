# -*- coding: utf-8 -*-
"""
图表风格模板库 v9.1 (Style Templates)

为不同 venue 提供统一的图表风格，对标顶刊审美标准。
配色方案遵循：低饱和度 + 色盲友好 + venue 自适应。
"""

from __future__ import annotations
from typing import Dict, Any


# ═══════════════════════════════════════════════════════════════
# IEEE TCSVT / TIP 风格（v9.1 专业版）
# ═══════════════════════════════════════════════════════════════

TCSVT_STYLE = {
    # 尺寸规范（IEEE 官方）
    "single_column_width": 3.5,    # inch (88.9mm)
    "double_column_width": 7.16,   # inch (182mm)
    "max_height": 8.5,             # inch
    "dpi_lineart": 600,
    "dpi_color": 300,

    # 字体
    "font_family": "serif",
    "font_serif": ["Times New Roman", "DejaVu Serif"],
    "font_sizes": {
        "title": 10,
        "axis_label": 9,
        "tick_label": 7,
        "legend": 7,
        "annotation": 7,
        "panel_label": 10,  # (a) (b) (c) 粗体
    },

    # 配色方案 — 蓝色梯度 + 橙色强调（色盲友好）
    "colors": {
        # 主色系 — 蓝色梯度（用于不同模块/方法）
        "primary_dark": "#1B3A5C",
        "primary": "#2E5090",
        "primary_light": "#5B8DB8",
        "primary_lighter": "#A3C4E0",
        "primary_lightest": "#D6E6F2",
        # 强调色 — 创新点高亮
        "accent": "#D4772C",       # 橙色，与蓝色互补
        "accent_light": "#F0C89A",
        # 对比色 — 消融/对比实验
        "comparison": ["#2E5090", "#D4772C", "#27AE60", "#C0392B", "#8E44AD", "#2C3E50"],
        # 中性色
        "border": "#34495E",
        "text": "#2C3E50",
        "text_light": "#7F8C8D",
        "background": "#FFFFFF",
        "light_bg": "#F5F7FA",
        "grid": "#E0E0E0",
    },

    # 模块填充色 — 低饱和度（opacity 0.25 效果）
    "module_fills": [
        "#D6E6F2",  # 浅蓝 — 输入/数据
        "#FDE8D0",  # 浅橙 — 分析/处理
        "#D5F0E0",  # 浅绿 — 核心模块
        "#FADBD8",  # 浅红 — 分类/判别
        "#E8DAEF",  # 浅紫 — 估计/预测
        "#D1F2EB",  # 浅青 — 融合/输出
    ],

    # 布局参数
    "layout": {
        "module_gap_mm": 3,
        "padding_mm": 2,
        "border_width": 0.8,
        "corner_radius": 3,        # px (SVG)
        "arrow_width": 0.8,
        "arrow_head_size": 5,      # px
    },

    # 数据图表参数
    "chart": {
        "bar_width": 0.6,
        "line_width": 1.2,
        "marker_size": 5,
        "grid_alpha": 0.3,
        "spine_width": 0.5,
    },
}

# 向后兼容
IEEE_STYLE = TCSVT_STYLE

# ═══════════════════════════════════════════════════════════════
# 会议论文风格 (CVPR/ICCV/ECCV)
# ═══════════════════════════════════════════════════════════════

CONFERENCE_STYLE = {
    "single_column_width": 3.25,
    "double_column_width": 6.75,
    "max_height": 8.0,
    "dpi_lineart": 600,
    "dpi_color": 300,

    "font_family": "sans-serif",
    "font_serif": ["Arial", "Helvetica", "DejaVu Sans"],
    "font_sizes": {
        "title": 10,
        "axis_label": 9,
        "tick_label": 8,
        "legend": 7,
        "annotation": 7,
        "panel_label": 10,
    },

    "colors": {
        "primary_dark": "#2C3E50",
        "primary": "#3498DB",
        "primary_light": "#85C1E9",
        "primary_lighter": "#AED6F1",
        "primary_lightest": "#D6EAF8",
        "accent": "#E67E22",
        "accent_light": "#F5CBA7",
        "comparison": ["#3498DB", "#E67E22", "#2ECC71", "#E74C3C", "#9B59B6", "#1ABC9C"],
        "border": "#2C3E50",
        "text": "#2C3E50",
        "text_light": "#95A5A6",
        "background": "#FFFFFF",
        "light_bg": "#F8F9FA",
        "grid": "#ECF0F1",
    },

    "module_fills": [
        "#D6EAF8", "#FDEBD0", "#D5F5E3", "#FADBD8", "#E8DAEF", "#D1F2EB",
    ],

    "layout": {
        "module_gap_mm": 3,
        "padding_mm": 2,
        "border_width": 0.8,
        "corner_radius": 4,
        "arrow_width": 0.8,
        "arrow_head_size": 5,
    },

    "chart": {
        "bar_width": 0.6,
        "line_width": 1.5,
        "marker_size": 6,
        "grid_alpha": 0.2,
        "spine_width": 0.5,
    },
}

# ═══════════════════════════════════════════════════════════════
# NeurIPS / ICML 风格
# ═══════════════════════════════════════════════════════════════

NEURIPS_STYLE = {
    "single_column_width": 3.25,
    "double_column_width": 6.75,
    "max_height": 8.0,
    "dpi_lineart": 600,
    "dpi_color": 300,

    "font_family": "sans-serif",
    "font_serif": ["Helvetica", "Arial", "DejaVu Sans"],
    "font_sizes": {
        "title": 10,
        "axis_label": 9,
        "tick_label": 8,
        "legend": 7,
        "annotation": 7,
        "panel_label": 10,
    },

    "colors": {
        "primary_dark": "#1A1A2E",
        "primary": "#4C72B0",
        "primary_light": "#8FAADC",
        "primary_lighter": "#B4C7E7",
        "primary_lightest": "#D9E4F1",
        "accent": "#DD8452",
        "accent_light": "#F0C89A",
        "comparison": ["#4C72B0", "#DD8452", "#55A868", "#C44E52", "#8172B3", "#937860"],
        "border": "#333333",
        "text": "#333333",
        "text_light": "#888888",
        "background": "#FFFFFF",
        "light_bg": "#FAFAFA",
        "grid": "#E5E5E5",
    },

    "module_fills": [
        "#D9E4F1", "#FDE8D0", "#D4EDDA", "#F8D7DA", "#E2D9F3", "#D1ECF1",
    ],

    "layout": {
        "module_gap_mm": 3,
        "padding_mm": 2,
        "border_width": 0.7,
        "corner_radius": 2,
        "arrow_width": 0.7,
        "arrow_head_size": 4,
    },

    "chart": {
        "bar_width": 0.6,
        "line_width": 1.5,
        "marker_size": 5,
        "grid_alpha": 0.0,
        "spine_width": 0.5,
    },
}


# ═══════════════════════════════════════════════════════════════
# Venue 映射
# ═══════════════════════════════════════════════════════════════

VENUE_STYLES = {
    "IEEE TIP": TCSVT_STYLE,
    "IEEE TCSVT": TCSVT_STYLE,
    "IEEE TPAMI": TCSVT_STYLE,
    "IEEE Trans": TCSVT_STYLE,
    "CVPR": CONFERENCE_STYLE,
    "ICCV": CONFERENCE_STYLE,
    "ECCV": CONFERENCE_STYLE,
    "NeurIPS": NEURIPS_STYLE,
    "ICML": NEURIPS_STYLE,
    "ICLR": NEURIPS_STYLE,
}


def get_style(venue_name: str) -> Dict:
    """获取 venue 对应的图表风格，支持模糊匹配"""
    # 精确匹配
    if venue_name in VENUE_STYLES:
        return VENUE_STYLES[venue_name]
    # 模糊匹配
    venue_lower = venue_name.lower()
    for key, style in VENUE_STYLES.items():
        if key.lower() in venue_lower or venue_lower in key.lower():
            return style
    return TCSVT_STYLE  # 默认 IEEE 风格


def get_figure_size(style: Dict, size_type: str = "single") -> tuple:
    """
    获取图表尺寸 (width, height) in inches

    Args:
        style: 风格字典
        size_type: "single" (单栏) | "double" (双栏) | "teaser" (主图)
    """
    if size_type == "teaser":
        w = style.get("double_column_width", 7.16)
        h = min(3.5, style.get("max_height", 8.5))
    elif size_type == "double":
        w = style.get("double_column_width", 7.16)
        h = min(4.0, style.get("max_height", 8.5))
    else:
        w = style.get("single_column_width", 3.5)
        h = min(4.0, style.get("max_height", 8.5))
    return (w, h)
