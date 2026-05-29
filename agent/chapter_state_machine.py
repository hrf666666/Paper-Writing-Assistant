# -*- coding: utf-8 -*-
"""
章节级状态机 — outline→draft→review→revision→final

借鉴 auto_research_agent 的 module-level state machine 设计：
- 每个章节经历 5 个阶段，每个阶段有明确的进入/退出条件
- 阶段之间有 stage gate（由 VERIFY 层提供）
- 最多允许 N 次修订循环（防死循环）
- 每次阶段转换记录原因和结果

解决的问题：
- 当前每个章节只生成一次就结束，质量不稳定
- 无法知道章节处于什么状态
- 修订没有明确的方向（盲目重试）

状态转换图:
    outline ──[gate]──> draft ──[gate]──> review ──[gate]──> revision ──[gate]──> final
       ^                                                            |
       |_____________________retry (< MAX_CYCLES)___________________|

用法:
    sm = ChapterStateMachine("Introduction")
    sm.advance("outline", outline_content, verify_report)
    if sm.can_advance:
        sm.advance("draft", draft_content, verify_report)
"""

import time
import logging
from typing import Dict, List, Optional, Any
from enum import Enum
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class ChapterPhase(str, Enum):
    """章节阶段"""
    OUTLINE = "outline"
    DRAFT = "draft"
    REVIEW = "review"
    REVISION = "revision"
    FINAL = "final"


@dataclass
class PhaseTransition:
    """阶段转换记录"""
    from_phase: str
    to_phase: str
    timestamp: float
    passed: bool
    score: float
    reason: str
    content_length: int = 0


@dataclass
class ChapterState:
    """单个章节的状态"""
    chapter_name: str
    chapter_key: str  # "1", "2", "3", "4", "5", "5_1", "5_2"
    current_phase: ChapterPhase = ChapterPhase.OUTLINE
    content: str = ""
    phase_contents: Dict[str, str] = field(default_factory=dict)
    transitions: List[PhaseTransition] = field(default_factory=list)
    retry_count: int = 0
    max_retries: int = 3
    quality_scores: Dict[str, float] = field(default_factory=dict)

    @property
    def is_complete(self) -> bool:
        return self.current_phase == ChapterPhase.FINAL

    @property
    def can_advance(self) -> bool:
        """是否可以推进到下一阶段"""
        if self.is_complete:
            return False
        if self.retry_count >= self.max_retries:
            return self.current_phase != ChapterPhase.FINAL
        return True

    @property
    def needs_revision(self) -> bool:
        """是否需要修订"""
        return self.current_phase == ChapterPhase.REVISION


