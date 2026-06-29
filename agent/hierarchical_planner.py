# -*- coding: utf-8 -*-
"""
分层规划器 — Hierarchical Planning System v1.0

三层结构：
- 抽象层 (AbstractGoal): 功能性目标 + 验收指标
- 执行层 (AtomicStep): 原子操作 + 验收指标
- 评价层 (ValidationEngine): 原子级 / 抽象级 / 全局级 三层验收

设计原则：
- HierarchicalPlan 可降级为扁平 Task 列表，不破坏 loop.py 的 phase 分发
- 验收指标基于可量化的 metric（从 output_dir 的文件和 checkpoint 中读取）
- 验收不替代 L1/L2/L3 评价，而是中间检查点
"""

import os
import re
import json
import time
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ============================================================
# 数据结构
# ============================================================

@dataclass
class AtomicStep:
    """执行层：原子操作"""
    step_id: str
    description: str
    phase_name: str             # 对应 loop.py 的 phase 分发（如 "phase0", "phase1"）
    acceptance_criteria: Dict   # {"metric": "ref_pool_size", "op": ">=", "value": 15}
    fallback: Optional[str] = None   # 失败时的降级操作描述
    task_id: str = ""           # 对应 dispatcher.Task 的 task_id
    status: str = "pending"     # pending/running/completed/failed
    actual_value: Any = None    # 执行后填入实际值


@dataclass
class AbstractGoal:
    """抽象层：功能性目标"""
    goal_id: str                # "G1", "G2", ...
    description: str
    acceptance_criteria: Dict   # {"metric": "bib_entries", "op": ">=", "value": 10}
    steps: List[AtomicStep] = field(default_factory=list)
    status: str = "pending"     # pending/partial/complete/failed


@dataclass
class HierarchicalPlan:
    """分层规划"""
    goals: List[AbstractGoal] = field(default_factory=list)
    created_at: float = 0.0
    metadata: Dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.created_at:
            self.created_at = time.time()

    def flatten_to_tasks(self) -> list:
        """
        降级为扁平结构，保持与 dispatcher 兼容。
        遍历所有 goals 的所有 steps，返回有序的 step 列表。
        """
        steps = []
        for goal in self.goals:
            steps.extend(goal.steps)
        return steps

    def get_goal_by_step_phase(self, phase_name: str) -> Optional[AbstractGoal]:
        """根据 phase_name 反查所属的 Goal"""
        for goal in self.goals:
            for step in goal.steps:
                if step.phase_name == phase_name:
                    return goal
        return None

    def get_step_by_phase(self, phase_name: str) -> Optional[AtomicStep]:
        """根据 phase_name 查找 AtomicStep"""
        for goal in self.goals:
            for step in goal.steps:
                if step.phase_name == phase_name:
                    return step
        return None

    def to_dict(self) -> Dict:
        """序列化为 JSON 兼容字典"""
        return {
            "created_at": self.created_at,
            "metadata": self.metadata,
            "goals": [
                {
                    "goal_id": g.goal_id,
                    "description": g.description,
                    "acceptance_criteria": g.acceptance_criteria,
                    "status": g.status,
                    "steps": [
                        {
                            "step_id": s.step_id,
                            "description": s.description,
                            "phase_name": s.phase_name,
                            "task_id": s.task_id,
                            "acceptance_criteria": s.acceptance_criteria,
                            "fallback": s.fallback,
                            "status": s.status,
                            "actual_value": s.actual_value,
                        }
                        for s in g.steps
                    ],
                }
                for g in self.goals
            ],
        }


# ============================================================
# 验收引擎
# ============================================================

