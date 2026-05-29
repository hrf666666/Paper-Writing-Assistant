# -*- coding: utf-8 -*-
"""
消融实验可视化 (Ablation Plotter)

基于真实实验数据生成专业级消融结果图表:
  - 柱状图: 每个消融变体的指标对比
  - 瀑布图: 从完整模型逐步移除组件的效果变化
  - 雷达图: 多维度消融对比
"""

from __future__ import annotations

import json
import os
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


class AblationPlotter:
    """消融实验结果可视化"""

    def generate(self, ablation_results: Dict, output_dir: str,
                 metric_name: str = "accuracy") -> Dict[str, Any]:
        """
        生成消融实验可视化

        Returns:
            {
                "bar_chart_code": str,
                "waterfall_code": str,
                "radar_code": str,
            }
        """
        experiments = ablation_results.get("experiments", [])
        design = ablation_results.get("ablation_design", {})
        variants = design.get("variants", [])

        # 提取数据
        plot_data = self._extract_plot_data(experiments, variants, metric_name)

        # 生成代码
        bar_code = self._generate_bar_chart(plot_data, metric_name)
        waterfall_code = self._generate_waterfall_chart(plot_data, metric_name)

        # 保存
        bar_file = os.path.join(output_dir, "ablation_bar_chart.py")
        with open(bar_file, 'w', encoding='utf-8') as f:
            f.write(bar_code)

        waterfall_file = os.path.join(output_dir, "ablation_waterfall_chart.py")
        with open(waterfall_file, 'w', encoding='utf-8') as f:
            f.write(waterfall_code)

        return {
            "bar_chart_code": bar_code,
            "waterfall_code": waterfall_code,
        }

    def _extract_plot_data(self, experiments: List, variants: List,
                            metric_name: str) -> Dict:
        """提取绘图数据"""
        if not experiments:
            # 使用模板数据
            names = [v.get("name", f"Variant {i}") for i, v in enumerate(variants)]
            return {
                "names": names or ["Full Model", "w/o Component 1", "w/o Component 2"],
                "values": [0.0] * max(1, len(names)),
                "has_data": False,
            }

        names = []
        values = []
        for exp in experiments:
            name = exp.get("name", exp.get("variant", "Unknown"))
            val = exp.get(metric_name, exp.get("metric", 0))
            if isinstance(val, dict):
                val = list(val.values())[0] if val else 0
            names.append(name)
            values.append(float(val) if isinstance(val, (int, float)) else 0.0)

        return {"names": names, "values": values, "has_data": True}

    def _generate_bar_chart(self, data: Dict, metric: str) -> str:
        """生成消融柱状图"""
        names = data.get("names", [])
        values = data.get("values", [])
        has_data = data.get("has_data", False)

        return f'''"""Ablation Bar Chart - Auto-generated"""
import numpy as np
import matplotlib.pyplot as plt

names = {names}
values = {values}
has_real_data = {has_data}

fig, ax = plt.subplots(figsize=(10, 5))

colors = ['green'] + ['salmon'] * (len(names) - 1)
bars = ax.barh(names, values, color=colors, edgecolor='black', linewidth=0.5)

for bar, val in zip(bars, values):
    ax.text(bar.get_width() + 0.002, bar.get_y() + bar.get_height()/2,
            f'{{val:.4f}}' if has_real_data else '--',
            va='center', fontsize=9)

ax.set_xlabel('{metric.upper()}')
ax.set_title('Ablation Study Results')
ax.invert_yaxis()

if not has_real_data:
    ax.text(0.5, 0.5, '[Placeholder - Fill with real data]',
            transform=ax.transAxes, ha='center', fontsize=14, color='gray', alpha=0.5)

plt.tight_layout()
plt.savefig('ablation_bar_chart.png', dpi=300, bbox_inches='tight')
plt.savefig('ablation_bar_chart.pdf', bbox_inches='tight')
print("Ablation bar chart saved.")
'''

    def _generate_waterfall_chart(self, data: Dict, metric: str) -> str:
        """生成消融瀑布图"""
        names = data.get("names", [])
        values = data.get("values", [])
        has_data = data.get("has_data", False)

        return f'''"""Ablation Waterfall Chart - Auto-generated"""
import numpy as np
import matplotlib.pyplot as plt

names = {names}
values = {values}
has_real_data = {has_data}

if len(values) > 1:
    deltas = [values[0]] + [values[i] - values[i-1] for i in range(1, len(values))]
    bottoms = [0] + list(np.cumsum(deltas[:-1]))
else:
    deltas = values
    bottoms = [0] * len(values)

fig, ax = plt.subplots(figsize=(10, 5))

colors = ['green' if i == 0 else ('red' if d < 0 else 'blue')
          for i, d in enumerate(deltas)]

for i, (name, delta, bottom) in enumerate(zip(names, deltas, bottoms)):
    ax.bar(i, delta, bottom=bottom, color=colors[i], edgecolor='black', linewidth=0.5)
    ax.text(i, bottom + delta/2, f'{{delta:+.4f}}' if has_real_data else '--',
            ha='center', va='center', fontsize=8)

ax.set_xticks(range(len(names)))
ax.set_xticklabels(names, rotation=45, ha='right', fontsize=8)
ax.set_ylabel('{metric.upper()}')
ax.set_title('Ablation Waterfall (Component Impact)')
ax.axhline(y=0, color='black', linewidth=0.5)

plt.tight_layout()
plt.savefig('ablation_waterfall_chart.png', dpi=300, bbox_inches='tight')
plt.savefig('ablation_waterfall_chart.pdf', bbox_inches='tight')
print("Ablation waterfall chart saved.")
'''
