# -*- coding: utf-8 -*-
"""
Venue Adapter — 场景适配器

统一接口，让所有 skill/agent 无需关心具体 venue 差异。
下游代码通过 `get_active_profile()` 获取当前配置。
"""

from __future__ import annotations
import logging
from typing import Optional, Dict, Any, List

from config.venue_profiles.base_profile import (
    VenueProfile, SectionBudget, FigureRequirement, AblationConfig,
)
from config.venue_profiles import get_profile

logger = logging.getLogger(__name__)

# 模块级缓存
_active_profile: Optional[VenueProfile] = None


def get_active_profile(article_type: str = None) -> VenueProfile:
    """
    获取当前活跃的 venue profile

    Args:
        article_type: 如果不传，从 project_config 读取 ARTICLE_TYPE

    Returns:
        VenueProfile 实例
    """
    global _active_profile
    if _active_profile is not None and article_type is None:
        return _active_profile

    try:
        if article_type is None:
            from config.project_config import ARTICLE_TYPE
            article_type = ARTICLE_TYPE
        _active_profile = get_profile(article_type)
    except (ImportError, KeyError, ValueError) as e:
        logger.error(f"获取 venue profile 失败: {e}")
        raise
    except Exception as e:
        logger.error(f"获取 venue profile 时发生未知错误: {e}")
        raise

    logger.info(f"Venue profile activated: {_active_profile.venue_name} ({_active_profile.venue_type})")
    return _active_profile


def reset_profile():
    """重置缓存（用于测试或切换 venue）"""
    global _active_profile
    _active_profile = None


class VenueAdapter:
    """
    场景适配器

    封装 VenueProfile，提供面向下游 skill 的便捷查询接口。
    """

    def __init__(self, profile: VenueProfile = None):
        try:
            self.profile = profile or get_active_profile()
        except Exception as e:
            logger.error(f"VenueAdapter 初始化失败: {e}")
            raise

    # ---- 章节篇幅 ----

    def get_section_word_budget(self, section_name: str) -> Dict[str, int]:
        """获取章节字数预算 {target, min, max}"""
        try:
            budget = self.profile.get_section_budget(section_name)
            if budget:
                return {"target": budget.target_words, "min": budget.min_words, "max": budget.max_words}
        except Exception as e:
            logger.warning(f"获取章节字数预算失败 ({section_name}): {e}")
        # 默认值
        if self.is_journal():
            return {"target": 1500, "min": 800, "max": 2500}
        return {"target": 800, "min": 400, "max": 1200}

    def get_section_prompt_hint(self, section_name: str) -> str:
        """获取章节写作提示（字数预算 + 深度要求）"""
        try:
            budget = self.profile.get_section_budget(section_name)
            depth = self.profile.writing_style.get("methodology_depth", "moderate")

            hints = []
            if budget:
                hints.append(f"Target ~{budget.target_words} words (range: {budget.min_words}-{budget.max_words}).")
                subsections = getattr(budget, 'subsections', None)
                if subsections:
                    hints.append(f"Expected subsections: {', '.join(subsections)}")
            if depth:
                hints.append(f"Depth: {depth}")
            return " ".join(hints)
        except Exception as e:
            logger.warning(f"获取章节提示失败 ({section_name}): {e}")
            return ""

    # ---- 消融实验 ----

    def get_ablation_config(self) -> AblationConfig:
        return self.profile.ablation

    def get_ablation_prompt_block(self) -> str:
        """生成消融实验相关的 prompt 块"""
        cfg = self.profile.ablation
        lines = [
            f"Ablation experiments: {cfg.min_ablations}-{cfg.max_ablations} ablation groups.",
            f"Datasets: at least {cfg.expected_datasets}.",
        ]
        if cfg.needs_computational_analysis:
            lines.append("Must include computational complexity analysis (FLOPs, parameters, inference time).")
        if cfg.needs_failure_analysis:
            lines.append("Must include failure case analysis.")
        if cfg.needs_cross_dataset:
            lines.append("Must include cross-dataset/generalization evaluation.")
        if cfg.needs_statistical_analysis:
            lines.append("Must include statistical significance tests.")
        return "\n".join(lines)

    # ---- 图表 ----

    def get_figure_requirements(self) -> List[FigureRequirement]:
        return self.profile.figure_requirements

    def needs_figure_type(self, figure_type: str) -> bool:
        req = self.profile.get_figure_requirement(figure_type)
        return req.required if req else False

    # ---- 场景判断 ----

    def is_journal(self) -> bool:
        return self.profile.venue_type == "journal"

    def is_conference(self) -> bool:
        return self.profile.venue_type == "conference"

    def get_full_sections(self) -> List[str]:
        return self.profile.get_full_sections()

    def get_extra_sections(self) -> List[str]:
        return self.profile.extra_sections

    # ---- 术语约束 ----

    def get_prohibited_terms_prompt(self) -> str:
        if not self.profile.prohibited_terms:
            return ""
        lines = ["**Prohibited terms** (do NOT use):"]
        for term in self.profile.prohibited_terms:
            replacement = self.profile.preferred_terms.get(term, "use more precise CS terminology")
            lines.append(f'  - "{term}" → use: {replacement}')
        return "\n".join(lines)

    # ---- 质量门控 ----

    def get_quality_threshold(self) -> float:
        return self.profile.quality_pass_threshold

    def get_num_reviewers(self) -> int:
        return self.profile.num_reviewers

    def needs_seven_anchor_test(self) -> bool:
        return self.profile.needs_seven_anchor_test

    def needs_closed_book_rewrite(self) -> bool:
        return self.profile.needs_closed_book_rewrite

    # ---- Prompt 生成 ----

    def build_venue_context_block(self) -> str:
        """生成完整的 venue context prompt 块"""
        blocks = [
            self.profile.to_prompt_block(),
            "",
            self.get_ablation_prompt_block(),
            "",
            self.get_prohibited_terms_prompt(),
        ]
        return "\n".join(b for b in blocks if b)

    # ---- 兼容性：返回与旧 get_article_type_info() 相同结构的字典 ----

    def to_legacy_dict(self) -> Dict[str, Any]:
        """返回与旧 project_config.get_article_type_info() 兼容的字典"""
        try:
            p = self.profile
            return {
                "name": getattr(p, 'venue_name', ''),
                "citation_style": getattr(p, 'citation_style', 'APA'),
                "figure_style": getattr(p, 'figure_style', 'matplotlib'),
                "max_pages": getattr(p, 'max_pages', 10),
                "abstract_words": getattr(p, 'abstract_words', 250),
                "sections": p.get_full_sections() if hasattr(p, 'get_full_sections') else [],
                "latex_class": getattr(p, 'latex_class', 'article'),
                "tier": getattr(p, 'venue_tier', 3),
                "prohibited_terms": getattr(p, 'prohibited_terms', []),
                "preferred_terms": getattr(p, 'preferred_terms', {}),
                "writing_style": getattr(p, 'writing_style', {}),
            }
        except Exception as e:
            logger.error(f"生成 legacy dict 失败: {e}")
            return {}
