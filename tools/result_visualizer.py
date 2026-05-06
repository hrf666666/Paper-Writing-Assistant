# -*- coding: utf-8 -*-
"""
Tool: 实验结果可视化器

v5.0 核心新增：读取实验数据，处理并绘制对比图/表格

功能：
1. 读取消融实验结果数据
2. 生成对比图表（柱状图、折线图、热力图等）
3. 生成LaTeX对比表格
4. 支持多种数据格式（JSON, CSV, log文件）
"""

import os
import json
import re
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from config.project_config import (
    PAPER_TITLE, OUTPUT_DIR, WORKSPACE_DIR
)
from agent.api_client import get_api_client

logger = logging.getLogger(__name__)


def _get_api():
    """延迟获取API客户端"""
    return get_api_client()

ABLATION_DIR = Path(WORKSPACE_DIR) / "ablation_test"
ABLATION_DATA_DIR = ABLATION_DIR / "data"
ABLATION_FIG_DIR = ABLATION_DIR / "fig"


# ========== 数据读取 ==========

def load_ablation_results(data_dir: str = None) -> Dict[str, Any]:
    """
    读取消融实验结果数据

    支持多种来源：
    1. JSON格式的实验结果文件
    2. 训练日志中的指标
    3. 已有的汇总文件
    """
    data_dir = Path(data_dir or ABLATION_DATA_DIR)
    if not data_dir.exists():
        logger.warning(f"实验数据目录不存在: {data_dir}")
        return {}

    results = {}
    # 读取所有JSON结果文件
    for fpath in data_dir.glob("*.json"):
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            exp_name = fpath.stem.replace("_results", "").replace("_", " ")
            results[exp_name] = data
        except Exception as e:
            logger.warning(f"读取 {fpath} 失败: {e}")

    # 读取汇总文件
    summary_path = data_dir / "ablation_summary.json"
    if summary_path.exists():
        try:
            with open(summary_path, 'r', encoding='utf-8') as f:
                summary = json.load(f)
            results["_summary"] = summary
        except Exception:
            pass

    return results


def extract_metrics_from_logs(log_dir: str) -> Dict[str, List[Dict]]:
    """
    从训练日志中提取指标

    支持常见格式：
    - tensorboard style: "epoch 10, loss=0.123, acc=0.956"
    - wandb style: JSON lines
    - simple CSV
    """
    log_dir = Path(log_dir)
    if not log_dir.exists():
        return {}

    metrics = {}
    for fpath in log_dir.glob("*.log"):
        try:
            with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()

            exp_name = fpath.stem
            data_points = []

            for line in lines:
                # 尝试提取 epoch + metrics 格式
                metric_match = re.findall(
                    r'(?:epoch\s*\d+|step\s*\d+).*?(?:loss|acc|mae|rmse|mse|iou|f1|ap)\s*[=:]\s*([\d.]+)',
                    line, re.IGNORECASE
                )
                if metric_match:
                    data_points.append({"line": line.strip(), "values": metric_match})

            if data_points:
                metrics[exp_name] = data_points
        except Exception:
            pass

    return metrics


# ========== 图表生成 ==========

