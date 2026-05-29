# -*- coding: utf-8 -*-
"""
测试 agent/dispatcher.py - 任务调度器
"""

import pytest
from unittest.mock import MagicMock, patch

from agent.dispatcher import Task, AgentDispatcher


class TestTask:
    """测试 Task 数据类"""

    def test_task_creation_defaults(self):
        task = Task(
            task_id="t1",
            task_type="generate",
            phase_name="phase1",
            target="Introduction",
        )
        assert task.task_id == "t1"
        assert task.task_type == "generate"
        assert task.phase_name == "phase1"
        assert task.target == "Introduction"
        assert task.params == {}
        assert task.status == "pending"
        assert task.result is None
        assert task.quality_report is None
        assert task.retry_count == 0
        assert task.max_retries == 3

    def test_task_custom_params(self):
        task = Task(
            task_id="t2",
            task_type="review",
            phase_name="phase2",
            target="Methodology",
            params={"key": "val"},
            max_retries=5,
        )
        assert task.params == {"key": "val"}
        assert task.max_retries == 5

    def test_task_status_transitions(self):
        task = Task(task_id="t", task_type="generate", phase_name="p", target="x")
        assert task.status == "pending"

        task.status = "running"
        assert task.status == "running"

        task.status = "completed"
        assert task.status == "completed"

        task.status = "failed"
        assert task.status == "failed"


