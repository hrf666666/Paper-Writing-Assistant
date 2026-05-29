# -*- coding: utf-8 -*-
"""
Teaser Figure 设计器 (Teaser Designer)

自动分析论文创新点，设计 Figure 1 (Teaser) 布局。

典型 teaser 布局:
  - 输入示例 → 方法核心可视化 → 输出对比
  - 3-4个子图横向排列
  - 底部标注关键差异

支持双渲染:
  - TikZ (论文内嵌，矢量)
  - matplotlib (独立高清 PNG，投稿预览)
"""

from __future__ import annotations

import json
import os
import logging
import re
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class TeaserDesigner:
    """Teaser Figure 设计器"""

    def __init__(self, api_client=None):
        self.api_client = api_client

    def design(self, project_data: Dict, output_dir: str,
               venue_adapter=None) -> Dict[str, Any]:
        """
        设计 teaser figure

        Returns:
            {
                "layout": dict,           # 布局描述
                "tikz_code": str,          # TikZ 代码
                "matplotlib_code": str,     # matplotlib 代码
                "caption": str,             # 图注
            }
        """
        innovations = project_data.get("innovation_points", [])
        arch = project_data.get("model_architecture", {})
        exp = project_data.get("experiment_design", {})

        # Step 1: 分析创新点确定布局
        layout = self._analyze_layout(innovations, arch)
        logger.info(f"[TeaserDesigner] 布局: {layout.get('type', 'standard')}")

        # Step 2: 生成 TikZ 代码
        tikz_code = self._generate_tikz(layout, innovations)

        # Step 3: 生成 matplotlib 代码
        mpl_code = self._generate_matplotlib(layout, innovations)

        # Step 4: 生成图注
        caption = self._generate_caption(innovations, layout)

        result = {
            "layout": layout,
            "tikz_code": tikz_code,
            "matplotlib_code": mpl_code,
            "caption": caption,
        }

        # 保存
        tikz_file = os.path.join(output_dir, "teaser_figure.tex")
        with open(tikz_file, 'w', encoding='utf-8') as f:
            f.write(tikz_code)

        mpl_file = os.path.join(output_dir, "teaser_figure.py")
        with open(mpl_file, 'w', encoding='utf-8') as f:
            f.write(mpl_code)

        result_file = os.path.join(output_dir, "teaser_design.json")
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        logger.info(f"[TeaserDesigner] Teaser figure 设计完成")
        return result

    def _analyze_layout(self, innovations: List, arch: Dict) -> Dict:
        """分析创新点确定 teaser 布局"""
        num_innovations = len(innovations)

        if num_innovations >= 3:
            layout_type = "input_process_output"
            panels = 4  # input + 2 process + output
        elif num_innovations == 2:
            layout_type = "comparison"
            panels = 3  # input + method + output
        else:
            layout_type = "simple"
            panels = 2

        return {
            "type": layout_type,
            "panels": panels,
            "orientation": "horizontal",
            "width_ratio": [1] * panels,
            "innovations_mapped": [inn.get("创新点名称", f"Feature {i+1}")
                                   for i, inn in enumerate(innovations[:panels-1])],
        }

    def _generate_tikz(self, layout: Dict, innovations: List) -> str:
        """生成 TikZ teaser figure 代码"""
        panels = layout.get("panels", 3)
        innovations_mapped = layout.get("innovations_mapped", [])

        lines = [
            "% Teaser Figure - Auto-generated",
            "\\begin{figure*}[t]",
            "\\centering",
            f"\\begin{{tikzpicture}}[scale=1]",
        ]

        panel_width = 3.5
        gap = 0.3

        for i in range(panels):
            x = i * (panel_width + gap)
            lines.append(f"  % Panel {i+1}")

            if i == 0:
                lines.append(f"  \\node[draw, minimum width={panel_width}cm, minimum height=2.5cm, "
                             f"fill=blue!5] (panel{i}) at ({x}, 0) {{\\textbf{{Input}}}};")
            elif i == panels - 1:
                lines.append(f"  \\node[draw, minimum width={panel_width}cm, minimum height=2.5cm, "
                             f"fill=green!10] (panel{i}) at ({x}, 0) {{\\textbf{{Ours}}}};")
            else:
                label = innovations_mapped[i-1] if i-1 < len(innovations_mapped) else f"Module {i}"
                lines.append(f"  \\node[draw, minimum width={panel_width}cm, minimum height=2.5cm, "
                             f"fill=orange!5] (panel{i}) at ({x}, 0) {{{label[:20]}}};")

            # 箭头
            if i > 0:
                prev_x = (i-1) * (panel_width + gap) + panel_width/2
                curr_x = x - panel_width/2
                lines.append(f"  \\draw[->, thick] ({prev_x + panel_width/2 + 0.05}, 0) "
                             f"-- ({curr_x - 0.05}, 0);")

        lines.extend([
            "\\end{tikzpicture}",
            "\\caption{TEASER_CAPTION}",
            "\\label{fig:teaser}",
            "\\end{figure*}",
        ])

        return "\n".join(lines)

    def _generate_matplotlib(self, layout: Dict, innovations: List) -> str:
        """生成 matplotlib teaser figure 代码"""
        panels = layout.get("panels", 3)

        code_lines = [
            '"""Teaser Figure - Auto-generated matplotlib code"""',
            'import matplotlib.pyplot as plt',
            'import matplotlib.patches as patches',
            'import numpy as np',
            '',
            'fig, axes = plt.subplots(1, {}, figsize=(15, 4))'.format(panels),
            '',
            'panel_titles = []',
        ]

        for i in range(panels):
            if i == 0:
                code_lines.append(f'panel_titles.append("Input")')
            elif i == panels - 1:
                code_lines.append(f'panel_titles.append("Ours")')
            else:
                label = innovations[i-1].get("创新点名称", f"Module {i}") if i-1 < len(innovations) else f"Module {i}"
                code_lines.append(f'panel_titles.append("{label[:20]}")')

        code_lines.extend([
            '',
            'for i, (ax, title) in enumerate(zip(axes, panel_titles)):',
            '    # Placeholder: replace with actual images/data',
            '    ax.add_patch(patches.Rectangle((0, 0), 1, 1, fill=True,',
            '        facecolor="lightblue" if i == 0 else "lightyellow" if i < len(panel_titles)-1 else "lightgreen",',
            '        edgecolor="black"))',
            '    ax.set_title(title, fontsize=12, fontweight="bold")',
            '    ax.set_xlim(0, 1)',
            '    ax.set_ylim(0, 1)',
            '    ax.axis("off")',
            '',
            '    # Add arrow between panels',
            '    if i < len(panel_titles) - 1:',
            '        ax.annotate("", xy=(1.15, 0.5), xytext=(1.05, 0.5),',
            '            xycoords="axes fraction",',
            '            arrowprops=dict(arrowstyle="->", lw=2))',
            '',
            'plt.tight_layout()',
            'plt.savefig("teaser_figure.png", dpi=300, bbox_inches="tight")',
            'plt.savefig("teaser_figure.pdf", bbox_inches="tight")',
            'print("Teaser figure saved.")',
        ])

        return "\n".join(code_lines)

    def _generate_caption(self, innovations: List, layout: Dict) -> str:
        """生成 teaser figure 图注"""
        if not innovations:
            return "Overview of our proposed method."

        parts = ["Overview of our proposed method."]
        for i, inn in enumerate(innovations[:3]):
            name = inn.get("创新点名称", f"component {i+1}")
            value = inn.get("创新点价值", "")
            if value:
                parts.append(f"Our {name} {value[:80]}.")
            else:
                parts.append(f"The {name} is highlighted in the {['first', 'second', 'third'][i]} panel.")

        return " ".join(parts)
