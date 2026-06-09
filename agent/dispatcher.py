# -*- coding: utf-8 -*-
"""
Agent调度器 - Leader-Worker 分层调度模式

设计：
- Leader: 规划整体任务、分配Worker、评估结果
- Worker: 执行具体章节生成、审查等任务
- 支持动态重调度（质量不达标时调整策略）
"""

import json
import time
import logging
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, field

from agent.api_client import get_api_client, UnifiedAPIClient
from agent.memory import MemoryManager
from agent.quality_gate import QualityGate, QualityReport
from agent.hierarchical_planner import (
    HierarchicalPlan, AbstractGoal, AtomicStep, build_default_plan,
)

logger = logging.getLogger(__name__)


@dataclass
class Task:
    """调度任务"""
    task_id: str
    task_type: str       # "generate" | "review" | "refine" | "search"
    phase_name: str
    target: str          # 章节名或目标描述
    params: Dict[str, Any] = field(default_factory=dict)
    status: str = "pending"  # "pending" | "running" | "completed" | "failed"
    result: Any = None
    quality_report: Optional[Dict] = None
    retry_count: int = 0
    max_retries: int = 3


class AgentDispatcher:
    """
    Agent调度器

    Leader-Worker 模式：
    - Leader 规划任务队列
    - Worker 执行具体任务
    - Leader 评估结果，必要时重调度
    """

    def __init__(self, api_client: UnifiedAPIClient = None,
                 memory: MemoryManager = None,
                 quality_gate: QualityGate = None):
        try:
            self.api_client = api_client or get_api_client()
            self.memory = memory or MemoryManager()
            self.quality_gate = quality_gate or QualityGate(self.api_client)
        except Exception as e:
            logger.error(f"Dispatcher 初始化失败: {e}")
            raise
        self._task_queue: List[Task] = []
        self._completed_tasks: Dict[str, Task] = {}
        self._plan: Optional[HierarchicalPlan] = None  # v12.0: 分层规划
        self._max_global_retries = 3  # 全局最大重试次数

    def plan_tasks(self, project_data: Dict, ref_data: Dict,
                   venue_adapter=None) -> List[Task]:
        """
        Leader: 根据项目数据和参考资料规划任务队列

        v12.0: 使用 HierarchicalPlan 分层规划
        - 构建抽象层 Goals (G1~G5) + 执行层 AtomicSteps
        - 降级为扁平 Task 列表返回，保持 loop.py 兼容
        - 每个 Task 通过 task_id 关联到 AtomicStep

        Args:
            project_data: 项目分析数据
            ref_data: 参考PDF分析数据
            venue_adapter: VenueAdapter 实例（可选）

        Returns:
            List[Task]: 任务队列（从 HierarchicalPlan 扁平展开）
        """
        self._task_queue.clear()

        # 构建分层规划
        self._plan = build_default_plan(venue_adapter=venue_adapter)

        # 从分层规划展开为扁平 Task 列表
        for goal in self._plan.goals:
            for step in goal.steps:
                self._task_queue.append(Task(
                    task_id=step.task_id or step.step_id,
                    task_type="generate",  # 统一为 generate，loop.py 按 phase 分发
                    phase_name=step.phase_name,
                    target=step.description,
                ))

        # 保存分层规划到文件（便于调试和 Phase 8.8 验收）
        try:
            import os
            from config.project_config import OUTPUT_DIR
            plan_path = os.path.join(OUTPUT_DIR, "hierarchical_plan.json")
            os.makedirs(OUTPUT_DIR, exist_ok=True)
            with open(plan_path, "w", encoding="utf-8") as f:
                json.dump(self._plan.to_dict(), f, ensure_ascii=False, indent=2)
            logger.info(f"分层规划已保存: {plan_path}")
        except Exception as e:
            logger.debug(f"分层规划保存失败（不影响执行）: {e}")

        logger.info(f"任务规划完成，共 {len(self._task_queue)} 个任务 "
                     f"({len(self._plan.goals)} 个 Goals)")
        return self._task_queue

    def get_plan(self) -> Optional[HierarchicalPlan]:
        """获取当前分层规划"""
        return self._plan

    def update_step_status(self, phase_name: str, status: str, actual_value=None):
        """更新 AtomicStep 的状态（loop.py 每个 phase 完成后调用）"""
        if not self._plan:
            return
        step = self._plan.get_step_by_phase(phase_name)
        if step:
            step.status = status
            if actual_value is not None:
                step.actual_value = actual_value

    def get_next_task(self) -> Optional[Task]:
        """获取下一个待执行的任务"""
        for task in self._task_queue:
            if task.status == "pending":
                return task
        return None

    def mark_task_running(self, task: Task):
        """标记任务为运行中"""
        task.status = "running"
        self.memory.add_log("log", f"开始执行任务: {task.task_id} - {task.target}")

    def mark_task_completed(self, task: Task, result: Any, quality_report: QualityReport = None):
        """标记任务为已完成"""
        try:
            task.status = "completed"
            task.result = result
            if quality_report:
                task.quality_report = quality_report.to_dict()
                task.quality_report["overall_score"] = quality_report.overall_score
            self._completed_tasks[task.task_id] = task
            score_str = f"{quality_report.overall_score}" if quality_report else "N/A"
            self.memory.add_log("log", f"任务完成: {task.task_id}, 质量: {score_str}")
        except Exception as e:
            logger.error(f"标记任务完成时出错 ({task.task_id}): {e}")
            task.status = "completed"
            task.result = result
            self._completed_tasks[task.task_id] = task

    def mark_task_failed(self, task: Task, error: str):
        """标记任务为失败"""
        task.status = "failed"
        task.result = error
        task.retry_count += 1
        self.memory.add_log("error", f"任务失败: {task.task_id}, 原因: {error[:200]}")

    def should_retry_task(self, task: Task, quality_report: QualityReport = None) -> bool:
        """
        判断任务是否需要重试

        综合考虑：
        1. 质量门控评估结果
        2. 重试次数限制
        3. 是否是已确认的死路
        """
        try:
            # 重试次数限制
            if task.retry_count >= task.max_retries:
                logger.info(f"任务 {task.task_id} 已达最大重试次数({task.max_retries})")
                return False

            # 死路检查
            if self.memory.is_dead_end(f"{task.task_id}:{task.retry_count}"):
                logger.info(f"任务 {task.task_id} 的重试策略已被确认为死路")
                return False

            # 质量评估
            if quality_report:
                return self.quality_gate.should_retry(quality_report, task.retry_count)

            # 执行失败时默认重试
            return task.status == "failed"
        except Exception as e:
            logger.warning(f"判断重试策略时出错 ({task.task_id}): {e}")
            return False

    def reschedule_task(self, task: Task, strategy: str = "retry"):
        """
        重新调度任务

        Args:
            task: 需要重调度的任务
            strategy: 重调度策略 ("retry" | "revise" | "regenerate")

        注意: retry_count 不在此处增加，由 mark_task_failed 统一管理
        """
        try:
            task.status = "pending"
            task.params["strategy"] = strategy

            # 将任务重新插入队列头部（用 task_id 查找避免 dataclass 值相等问题）
            existing_idx = None
            for i, t in enumerate(self._task_queue):
                if t.task_id == task.task_id:
                    existing_idx = i
                    break

            if existing_idx is not None:
                # 已在队列中，移到头部
                self._task_queue.pop(existing_idx)
                self._task_queue.insert(0, task)
            else:
                # 不在队列中，插入头部
                self._task_queue.insert(0, task)

            self.memory.add_log("decision",
                               f"重调度任务: {task.task_id}, 策略: {strategy}, 第{task.retry_count}次重试")
        except Exception as e:
            logger.error(f"重调度任务时出错 ({task.task_id}): {e}")
            task.status = "pending"

    def get_all_tasks(self) -> List[Task]:
        """获取所有任务的副本列表"""
        return list(self._task_queue)

    def skip_task_by_name(self, target: str):
        """v11.8: 根据名称跳过任务 — 精确匹配 task_id 或 phase_name，避免子串误杀"""
        target_lower = target.lower().strip()
        for task in self._task_queue:
            # 精确匹配 task_id（如 "generate_chapter1"）或 phase_name（如 "phase1"）
            if (task.task_id.lower() == target_lower
                    or task.phase_name.lower() == target_lower):
                task.status = "completed"
                logger.info(f"[directive] 跳过阶段: {task.target}")

    def redo_task_by_name(self, target: str):
        """v11.8: 根据名称重做任务 — 精确匹配 task_id 或 phase_name"""
        target_lower = target.lower().strip()
        for task in self._task_queue:
            if (task.task_id.lower() == target_lower
                    or task.phase_name.lower() == target_lower):
                task.status = "pending"
                task.retry_count = 0
                logger.info(f"[directive] 重做阶段: {task.target}")

    def get_progress(self) -> Dict[str, Any]:
        """获取执行进度"""
        total = len(self._task_queue)
        completed = sum(1 for t in self._task_queue if t.status == "completed")
        failed = sum(1 for t in self._task_queue if t.status == "failed")
        pending = sum(1 for t in self._task_queue if t.status == "pending")
        running = sum(1 for t in self._task_queue if t.status == "running")

        return {
            "total": total,
            "completed": completed,
            "failed": failed,
            "pending": pending,
            "running": running,
            "progress_pct": (completed / total * 100) if total > 0 else 0,
        }
