# -*- coding: utf-8 -*-
"""Unit tests for agent/venue_adapter.py — get_active_profile, VenueAdapter

Focuses on:
1. get_active_profile — correctly retrieves profile
2. VenueAdapter.__init__ — loads profile
3. get_section_word_budget — returns valid budget, degrades gracefully
4. get_section_prompt_hint — returns hint or empty
5. to_legacy_dict — returns complete dict
"""

import sys
import os
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


# ---------------------------------------------------------------------------
# Fixtures: build a lightweight VenueProfile
# ---------------------------------------------------------------------------

def _make_profile(
    venue_name="IEEE TIP",
    venue_type="journal",
    venue_tier="top_journal",
    extra_sections=None,
    section_budgets=None,
    writing_style=None,
    ablation=None,
):
    """Build a mock VenueProfile with sensible defaults."""
    from config.venue_profiles.base_profile import (
        VenueProfile, SectionBudget, AblationConfig,
    )

    class TestProfile(VenueProfile):
        pass

    p = TestProfile()
    p.venue_name = venue_name
    p.venue_type = venue_type
    p.venue_tier = venue_tier
    p.max_pages = 14
    p.abstract_words = 250
    p.abstract_max_words = 300
    p.citation_style = "numeric"
    p.figure_style = "column_width"
    p.latex_class = "IEEEtran"
    p.sections = ["Introduction", "Related Work", "Methodology", "Experiments", "Conclusion"]
    p.extra_sections = extra_sections or []
    p.section_budgets = section_budgets or [
        SectionBudget("Introduction", 800, 600, 1000),
        SectionBudget("Methodology", 2000, 1500, 2500),
    ]
    p.writing_style = writing_style or {"tone": "formal", "methodology_depth": "moderate"}
    p.ablation = ablation or AblationConfig(
        min_ablations=3, max_ablations=5, expected_datasets=2,
    )
    p.figure_requirements = []
    p.prohibited_terms = []
    p.preferred_terms = {}
    p.quality_pass_threshold = 70.0
    p.quality_max_retries = 3
    p.num_reviewers = 1
    p.needs_seven_anchor_test = False
    p.needs_closed_book_rewrite = False
    return p


# =====================================================================
# 1. get_active_profile
# =====================================================================

class TestGetActiveProfile:

    def setup_method(self):
        """Reset module-level cache before each test."""
        from agent.venue_adapter import reset_profile
        reset_profile()

    def test_returns_profile_for_known_article_type(self):
        from agent.venue_adapter import get_active_profile
        profile = get_active_profile("IEEE TIP")
        assert profile is not None
        assert "TIP" in profile.venue_name or "Image Processing" in profile.venue_name

    def test_returns_default_for_unknown_article_type(self):
        from agent.venue_adapter import get_active_profile
        profile = get_active_profile("UNKNOWN_VENUE")
        assert profile is not None
        # Should default to IEEE TIP profile
        assert "Image Processing" in profile.venue_name

    def test_caches_profile(self):
        from agent.venue_adapter import get_active_profile
        p1 = get_active_profile("CVPR")
        p2 = get_active_profile()  # Should return cached
        assert p1 is p2

    def test_raises_on_invalid_article_type_with_explicit_none(self):
        """When article_type=None and config import fails, raises."""
        from agent.venue_adapter import get_active_profile, reset_profile
        reset_profile()
        with patch("agent.venue_adapter.get_profile", side_effect=KeyError("not found")):
            with pytest.raises(KeyError):
                get_active_profile("NONEXISTENT")


# =====================================================================
# 2. VenueAdapter initialization
# =====================================================================

class TestVenueAdapterInit:

    def test_init_with_explicit_profile(self):
        from agent.venue_adapter import VenueAdapter
        profile = _make_profile()
        adapter = VenueAdapter(profile=profile)
        assert adapter.profile is profile

    def test_init_loads_profile_via_get_active(self):
        from agent.venue_adapter import VenueAdapter, reset_profile
        reset_profile()
        adapter = VenueAdapter()
        assert adapter.profile is not None
        assert hasattr(adapter.profile, "venue_name")