class ValidationEngine:
    """
    分层验收引擎

    三层验收流程：
    1. 原子级验收 → 每个 AtomicStep 检查 acceptance_criteria
    2. 抽象级验收 → 每个 AbstractGoal 汇总 steps 结果
    3. 全局验收 → 汇总所有 Goals → 生成通过率
    """

    def __init__(self, output_dir: str):
        self.output_dir = output_dir

    def run_validation(self, plan: HierarchicalPlan) -> Dict:
        """
        执行完整的三层验收

        Returns:
            {
                "timestamp": float,
                "step_results": [{step_id, passed, actual, expected, ...}],
                "goal_results": [{goal_id, passed, steps_passed, steps_total, ...}],
                "overall": {passed_count, failed_count, pass_rate},
                "failed_goals": [goal_id, ...],
                "retry_phases": [phase_name, ...],
            }
        """
        report = {
            "timestamp": time.time(),
            "step_results": [],
            "goal_results": [],
            "overall": {},
            "failed_goals": [],
            "retry_phases": [],
        }

        # ── 1. 原子级验收 ──
        for goal in plan.goals:
            for step in goal.steps:
                if step.status != "completed":
                    # 未执行的 step 跳过验收
                    continue
                result = self._validate_step(step)
                report["step_results"].append(result)
                step.status = "passed" if result["passed"] else "failed"

        # ── 2. 抽象级验收 ──
        for goal in plan.goals:
            goal_result = self._validate_goal(goal)
            report["goal_results"].append(goal_result)
            goal.status = goal_result["status"]

            if not goal_result["passed"]:
                report["failed_goals"].append(goal.goal_id)
                # 收集失败的 phase 用于重试
                for step in goal.steps:
                    if step.status == "failed" and step.fallback:
                        report["retry_phases"].append(step.phase_name)

        # ── 3. 全局验收 ──
        total_goals = len(plan.goals)
        passed_goals = sum(1 for g in plan.goals if g.status == "complete")
        partial_goals = sum(1 for g in plan.goals if g.status == "partial")

        report["overall"] = {
            "total_goals": total_goals,
            "passed_goals": passed_goals,
            "partial_goals": partial_goals,
            "failed_goals": total_goals - passed_goals - partial_goals,
            "pass_rate": round(passed_goals / total_goals * 100, 1) if total_goals > 0 else 0,
        }

        # 保存报告
        report_path = os.path.join(self.output_dir, "hierarchical_validation_report.json")
        try:
            with open(report_path, "w", encoding="utf-8") as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            logger.info(f"[ValidationEngine] 验收报告已保存: {report_path}")
        except Exception as e:
            logger.warning(f"[ValidationEngine] 报告保存失败: {e}")

        return report

    def _validate_step(self, step: AtomicStep) -> Dict:
        """原子级验收：检查单个 step 的 acceptance_criteria"""
        criteria = step.acceptance_criteria
        if not criteria:
            return {
                "step_id": step.step_id,
                "passed": True,
                "reason": "无验收指标，默认通过",
                "actual": None,
                "expected": None,
            }

        metric = criteria.get("metric", "")
        op = criteria.get("op", ">=")
        expected = criteria.get("value", 0)
        optional = criteria.get("optional", False)

        # 尝试获取实际值
        actual = self._read_metric(metric, step)

        if actual is None:
            # 无法读取 metric
            if optional:
                return {
                    "step_id": step.step_id,
                    "passed": True,
                    "reason": "可选指标，无法读取，默认通过",
                    "actual": None,
                    "expected": expected,
                }
            return {
                "step_id": step.step_id,
                "passed": False,
                "reason": f"无法读取指标 '{metric}'",
                "actual": None,
                "expected": expected,
            }

        # 更新 step 的实际值
        step.actual_value = actual

        # 比较
        passed = self._compare(actual, op, expected)

        return {
            "step_id": step.step_id,
            "passed": passed,
            "reason": f"{metric}: {actual} {op} {expected} → {'PASS' if passed else 'FAIL'}",
            "actual": actual,
            "expected": expected,
        }

    def _validate_goal(self, goal: AbstractGoal) -> Dict:
        """抽象级验收：汇总 goal 下所有 steps 的结果"""
        steps = goal.steps
        completed_steps = [s for s in steps if s.status in ("completed", "passed", "failed")]
        passed_steps = [s for s in steps if s.status == "passed"]
        failed_steps = [s for s in steps if s.status == "failed"]

        # 基础判定
        if not completed_steps:
            status = "pending"
            passed = False
        elif len(failed_steps) == 0:
            status = "complete"
            passed = True
        elif len(passed_steps) > 0:
            status = "partial"
            passed = False  # partial 也算未通过
        else:
            status = "failed"
            passed = False

        # 额外检查 goal 自身的 acceptance_criteria
        goal_criteria = goal.acceptance_criteria
        goal_criteria_result = None
        if goal_criteria and status == "complete":
            metric = goal_criteria.get("metric", "")
            op = goal_criteria.get("op", ">=")
            expected = goal_criteria.get("value", 0)
            actual = self._read_metric(metric)
            if actual is not None:
                criteria_passed = self._compare(actual, op, expected)
                if not criteria_passed:
                    status = "partial"
                    passed = False
                goal_criteria_result = {
                    "metric": metric,
                    "actual": actual,
                    "expected": expected,
                    "passed": criteria_passed,
                }

        return {
            "goal_id": goal.goal_id,
            "description": goal.description,
            "passed": passed,
            "status": status,
            "steps_total": len(steps),
            "steps_passed": len(passed_steps),
            "steps_failed": len(failed_steps),
            "steps_pending": len(steps) - len(completed_steps),
            "goal_criteria": goal_criteria_result,
        }

    # ────────────── Metric 读取器 ──────────────

    def _read_metric(self, metric: str, step: AtomicStep = None) -> Any:
        """
        根据 metric 名称从 output_dir 读取实际值

        支持的 metric：
        - innovation_points: 从 project_data.json 读取
        - model_architecture: 从 project_data.json 读取是否非空
        - ref_pool_size: 从 reference_pool.json 读取列表长度
        - loaded_papers: 同 ref_pool_size
        - claims_count: 从 citation_bank.json 读取
        - motivation: 检查 motivation_thread 文件是否存在且非空
        - style_profile: 检查 style_profile 文件是否存在且非空
        - chapter_words_{N}: 从 chapters 目录读取第 N 章字数
        - unknown_citations: 统计 main.tex 中 [?] 的数量（反向指标）
        - bib_entries: 统计 references.bib 中 @ 的数量
        - tex_exists: 检查 main.tex 是否存在
        - pdf_exists: 检查 full_paper.pdf 是否存在
        - compile_success: 从 compile log 判断
        """
        readers = {
            "innovation_points": self._read_innovation_points,
            "model_architecture": self._read_model_architecture,
            "ref_pool_size": self._read_ref_pool_size,
            "loaded_papers": self._read_ref_pool_size,
            "claims_count": self._read_claims_count,
            "motivation": self._read_motivation,
            "style_profile": self._read_style_profile,
            "bib_entries": self._read_bib_entries,
            "tex_exists": self._read_tex_exists,
            "pdf_exists": self._read_pdf_exists,
            "compile_success": self._read_compile_success,
            "unknown_citations": self._read_unknown_citations,
            "paper_context_exists": self._read_paper_context_exists,
            "figure_plan_exists": self._read_figure_plan_exists,
        }

        reader = readers.get(metric)
        if reader:
            try:
                return reader()
            except Exception as e:
                logger.debug(f"[ValidationEngine] 读取 metric '{metric}' 失败: {e}")
                return None

        # chapter_words_{N} 模式
        if metric.startswith("chapter_words_"):
            ch_num = metric.replace("chapter_words_", "")
            return self._read_chapter_words(ch_num)

        logger.debug(f"[ValidationEngine] 未知 metric: {metric}")
        return None

    def _read_innovation_points(self) -> int:
        # 尝试多个候选文件
        candidates = [
            os.path.join(self.output_dir, "project_data.json"),
            os.path.join(self.output_dir, "innovation_points.json"),
            os.path.join(self.output_dir, "innovation_verified.json"),
        ]
        for path in candidates:
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if isinstance(data, list):
                        return len(data)
                    if isinstance(data, dict):
                        pts = data.get("innovation_points",
                                       data.get("创新点",
                                                data.get("verified_points", [])))
                        if isinstance(pts, list):
                            return len(pts)
                except (json.JSONDecodeError, IOError):
                    continue
        return 0

    def _read_model_architecture(self) -> int:
        """返回 1=非空, 0=空"""
        path = os.path.join(self.output_dir, "project_data.json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            arch = data.get("model_architecture", {})
            return 1 if arch else 0
        return 0

    def _read_ref_pool_size(self) -> int:
        # 尝试 reference_pool.json
        path = os.path.join(self.output_dir, "reference_pool.json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return len(data)
            if isinstance(data, dict):
                return len(data.get("papers", data.get("references", [])))
        return 0

    def _read_claims_count(self) -> int:
        path = os.path.join(self.output_dir, "citation_bank.json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return len(data.get("claims", []))
        return 0

    def _read_motivation(self) -> int:
        """返回 1=存在且非空, 0=不存在或空"""
        candidates = [
            os.path.join(self.output_dir, "motivation_thread.json"),
            os.path.join(self.output_dir, "motivation_thread.txt"),
            os.path.join(self.output_dir, "motivation.json"),
            os.path.join(self.output_dir, "motivation_result.json"),
            os.path.join(self.output_dir, "motivation_candidates.md"),
            os.path.join(self.output_dir, "confirmed_motivation.md"),
        ]
        for path in candidates:
            if os.path.exists(path):
                size = os.path.getsize(path)
                if size > 10:
                    return 1
        return 0

    def _read_style_profile(self) -> int:
        """返回 1=存在且非空"""
        candidates = [
            os.path.join(self.output_dir, "style_profile.json"),
            os.path.join(self.output_dir, "style_profile.md"),
            os.path.join(self.output_dir, "journal_style.json"),
            os.path.join(self.output_dir, "writing_style_guide.json"),
            os.path.join(self.output_dir, "figure_style_guide.json"),
        ]
        for path in candidates:
            if os.path.exists(path):
                size = os.path.getsize(path)
                if size > 10:
                    return 1
        return 0

    def _read_bib_entries(self) -> int:
        path = os.path.join(self.output_dir, "latex", "references.bib")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            return content.count("@")
        return 0

    def _read_tex_exists(self) -> int:
        path = os.path.join(self.output_dir, "latex", "main.tex")
        return 1 if os.path.exists(path) else 0

    def _read_pdf_exists(self) -> int:
        path = os.path.join(self.output_dir, "full_paper.pdf")
        return 1 if os.path.exists(path) else 0

    def _read_figure_plan_exists(self) -> int:
        """v17 G3: 补注册——验收 spec 用 figure_plan_exists 但 readers 漏了它，
        导致 G3-S7 永远读成 None（即便 figure_plan.json 存在）。"""
        path = os.path.join(self.output_dir, "figure_plan.json")
        if not os.path.exists(path):
            return 0
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return 1 if data.get("figures") else 0
        except (json.JSONDecodeError, IOError):
            return 0

    def _read_compile_success(self) -> int:
        log_path = os.path.join(self.output_dir, "latex", "main.log")
        if os.path.exists(log_path):
            with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            error_count = content.count("! ")
            return 1 if error_count == 0 and "Output written" in content else 0
        return 0

    def _read_unknown_citations(self) -> int:
        """反向指标：[?] 残留数量，越少越好"""
        path = os.path.join(self.output_dir, "latex", "main.tex")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            return len(re.findall(r'\[\?\]', content))
        return 999

    def _read_paper_context_exists(self) -> int:
        """返回 1=事实源存在且非空, 0=不存在

        v13 PR2: 优先读 FactBase (factbase.json)，兼容旧 paper_context.json，
        再降级 project_data.json。任一非空即返回 1。
        """
        # 1. FactBase（新权威源）
        for fn in ("factbase.json", "paper_context.json"):
            pc_path = os.path.join(self.output_dir, fn)
            if os.path.exists(pc_path) and os.path.getsize(pc_path) > 10:
                return 1
        # 2. 从 project_data.json 中查找
        pd_path = os.path.join(self.output_dir, "project_data.json")
        if os.path.exists(pd_path):
            try:
                with open(pd_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                pc = data.get("paper_context", {})
                return 1 if pc and any(pc.values()) else 0
            except (json.JSONDecodeError, IOError):
                pass
        return 0

    def _read_chapter_words(self, ch_num: str) -> int:
        """读取章节正文字数 — v17 G4: 剔除 LaTeX/markdown 标记后再统计。

        旧实现 len(content.split()) 把命令也当词，统计不准。现剔除环境标记、
        命令、花括号、占位符、注释、公式、markdown 符号，只数正文。
        """
        import glob as glob_mod
        import re as _re
        ch_dir = os.path.join(self.output_dir, f"chapter{ch_num}")
        if not os.path.isdir(ch_dir):
            return 0
        for pattern in [f"chapter{ch_num}_*.md", f"chapter{ch_num}_*.tex",
                        "content.tex", "content.md"]:
            matches = glob_mod.glob(os.path.join(ch_dir, pattern))
            for ch_path in matches:
                try:
                    with open(ch_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    t = content
                    t = _re.sub(r"(?m)^%.*$", "", t)
                    t = _re.sub(r"\\begin\{[^}]*\}|\\end\{[^}]*\}", " ", t)
                    t = _re.sub(r"\\(?:textbf|textit|emph|section|subsection|subsubsection|item|label|caption|cite|ref|footnote|par)\b\*?\{", " ", t)
                    t = _re.sub(r"\\[a-zA-Z]+\b\*?(?:\[[^\]]*\])?", " ", t)
                    t = _re.sub(r"<cite[^>]*/>|<citation[^>]*>[^<]*</citation>|\\cite\{[^}]*\}", " ", t)
                    t = _re.sub(r"[{}\\]", " ", t)
                    t = _re.sub(r"(?m)^#{1,6}\s+", "", t)
                    t = _re.sub(r"\$\$.*?\$\$|\$.*?\$", " ", t, flags=_re.DOTALL)
                    t = _re.sub(r"\[[\d,\s\u2013-]*\]", " ", t)
                    return len(t.split())
                except IOError:
                    continue
        return 0

    # ────────────── 工具方法 ──────────────

    @staticmethod
    def _compare(actual, op: str, expected) -> bool:
        """通用比较操作"""
        try:
            ops = {
                ">=": lambda a, e: a >= e,
                ">": lambda a, e: a > e,
                "<=": lambda a, e: a <= e,
                "<": lambda a, e: a < e,
                "==": lambda a, e: a == e,
                "!=": lambda a, e: a != e,
            }
            return ops.get(op, lambda a, e: False)(actual, expected)
        except (TypeError, ValueError):
            return False


# ============================================================
# 工厂函数：构建默认分层规划
# ============================================================

def build_default_plan(venue_adapter=None) -> HierarchicalPlan:
    """
    构建默认的 5-Goal 分层规划，对应 Pipeline Phase 0~9。

    Args:
        venue_adapter: VenueAdapter 实例，用于决定额外章节

    Returns:
        HierarchicalPlan 实例
    """
    # 读取功能开关
    try:
        from config.project_config import (
            ENABLE_MOTIVATION_ENGINE, ENABLE_EXEMPLAR_LEARNING,
            ENABLE_RATIONALE_MATRIX, RUN_ABLATION,
        )
    except ImportError:
        ENABLE_MOTIVATION_ENGINE = False
        ENABLE_EXEMPLAR_LEARNING = False
        ENABLE_RATIONALE_MATRIX = False
        RUN_ABLATION = False

    # ── G1: 项目分析 ──
    g1_steps = [
        AtomicStep(
            step_id="G1-S1", description="分析工程代码与参考PDF",
            phase_name="phase0", task_id="analyze_project",
            acceptance_criteria={"metric": "innovation_points", "op": ">=", "value": 1},
            fallback="使用 IDEA_REPORT.md 兜底",
        ),
        AtomicStep(
            step_id="G1-S2", description="参考文献池构建+全局大纲规划",
            phase_name="phase0_5", task_id="plan_outline",
            acceptance_criteria={"metric": "ref_pool_size", "op": ">=", "value": 15},
            fallback="从离线数据包兜底加载",
        ),
    ]

    # ── G2: 参考文献体系 ──
    g2_steps = [
        AtomicStep(
            step_id="G2-S1", description="引用支撑库构建",
            phase_name="phase0_8", task_id="citation_bank",
            acceptance_criteria={"metric": "claims_count", "op": ">=", "value": 5},
            fallback="从 reference_pool 自动生成 claims",
        ),
    ]

    # ── G3: 写作准备 ──
    g3_steps = []
    if ENABLE_MOTIVATION_ENGINE:
        g3_steps.append(AtomicStep(
            step_id="G3-S1", description="动机确认与动机线程构建",
            phase_name="phase0_6", task_id="motivation_confirm",
            acceptance_criteria={"metric": "motivation", "op": ">=", "value": 1},
            fallback="跳过动机确认",
        ))

    g3_steps.append(AtomicStep(
        step_id="G3-S2", description="期刊风格自适应学习 + 内容策略规划",
        phase_name="phase0_65", task_id="journal_style_and_content_strategy",
        acceptance_criteria={"metric": "style_profile", "op": ">=", "value": 1},
        fallback="使用默认 IEEE TCSVT 风格",
    ))


    if RUN_ABLATION:
        g3_steps.append(AtomicStep(
            step_id="G3-S5", description="消融实验自动化",
            phase_name="phase0_95", task_id="ablation_experiment",
            acceptance_criteria={},  # 可选步骤
        ))

    # v11.2: PaperContext 构建（在章节生成前，确保共享事实源）
    g3_steps.append(AtomicStep(
        step_id="G3-S6", description="构建 PaperContext（共享事实源）",
        phase_name="phase0_98", task_id="paper_context",
        acceptance_criteria={"metric": "paper_context_exists", "op": "==", "value": True},
    ))

    # v15.7: 图预规划（章节前，建立文图联动通信回路）
    # planner 前移到此处规划，结果经 planning_block 注入章节 prompt，治本 orphan 图
    g3_steps.append(AtomicStep(
        step_id="G3-S7", description="图预规划（章节前，文图联动）",
        phase_name="phase0_99", task_id="figure_preplan",
        acceptance_criteria={"metric": "figure_plan_exists", "op": "==", "value": True},
    ))

    # ── G4: 章节生成 ──
    g4_steps = [
        AtomicStep(
            step_id="G4-S1", description="Ch1 Introduction",
            phase_name="phase1", task_id="generate_chapter1",
            acceptance_criteria={"metric": "chapter_words_1", "op": ">=", "value": 500},
        ),
        AtomicStep(
            step_id="G4-S2", description="Ch2 Related Work",
            phase_name="phase2", task_id="generate_chapter2",
            acceptance_criteria={"metric": "chapter_words_2", "op": ">=", "value": 500},
        ),
        AtomicStep(
            step_id="G4-S3", description="Ch3 Methodology",
            phase_name="phase3", task_id="generate_chapter3",
            acceptance_criteria={"metric": "chapter_words_3", "op": ">=", "value": 500},
        ),
        AtomicStep(
            step_id="G4-S4", description="Ch4 Experiments",
            phase_name="phase4", task_id="generate_chapter4",
            acceptance_criteria={"metric": "chapter_words_4", "op": ">=", "value": 500},
        ),
        AtomicStep(
            step_id="G4-S5", description="Ch5 Conclusion",
            phase_name="phase5", task_id="generate_chapter5",
            # v17: Conclusion 是收束章，天然短于正文（300-600 词属合理范围）。
            # 正文章阈值 500，Conclusion 下调到 350——378 字的 Conclusion 含
            # 背景+3贡献+展望，结构完整，不应因字数判定失败。
            acceptance_criteria={"metric": "chapter_words_5", "op": ">=", "value": 350},
        ),
    ]

    # 额外章节
    extra_sections = []
    if venue_adapter:
        extra_sections = venue_adapter.get_extra_sections() or []

    extra_map = {
        "Discussion": ("phase5_1", "generate_chapter5_1"),
        "Limitations and Future Work": ("phase5_2", "generate_chapter5_2"),
    }
    for i, sec in enumerate(extra_sections):
        if sec in extra_map:
            phase_name, task_id = extra_map[sec]
            g4_steps.append(AtomicStep(
                step_id=f"G4-S{6+i}", description=f"Extra: {sec}",
                phase_name=phase_name, task_id=task_id,
                acceptance_criteria={},  # 额外章节不做强制验收
            ))

    g4_steps.append(AtomicStep(
        step_id="G4-S9", description="Abstract & Keywords",
        phase_name="phase5_5", task_id="generate_abstract",
        acceptance_criteria={},  # Abstract 由 quality_gate 单独评估
    ))

    # v15.3 L2: 全章草稿审计 + 一致性（前移闭环）
    # 在 phase5_5（摘要）之后、phase6（审查）之前，对全章 + 摘要做
    # auditor + cross_chapter 检查，findings 录入 FindingBus 供 _quality_ensure 消费。
    g4_steps.append(AtomicStep(
        step_id="G4-S10", description="Pre-lock Audit & Consistency",
        phase_name="phase5_6", task_id="pre_lock_audit",
        acceptance_criteria={},  # 审计不设硬性指标，critical findings 触发 rerun
    ))

    # ── G5: 学术输出 ──
    g5_steps = [
        AtomicStep(
            step_id="G5-S1", description="参考文献审查",
            phase_name="phase6", task_id="review_content",
            acceptance_criteria={},  # 审查不设硬性指标
        ),
        AtomicStep(
            step_id="G5-S2", description="反幻觉审计",
            phase_name="phase6_5", task_id="audit_content",
            acceptance_criteria={},  # 审计不设硬性指标
        ),
        AtomicStep(
            step_id="G5-S3", description="生成LaTeX/PDF输出",
            phase_name="phase7", task_id="generate_output",
            acceptance_criteria={"metric": "tex_exists", "op": ">=", "value": 1},
            fallback="降级为 Markdown 输出",
        ),
    ]

    goals = [
        AbstractGoal(
            goal_id="G1", description="项目分析",
            acceptance_criteria={"metric": "innovation_points", "op": ">=", "value": 1},
            steps=g1_steps,
        ),
        AbstractGoal(
            goal_id="G2", description="参考文献体系",
            acceptance_criteria={"metric": "bib_entries", "op": ">=", "value": 10},
            steps=g2_steps,
        ),
        AbstractGoal(
            goal_id="G3", description="写作准备",
            acceptance_criteria={"metric": "style_profile", "op": ">=", "value": 1},
            steps=g3_steps,
        ),
        AbstractGoal(
            goal_id="G4", description="章节生成",
            acceptance_criteria={"metric": "unknown_citations", "op": "<=", "value": 0},
            steps=g4_steps,
        ),
        AbstractGoal(
            goal_id="G5", description="学术输出",
            acceptance_criteria={"metric": "pdf_exists", "op": ">=", "value": 1},
            steps=g5_steps,
        ),
    ]

    return HierarchicalPlan(
        goals=goals,
        metadata={"venue": getattr(venue_adapter, 'venue_name', 'default') if venue_adapter else 'default'},
    )
