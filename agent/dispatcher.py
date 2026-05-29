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
        self._max_global_retries = 3  # 全局最大重试次数

    def plan_tasks(self, project_data: Dict, ref_data: Dict,
                   venue_adapter=None) -> List[Task]:
        """
        Leader: 根据项目数据和参考资料规划任务队列

        v7.0: 新增 Phase 0.1~0.5 子流程（动机→范例→引用→写作矩阵→消融）
              根据 venue_adapter 动态决定是否启用各子流程。

        Args:
            project_data: 项目分析数据
            ref_data: 参考PDF分析数据
            venue_adapter: VenueAdapter 实例（可选）

        Returns:
            List[Task]: 任务队列
        """
        self._task_queue.clear()

        # 读取 v7.0 功能开关
        try:
            from config.project_config import (
                ENABLE_MOTIVATION_ENGINE, ENABLE_EXEMPLAR_LEARNING,
                ENABLE_RATIONALE_MATRIX, RUN_ABLATION,
            )
        except ImportError as e:
            logger.warning(f"加载 v7.0 功能开关失败，使用默认值: {e}")
            ENABLE_MOTIVATION_ENGINE = False
            ENABLE_EXEMPLAR_LEARNING = False
            ENABLE_RATIONALE_MATRIX = False
            RUN_ABLATION = False

        # Phase 0: 分析
        self._task_queue.append(Task(
            task_id="analyze_project",
            task_type="generate",
            phase_name="phase0",
            target="分析工程代码与参考PDF",
        ))

        # Phase 0.5: 参考文献池 + 大纲（在 loop._initialize_project_data 中执行）
        self._task_queue.append(Task(
            task_id="plan_outline",
            task_type="generate",
            phase_name="phase0_5",
            target="参考文献池构建+全局大纲规划",
        ))

        # ---- v7.0 子流程阶段（可配置开关） ----

        # Phase 0.6: 动机确认
        if ENABLE_MOTIVATION_ENGINE:
            self._task_queue.append(Task(
                task_id="motivation_confirm",
                task_type="generate",
                phase_name="phase0_6",
                target="动机确认与动机线程构建",
            ))

        # Phase 0.7: 范例学习
        if ENABLE_EXEMPLAR_LEARNING:
            self._task_queue.append(Task(
                task_id="exemplar_analysis",
                task_type="generate",
                phase_name="phase0_7",
                target="深度范例学习（6层阅读协议）",
            ))

        # Phase 0.8: 引用支撑库
        self._task_queue.append(Task(
            task_id="citation_bank",
            task_type="generate",
            phase_name="phase0_8",
            target="引用支撑库构建（claim级引用管理）",
        ))

        # Phase 0.9: 写作理由矩阵
        if ENABLE_RATIONALE_MATRIX:
            self._task_queue.append(Task(
                task_id="rationale_matrix",
                task_type="generate",
                phase_name="phase0_9",
                target="写作理由矩阵（事前规划型）",
            ))

        # Phase 0.95: 消融实验自动化
        if RUN_ABLATION:
            self._task_queue.append(Task(
                task_id="ablation_experiment",
                task_type="generate",
                phase_name="phase0_95",
                target="消融实验自动化（调用auto_research_agent）",
            ))

        # ---- 核心章节生成（动态适配 venue） ----
        sections = [
            ("phase1", "Introduction", "chapter1"),
            ("phase2", "Related Work", "chapter2"),
            ("phase3", "Methodology", "chapter3"),
            ("phase4", "Experiments", "chapter4"),
            ("phase5", "Conclusion", "chapter5"),
        ]

        # 如果 venue 有额外章节（如 Discussion），动态追加
        extra_section_map = {
            "Discussion": ("phase5_1", "Discussion", "chapter5_1"),
            "Limitations and Future Work": ("phase5_2", "Limitations and Future Work", "chapter5_2"),
        }
        if venue_adapter:
            for extra_sec in venue_adapter.get_extra_sections():
                if extra_sec in extra_section_map:
                    sections.append(extra_section_map[extra_sec])

        for phase_name, chapter_name, task_id in sections:
            self._task_queue.append(Task(
                task_id=f"generate_{task_id}",
                task_type="generate",
                phase_name=phase_name,
                target=chapter_name,
            ))

        # Phase 5.5: 生成摘要和关键词
        self._task_queue.append(Task(
            task_id="generate_abstract",
            task_type="generate",
            phase_name="phase5_5",
            target="Abstract & Keywords",
        ))

        # Phase 6: 审查
        self._task_queue.append(Task(
            task_id="review_content",
            task_type="review",
            phase_name="phase6",
            target="内容审查与参考文献审查",
        ))

        # Phase 6.5: 反幻觉审计
        self._task_queue.append(Task(
            task_id="audit_content",
            task_type="review",
            phase_name="phase6_5",
            target="反幻觉审计：逐步验证+参考文献反向检索+内容真实性校验",
        ))

        # Phase 7: 输出
        self._task_queue.append(Task(
            task_id="generate_output",
            task_type="generate",
            phase_name="phase7",
            target="生成LaTeX/Word输出",
        ))

        logger.info(f"任务规划完成，共 {len(self._task_queue)} 个任务")
        return self._task_queue

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
        """根据名称跳过任务（将匹配任务标记为 completed）"""
        target_lower = target.lower()
        for task in self._task_queue:
            if target_lower in task.phase_name.lower() or target_lower in task.target.lower():
                task.status = "completed"
                logger.info(f"[directive] 跳过阶段: {task.target}")

    def redo_task_by_name(self, target: str):
        """根据名称重做任务（将匹配任务重置为 pending）"""
        target_lower = target.lower()
        for task in self._task_queue:
            if target_lower in task.phase_name.lower() or target_lower in task.target.lower():
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
