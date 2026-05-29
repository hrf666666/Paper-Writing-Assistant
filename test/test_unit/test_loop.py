# -*- coding: utf-8 -*-
"""Unit tests for agent/loop.py — ResearchLoop

Focuses on:
1. __init__ — all state variables initialized
2. _try_resume — no checkpoint → False; with checkpoint → restore 12 state vars
3. _save_all_state — checkpoint._state_data has all 12 keys
4. _save_checkpoint — checkpoint contains phase record + state persisted to disk
"""

import sys
import os
import json
from unittest.mock import MagicMock, patch

import pytest

# Make project root importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_checkpoint():
    """Create a mock CheckpointManager with real state storage."""
    cp = MagicMock()
    cp._state_data = {}
    cp._checkpoints = {}

    def _save_state(key, value):
        cp._state_data[key] = value

    def _get_state(key, default=None):
        return cp._state_data.get(key, default)

    cp.save_state.side_effect = _save_state
    cp.get_state.side_effect = _get_state
    cp.load.return_value = False
    cp.get_last_completed_phase.return_value = None
    return cp


def _make_loop(**overrides):
    """Build a ResearchLoop with all heavy dependencies mocked.

    Dependencies imported at module level: get_api_client, MemoryManager,
    CheckpointManager, QualityGate, DirectiveManager, AgentDispatcher.
    Dependencies imported inside __init__: Auditor, CrossChapterChecker,
    CitationManager, VenueAdapter, setup_tool_api.
    """
    with patch("agent.api_client.get_api_client") as mock_get_api, \
         patch("agent.memory.MemoryManager.__init__", return_value=None), \
         patch("agent.checkpoint.CheckpointManager.__init__", return_value=None), \
         patch("agent.quality_gate.QualityGate.__init__", return_value=None), \
         patch("agent.human_directive.DirectiveManager.__init__", return_value=None), \
         patch("agent.dispatcher.AgentDispatcher.__init__", return_value=None), \
         patch("agent.auditor.Auditor.__init__", return_value=None), \
         patch("agent.cross_chapter_checker.CrossChapterChecker.__init__", return_value=None), \
         patch("agent.citation_manager.CitationManager.__init__", return_value=None), \
         patch("agent.venue_adapter.VenueAdapter.__init__", return_value=None), \
         patch("tools.base_tool.setup_tool_api"), \
         patch("config.project_config.OUTPUT_DIR", "/tmp/test_output"):

        mock_api = MagicMock()
        mock_get_api.return_value = mock_api

        from agent.loop import ResearchLoop
        loop = ResearchLoop(api_client=mock_api)

    # Replace checkpoint with our mock
    loop.checkpoint = _make_mock_checkpoint()

    # Replace memory with a mock
    loop.memory = MagicMock()
    loop.memory.load.return_value = True

    # Allow caller to override attributes
    for k, v in overrides.items():
        setattr(loop, k, v)
    return loop


# =====================================================================
# 1. Initialization tests
# =====================================================================

class TestResearchLoopInit:

    def test_chapters_initialized(self):
        loop = _make_loop()
        assert loop._chapters == {}

    def test_project_data_initialized(self):
        loop = _make_loop()
        assert loop._project_data == {}

    def test_ref_data_initialized(self):
        loop = _make_loop()
        assert loop._ref_data == {}

    def test_abstract_initialized(self):
        loop = _make_loop()
        assert loop._abstract == ""

    def test_reference_pool_initialized(self):
        loop = _make_loop()
        assert loop._reference_pool == []

    def test_outline_initialized(self):
        loop = _make_loop()
        assert loop._outline == {}

    def test_motivation_thread_initialized(self):
        loop = _make_loop()
        assert loop._motivation_thread == ""

    def test_exemplar_dossier_initialized(self):
        loop = _make_loop()
        assert loop._exemplar_dossier == {}

    def test_style_profile_initialized(self):
        loop = _make_loop()
        assert loop._style_profile == {}

    def test_citation_bank_initialized(self):
        loop = _make_loop()
        assert loop._citation_bank == {}

    def test_rationale_matrix_initialized(self):
        loop = _make_loop()
        assert loop._rationale_matrix == {}

    def test_ablation_results_initialized(self):
        loop = _make_loop()
        assert loop._ablation_results == {}


# =====================================================================
# 2. _try_resume tests
# =====================================================================