# =====================================================================
# 3. get_section_word_budget
# =====================================================================

class TestGetSectionWordBudget:

    def test_returns_budget_for_known_section(self):
        from agent.venue_adapter import VenueAdapter
        adapter = VenueAdapter(profile=_make_profile())
        budget = adapter.get_section_word_budget("Introduction")
        assert budget == {"target": 800, "min": 600, "max": 1000}

    def test_returns_budget_case_insensitive(self):
        from agent.venue_adapter import VenueAdapter
        adapter = VenueAdapter(profile=_make_profile())
        budget = adapter.get_section_word_budget("introduction")
        assert budget["target"] == 800

    def test_returns_default_journal_budget_for_unknown_section(self):
        from agent.venue_adapter import VenueAdapter
        adapter = VenueAdapter(profile=_make_profile(venue_type="journal"))
        budget = adapter.get_section_word_budget("Nonexistent Section")
        assert budget == {"target": 1500, "min": 800, "max": 2500}

    def test_returns_default_conference_budget_for_unknown_section(self):
        from agent.venue_adapter import VenueAdapter
        adapter = VenueAdapter(profile=_make_profile(venue_type="conference"))
        budget = adapter.get_section_word_budget("Nonexistent Section")
        assert budget == {"target": 800, "min": 400, "max": 1200}


# =====================================================================
# 4. get_section_prompt_hint
# =====================================================================

class TestGetSectionPromptHint:

    def test_returns_hint_for_known_section(self):
        from agent.venue_adapter import VenueAdapter
        adapter = VenueAdapter(profile=_make_profile())
        hint = adapter.get_section_prompt_hint("Introduction")
        assert "800" in hint  # target words
        assert "600" in hint or "1000" in hint  # range

    def test_returns_non_empty_string(self):
        from agent.venue_adapter import VenueAdapter
        adapter = VenueAdapter(profile=_make_profile())
        hint = adapter.get_section_prompt_hint("Methodology")
        assert isinstance(hint, str)
        assert len(hint) > 0

    def test_returns_empty_for_exception(self):
        from agent.venue_adapter import VenueAdapter
        profile = _make_profile()
        # Force get_section_budget to raise
        profile.get_section_budget = MagicMock(side_effect=Exception("boom"))
        adapter = VenueAdapter(profile=profile)
        hint = adapter.get_section_prompt_hint("Anything")
        assert hint == ""


# =====================================================================
# 5. to_legacy_dict
# =====================================================================

class TestToLegacyDict:

    def test_returns_complete_dict(self):
        from agent.venue_adapter import VenueAdapter
        profile = _make_profile()
        adapter = VenueAdapter(profile=profile)
        d = adapter.to_legacy_dict()

        assert "name" in d
        assert "citation_style" in d
        assert "figure_style" in d
        assert "max_pages" in d
        assert "abstract_words" in d
        assert "sections" in d
        assert "latex_class" in d
        assert "tier" in d
        assert "prohibited_terms" in d
        assert "preferred_terms" in d
        assert "writing_style" in d

    def test_dict_values_match_profile(self):
        from agent.venue_adapter import VenueAdapter
        profile = _make_profile(venue_name="CVPR")
        profile.citation_style = "author_year"
        profile.max_pages = 8
        adapter = VenueAdapter(profile=profile)
        d = adapter.to_legacy_dict()

        assert d["name"] == "CVPR"
        assert d["citation_style"] == "author_year"
        assert d["max_pages"] == 8
        assert "Introduction" in d["sections"]

    def test_returns_empty_dict_on_error(self):
        from agent.venue_adapter import VenueAdapter
        profile = _make_profile()
        # Break profile to trigger exception
        profile.get_full_sections = MagicMock(side_effect=Exception("fail"))
        adapter = VenueAdapter(profile=profile)
        d = adapter.to_legacy_dict()
        # Should return {} due to exception handler
        assert d == {}
