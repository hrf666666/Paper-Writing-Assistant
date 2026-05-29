# -*- coding: utf-8 -*-
"""
Tool: 实验数据单一数据源 (Single Source of Truth)

从工程代码/报告/消融结果中提取实验数据，构建 unified_results.json。
所有章节生成时从该文件读取数据，禁止 LLM 编造数字。
"""

import os
import re
import json
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class DataSourceManager:
    """
    实验数据单一数据源

    数据优先级：
    1. 消融实验实际运行结果 (ablation_results.json)
    2. 工程目录中的训练日志/报告 (MCP web-reader 提取)
    3. project_analyzer 提取的结构化数据
    4. [DATA-PLACEHOLDER] 标记（由用户填写）
    """

    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        self.results_path = os.path.join(output_dir, "unified_results.json")
        self._data = None

    def build_unified_results(self, project_path: str = "",
                              project_data: Dict = None) -> Dict:
        """
        构建统一实验数据文件

        Returns:
            unified_results dict
        """
        project_data = project_data or {}

        unified = {
            "datasets": [],
            "metrics": [],
            "main_results": [],
            "ablation_results": [],
            "key_findings": {},
            "source": "unknown",
            "confidence": "low",
        }

        # 策略1: 从消融实验结果读取
        ablation_path = os.path.join(self.output_dir, "ablation_results.json")
        if os.path.exists(ablation_path):
            self._merge_ablation_results(unified, ablation_path)
            unified["source"] = "ablation_run"

        # 策略2: 从 experiment_design.json 读取（project_analyzer 提取的）
        exp_design_path = os.path.join(self.output_dir, "experiment_design.json")
        if os.path.exists(exp_design_path):
            self._merge_experiment_design(unified, exp_design_path)
            if unified["source"] == "unknown":
                unified["source"] = "project_analyzer"

        # 策略3: 从已有报告/Markdown 中提取数字
        for chapter_dir in ["chapter4", "chapter5"]:
            chapter_path = os.path.join(self.output_dir, chapter_dir)
            if os.path.isdir(chapter_path):
                for fname in os.listdir(chapter_path):
                    if fname.endswith(".md"):
                        fpath = os.path.join(chapter_path, fname)
                        self._extract_numbers_from_md(unified, fpath)

        # 策略4: 从 project_data 参数补充
        if project_data:
            self._merge_project_data(unified, project_data)

        # 提取关键发现
        self._compute_key_findings(unified)

        # 评估置信度
        self._assess_confidence(unified)

        # 保存
        with open(self.results_path, "w", encoding="utf-8") as f:
            json.dump(unified, f, ensure_ascii=False, indent=2)

        self._data = unified
        logger.info(f"[DataSource] 统一数据源已构建: {unified['source']}, "
                     f"置信度: {unified['confidence']}, "
                     f"数据集: {len(unified['datasets'])}, "
                     f"主结果: {len(unified['main_results'])}")

        return unified

    def get_value(self, key_path: str, default=None) -> Any:
        """从统一数据源读取值"""
        if self._data is None:
            if os.path.exists(self.results_path):
                with open(self.results_path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
            else:
                return default

        keys = key_path.split(".")
        current = self._data
        for k in keys:
            if isinstance(current, dict) and k in current:
                current = current[k]
            else:
                return default
        return current

    def inject_data_constraint(self, prompt: str) -> str:
        """在 prompt 中注入数据约束"""
        if not self._data:
            return prompt

        # 提取关键数值
        key_numbers = []
        for finding, value in self._data.get("key_findings", {}).items():
            key_numbers.append(f"- {finding}: {value}")

        if not key_numbers:
            return prompt

        constraint = (
            "\n\n**实验数据约束（来自统一数据源，禁止修改任何数字）:**\n"
            + "\n".join(key_numbers)
            + "\n\n如果需要引用其他数字，请使用 [DATA-PLACEHOLDER: 描述] 标记。\n"
        )

        return prompt + constraint

    def load(self) -> Optional[Dict]:
        """加载已保存的数据"""
        if os.path.exists(self.results_path):
            with open(self.results_path, "r", encoding="utf-8") as f:
                self._data = json.load(f)
                return self._data
        return None

    def _merge_ablation_results(self, unified: Dict, path: str):
        """从消融实验结果合并"""
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            ablations = data if isinstance(data, list) else data.get("ablations", [])
            unified["ablation_results"] = ablations
        except Exception as e:
            logger.debug(f"读取消融结果失败: {e}")

    def _merge_experiment_design(self, unified: Dict, path: str):
        """从 experiment_design.json 合并"""
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # 数据集
            datasets = data.get("数据集", data.get("datasets", []))
            if isinstance(datasets, list):
                for ds in datasets:
                    if isinstance(ds, str):
                        unified["datasets"].append({"name": ds})
                    elif isinstance(ds, dict):
                        unified["datasets"].append(ds)

            # 指标
            metrics = data.get("评估指标", data.get("metrics", []))
            if isinstance(metrics, list):
                for m in metrics:
                    if isinstance(m, str):
                        unified["metrics"].append({
                            "name": m, "direction": "lower",
                            "unit": "",
                        })
                    elif isinstance(m, dict):
                        unified["metrics"].append(m)

            # 关键结果
            results = data.get("关键结果", data.get("key_results", {}))
            if isinstance(results, dict):
                for method, values in results.items():
                    if isinstance(values, dict):
                        entry = {"method": method}
                        entry.update(values)
                        unified["main_results"].append(entry)

        except Exception as e:
            logger.debug(f"读取 experiment_design 失败: {e}")

    def _extract_numbers_from_md(self, unified: Dict, md_path: str):
        """从 Markdown 文件中提取关键数字"""
        try:
            with open(md_path, "r", encoding="utf-8") as f:
                content = f.read()

            # 提取 MAE/RMSE/BadPix 等常见指标
            patterns = {
                "MAE": r'(?:MAE|Mean Absolute Error)[:\s=]+(\d+\.?\d*)',
                "RMSE": r'(?:RMSE|Root Mean Square Error)[:\s=]+(\d+\.?\d*)',
                "BadPix_0.01": r'(?:BadPix[^)]*0\.01[^)]*)[:\s=]+(\d+\.?\d*)',
                "BadPix_0.03": r'(?:BadPix[^)]*0\.03[^)]*)[:\s=]+(\d+\.?\d*)',
                "BadPix_0.07": r'(?:BadPix[^)]*0\.07[^)]*)[:\s=]+(\d+\.?\d*)',
            }

            for metric_name, pattern in patterns.items():
                matches = re.findall(pattern, content, re.IGNORECASE)
                if matches:
                    # 取第一个出现
                    unified["key_findings"][metric_name] = float(matches[0])

            # 提取改进百分比
            improvement = re.search(
                r'(?:improvement|improve|reduction|reduce).*?(\d+\.?\d*)\s*%',
                content, re.IGNORECASE,
            )
            if improvement:
                unified["key_findings"]["improvement_pct"] = float(improvement.group(1))

        except Exception as e:
            logger.debug(f"从 MD 提取数字失败: {e}")

    def _merge_project_data(self, unified: Dict, project_data: Dict):
        """从 project_data 参数补充"""
        exp_design = project_data.get("experiment_design", {})
        if exp_design and not unified["main_results"]:
            results = exp_design.get("关键结果", {})
            if isinstance(results, dict):
                for method, values in results.items():
                    unified["main_results"].append({"method": method, **values})

    def _compute_key_findings(self, unified: Dict):
        """计算关键发现"""
        if unified["key_findings"]:
            return

        # 从 main_results 中提取
        for result in unified["main_results"]:
            method = result.get("method", "")
            if "ours" in method.lower():
                for key, value in result.items():
                    if key != "method" and isinstance(value, (int, float)):
                        unified["key_findings"][f"our_{key}"] = value

    def _assess_confidence(self, unified: Dict):
        """评估数据置信度"""
        has_datasets = len(unified["datasets"]) > 0
        has_results = len(unified["main_results"]) > 0
        has_findings = len(unified["key_findings"]) > 0

        if has_datasets and has_results and has_findings:
            unified["confidence"] = "high"
        elif has_datasets or has_findings:
            unified["confidence"] = "medium"
        else:
            unified["confidence"] = "low"


def run_data_source_manager(output_dir: str, project_path: str = "",
                             project_data: Dict = None) -> Dict:
    """数据源管理器入口"""
    mgr = DataSourceManager(output_dir)
    return mgr.build_unified_results(project_path, project_data)