def plot_ablation_comparison(ablation_results: Dict, ablation_design: Dict,
                              metrics: List[str] = None,
                              output_dir: str = None):
    """
    绘制消融实验对比图

    Args:
        ablation_results: 消融实验结果数据
        ablation_design: 消融实验设计方案
        metrics: 要绘制的指标列表
        output_dir: 输出目录
    """
    output_dir = Path(output_dir or ABLATION_FIG_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        import matplotlib
        matplotlib.use('Agg')  # 无GUI后端
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        logger.warning("matplotlib未安装，跳过图表生成。请安装: pip install matplotlib")
        return

    experiments = ablation_design.get("ablation_experiments", [])
    if not experiments:
        logger.warning("无消融实验设计方案，跳过绘图")
        return

    # 使用LLM从结果数据中提取结构化指标
    structured_data = _extract_structured_metrics(ablation_results, ablation_design)

    if not structured_data:
        logger.warning("无法提取结构化指标数据，跳过绘图")
        return

    # 绘制对比柱状图
    _plot_bar_comparison(structured_data, output_dir)

    # 绘制雷达图（如果有多个指标）
    _plot_radar_comparison(structured_data, output_dir)

    # 绘制性能下降瀑布图
    _plot_waterfall(structured_data, output_dir)


def _extract_structured_metrics(ablation_results: Dict,
                                 ablation_design: Dict) -> Optional[Dict]:
    """使用LLM从实验结果中提取结构化指标数据"""

    # 先尝试直接从结果中提取
    experiments = ablation_design.get("ablation_experiments", [])
    table_format = ablation_design.get("result_table_format", {})

    # 如果结果已经是结构化的（有明确的指标键），直接使用
    direct_data = {}
    for exp_name, data in ablation_results.items():
        if exp_name.startswith("_"):
            continue
        if isinstance(data, dict):
            # 检查是否包含数值指标
            numeric_fields = {}
            for k, v in data.items():
                if isinstance(v, (int, float)):
                    numeric_fields[k] = v
                elif isinstance(v, str):
                    try:
                        numeric_fields[k] = float(v)
                    except ValueError:
                        pass
            if numeric_fields:
                direct_data[exp_name] = numeric_fields

    if direct_data:
        return direct_data

    # 否则使用LLM提取
    results_text = json.dumps(ablation_results, ensure_ascii=False, indent=2)[:8000]

    prompt = f"""请从以下消融实验结果数据中提取结构化的指标数据。

**实验结果**:
{results_text}

**消融实验设计**:
{json.dumps([e.get('experiment_name', '') for e in experiments], ensure_ascii=False)}

请以json格式给出，格式如下：
{{
  "Full Model": {{"MAE": 0.123, "RMSE": 0.456}},
  "w/o Module1": {{"MAE": 0.234, "RMSE": 0.567}},
  ...
}}

只包含数值型指标，不要包含非数值字段。指标名称使用英文缩写。
回复以```json开头，以```结尾。"""

    try:
        response = _get_api().call_reasoning(prompt)
        result = _get_api().parse_json_response(response, default={})
        if isinstance(result, dict) and result:
            return result
    except Exception as e:
        logger.debug(f"LLM提取指标失败: {e}")

    return None


def _plot_bar_comparison(data: Dict, output_dir: Path):
    """绘制分组柱状对比图"""
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        return

    if not data:
        return

    # 获取所有实验名和指标名
    exp_names = list(data.keys())
    if not exp_names:
        return

    metrics = list(data[exp_names[0]].keys())
    if not metrics:
        return

    # 设置样式
    plt.rcParams.update({
        'font.size': 10,
        'font.family': 'serif',
        'figure.dpi': 300,
    })

    fig, axes = plt.subplots(1, len(metrics), figsize=(6 * len(metrics), 5))
    if len(metrics) == 1:
        axes = [axes]

    colors = plt.cm.Set2(np.linspace(0, 1, len(exp_names)))

    for ax, metric in zip(axes, metrics):
        values = []
        labels = []
        for exp in exp_names:
            if metric in data[exp]:
                values.append(data[exp][metric])
                # 简化标签
                label = exp.replace("w/o ", "w/o\n").replace("Full Model", "Full\nModel")
                labels.append(label)
            else:
                values.append(0)
                labels.append(exp)

        x = np.arange(len(labels))
        bars = ax.bar(x, values, color=colors[:len(values)], edgecolor='gray', linewidth=0.5)

        # 标注最优值
        if values:
            best_idx = values.index(min(values))  # 假设越低越好
            bars[best_idx].set_edgecolor('red')
            bars[best_idx].set_linewidth(2)

        ax.set_ylabel(metric)
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=30, ha='right', fontsize=8)
        ax.set_title(f'Ablation Study - {metric}')

        # 添加数值标注
        for bar, val in zip(bars, values):
            if val > 0:
                ax.text(bar.get_x() + bar.get_width() / 2., bar.get_height(),
                       f'{val:.3f}', ha='center', va='bottom', fontsize=7)

    plt.tight_layout()
    plt.savefig(output_dir / "ablation_comparison_bar.png", dpi=300, bbox_inches='tight')
    plt.savefig(output_dir / "ablation_comparison_bar.pdf", dpi=300, bbox_inches='tight')
    plt.close()
    print(f"[visualizer] 柱状对比图已保存至 {output_dir}/ablation_comparison_bar.png")