class TestAgentDispatcher:
    """测试 AgentDispatcher"""

    def _make_dispatcher(self):
        """创建一个 mock 依赖的 Dispatcher"""
        mock_api = MagicMock()
        mock_memory = MagicMock()
        mock_quality = MagicMock()
        return AgentDispatcher(
            api_client=mock_api,
            memory=mock_memory,
            quality_gate=mock_quality,
        )

    def test_init(self):
        disp = self._make_dispatcher()
        assert disp._task_queue == []
        assert disp._completed_tasks == {}

    def test_plan_tasks_returns_list(self):
        disp = self._make_dispatcher()
        tasks = disp.plan_tasks({}, {})
        assert isinstance(tasks, list)
        assert len(tasks) > 0

    def test_plan_tasks_contains_core_phases(self):
        disp = self._make_dispatcher()
        with patch.dict("sys.modules", {}):
            tasks = disp.plan_tasks({}, {})

        task_ids = [t.task_id for t in tasks]
        assert "analyze_project" in task_ids
        assert "generate_chapter1" in task_ids
        assert "generate_chapter2" in task_ids
        assert "generate_chapter3" in task_ids
        assert "generate_chapter4" in task_ids
        assert "generate_chapter5" in task_ids
        assert "review_content" in task_ids
        assert "generate_output" in task_ids

    def test_plan_tasks_all_pending(self):
        disp = self._make_dispatcher()
        tasks = disp.plan_tasks({}, {})
        assert all(t.status == "pending" for t in tasks)

    def test_get_next_task(self):
        disp = self._make_dispatcher()
        disp._task_queue = [
            Task(task_id="t1", task_type="g", phase_name="p1", target="a", status="completed"),
            Task(task_id="t2", task_type="g", phase_name="p2", target="b", status="pending"),
            Task(task_id="t3", task_type="g", phase_name="p3", target="c", status="pending"),
        ]
        next_task = disp.get_next_task()
        assert next_task.task_id == "t2"

    def test_get_next_task_none_when_all_done(self):
        disp = self._make_dispatcher()
        disp._task_queue = [
            Task(task_id="t1", task_type="g", phase_name="p1", target="a", status="completed"),
            Task(task_id="t2", task_type="g", phase_name="p2", target="b", status="completed"),
        ]
        assert disp.get_next_task() is None

    def test_get_next_task_none_when_empty(self):
        disp = self._make_dispatcher()
        assert disp.get_next_task() is None

    def test_mark_task_running(self):
        disp = self._make_dispatcher()
        task = Task(task_id="t1", task_type="g", phase_name="p1", target="a")
        disp.mark_task_running(task)
        assert task.status == "running"

    def test_mark_task_completed(self):
        disp = self._make_dispatcher()
        task = Task(task_id="t1", task_type="g", phase_name="p1", target="a")
        disp.mark_task_completed(task, result="generated content")
        assert task.status == "completed"
        assert task.result == "generated content"
        assert "t1" in disp._completed_tasks

    def test_mark_task_completed_with_quality_report(self):
        disp = self._make_dispatcher()
        task = Task(task_id="t1", task_type="g", phase_name="p1", target="a")

        mock_report = MagicMock()
        mock_report.overall_score = 85.0
        mock_report.to_dict.return_value = {"passed": True, "overall_score": 85.0}

        disp.mark_task_completed(task, result="content", quality_report=mock_report)
        assert task.quality_report["overall_score"] == 85.0

    def test_mark_task_failed(self):
        disp = self._make_dispatcher()
        task = Task(task_id="t1", task_type="g", phase_name="p1", target="a")
        disp.mark_task_failed(task, "API timeout")
        assert task.status == "failed"
        assert task.result == "API timeout"
        assert task.retry_count == 1

    def test_reschedule_task(self):
        disp = self._make_dispatcher()
        task = Task(task_id="t1", task_type="g", phase_name="p1", target="a")
        disp._task_queue = [
            Task(task_id="t1", task_type="g", phase_name="p1", target="a", status="failed"),
            Task(task_id="t2", task_type="g", phase_name="p2", target="b"),
        ]
        disp.reschedule_task(task, strategy="retry")
        assert task.status == "pending"
        assert task.params["strategy"] == "retry"
        assert disp._task_queue[0].task_id == "t1"

    def test_get_progress(self):
        disp = self._make_dispatcher()
        disp._task_queue = [
            Task(task_id="t1", task_type="g", phase_name="p1", target="a", status="completed"),
            Task(task_id="t2", task_type="g", phase_name="p2", target="b", status="running"),
            Task(task_id="t3", task_type="g", phase_name="p3", target="c", status="pending"),
            Task(task_id="t4", task_type="g", phase_name="p4", target="d", status="failed"),
        ]
        progress = disp.get_progress()
        assert progress["total"] == 4
        assert progress["completed"] == 1
        assert progress["running"] == 1
        assert progress["pending"] == 1
        assert progress["failed"] == 1
        assert progress["progress_pct"] == 25.0

    def test_get_progress_empty(self):
        disp = self._make_dispatcher()
        progress = disp.get_progress()
        assert progress["total"] == 0
        assert progress["progress_pct"] == 0

    def test_get_all_tasks(self):
        disp = self._make_dispatcher()
        disp._task_queue = [
            Task(task_id="t1", task_type="g", phase_name="p1", target="a"),
        ]
        all_tasks = disp.get_all_tasks()
        assert len(all_tasks) == 1
        # 返回的是副本，修改不影响原队列
        all_tasks.clear()
        assert len(disp._task_queue) == 1

    def test_skip_task_by_name(self):
        disp = self._make_dispatcher()
        disp._task_queue = [
            Task(task_id="t1", task_type="g", phase_name="phase1", target="Introduction"),
            Task(task_id="t2", task_type="g", phase_name="phase2", target="Methodology"),
        ]
        disp.skip_task_by_name("introduction")
        assert disp._task_queue[0].status == "completed"
        assert disp._task_queue[1].status == "pending"

    def test_redo_task_by_name(self):
        disp = self._make_dispatcher()
        task = Task(task_id="t1", task_type="g", phase_name="phase1", target="Introduction",
                    status="completed", retry_count=3)
        disp._task_queue = [task]
        disp.redo_task_by_name("introduction")
        assert disp._task_queue[0].status == "pending"
        assert disp._task_queue[0].retry_count == 0