class TestTryResume:

    def test_no_checkpoint_returns_false(self):
        """When checkpoint.load() returns False, _try_resume returns False."""
        loop = _make_loop()
        loop.checkpoint.load.return_value = False
        assert loop._try_resume() is False

    def test_no_last_phase_returns_false(self):
        """checkpoint.load() succeeds but no completed phase → False."""
        loop = _make_loop()
        loop.checkpoint.load.return_value = True
        loop.checkpoint.get_last_completed_phase.return_value = None
        assert loop._try_resume() is False

    def test_resume_restores_12_state_vars(self):
        """When checkpoint has a completed phase, all 12 state variables are restored."""
        loop = _make_loop()

        saved_data = {
            "project_data": {"title": "Test"},
            "ref_data": {"papers": [1, 2]},
            "chapters": {1: "Intro content"},
            "reference_pool": [{"id": "ref1"}],
            "outline": {"sections": ["Intro"]},
            "motivation_thread": "motivation string",
            "exemplar_dossier": {"ex1": "data"},
            "style_profile": {"tone": "formal"},
            "citation_bank": {"claim1": "cite1"},
            "rationale_matrix": {"rows": []},
            "abstract": "Test abstract",
            "ablation_results": {"experiments": []},
        }

        def _get_state(key, default=None):
            return saved_data.get(key, default)

        loop.checkpoint.load.return_value = True
        loop.checkpoint.get_last_completed_phase.return_value = "phase1"
        loop.checkpoint.get_state.side_effect = _get_state

        result = loop._try_resume()

        assert result is True
        assert loop._project_data == {"title": "Test"}
        assert loop._ref_data == {"papers": [1, 2]}
        assert loop._chapters == {1: "Intro content"}
        assert loop._reference_pool == [{"id": "ref1"}]
        assert loop._outline == {"sections": ["Intro"]}
        assert loop._motivation_thread == "motivation string"
        assert loop._exemplar_dossier == {"ex1": "data"}
        assert loop._style_profile == {"tone": "formal"}
        assert loop._citation_bank == {"claim1": "cite1"}
        assert loop._rationale_matrix == {"rows": []}
        assert loop._abstract == "Test abstract"
        assert loop._ablation_results == {"experiments": []}

    def test_resume_restores_ablation_results(self):
        """Explicitly verify _ablation_results is restored."""
        loop = _make_loop()

        saved_data = {"project_data": {"key": "val"}, "ablation_results": {"exp1": "done"}}

        def _get_state(key, default=None):
            return saved_data.get(key, default)

        loop.checkpoint.load.return_value = True
        loop.checkpoint.get_last_completed_phase.return_value = "phase0_95"
        loop.checkpoint.get_state.side_effect = _get_state

        loop._try_resume()
        assert loop._ablation_results == {"exp1": "done"}


# =====================================================================
# 3. _save_all_state tests
# =====================================================================

class TestSaveAllState:

    def test_state_data_has_all_12_keys(self):
        """After _save_all_state, checkpoint should contain 12 state keys."""
        loop = _make_loop()

        loop._chapters = {1: "intro"}
        loop._project_data = {"p": 1}
        loop._ref_data = {"r": 2}
        loop._reference_pool = ["ref"]
        loop._outline = {"outline": True}
        loop._motivation_thread = "motivation"
        loop._exemplar_dossier = {"exemplar": True}
        loop._style_profile = {"style": True}
        loop._citation_bank = {"cite": True}
        loop._rationale_matrix = {"matrix": True}
        loop._abstract = "abstract text"
        loop._ablation_results = {"ablation": True}

        loop._save_all_state()

        expected_keys = {
            "chapters", "project_data", "ref_data", "reference_pool",
            "outline", "motivation_thread", "exemplar_dossier",
            "style_profile", "citation_bank", "rationale_matrix",
            "abstract", "ablation_results",
        }
        actual_keys = set(loop.checkpoint._state_data.keys())
        assert expected_keys == actual_keys


# =====================================================================
# 4. _save_checkpoint tests
# =====================================================================

class TestSaveCheckpoint:

    def test_save_checkpoint_calls_save_checkpoint_with_phase(self):
        """save_checkpoint records the correct phase_name."""
        loop = _make_loop()
        loop._start_time = 0.0

        task = MagicMock()
        task.phase_name = "phase3"
        task.status = "completed"
        task.quality_report = {"overall_score": 85.0}

        loop._save_checkpoint(task)

        loop.checkpoint.save_checkpoint.assert_called_once()
        call_args = loop.checkpoint.save_checkpoint.call_args
        assert call_args[0][0] == "phase3"

    def test_save_checkpoint_persists_all_state(self):
        """After _save_checkpoint, all 12 state keys are saved to checkpoint."""
        loop = _make_loop()
        loop._start_time = 0.0

        loop._chapters = {1: "Intro"}
        loop._project_data = {"title": "Test Paper"}
        loop._ref_data = {}
        loop._reference_pool = []
        loop._outline = {}
        loop._motivation_thread = ""
        loop._exemplar_dossier = {}
        loop._style_profile = {}
        loop._citation_bank = {}
        loop._rationale_matrix = {}
        loop._abstract = ""
        loop._ablation_results = {}

        task = MagicMock()
        task.phase_name = "phase1"
        task.status = "completed"
        task.quality_report = None

        loop._save_checkpoint(task)

        # Verify save_checkpoint was called for phase record
        assert loop.checkpoint.save_checkpoint.called
        # Verify all 12 state keys were saved via save_state
        saved_keys = set(loop.checkpoint._state_data.keys())
        assert "chapters" in saved_keys
        assert "project_data" in saved_keys
        assert loop.checkpoint._state_data["chapters"] == {1: "Intro"}
        assert loop.checkpoint._state_data["project_data"] == {"title": "Test Paper"}