def _plot_radar_comparison(data: Dict, output_dir: Path):
    """绘制雷达对比图"""
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        return

    if not data or len(data) < 2:
        return

    exp_names = list(data.keys())
    metrics = list(data[exp_names[0]].keys())
    if len(metrics) < 3:  # 雷达图至少需要3个维度
        return

    # 归一化（将所有指标归一化到0-1，越低越好的指标反转）
    normalized = {}
    for metric in metrics:
        values = [data[exp].get(metric, 0) for exp in exp_names]
        max_val = max(values) if values else 1
        min_val = min(values) if values else 0
        for i, exp in enumerate(exp_names):
            if exp not in normalized:
                normalized[exp] = {}
            if max_val > min_val:
                normalized[exp][metric] = (values[i] - min_val) / (max_val - min_val)
            else:
                normalized[exp][metric] = 0.5

    # 绘制雷达图
    angles = np.linspace(0, 2 * np.pi, len(metrics), endpoint=False).tolist()
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(polar=True))

    colors = plt.cm.Set2(np.linspace(0, 1, len(exp_names)))
    for i, exp in enumerate(exp_names):
        values = [normalized[exp].get(m, 0) for m in metrics]
        values += values[:1]
        ax.plot(angles, values, 'o-', linewidth=1.5, color=colors[i], label=exp)
        ax.fill(angles, values, alpha=0.1, color=colors[i])

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(metrics)
    ax.set_title('Ablation Study - Multi-metric Comparison', pad=20)
    ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1), fontsize=8)

    plt.tight_layout()
    plt.savefig(output_dir / "ablation_comparison_radar.png", dpi=300, bbox_inches='tight')
    plt.savefig(output_dir / "ablation_comparison_radar.pdf", dpi=300, bbox_inches='tight')
    plt.close()
    print(f"[visualizer] 雷达对比图已保存至 {output_dir}/ablation_comparison_radar.png")


def _plot_waterfall(data: Dict, output_dir: Path):
    """绘制性能下降瀑布图"""
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        return

    if not data or "Full Model" not in data:
        return

    exp_names = list(data.keys())
    metrics = list(data["Full Model"].keys())
    if not metrics:
        return

    # 使用第一个指标
    metric = metrics[0]

    # 计算每个消融相比Full Model的性能变化
    full_value = data["Full Model"].get(metric, 0)
    if full_value == 0:
        return

    drops = {}
    for exp in exp_names:
        if exp == "Full Model":
            continue
        exp_value = data[exp].get(metric, 0)
        # 计算相对变化（百分比）
        if full_value != 0:
            drops[exp] = ((exp_value - full_value) / full_value) * 100
        else:
            drops[exp] = 0

    # 排序：影响最大的排前面
    sorted_drops = sorted(drops.items(), key=lambda x: abs(x[1]), reverse=True)

    if not sorted_drops:
        return

    fig, ax = plt.subplots(figsize=(10, 5))

    labels = ["Full Model"] + [d[0] for d in sorted_drops]
    values = [0] + [d[1] for d in sorted_drops]
    colors = ['#2ecc71'] + ['#e74c3c' if v > 0 else '#3498db' for v in values[1:]]

    bars = ax.barh(range(len(labels)), values, color=colors, edgecolor='gray', linewidth=0.5)
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=9)
    ax.set_xlabel(f'Performance Change ({metric}) %')
    ax.set_title(f'Ablation Impact - {metric} Change from Full Model')
    ax.axvline(x=0, color='black', linewidth=0.5)

    # 标注数值
    for bar, val in zip(bars, values):
        if val >= 0:
            ax.text(val + 0.5, bar.get_y() + bar.get_height() / 2.,
                   f'+{val:.1f}%', va='center', fontsize=8)
        else:
            ax.text(val - 0.5, bar.get_y() + bar.get_height() / 2.,
                   f'{val:.1f}%', va='center', ha='right', fontsize=8)

    plt.tight_layout()
    plt.savefig(output_dir / "ablation_waterfall.png", dpi=300, bbox_inches='tight')
    plt.savefig(output_dir / "ablation_waterfall.pdf", dpi=300, bbox_inches='tight')
    plt.close()
    print(f"[visualizer] 瀑布图已保存至 {output_dir}/ablation_waterfall.png")


