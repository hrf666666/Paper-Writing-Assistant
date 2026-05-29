# -*- coding: utf-8 -*-
"""
测试 agent/checkpoint.py - 检查点管理器
"""

import json
import os
import time
import pytest
from unittest.mock import patch

from agent.checkpoint import CheckpointManager, PhaseCheckpoint


class TestPhaseCheckpoint:
    """测试 PhaseCheckpoint 数据类"""

    def test_to_dict(self):
        cp = PhaseCheckpoint(
            phase_name="test_phase",
            phase_index=1,
            timestamp=1000.0,
            status="completed",
            output_files=["a.md"],
        )
        d = cp.to_dict()
        assert d["phase_name"] == "test_phase"
        assert d["phase_index"] == 1
        assert d["status"] == "completed"
        assert d["output_files"] == ["a.md"]
        assert d["error_message"] == ""

    def test_from_dict(self):
        d = {
            "phase_name": "phase2",
            "phase_index": 2,
            "timestamp": 2000.0,
            "status": "failed",
            "output_files": [],
            "error_message": "boom",
            "duration_seconds": 10.0,
            "quality_score": 85.0,
        }
        cp = PhaseCheckpoint.from_dict(d)
        assert cp.phase_name == "phase2"
        assert cp.status == "failed"
        assert cp.error_message == "boom"
        assert cp.quality_score == 85.0

    def test_from_dict_ignores_extra_keys(self):
        d = {
            "phase_name": "p",
            "phase_index": 0,
            "timestamp": 0.0,
            "status": "completed",
            "output_files": [],
            "extra_key": "should be ignored",
        }
        cp = PhaseCheckpoint.from_dict(d)
        assert cp.phase_name == "p"


class TestCheckpointManager:
    """测试 CheckpointManager"""

    def test_init_with_custom_dir(self, tmp_path):
        mgr = CheckpointManager(output_dir=str(tmp_path))
        assert mgr.output_dir == str(tmp_path)
        assert mgr.checkpoint_dir == os.path.join(str(tmp_path), ".checkpoints")

    def test_save_and_get_completed_phases(self, tmp_path):
        mgr = CheckpointManager(output_dir=str(tmp_path))
        mgr.save_checkpoint("phase1", 1, status="completed")
        mgr.save_checkpoint("phase2", 2, status="completed")
        mgr.save_checkpoint("phase3", 3, status="failed")

        completed = mgr.get_completed_phases()
        assert "phase1" in completed
        assert "phase2" in completed
        assert "phase3" not in completed

    def test_is_phase_completed(self, tmp_path):
        mgr = CheckpointManager(output_dir=str(tmp_path))
        assert not mgr.is_phase_completed("phase1")

        mgr.save_checkpoint("phase1", 1, status="completed")
        assert mgr.is_phase_completed("phase1")

        mgr.save_checkpoint("phase2", 2, status="failed")
        assert not mgr.is_phase_completed("phase2")

    def test_get_last_completed_phase(self, tmp_path):
        mgr = CheckpointManager(output_dir=str(tmp_path))
        assert mgr.get_last_completed_phase() is None

        mgr.save_checkpoint("phase1", 1, status="completed")
        mgr.save_checkpoint("phase3", 3, status="completed")
        mgr.save_checkpoint("phase2", 2, status="completed")

        last = mgr.get_last_completed_phase()
        assert last == "phase3"

    def test_get_last_completed_phase_with_gaps(self, tmp_path):
        mgr = CheckpointManager(output_dir=str(tmp_path))
        mgr.save_checkpoint("phase1", 1, status="completed")
        mgr.save_checkpoint("phase2", 2, status="failed")
        mgr.save_checkpoint("phase3", 3, status="completed")

        last = mgr.get_last_completed_phase()
        assert last == "phase3"

    def test_get_failed_phases(self, tmp_path):
        mgr = CheckpointManager(output_dir=str(tmp_path))
        mgr.save_checkpoint("phase1", 1, status="completed")
        mgr.save_checkpoint("phase2", 2, status="failed")

        failed = mgr.get_failed_phases()
        assert "phase2" in failed
        assert "phase1" not in failed

    def test_save_state_and_get_state(self, tmp_path):
        mgr = CheckpointManager(output_dir=str(tmp_path))
        mgr.save_state("key1", {"data": 123})
        mgr.save_state("key2", "simple_string")

        assert mgr.get_state("key1") == {"data": 123}
        assert mgr.get_state("key2") == "simple_string"
        assert mgr.get_state("nonexistent") is None
        assert mgr.get_state("nonexistent", "default") == "default"

    def test_persist_and_load(self, tmp_path):
        mgr = CheckpointManager(output_dir=str(tmp_path))
        mgr.save_state("shared_key", {"val": 42})
        # save_state alone does NOT trigger _persist; save_checkpoint does
        mgr.save_checkpoint("phase1", 1, status="completed", output_files=["a.md"])

        # 创建新实例从磁盘加载
        mgr2 = CheckpointManager(output_dir=str(tmp_path))
        loaded = mgr2.load()
        assert loaded is True
        assert mgr2.is_phase_completed("phase1")
        assert mgr2.get_state("shared_key") == {"val": 42}

    def test_load_returns_false_when_no_index(self, tmp_path):
        mgr = CheckpointManager(output_dir=str(tmp_path))
        assert mgr.load() is False

    def test_clear(self, tmp_path):
        mgr = CheckpointManager(output_dir=str(tmp_path))
        mgr.save_checkpoint("phase1", 1, status="completed")
        mgr.save_state("key1", "val1")

        mgr.clear()
        assert mgr.get_completed_phases() == []
        assert mgr.get_state("key1") is None
        assert not os.path.exists(mgr.checkpoint_dir)

    def test_get_summary(self, tmp_path):
        mgr = CheckpointManager(output_dir=str(tmp_path))
        mgr.save_checkpoint("phase1", 1, status="completed")
        mgr.save_checkpoint("phase2", 2, status="failed")

        summary = mgr.get_summary()
        assert "phase1" in summary
        assert "phase2" in summary
        assert "completed" in summary
        assert "failed" in summary

    def test_save_checkpoint_with_quality_score(self, tmp_path):
        mgr = CheckpointManager(output_dir=str(tmp_path))
        mgr.save_checkpoint("phase1", 1, status="completed", quality_score=88.5)

        cp = mgr._checkpoints["phase1"]
        assert cp.quality_score == 88.5
