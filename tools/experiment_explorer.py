# -*- coding: utf-8 -*-
"""
Tool: 实验数据探索器 v9.2 (Experiment Explorer)

主动扫描目标项目的实验数据，分析汇总可用于论文图表的结果。
解决"数据图全部跳过"的问题。

工作流程：
1. 扫描（感知）：发现项目中的 results.json、实验数据库、已有图表
2. 分析（提炼）：解析实验数据，提取关键指标和对比结论
3. 汇总（表达）：生成结构化的 ExperimentSummary 供图表生成器使用

不依赖 LLM，纯规则驱动。
"""

import json
import logging
import os
import sqlite3
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class ExperimentResult:
    """单个实验的结果"""
    experiment_name: str
    model_name: str = ""
    metrics: Dict[str, float] = field(default_factory=dict)  # {metric_name: value}
    datasets: List[str] = field(default_factory=list)
    details: Dict = field(default_factory=dict)  # 原始 JSON 数据


@dataclass
class ComparisonData:
    """SOTA 对比数据（表格形式）"""
    title: str
    methods: List[str] = field(default_factory=list)
    datasets: List[str] = field(default_factory=list)
    metrics: List[str] = field(default_factory=list)  # ["MAE", "RMSE", ...]
    values: List[List[float]] = field(default_factory=list)  # [method_idx][dataset_idx]
    best_method_per_dataset: Dict[str, str] = field(default_factory=dict)


@dataclass
class AblationData:
    """消融实验数据"""
    title: str
    components: List[str] = field(default_factory=list)  # 逐步添加的组件
    full_model: str = ""
    metrics: Dict[str, List[float]] = field(default_factory=dict)  # {metric: [values_per_component]}
    best_config: str = ""


@dataclass
class AvailableImage:
    """已有的可视化图片"""
    path: str
    description: str = ""
    image_type: str = ""  # heatmap / histogram / curve / grid / comparison


@dataclass
class ExperimentSummary:
    """实验数据汇总"""
    project_path: str = ""
    available_results: List[ExperimentResult] = field(default_factory=list)
    comparison_data: Optional[ComparisonData] = None
    ablation_data: Optional[AblationData] = None
    available_images: List[AvailableImage] = field(default_factory=list)
    missing_data: List[str] = field(default_factory=list)
    recommended_figures: List[Dict] = field(default_factory=list)


def explore_experiments(project_path: str) -> ExperimentSummary:
    """
    探索目标项目的实验数据。

    Args:
        project_path: 项目根目录路径

    Returns:
        ExperimentSummary 汇总
    """
    summary = ExperimentSummary(project_path=project_path)

    if not os.path.isdir(project_path):
        logger.error(f"[ExpExplorer] 项目路径不存在: {project_path}")
        summary.missing_data.append(f"Project path does not exist: {project_path}")
        return summary

    logger.info(f"[ExpExplorer] 开始探索: {project_path}")

    # 1. 扫描 results.json 文件
    results = _scan_results_json(project_path)
    summary.available_results = results

    # 2. 扫描已有图片
    images = _scan_available_images(project_path)
    summary.available_images = images

    # 3. 尝试读取实验历史数据库
    db_results = _scan_experiment_db(project_path)
    results.extend(db_results)

    # 4. 分析并构建对比数据
    summary.comparison_data = _build_comparison_data(results)

    # 5. 分析消融数据
    summary.ablation_data = _build_ablation_data(results)

    # 6. 生成推荐图表
    summary.recommended_figures = _recommend_figures(summary)

    # 7. 记录缺失数据
    summary.missing_data = _identify_missing(summary)

    logger.info(
        f"[ExpExplorer] 探索完成: "
        f"{len(summary.available_results)} 个实验结果, "
        f"{len(summary.available_images)} 张已有图片, "
        f"{len(summary.recommended_figures)} 个推荐图表"
    )
    return summary


# ═══════════════════════════════════════════════════════════════
# 扫描工具
# ═══════════════════════════════════════════════════════════════

def _scan_results_json(project_path: str) -> List[ExperimentResult]:
    """扫描 outputs/ 和 workspace/ 下的 results.json"""
    results = []
    search_dirs = [
        os.path.join(project_path, "outputs"),
        os.path.join(project_path, "workspace"),
        os.path.join(project_path, "results"),
    ]

    for base_dir in search_dirs:
        if not os.path.isdir(base_dir):
            continue
        for root, dirs, files in os.walk(base_dir):
            for fname in files:
                if fname.endswith(".json") and ("result" in fname.lower() or "metric" in fname.lower()):
                    fpath = os.path.join(root, fname)
                    result = _parse_result_json(fpath)
                    if result:
                        results.append(result)

    return results