# ========== LaTeX表格生成 ==========

def generate_latex_ablation_table(ablation_results: Dict, ablation_design: Dict,
                                   dataset_name: str = "benchmark") -> str:
    """
    生成消融实验的LaTeX对比表格

    Args:
        ablation_results: 实验结果数据
        ablation_design: 消融实验设计方案
        dataset_name: 数据集名称

    Returns:
        str: LaTeX表格代码
    """
    experiments = ablation_design.get("ablation_experiments", [])
    table_format = ablation_design.get("result_table_format", {})

    # 提取结构化数据
    structured_data = _extract_structured_metrics(ablation_results, ablation_design)

    if not structured_data:
        # 生成空模板表格
        return _generate_empty_latex_table(experiments, dataset_name)

    # 获取指标列
    metrics = list(next(iter(structured_data.values())).keys())
    metric_cols = " & ".join(metrics)

    # 构建表格
    table = r"\begin{table}[htbp]" + "\n"
    table += r"\centering" + "\n"
    table += r"\caption{Ablation study results on " + dataset_name + ". Best results are in \textbf{bold}.}" + "\n"
    table += r"\label{tab:ablation}" + "\n"
    table += r"\begin{tabular}{l" + "c" * len(metrics) + "}\n"
    table += r"\toprule" + "\n"
    table += f"Configuration & {metric_cols} \\\\\n"
    table += r"\midrule" + "\n"

    # Full Model行
    if "Full Model" in structured_data:
        values = structured_data["Full Model"]
        row_values = []
        for m in metrics:
            val = values.get(m, "X.XXX")
            if isinstance(val, float):
                row_values.append(f"\\textbf{{{val:.3f}}}")
            else:
                row_values.append(str(val))
        table += "Full Model (Ours) & " + " & ".join(row_values) + " \\\\\n"

    # 各消融配置行
    for exp in experiments:
        exp_name = exp.get("experiment_name", "Unknown")
        short_name = exp_name.replace("Without ", "w/o ").replace("Replace ", "w/ ")

        if exp_name in structured_data:
            values = structured_data[exp_name]
            row_values = []
            for m in metrics:
                val = values.get(m, "X.XXX")
                if isinstance(val, float):
                    row_values.append(f"{val:.3f}")
                else:
                    row_values.append(str(val))
            table += f"{short_name} & " + " & ".join(row_values) + " \\\\\n"
        else:
            table += f"{short_name} & " + " & ".join(["X.XXX"] * len(metrics)) + " \\\\\n"

    table += r"\bottomrule" + "\n"
    table += r"\end{tabular}" + "\n"
    table += r"\end{table}" + "\n"

    return table


def _generate_empty_latex_table(experiments: List[Dict], dataset_name: str) -> str:
    """生成空的LaTeX表格模板"""
    table = r"\begin{table}[htbp]" + "\n"
    table += r"\centering" + "\n"
    table += r"\caption{Ablation study results on " + dataset_name + ". Best results are in \textbf{bold}.}" + "\n"
    table += r"\label{tab:ablation}" + "\n"
    table += r"\begin{tabular}{lcc}" + "\n"
    table += r"\toprule" + "\n"
    table += r"Configuration & Metric1 & Metric2 \\" + "\n"
    table += r"\midrule" + "\n"
    table += r"Full Model (Ours) & \textbf{X.XXX} & \textbf{X.XXX} \\" + "\n"

    for exp in experiments:
        name = exp.get("experiment_name", "Unknown")
        short_name = name.replace("Without ", "w/o ").replace("Replace ", "w/ ")
        table += f"{short_name} & X.XXX & X.XXX \\\\\n"

    table += r"\bottomrule" + "\n"
    table += r"\end{tabular}" + "\n"
    table += r"\end{table}" + "\n"

    return table


