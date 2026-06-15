# -*- coding: utf-8 -*-
"""
FactBase —— 全系统唯一事实源 (v13 PR2)

替代旧 PaperContext 的写读分裂问题：
- 旧：loop._build_paper_context 写 output/paper_context.json，
      hierarchical_planner._read_paper_context_exists 读同路径，
      auditor/verifier 却各自从 project_data 重新推导 → 数值分歧。
- 新：FactBase 是唯一事实源。构建一次，多处只读。

设计：
- dataclass + 明确字段，而非松散 dict
- 持久化保证：build() 成功必然落盘（失败抛 PermanentError，不静默）
- 读 API：load() / get_metric() / as_fact_sheet() / exists()
- 写 API：build_from_project_data() 一次性构建
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# 持久化文件名（全系统约定，验收器/生成器/检查器都读这个）
FACTBASE_FILENAME = "factbase.json"


@dataclass
class FactBase:
    """全系统唯一事实源。

    所有验证/修复读这里，不读 project_data 原文。
    数值矛盾修复（cross_chapter_checker）以 metrics 为权威。
    """
    hardware: str = ""
    training_params: Dict[str, Any] = field(default_factory=dict)
    loss_terms: List[str] = field(default_factory=list)
    datasets: List[str] = field(default_factory=list)
    metrics: Dict[str, float] = field(default_factory=dict)   # {MAE: 0.133, ...} 权威数值
    model_name: str = ""
    innovation_names: List[str] = field(default_factory=list)
    # 兼容旧字段（paper_context 的同义）
    paper_title: str = ""

    # ── 查询 API ──

    def get_metric(self, name: str, default: Optional[float] = None) -> Optional[float]:
        """读取权威数值。大小写不敏感，去空白。"""
        if not self.metrics:
            return default
        name_norm = name.strip().lower()
        for k, v in self.metrics.items():
            if k.strip().lower() == name_norm:
                try:
                    return float(v)
                except (TypeError, ValueError):
                    return default
        return default

    def find_metric_value(self, value: float, rel_tol: float = 0.01) -> Optional[str]:
        """反向查询：给定一个数值，找它在 metrics 里对应的指标名。

        用于 cross_chapter_checker 判断一个数是否是"我们的权威结果"。
        rel_tol: 相对容差（默认 1%）。
        """
        try:
            v = float(value)
        except (TypeError, ValueError):
            return None
        for k, mv in self.metrics.items():
            try:
                mvf = float(mv)
            except (TypeError, ValueError):
                continue
            if mvf == 0:
                if v == 0:
                    return k
                continue
            if abs(v - mvf) / abs(mvf) <= rel_tol:
                return k
        return None

    def as_fact_sheet(self) -> str:
        """渲染为可注入 prompt 的"事实清单"文本（紧凑）。"""
        lines = ["<fact_base>  # 以下为权威事实，正文数值必须与此一致"]
        if self.model_name:
            lines.append(f"model: {self.model_name}")
        if self.hardware:
            lines.append(f"hardware: {self.hardware}")
        if self.training_params:
            tp = ", ".join(f"{k}={v}" for k, v in self.training_params.items())
            lines.append(f"training: {tp}")
        if self.datasets:
            lines.append(f"datasets: {', '.join(self.datasets)}")
        if self.loss_terms:
            lines.append(f"loss_terms: {', '.join(self.loss_terms)}")
        if self.metrics:
            ms = ", ".join(f"{k}={v}" for k, v in self.metrics.items())
            lines.append(f"metrics (Ours 权威值): {ms}")
        if self.innovation_names:
            lines.append(f"innovations: {', '.join(self.innovation_names)}")
        lines.append("</fact_base>")
        return "\n".join(lines)

    def is_empty(self) -> bool:
        """是否实质为空（无任何有效事实）。"""
        return not any([self.hardware, self.training_params, self.loss_terms,
                        self.datasets, self.metrics, self.model_name,
                        self.innovation_names])

    # ── 序列化 ──

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "FactBase":
        # 容忍多余字段（向前兼容 paper_context 的旧结构）
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in (d or {}).items() if k in known})

    @classmethod
    def from_paper_context(cls, pc: Dict[str, Any]) -> "FactBase":
        """从旧 paper_context dict 构造（迁移用）。"""
        return cls.from_dict(pc or {})


# ──────────────────────────────────────────────────────────────
# 持久化（保证落盘，失败抛错而非静默）
# ──────────────────────────────────────────────────────────────

def save(factbase: FactBase, output_dir: str) -> str:
    """持久化到 {output_dir}/factbase.json。失败抛 IOError（调用方决定降级）。"""
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, FACTBASE_FILENAME)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(factbase.to_dict(), f, ensure_ascii=False, indent=2)
    # 同时写一份 paper_context.json 兼容旧验收器（_read_paper_context_exists 读它）
    legacy = os.path.join(output_dir, "paper_context.json")
    try:
        with open(legacy, "w", encoding="utf-8") as f:
            json.dump(factbase.to_dict(), f, ensure_ascii=False, indent=2)
    except OSError as e:
        logger.warning(f"[FactBase] 兼容旧 paper_context.json 写入失败: {e}")
    logger.info(f"[FactBase] 已持久化: {path}")
    return path


def load(output_dir: str) -> Optional[FactBase]:
    """从磁盘加载。不存在返回 None。"""
    path = os.path.join(output_dir, FACTBASE_FILENAME)
    if not os.path.exists(path):
        # 降级读旧 paper_context.json
        legacy = os.path.join(output_dir, "paper_context.json")
        if os.path.exists(legacy):
            path = legacy
        else:
            return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return FactBase.from_dict(json.load(f))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"[FactBase] 加载失败 {path}: {e}")
        return None


def exists(output_dir: str) -> bool:
    """验收器用：factbase.json 或 paper_context.json 任一存在且非空。"""
    for fn in (FACTBASE_FILENAME, "paper_context.json"):
        p = os.path.join(output_dir, fn)
        if os.path.exists(p) and os.path.getsize(p) > 10:
            return True
    return False


# ──────────────────────────────────────────────────────────────
# 构建（从 project_data 一次性提取，替代旧 _build_paper_context）
# ──────────────────────────────────────────────────────────────

def build_from_project_data(project_data: Dict[str, Any],
                             ablation_results: Optional[Dict] = None) -> FactBase:
    """从 project_data + experiment_design + ablation_results 提取权威事实。

    与旧 _build_paper_context 的提取逻辑等价，但返回 FactBase dataclass，
    并保证字段类型规范（metrics 统一为 float）。
    """
    pd = project_data or {}
    exp_design = pd.get("experiment_design", {}) or {}
    ablation = ablation_results or {}

    # hardware
    hardware = ""
    proj_info = pd.get("project_info", {}) or {}
    if isinstance(proj_info, dict):
        hardware = str(proj_info.get("hardware", "") or "")

    # training_params
    training_params: Dict[str, Any] = {}
    tp_raw = exp_design.get("训练参数", exp_design.get("training_params", {}))
    if isinstance(tp_raw, dict):
        training_params = dict(list(tp_raw.items())[:8])

    # loss_terms
    loss_terms: List[str] = []
    lt_raw = exp_design.get("损失函数", exp_design.get("loss_terms", []))
    if isinstance(lt_raw, list):
        loss_terms = [str(x) for x in lt_raw][:10]
    elif isinstance(lt_raw, dict):
        loss_terms = list(lt_raw.keys())[:10]

    # datasets
    datasets: List[str] = []
    ds_raw = exp_design.get("数据集", exp_design.get("datasets", []))
    if isinstance(ds_raw, list):
        datasets = [str(x) for x in ds_raw][:8]

    # metrics（权威数值，统一 float）
    metrics: Dict[str, float] = {}
    kr = exp_design.get("关键结果", exp_design.get("key_results", {}))
    if isinstance(kr, dict):
        for k, v in list(kr.items())[:10]:
            try:
                metrics[str(k)] = float(v)
            except (TypeError, ValueError):
                continue
    # 消融结果里的 Ours 最佳值也并入（作为兜底权威源）
    if isinstance(ablation, dict):
        best = ablation.get("best_results", ablation.get("ours", {}))
        if isinstance(best, dict):
            for k, v in list(best.items())[:8]:
                try:
                    if str(k) not in metrics:
                        metrics[str(k)] = float(v)
                except (TypeError, ValueError):
                    continue

    # model_name
    model_name = ""
    arch = pd.get("model_architecture", {}) or {}
    if isinstance(arch, dict):
        model_name = str(arch.get("模型名称", arch.get("model_name", "")) or "")

    # innovation_names
    innovation_names: List[str] = []
    inn = pd.get("innovation_points", []) or []
    if isinstance(inn, list):
        for ip in inn[:8]:
            if isinstance(ip, dict):
                name = ip.get("创新点名称", ip.get("name", ""))
                if name:
                    innovation_names.append(str(name))

    fb = FactBase(
        hardware=hardware,
        training_params=training_params,
        loss_terms=loss_terms,
        datasets=datasets,
        metrics=metrics,
        model_name=model_name,
        innovation_names=innovation_names,
    )
    logger.info(f"[FactBase] 构建完成: model={model_name or 'N/A'}, "
                f"metrics={list(metrics.keys())}, datasets={datasets}, "
                f"loss_terms={len(loss_terms)}, innovations={len(innovation_names)}")
    return fb