class ChapterStateMachine:
    """
    章节级状态机

    管理单个章节从大纲到终稿的完整生命周期。
    每个阶段转换都需要通过验证（由 ContentVerifier 提供）。
    """

    # 阶段转换顺序
    PHASE_ORDER = [
        ChapterPhase.OUTLINE,
        ChapterPhase.DRAFT,
        ChapterPhase.REVIEW,
        ChapterPhase.REVISION,
        ChapterPhase.FINAL,
    ]

    # 每个阶段的最低质量分数
    PHASE_THRESHOLDS = {
        ChapterPhase.OUTLINE: 30,
        ChapterPhase.DRAFT: 50,
        ChapterPhase.REVIEW: 60,
        ChapterPhase.REVISION: 70,
        ChapterPhase.FINAL: 75,
    }

    def __init__(self, chapter_name: str, chapter_key: str = ""):
        self.state = ChapterState(
            chapter_name=chapter_name,
            chapter_key=chapter_key or chapter_name,
        )

    @property
    def phase(self) -> ChapterPhase:
        return self.state.current_phase

    @property
    def content(self) -> str:
        return self.state.content

    @property
    def is_complete(self) -> bool:
        return self.state.is_complete

    def advance(self, phase_name: str, content: str,
                verify_score: float = 100,
                verify_passed: bool = True,
                reason: str = "") -> bool:
        """
        尝试推进到指定阶段

        Args:
            phase_name: 目标阶段名
            content: 该阶段的内容
            verify_score: 验证得分 (0-100)
            verify_passed: 验证是否通过
            reason: 转换原因

        Returns:
            是否成功推进
        """
        try:
            target_phase = ChapterPhase(phase_name)
        except ValueError:
            logger.error(f"[StateMachine] 未知阶段: {phase_name}")
            return False

        current_idx = self.PHASE_ORDER.index(self.state.current_phase)
        target_idx = self.PHASE_ORDER.index(target_phase)

        # 只能推进到下一阶段或回退到修订阶段
        if target_idx > current_idx + 1 and target_phase != ChapterPhase.REVISION:
            logger.warning(
                f"[StateMachine] 不能从 {self.state.current_phase} "
                f"跳到 {target_phase}"
            )
            return False

        # 检查质量门控
        threshold = self.PHASE_THRESHOLDS.get(target_phase, 60)

        transition = PhaseTransition(
            from_phase=self.state.current_phase.value,
            to_phase=target_phase.value,
            timestamp=time.time(),
            passed=verify_passed and verify_score >= threshold,
            score=verify_score,
            reason=reason,
            content_length=len(content) if content else 0,
        )

        if transition.passed:
            # 通过：更新状态
            self.state.current_phase = target_phase
            self.state.content = content
            self.state.phase_contents[target_phase.value] = content
            self.state.quality_scores[target_phase.value] = verify_score
            self.state.transitions.append(transition)

            logger.info(
                f"[StateMachine] {self.state.chapter_name} "
                f"{transition.from_phase} → {target_phase.value} "
                f"(score={verify_score:.1f})"
            )
            return True
        else:
            # 未通过：记录并决定是否重试
            self.state.retry_count += 1
            self.state.transitions.append(transition)

            if self.state.retry_count >= self.state.max_retries:
                # 达到最大重试，强制推进
                logger.warning(
                    f"[StateMachine] {self.state.chapter_name} "
                    f"达到最大重试({self.state.max_retries})，强制推进到 {target_phase.value}"
                )
                self.state.current_phase = target_phase
                self.state.content = content
                self.state.phase_contents[target_phase.value] = content
                self.state.quality_scores[target_phase.value] = verify_score
                return True
            else:
                # 需要重试
                if self.state.current_phase == ChapterPhase.REVISION:
                    # 修订阶段失败，回退到草稿
                    self.state.current_phase = ChapterPhase.DRAFT
                logger.info(
                    f"[StateMachine] {self.state.chapter_name} "
                    f"阶段 {target_phase.value} 未通过 "
                    f"(score={verify_score:.1f} < {threshold})，"
                    f"重试 {self.state.retry_count}/{self.state.max_retries}"
                )
                return False

    def force_complete(self, content: str, reason: str = ""):
        """强制完成章节（跳过剩余阶段）"""
        transition = PhaseTransition(
            from_phase=self.state.current_phase.value,
            to_phase=ChapterPhase.FINAL.value,
            timestamp=time.time(),
            passed=True,
            score=0,
            reason=f"强制完成: {reason}",
            content_length=len(content) if content else 0,
        )
        self.state.current_phase = ChapterPhase.FINAL
        self.state.content = content
        self.state.phase_contents[ChapterPhase.FINAL.value] = content
        self.state.transitions.append(transition)

        logger.info(
            f"[StateMachine] {self.state.chapter_name} 强制完成"
        )

    def get_next_phase(self) -> Optional[ChapterPhase]:
        """获取下一阶段"""
        if self.state.is_complete:
            return None
        current_idx = self.PHASE_ORDER.index(self.state.current_phase)
        if current_idx + 1 < len(self.PHASE_ORDER):
            return self.PHASE_ORDER[current_idx + 1]
        return None

    def get_history(self) -> List[Dict]:
        """获取阶段转换历史"""
        return [
            {
                "from": t.from_phase,
                "to": t.to_phase,
                "passed": t.passed,
                "score": t.score,
                "reason": t.reason,
                "content_length": t.content_length,
            }
            for t in self.state.transitions
        ]

    def to_dict(self) -> dict:
        return {
            "chapter_name": self.state.chapter_name,
            "chapter_key": self.state.chapter_key,
            "current_phase": self.state.current_phase.value,
            "is_complete": self.state.is_complete,
            "retry_count": self.state.retry_count,
            "quality_scores": self.state.quality_scores,
            "transitions": self.get_history(),
        }


class PaperStateMachine:
    """
    论文级状态机 — 管理所有章节的状态

    用法:
        psm = PaperStateMachine()
        psm.register_chapter("1", "Introduction")
        psm.register_chapter("2", "Related Work")
        ...
        intro_sm = psm.get_chapter("1")
        intro_sm.advance("outline", outline_text, 80)
    """

    def __init__(self):
        self._chapters: Dict[str, ChapterStateMachine] = {}
        self._chapter_order: List[str] = []

    def register_chapter(self, key: str, name: str):
        """注册一个章节"""
        self._chapters[key] = ChapterStateMachine(name, key)
        self._chapter_order.append(key)
        logger.debug(f"[PaperStateMachine] 注册章节: {key} - {name}")

    def get_chapter(self, key: str) -> Optional[ChapterStateMachine]:
        """获取章节状态机"""
        return self._chapters.get(key)

    def get_next_pending(self) -> Optional[ChapterStateMachine]:
        """获取下一个需要处理的章节（按顺序）"""
        for key in self._chapter_order:
            sm = self._chapters[key]
            if not sm.is_complete:
                return sm
        return None

    @property
    def all_complete(self) -> bool:
        """所有章节是否都已完成"""
        return all(sm.is_complete for sm in self._chapters.values())

    @property
    def progress(self) -> Dict[str, Any]:
        """获取整体进度"""
        total = len(self._chapters)
        completed = sum(1 for sm in self._chapters.values() if sm.is_complete)
        return {
            "total": total,
            "completed": completed,
            "pending": total - completed,
            "progress_pct": completed / total * 100 if total > 0 else 0,
        }

    def get_summary(self) -> Dict[str, Dict]:
        """获取所有章节的摘要"""
        return {
            key: sm.to_dict()
            for key, sm in self._chapters.items()
        }

    def to_dict(self) -> dict:
        return {
            "chapters": {k: v.to_dict() for k, v in self._chapters.items()},
            "chapter_order": self._chapter_order,
            "all_complete": self.all_complete,
            "progress": self.progress,
        }