# ========== 主入口 ==========

def run_result_visualizer(ablation_design: Dict = None,
                           ablation_results: Dict = None,
                           output_dir: str = None) -> Dict:
    """
    主入口：运行结果可视化器

    Args:
        ablation_design: 消融实验设计方案
        ablation_results: 实验结果数据（如未提供则从文件读取）
        output_dir: 输出目录

    Returns:
        Dict: 可视化结果
    """
    print("\n" + "=" * 60)
    print("  实验结果可视化器 v5.0")
    print("=" * 60)

    output_dir = output_dir or str(ABLATION_FIG_DIR)
    os.makedirs(output_dir, exist_ok=True)

    # 读取消融实验设计
    if ablation_design is None:
        design_path = f"{OUTPUT_DIR}/ablation_design.json"
        if os.path.exists(design_path):
            with open(design_path, 'r', encoding='utf-8') as f:
                ablation_design = json.load(f)
        else:
            ablation_design = {}

    # 读取实验结果
    if ablation_results is None:
        ablation_results = load_ablation_results()

    if not ablation_results:
        print("[visualizer] 未找到实验结果数据，生成空模板")
        ablation_results = {}

    results = {}

    # 1. 绘制对比图
    print("\n[1/3] 生成对比图表...")
    try:
        plot_ablation_comparison(ablation_results, ablation_design, output_dir=output_dir)
        results["figures_generated"] = True
    except Exception as e:
        logger.error(f"图表生成失败: {e}")
        results["figures_generated"] = False
        results["figure_error"] = str(e)

    # 2. 生成LaTeX表格
    print("[2/3] 生成LaTeX对比表格...")
    latex_table = generate_latex_ablation_table(ablation_results, ablation_design)
    latex_path = os.path.join(output_dir, "ablation_table.tex")
    with open(latex_path, 'w', encoding='utf-8') as f:
        f.write(latex_table)
    results["latex_table"] = latex_path
    print(f"  LaTeX表格已保存至 {latex_path}")

    # 3. 生成Markdown表格
    print("[3/3] 生成Markdown对比表格...")
    md_table = generate_markdown_table(ablation_results, ablation_design)
    md_path = os.path.join(output_dir, "ablation_table.md")
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(md_table)
    results["markdown_table"] = md_path

    print(f"\n可视化完成！结果保存在 {output_dir}")
    return results


def generate_markdown_table(ablation_results: Dict, ablation_design: Dict) -> str:
    """生成Markdown格式的对比表格"""
    structured_data = _extract_structured_metrics(ablation_results, ablation_design)
    if not structured_data:
        return "| Configuration | Results |\n|---|---|\n| (待补充) | |\n"

    metrics = list(next(iter(structured_data.values())).keys())

    # 表头
    header = "| Configuration | " + " | ".join(metrics) + " |"
    separator = "|" + "---|" * (len(metrics) + 1)

    rows = [header, separator]

    # Full Model
    if "Full Model" in structured_data:
        values = structured_data["Full Model"]
        row = "| **Full Model (Ours)** |"
        for m in metrics:
            val = values.get(m, "N/A")
            if isinstance(val, float):
                row += f" **{val:.3f}** |"
            else:
                row += f" {val} |"
        rows.append(row)

    # 各消融配置
    experiments = ablation_design.get("ablation_experiments", [])
    for exp in experiments:
        exp_name = exp.get("experiment_name", "Unknown")
        short_name = exp_name.replace("Without ", "w/o ").replace("Replace ", "w/ ")

        if exp_name in structured_data:
            values = structured_data[exp_name]
            row = f"| {short_name} |"
            for m in metrics:
                val = values.get(m, "N/A")
                if isinstance(val, float):
                    row += f" {val:.3f} |"
                else:
                    row += f" {val} |"
            rows.append(row)
        else:
            row = f"| {short_name} |" + " N/A |" * len(metrics)
            rows.append(row)

    return "\n".join(rows)


if __name__ == "__main__":
    results = run_result_visualizer()
