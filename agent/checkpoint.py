# -*- coding: utf-8 -*-
"""
检查点管理器 - 状态持久化与断点恢复

特性：
1. 每个Phase完成后自动保存检查点
2. 支持从任意Phase恢复执行
3. 增量保存，避免全量序列化
"""

import json
import time
import os
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict

from config.project_config import OUTPUT_DIR

logger = logging.getLogger(__name__)


@dataclass
class PhaseCheckpoint:
    """阶段检查点"""
    phase_name: str
    phase_index: int
    timestamp: float
    status: str          # "completed" | "failed" | "skipped"
    output_files: List[str]
    error_message: str = ""
    duration_seconds: float = 0.0
    quality_score: float = -1.0  # -1 表示未评估

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "PhaseCheckpoint":
        # 确保 phase_index 从 JSON 恢复后为 int
        if 'phase_index' in d:
            d['phase_index'] = int(d['phase_index'])
        if 'quality_score' in d:
            d['quality_score'] = float(d['quality_score'])
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


class CheckpointManager:
    """
    检查点管理器

    管理流水线各阶段的执行状态，支持：
    1. 自动保存每阶段完成后的状态
    2. 崩溃后从最后成功的检查点恢复
    3. 跳过已完成的阶段
    """

    def __init__(self, output_dir: str = None):
        self.output_dir = output_dir or OUTPUT_DIR
        self.checkpoint_dir = os.path.join(self.output_dir, ".checkpoints")
        self._checkpoints: Dict[str, PhaseCheckpoint] = {}
        self._state_data: Dict[str, Any] = {}  # 阶段间共享状态

    def save_checkpoint(self, phase_name: str, phase_index: int,
                        status: str = "completed", output_files: List[str] = None,
                        error_message: str = "", duration_seconds: float = 0.0,
                        quality_score: float = -1.0):
        """
        保存阶段检查点
        """
        checkpoint = PhaseCheckpoint(
            phase_name=phase_name,
            phase_index=phase_index,
            timestamp=time.time(),
            status=status,
            output_files=output_files or [],
            error_message=error_message,
            duration_seconds=duration_seconds,
            quality_score=quality_score,
        )

        self._checkpoints[phase_name] = checkpoint
        self._persist()
        logger.info(f"检查点已保存: {phase_name} ({status})")

    def is_phase_completed(self, phase_name: str) -> bool:
        """检查阶段是否已完成"""
        cp = self._checkpoints.get(phase_name)
        return cp is not None and cp.status == "completed"

    def get_last_completed_phase(self) -> Optional[str]:
        """获取最后一个成功完成的阶段名"""
        completed = [
            (cp.phase_index, cp.phase_name)
            for cp in self._checkpoints.values()
            if cp.status == "completed"
        ]
        if not completed:
            return None
        completed.sort(key=lambda x: x[0])
        return completed[-1][1]

    def get_failed_phases(self) -> List[str]:
        """获取所有失败的阶段"""
        return [
            name for name, cp in self._checkpoints.items()
            if cp.status == "failed"
        ]

    def save_state(self, key: str, value: Any):
        """保存阶段间共享状态数据"""
        self._state_data[key] = value

    def get_state(self, key: str, default: Any = None) -> Any:
        """获取阶段间共享状态数据"""
        return self._state_data.get(key, default)

    def _persist(self):
        """持久化所有检查点到磁盘"""
        os.makedirs(self.checkpoint_dir, exist_ok=True)

        state = {
            "checkpoints": {k: v.to_dict() for k, v in self._checkpoints.items()},
            "state_data_keys": list(self._state_data.keys()),
        }

        # 保存检查点索引
        with open(os.path.join(self.checkpoint_dir, "index.json"), 'w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False, indent=2)

        # 保存共享状态数据（每个key独立文件，避免大文件序列化问题）
        state_dir = os.path.join(self.checkpoint_dir, "state")
        os.makedirs(state_dir, exist_ok=True)
        for key, value in self._state_data.items():
            safe_key = key.replace("/", "_").replace("\\", "_")
            filepath = os.path.join(state_dir, f"{safe_key}.json")
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(value, f, ensure_ascii=False, indent=2)
            except (TypeError, ValueError) as e:
                logger.warning(f"无法序列化状态 {key}: {e}")

    def load(self) -> bool:
        """从磁盘加载检查点"""
        index_path = os.path.join(self.checkpoint_dir, "index.json")
        if not os.path.exists(index_path):
            return False

        try:
            with open(index_path, 'r', encoding='utf-8') as f:
                state = json.load(f)

            # 恢复检查点
            for name, cp_dict in state.get("checkpoints", {}).items():
                self._checkpoints[name] = PhaseCheckpoint.from_dict(cp_dict)

            # 恢复共享状态
            state_dir = os.path.join(self.checkpoint_dir, "state")
            for key in state.get("state_data_keys", []):
                safe_key = key.replace("/", "_").replace("\\", "_")
                filepath = os.path.join(state_dir, f"{safe_key}.json")
                if os.path.exists(filepath):
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            self._state_data[key] = json.load(f)
                    except Exception as e:
                        logger.warning(f"加载状态 {key} 失败: {e}")

            logger.info(f"检查点已加载: {len(self._checkpoints)} 个阶段, {len(self._state_data)} 个状态")
            return True
        except Exception as e:
            logger.error(f"加载检查点失败: {e}")
            return False

    def get_completed_phases(self) -> List[str]:
        """获取所有已完成阶段的名称列表"""
        return [
            name for name, cp in self._checkpoints.items()
            if cp.status == "completed"
        ]

    def clear(self):
        """清空所有检查点（内存+磁盘）"""
        self._checkpoints.clear()
        self._state_data.clear()
        # 同时清理磁盘文件
        if os.path.exists(self.checkpoint_dir):
            import shutil
            try:
                shutil.rmtree(self.checkpoint_dir)
                logger.info(f"已清空检查点目录: {self.checkpoint_dir}")
            except Exception as e:
                logger.warning(f"清空检查点目录失败: {e}")

    def get_summary(self) -> str:
        """获取检查点摘要（用于日志输出）"""
        lines = ["检查点摘要:"]
        def _safe_phase_index(item):
            """phase_index 从 JSON 恢复后可能是字符串，统一转为 int"""
            val = item[1].phase_index
            try:
                return int(val)
            except (TypeError, ValueError):
                return 0
        for name, cp in sorted(self._checkpoints.items(), key=_safe_phase_index):
            status_icon = "✓" if cp.status == "completed" else "✗" if cp.status == "failed" else "○"
            duration = f"{cp.duration_seconds:.0f}s" if cp.duration_seconds > 0 else "-"
            quality = f"Q={cp.quality_score:.1f}" if cp.quality_score >= 0 else ""
            lines.append(f"  {status_icon} [{cp.phase_index}] {name} - {cp.status} ({duration}) {quality}")
        return "\n".join(lines)
