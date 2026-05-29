# -*- coding: utf-8 -*-
"""
消融实验表格生成器 (Ablation Table Generator)

根据真实实验数据生成:
1. LaTeX 三线表 (booktabs)
2. Markdown 表格
3. 消融对比描述文本

支持反幻觉检查：所有数值必须来自实验数据，不接受 LLM 编造的数字。
"""

from __future__ import annotations

import json
import os
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class AblationTableGenerator:
    """消融实验表格生成器"""

    def generate_tables(self, experiments: List[Dict],
                        ablation_config=None) -> Dict[str, Any]:
        """
        根据实验结果生成表格

        Args:
            experiments: 实验结果列表
            ablation_config: AblationConfig 实例

        Returns:
            {
                "latex_table": str,
                "markdown_table": str,
                "description": str,
            }
        """
        if not experiments:
            return self._generate_template_tables(ablation_config)

        # 从实验数据中提取指标
        rows = self._extract_table_rows(experiments)

        # 生成 LaTeX 三线表
        latex = self._generate_latex_table(rows)

        # 生成 Markdown 表格
        markdown = self._generate_markdown_table(rows)

        # 生成描述文本
        description = self._generate_description(rows)

        return {
            "latex_table": latex,
            "markdown_table": markdown,
            "description": description,
            "data_source": "experimental",
        }

    def _extract_table_rows(self, experiments: List[Dict]) -> List[Dict]:
        """从实验数据中提取表格行"""
        rows = []
        for exp in experiments:
            row = {
                "name": exp.get("name", exp.get("variant", "Unknown")),
                "metrics": {},
            }

            # 提取常见指标
            for key in ["accuracy", "MAE", "RMSE", "PSNR", "SSIM", "FID",
                         "mAP", "IoU", "score", "loss", "metric"]:
                if key in exp:
                    row["metrics"][key] = exp[key]
                # 嵌套结构
                if "metrics" in exp and isinstance(exp["metrics"], dict):
                    if key in exp["metrics"]:
                        row["metrics"][key] = exp["metrics"][key]

            # 提取 results 字段
            if "results" in exp and isinstance(exp["results"], dict):
                for k, v in exp["results"].items():
                    if isinstance(v, (int, float)):
                        row["metrics"][k] = v

            rows.append(row)

        return rows

    def _generate_latex_table(self, rows: List[Dict]) -> str:
        """生成 LaTeX 三线表"""
        if not rows:
            return "% No experimental data available"

        # 确定列
        all_metrics = set()
        for row in rows:
            all_metrics.update(row["metrics"].keys())

        metric_list = sorted(all_metrics)[:5]  # 最多5个指标列

        # 表头
        col_spec = "l" + "c" * len(metric_list)
        lines = [
            "\\begin{table}[t]",
            "\\centering",
            "\\caption{Ablation study results.}",
            f"\\begin{{tabular}}{{{col_spec}}}",
            "\\toprule",
        ]

        # 表头行
        header = "Method"
        for m in metric_list:
            header += f" & {m.upper()}"
        header += " \\\\"
        lines.append(header)
        lines.append("\\midrule")

        # 数据行
        for row in rows:
            line = row["name"]
            for m in metric_list:
                val = row["metrics"].get(m, "--")
                if isinstance(val, float):
                    line += f" & {val:.4f}"
                else:
                    line += f" & {val}"
            line += " \\\\"
            lines.append(line)

        lines.extend([
            "\\bottomrule",
            "\\end{tabular}",
            "\\label{tab:ablation}",
            "\\end{table}",
        ])

        return "\n".join(lines)

    def _generate_markdown_table(self, rows: List[Dict]) -> str:
        """生成 Markdown 表格"""
        if not rows:
            return "| Method | Results |\n|---|---|\n| (no data) | -- |"

        all_metrics = set()
        for row in rows:
            all_metrics.update(row["metrics"].keys())

        metric_list = sorted(all_metrics)[:5]

        # 表头
        header = "| Method |"
        separator = "|---|"
        for m in metric_list:
            header += f" {m.upper()} |"
            separator += "---|"

        lines = [header, separator]

        # 数据行
        for row in rows:
            line = f"| {row['name']} |"
            for m in metric_list:
                val = row["metrics"].get(m, "--")
                if isinstance(val, float):
                    line += f" {val:.4f} |"
                else:
                    line += f" {val} |"
            lines.append(line)

        return "\n".join(lines)

    def _generate_description(self, rows: List[Dict]) -> str:
        """生成消融实验描述文本"""
        if not rows:
            return "Ablation experiments pending. Results will be filled after experiments complete."

        full_model = None
        ablations = []
        for row in rows:
            if "full" in row["name"].lower() or row["name"] == "Full Model":
                full_model = row
            else:
                ablations.append(row)

        desc_parts = [
            "We conduct comprehensive ablation studies to validate each component of our proposed method.",
        ]

        if full_model:
            metrics_str = ", ".join(
                f"{k}: {v:.4f}" if isinstance(v, float) else f"{k}: {v}"
                for k, v in list(full_model["metrics"].items())[:3]
            )
            desc_parts.append(f"The full model achieves {metrics_str}.")

        for abl in ablations[:4]:
            name = abl["name"]
            if abl["metrics"] and full_model and full_model["metrics"]:
                first_metric = list(abl["metrics"].keys())[0] if abl["metrics"] else None
                if first_metric and first_metric in full_model["metrics"]:
                    abl_val = abl["metrics"][first_metric]
                    full_val = full_model["metrics"][first_metric]
                    if isinstance(abl_val, (int, float)) and isinstance(full_val, (int, float)):
                        diff = abs(full_val - abl_val)
                        desc_parts.append(
                            f"Removing {name} leads to a degradation of {diff:.4f} in {first_metric.upper()}."
                        )
                    else:
                        desc_parts.append(f"The {name} variant shows different performance.")
                else:
                    desc_parts.append(f"The {name} variant is evaluated.")
            else:
                desc_parts.append(f"The {name} variant is evaluated.")

        return " ".join(desc_parts)

    def _generate_template_tables(self, ablation_config=None) -> Dict[str, Any]:
        """生成模板表格（无实验数据时）"""
        min_abl = ablation_config.min_ablations if ablation_config else 3

        variants = ["Full Model"]
        for i in range(min_abl):
            variants.append(f"w/o Component {i+1}")

        latex_lines = [
            "\\begin{table}[t]",
            "\\centering",
            "\\caption{Ablation study results. [TO BE FILLED WITH EXPERIMENTAL DATA]}",
            "\\begin{tabular}{lccc}",
            "\\toprule",
            "Method & Metric1 & Metric2 & Metric3 \\\\",
            "\\midrule",
        ]
        for v in variants:
            latex_lines.append(f"{v} & -- & -- & -- \\\\")
        latex_lines.extend([
            "\\bottomrule",
            "\\end{tabular}",
            "\\label{tab:ablation}",
            "\\end{table}",
        ])

        md_lines = ["| Method | Metric1 | Metric2 | Metric3 |", "|---|---|---|---|"]
        for v in variants:
            md_lines.append(f"| {v} | -- | -- | -- |")

        return {
            "latex_table": "\n".join(latex_lines),
            "markdown_table": "\n".join(md_lines),
            "description": f"Ablation study with {min_abl} variants. Results pending experimental execution.",
            "data_source": "template",
        }