def _parse_result_json(fpath: str) -> Optional[ExperimentResult]:
    """解析单个 results.json"""
    try:
        with open(fpath, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        logger.debug(f"[ExpExplorer] 无法解析 {fpath}: {e}")
        return None

    exp_name = os.path.basename(os.path.dirname(fpath))
    if exp_name in ("outputs", "workspace", "results", ""):
        exp_name = os.path.splitext(os.path.basename(fpath))[0]

    # 提取指标
    metrics = _extract_metrics(data)
    if not metrics:
        return None

    return ExperimentResult(
        experiment_name=exp_name,
        metrics=metrics,
        details=data,
    )


def _extract_metrics(data, prefix="") -> Dict[str, float]:
    """递归提取数值指标"""
    metrics = {}
    if isinstance(data, dict):
        for k, v in data.items():
            key = f"{prefix}.{k}" if prefix else k
            if isinstance(v, (int, float)):
                metrics[key] = float(v)
            elif isinstance(v, dict):
                metrics.update(_extract_metrics(v, key))
            elif isinstance(v, list) and v and isinstance(v[0], (int, float)):
                # 列表的统计摘要
                metrics[f"{key}_mean"] = sum(v) / len(v)
                metrics[f"{key}_min"] = min(v)
                metrics[f"{key}_max"] = max(v)
    return metrics


def _scan_available_images(project_path: str) -> List[AvailableImage]:
    """扫描已有的可视化图片"""
    images = []
    search_dirs = [
        os.path.join(project_path, "outputs"),
        os.path.join(project_path, "workspace"),
        os.path.join(project_path, "analysis"),
        os.path.join(project_path, "figures"),
    ]

    for base_dir in search_dirs:
        if not os.path.isdir(base_dir):
            continue
        for root, dirs, files in os.walk(base_dir):
            for fname in files:
                if fname.lower().endswith((".png", ".pdf", ".jpg")):
                    fpath = os.path.join(root, fname)
                    desc = _infer_image_description(fname, fpath)
                    img_type = _infer_image_type(fname)
                    images.append(AvailableImage(
                        path=fpath,
                        description=desc,
                        image_type=img_type,
                    ))

    return images


def _infer_image_description(fname: str, fpath: str) -> str:
    """从文件名推断图片描述"""
    name = fname.lower()
    keywords = {
        "comparison": "Method comparison chart",
        "ablation": "Ablation study chart",
        "confusion": "Confusion matrix",
        "heatmap": "Feature heatmap",
        "histogram": "Distribution histogram",
        "boxplot": "Statistical boxplot",
        "scatter": "Scatter plot",
        "curve": "Trend curve",
        "loss": "Training loss curve",
        "accuracy": "Accuracy chart",
        "mae": "MAE comparison",
        "energy_map": "Energy map visualization",
        "material": "Material analysis",
        "angular": "Angular domain analysis",
        "decomposition": "Signal decomposition",
        "defocus": "Defocus analysis",
        "depth": "Depth estimation result",
    }
    for kw, desc in keywords.items():
        if kw in name:
            return desc
    return f"Image: {fname}"


def _infer_image_type(fname: str) -> str:
    """从文件名推断图片类型"""
    name = fname.lower()
    if "heatmap" in name or "energy_map" in name:
        return "heatmap"
    if "histogram" in name or "hist" in name:
        return "histogram"
    if "curve" in name or "loss" in name or "plot" in name:
        return "curve"
    if "comparison" in name or "ablation" in name:
        return "comparison"
    if "boxplot" in name:
        return "boxplot"
    if "scatter" in name:
        return "scatter"
    return "grid"


def _scan_experiment_db(project_path: str) -> List[ExperimentResult]:
    """扫描 SQLite 实验历史数据库"""
    results = []
    db_path = os.path.join(project_path, "experiment_history.db")
    if not os.path.isfile(db_path):
        return results

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 查询所有表名
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]

        for table in tables:
            try:
                cursor.execute(f"SELECT * FROM {table} LIMIT 50")
                columns = [desc[0] for desc in cursor.description]
                for row in cursor.fetchall():
                    data = dict(zip(columns, row))
                    metrics = {}
                    for col, val in data.items():
                        if isinstance(val, (int, float)) and col not in ("id", "epoch", "cycle"):
                            metrics[col] = float(val)
                    if metrics:
                        exp_name = data.get("experiment_name", data.get("name", table))
                        results.append(ExperimentResult(
                            experiment_name=str(exp_name),
                            metrics=metrics,
                            details=data,
                        ))
            except sqlite3.Error:
                continue

        conn.close()
    except Exception as e:
        logger.warning(f"[ExpExplorer] 数据库读取失败: {e}")

    return results


# ═══════════════════════════════════════════════════════════════
# 数据构建
# ═══════════════════════════════════════════════════════════════

def _build_comparison_data(results: List[ExperimentResult]) -> Optional[ComparisonData]:
    """从实验结果中构建 SOTA 对比数据"""
    if not results:
        return None

    # 找有 MAE/MSE/RMSE 等指标的结果
    metric_keywords = ["mae", "mse", "rmse", "accuracy", "score", "loss", "bad_pix"]
    relevant = []
    for r in results:
        for mk in metric_keywords:
            if any(mk in k.lower() for k in r.metrics):
                relevant.append(r)
                break

    if not relevant:
        return None

    # 找共同指标
    all_metric_keys = set()
    for r in relevant:
        all_metric_keys.update(r.metrics.keys())

    # 选取最佳指标（通常是最小的那个）
    common_metrics = []
    for mk in metric_keywords:
        matching = [k for k in all_metric_keys if mk in k.lower()]
        if matching:
            common_metrics.append(matching[0])

    if not common_metrics:
        return None

    methods = []
    values = []
    for r in relevant[:8]:  # 最多8个方法
        methods.append(r.experiment_name)
        row = []
        for metric in common_metrics:
            row.append(r.metrics.get(metric, 0.0))
        values.append(row)

    # 找每个指标的最佳方法
    best_per_metric = {}
    for i, metric in enumerate(common_metrics):
        best_idx = min(range(len(values)), key=lambda j: values[j][i] if values[j][i] > 0 else float('inf'))
        best_per_metric[metric] = methods[best_idx]

    return ComparisonData(
        title="Performance Comparison",
        methods=methods,
        datasets=["Overall"],
        metrics=common_metrics,
        values=values,
        best_method_per_dataset=best_per_metric,
    )


def _build_ablation_data(results: List[ExperimentResult]) -> Optional[AblationData]:
    """从实验结果中构建消融数据"""
    # 查找名字中含 ablation / component / module / variant 的实验
    ablation_kw = ["ablation", "component", "variant", "without", "w/o", "no_"]
    ablation_results = []
    for r in results:
        name_lower = r.experiment_name.lower()
        if any(kw in name_lower for kw in ablation_kw):
            ablation_results.append(r)

    if not ablation_results:
        return None

    components = [r.experiment_name for r in ablation_results]

    # 找共同的 metric
    metric_keys = set.intersection(*[set(r.metrics.keys()) for r in ablation_results])
    # 优先选 MAE/MSE
    main_metric = next((k for k in metric_keys if "mae" in k.lower()), next(iter(metric_keys), None))

    metrics = {}
    if main_metric:
        metrics[main_metric] = [r.metrics.get(main_metric, 0.0) for r in ablation_results]

    best_config = ""
    if main_metric and metrics[main_metric]:
        best_idx = min(range(len(metrics[main_metric])),
                       key=lambda i: metrics[main_metric][i] if metrics[main_metric][i] > 0 else float('inf'))
        best_config = components[best_idx]

    return AblationData(
        title="Ablation Study",
        components=components,
        metrics=metrics,
        best_config=best_config,
    )


def _recommend_figures(summary: ExperimentSummary) -> List[Dict]:
    """基于探索结果推荐要生成的图表"""
    recommendations = []

    # 1. 如果有对比数据，推荐 SOTA 对比图
    if summary.comparison_data and summary.comparison_data.methods:
        recommendations.append({
            "fig_type": "comparison",
            "title": "Performance Comparison with State-of-the-Art Methods",
            "data_source": "comparison_data",
            "priority": 1,
            "chart_type": "grouped_bar",
        })

    # 2. 如果有消融数据，推荐消融图
    if summary.ablation_data and summary.ablation_data.components:
        recommendations.append({
            "fig_type": "ablation",
            "title": "Ablation Study of Key Components",
            "data_source": "ablation_data",
            "priority": 1,
            "chart_type": "bar",
        })

    # 3. 如果有热力图，推荐定性对比
    heatmap_images = [img for img in summary.available_images if img.image_type == "heatmap"]
    if len(heatmap_images) >= 3:
        recommendations.append({
            "fig_type": "qualitative",
            "title": "Qualitative Comparison of Analysis Results",
            "data_source": "available_images",
            "image_paths": [img.path for img in heatmap_images[:6]],
            "priority": 2,
        })

    # 4. 如果有训练曲线，推荐训练过程图
    curve_images = [img for img in summary.available_images if img.image_type == "curve"]
    if curve_images:
        recommendations.append({
            "fig_type": "comparison",
            "title": "Training Convergence Analysis",
            "data_source": "available_images",
            "image_paths": [img.path for img in curve_images[:4]],
            "priority": 2,
        })

    return recommendations


def _identify_missing(summary: ExperimentSummary) -> List[str]:
    """识别缺失的数据"""
    missing = []

    if not summary.available_results:
        missing.append("No experiment results (results.json) found")
    if not summary.comparison_data:
        missing.append("No SOTA comparison data available")
    if not summary.ablation_data:
        missing.append("No ablation study data available")

    comparison_images = [img for img in summary.available_images if img.image_type == "comparison"]
    if not comparison_images:
        missing.append("No comparison/visualization images found")

    return missing


# ═══════════════════════════════════════════════════════════════
# 序列化
# ═══════════════════════════════════════════════════════════════

def summary_to_dict(summary: ExperimentSummary) -> Dict:
    """将 ExperimentSummary 转为可序列化的 dict"""
    from dataclasses import asdict
    return asdict(summary)


def summary_to_json(summary: ExperimentSummary) -> str:
    """将 ExperimentSummary 序列化为 JSON"""
    return json.dumps(summary_to_dict(summary), indent=2, ensure_ascii=False)
