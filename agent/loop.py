# -*- coding: utf-8 -*-
"""
自主研究循环引擎 - THINK → EXECUTE → VERIFY → REFLECT 闭环

核心架构参考 auto_research_agent 的 4 阶段循环：
- THINK: 分析当前状态，规划下一步
- EXECUTE: 执行具体任务（章节生成、审查等）
- VERIFY: 纯代码验证（零LLM成本），独立于REFLECT
- REFLECT: LLM评估结果，更新记忆，决定下一步

v8.0 系统性升级：
1. VERIFY 独立验证层 — 8项纯代码检查（引用/数据/公式/去重/标记/结构/符号）
2. 有序门控流水线 — P0格式→P1一致性→P2写作质量（高优先级失败时跳过后续）
3. 恒定大小上下文 — 3层记忆固定5000字符预算（工作/短期/长期）
4. 章节级状态机 — outline→draft→review→revision→final（含死循环保护）
5. ToolTrace 反捏造 — 追踪工具调用，验证引用真实性
"""

import os
import re
import json
import time
import logging
import threading
import traceback
from typing import Optional, Dict, Any, List

from agent.api_client import get_api_client, UnifiedAPIClient
from agent.memory import MemoryManager
from agent.checkpoint import CheckpointManager
from agent.quality_gate import QualityGate, QualityReport
from agent.human_directive import DirectiveManager, HumanDirective
from agent.dispatcher import AgentDispatcher, Task
from agent.hierarchical_planner import ValidationEngine
from agent.pipeline_context import PipelineContext
from config.project_config import (
    PAPER_TITLE, ARTICLE_TYPE, PROJECT_CODE_PATH, REF_PDF_PATH,
    OUTPUT_DIR, WORKSPACE_DIR, OUTPUT_LATEX,
    CHECK_REFERENCES, RUN_ABLATION, ENABLE_AUDIT, get_article_type_info,
    ENABLE_MOTIVATION_ENGINE, ENABLE_EXEMPLAR_LEARNING,
    ENABLE_RATIONALE_MATRIX, ENABLE_SEVEN_ANCHOR_TEST,
    ENABLE_MULTI_REVIEWER, ENABLE_CLOSED_BOOK_REWRITE,
)

logger = logging.getLogger(__name__)


def _ctx_property(field_name: str):
    """创建属性代理，将 self._xxx 透明路由到 self.ctx.xxx。
    新代码应直接使用 self.ctx.xxx。"""
    return property(
        lambda self: getattr(self.ctx, field_name),
        lambda self, value: setattr(self.ctx, field_name, value),
    )


class ResearchLoop:
    """
    自主研究循环引擎

    核心循环：
    while self._running:
        directives = self._check_directives()
        thought = self._think()
        result = self._execute(thought)
        reflection = self._reflect(result)
        self._update_state(reflection)

    特性：
    1. 自主迭代：质量不达标自动重试
    2. 断点恢复：崩溃后从检查点恢复
    3. 人工干预：通过文件干预方向
    4. 记忆系统：跨阶段状态保持
    5. 质量门控：每步评估质量
    """

    # ---- PipelineContext 属性代理 ----
    # self._xxx 透明路由到 self.ctx.xxx（单一真相源）
    # 新代码应直接使用 self.ctx.xxx
    _project_data = _ctx_property('project_data')
    _ref_data = _ctx_property('ref_data')
    _chapters = _ctx_property('chapters')
    _abstract = _ctx_property('abstract')
    _reference_pool = _ctx_property('reference_pool')
    _outline = _ctx_property('outline')
    _motivation_thread = _ctx_property('motivation_thread')
    _style_profile = _ctx_property('style_profile')
    _citation_bank = _ctx_property('citation_bank')
    _ablation_results = _ctx_property('ablation_results')
    _journal_style = _ctx_property('journal_style')
    _content_strategy = _ctx_property('content_strategy')
    _paper_context = _ctx_property('paper_context')
    _cite_key_map = _ctx_property('cite_key_map')
    _title_to_key = _ctx_property('title_to_key')

    def __init__(self, api_client: UnifiedAPIClient = None):
        # PipelineContext 必须最先创建（属性代理依赖它）
        self.ctx = PipelineContext()

        self.api_client = api_client or get_api_client()
        self.memory = MemoryManager(OUTPUT_DIR)
        # v13 PR4: 统一问题总线（audit/constraint/quality/cross_chapter 协作中枢）
        from agent.core.finding import FindingBus
        self._findings = FindingBus()
        # v13 接线 P0: 图清单（文图联动单一真相源，替代裸字符串）
        from agent.core.figure_manifest import FigureManifest
        self._figure_manifest = FigureManifest()
        # v15.5 A2.2: figure plan 缓存开关（True = 强制重新规划，调试用）
        self._force_replan = False
        self.checkpoint = CheckpointManager(OUTPUT_DIR)
        self.quality_gate = QualityGate(self.api_client)
        self.directive_mgr = DirectiveManager(OUTPUT_DIR)
        self.dispatcher = AgentDispatcher(
            self.api_client, self.memory, self.quality_gate
        )

        # v5.0: 反幻觉审计引擎
        from agent.auditor import Auditor
        self.auditor = Auditor(self.api_client)

        # v5.5: 跨章节一致性检查器
        from agent.cross_chapter_checker import CrossChapterChecker
        self.cross_chapter_checker = CrossChapterChecker()

        # v7.0: 场景适配器
        from agent.venue_adapter import VenueAdapter
        self.venue_adapter = VenueAdapter()

        # ====== v8.0: 系统性升级模块 ======
        # 1. VERIFY 独立验证层（纯代码，零LLM成本）
        from agent.verifier import ContentVerifier
        self.verifier = ContentVerifier()

        # 2. 有序门控流水线（P0→P1→P2）
        from agent.ordered_gate import OrderedGatePipeline
        self.gate_pipeline = OrderedGatePipeline(
            verifier=self.verifier,
            quality_gate=self.quality_gate,
        )

        # v12.0: 分层验收引擎
        self.validation_engine = ValidationEngine(output_dir=OUTPUT_DIR)

        # 运行时控制（非持久化状态）
        self._running = False
        self._cycle_count = 0
        self._start_time = 0.0
        self._pause_event = threading.Event()  # PAUSE/RESUME 同步事件

        # 注入 API 客户端到 tools 层（解耦反向依赖）
        from tools.base_tool import setup_tool_api
        setup_tool_api(self.api_client)

    def run(self, resume: bool = True):
        """
        启动自主循环

        Args:
            resume: 是否从检查点恢复
        """
        self._running = True
        self._start_time = time.time()

        logger.info("=" * 60)
        logger.info("  论文范文写作助手 v8.0 - 系统性升级架构")
        logger.info("  THINK → EXECUTE → VERIFY → REFLECT 闭环")
        logger.info("=" * 60)
        self._print_config()

        # 初始化输出目录
        self._setup_output_dir()

        # 尝试从检查点恢复
        if resume:
            restored = self._try_resume()
            if not restored:
                self._initialize_project_data()
        else:
            self._initialize_project_data()

        # 创建人工干预模板
        self.directive_mgr.create_template()

        # 规划任务（v7.0: 传入 venue_adapter 实现场景自适应）
        self.dispatcher.plan_tasks(self._project_data, self._ref_data,
                                   venue_adapter=self.venue_adapter)

        # v8.0: 注册章节到状态机
        chapter_keys = ["phase1", "phase2", "phase3", "phase4", "phase5"]
        chapter_names_map = {
            "phase1": "Introduction", "phase2": "Related Work",
            "phase3": "Methodology", "phase4": "Experiments",
            "phase5": "Conclusion",
        }

        # 跳过已完成的阶段
        if resume:
            self._skip_completed_phases()

        # ====== 核心循环 ======
        while self._running:
            self._cycle_count += 1
            task = None  # v11.6: 初始化，防止 except 中 NameError

            try:
                # 1. 检查人工干预
                if not self._check_directives():
                    break

                # 2. 获取下一个任务
                task = self.dispatcher.get_next_task()

                if task is None:
                    # 所有任务完成
                    logger.info("[pipeline] 所有任务已完成！")
                    break

                # 3. THINK: 分析当前状态
                thought = self._think(task)
                self.memory.add_log("log", f"THINK: {thought[:200]}")

                # 4. EXECUTE: 执行任务
                self.dispatcher.mark_task_running(task)
                result = self._execute(task, thought)

                # 5. VERIFY: 纯代码验证（零LLM成本）
                verify_report = self._verify(task, result)

                # 6. REFLECT: LLM评估结果
                reflection = self._reflect(task, result, verify_report)

                # 7. 根据反思结果决定下一步
                if reflection.get("should_retry"):
                    task.retry_count += 1
                    if task.retry_count >= task.max_retries:
                        logger.warning(f"任务 {task.task_id} 达到最大重试({task.max_retries})，强制完成")
                        self._complete_task(task, result, reflection)
                    else:
                        self.dispatcher.reschedule_task(
                            task, reflection.get("strategy", "retry")
                        )
                else:
                    self._complete_task(task, result, reflection)

                # 8. 保存检查点
                self._save_checkpoint(task)

                # 9. 更新记忆
                self.memory.save()

            except KeyboardInterrupt:
                logger.info("[pipeline] 收到中断信号，保存状态...")
                self._running = False
                self._save_all_state()
                self.memory.save()
                self.checkpoint.save_checkpoint(
                    f"cycle_{self._cycle_count}", self._cycle_count,
                    status="interrupted"
                )
                break

            except Exception as e:
                logger.error(f"循环异常: {e}\n{traceback.format_exc()}")
                self.memory.add_log("error", f"循环异常: {str(e)[:500]}")

                # 保存状态后继续
                self._save_all_state()
                self.memory.save()
                try:
                    if task is not None and hasattr(task, 'status') and task.status == "running":
                        self.dispatcher.mark_task_failed(task, str(e))
                        self.checkpoint.save_checkpoint(
                            task.phase_name, task.phase_name.replace("phase", ""),
                            status="failed", error_message=str(e)[:500]
                        )
                        if task.retry_count < task.max_retries:
                            self.dispatcher.reschedule_task(task)
                        else:
                            logger.error(f"任务 {task.task_id} 已达最大重试次数，跳过")
                except NameError:
                    pass  # task 未定义（理论上不会发生）

        # ====== 循环结束 ======
        self._running = False
        elapsed = time.time() - self._start_time
        progress = self.dispatcher.get_progress()

        logger.info("\n" + "=" * 60)
        logger.info(f"  执行完成！耗时 {elapsed/60:.1f} 分钟，共 {self._cycle_count} 个循环")
        logger.info(f"  完成: {progress['completed']}/{progress['total']}")
        logger.info(f"  失败: {progress['failed']}/{progress['total']}")
        logger.info("=" * 60)

        logger.info(self.checkpoint.get_summary())

    def _print_config(self):
        """打印当前配置"""
        article_info = get_article_type_info()
        logger.info(f"  论文标题: {PAPER_TITLE}")
        logger.info(f"  文章类型: {ARTICLE_TYPE} ({article_info['name']})")
        logger.info(f"  场景模式: {self.venue_adapter.profile.venue_type}")
        logger.info(f"  项目代码: {PROJECT_CODE_PATH}")
        logger.info(f"  参考PDF: {REF_PDF_PATH}")
        logger.info(f"  输出格式: {'LaTeX' if OUTPUT_LATEX else 'Word'}")
        logger.info(f"  质量门控: 已启用（阈值 {self.venue_adapter.get_quality_threshold()}）")
        logger.info(f"  参考文献审查: {'是' if CHECK_REFERENCES else '否'}")
        logger.info(f"  反幻觉审计: {'是' if ENABLE_AUDIT else '否'}")
        logger.info(f"  消融实验: {'是' if RUN_ABLATION else '否'}")
        logger.info(f"  动机引擎: {'是' if ENABLE_MOTIVATION_ENGINE else '否'}")
        logger.info(f"  范例学习: {'是' if ENABLE_EXEMPLAR_LEARNING else '否'}")
        logger.info(f"  写作矩阵: {'是' if ENABLE_RATIONALE_MATRIX else '否'}")
        logger.info(f"  额外章节: {self.venue_adapter.get_extra_sections() or '无'}")

    def _setup_output_dir(self):
        """设置输出目录"""
        from datetime import datetime
        import shutil

        output_dir = OUTPUT_DIR
        if os.path.exists(output_dir):
            try:
                cases_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "cases")
                os.makedirs(cases_dir, exist_ok=True)
                current_time = datetime.now().strftime("%m%d_%H%M")
                new_dir_name = f"output_{current_time}"
                new_dir_path = os.path.join(cases_dir, new_dir_name)
                shutil.move(output_dir, new_dir_path)
                logger.info(f"[pipeline] 已将旧输出归档到 {new_dir_path}")
            except Exception as e:
                logger.warning(f"归档旧输出目录失败: {e}")

        os.makedirs(output_dir, exist_ok=True)
        for i in range(1, 6):
            os.makedirs(f"{output_dir}/chapter{i}", exist_ok=True)
        os.makedirs(f"{output_dir}/abstract", exist_ok=True)
        os.makedirs(f"{output_dir}/latex", exist_ok=True)

    def _try_resume(self) -> bool:
        """尝试从检查点恢复"""
        if self.checkpoint.load() and self.memory.load():
            last_phase = self.checkpoint.get_last_completed_phase()
            if last_phase:
                logger.info(f"[pipeline] 从检查点恢复，最后完成阶段: {last_phase}")
                # 恢复所有状态到 PipelineContext
                self.ctx.load_from_checkpoint(self.checkpoint)
                logger.info(
                    f"[pipeline] 恢复状态: chapters={len(self.ctx.chapters)}, "
                    f"ref_pool={len(self.ctx.reference_pool)}, "
                    f"outline={bool(self.ctx.outline)}, "
                    f"ablation={bool(self.ctx.ablation_results)}"
                )

                return bool(self._project_data)
        return False

    def _initialize_project_data(self):
        """初始化项目数据（Phase 0）"""
        from agent.skill_orchestrators.project_analyzer import run_project_analyzer
        from agent.skill_orchestrators.ref_pdf_analyzer import run_ref_pdf_analyzer

        logger.info("\n" + "=" * 60)
        logger.info("  Phase 0: 分析工程代码与参考论文")
        logger.info("=" * 60)

        # 分析工程代码
        logger.info("[Phase 0.1] 分析项目工程代码...")
        self._project_data = run_project_analyzer()

        # 分析参考PDF
        logger.info("[Phase 0.2] 分析参考论文PDF...")
        self._ref_data = run_ref_pdf_analyzer()

        # 初始化记忆中的项目简报
        self.memory.brief = self._build_project_brief()

        # 保存到检查点
        self.checkpoint.save_state("project_data", self._project_data)
        self.checkpoint.save_state("ref_data", self._ref_data)
        self.checkpoint.save_checkpoint("phase0", 0, status="completed")

        # Phase 0.5 现在由 dispatcher 统一调度，不再在此处执行

        # ====== Phase 0.3: 创新点验证与递进设计 ======
        try:
            innovation_points = self._project_data.get("innovation_points", [])
            if innovation_points:
                logger.info("[Phase 0.3] 创新点验证与递进设计...")
                from tools.innovation_verifier import run_innovation_verifier
                verify_result = run_innovation_verifier(
                    OUTPUT_DIR, innovation_points, api_client=self.api_client)
                # 更新 project_data 中的创新点（增加验证信息）
                self._project_data["innovation_points"] = verify_result.get(
                    "innovation_points", innovation_points)
                self._project_data["anchor_map"] = verify_result.get("anchor_map", {})
                novelty = verify_result.get("novelty_scores", [])
                avg_novelty = sum(n.get("score", 0.5) for n in novelty) / max(len(novelty), 1)
                logger.info(f"[Phase 0.3] 验证完成: 平均新颖性={avg_novelty:.2f}")
        except Exception as e:
            logger.warning(f"[Phase 0.3] 创新点验证失败: {e}")

    def _build_project_brief(self) -> str:
        """构建项目简报（用于记忆系统）"""
        brief_parts = [f"论文标题: {PAPER_TITLE}"]

        innovation = self._project_data.get("innovation_points", [])
        if innovation:
            brief_parts.append("\n创新点:")
            for i, ip in enumerate(innovation, 1):
                brief_parts.append(f"  {i}. {ip.get('创新点名称', 'N/A')}: {ip.get('创新点价值', 'N/A')}")

        arch = self._project_data.get("model_architecture", {})
        if arch:
            brief_parts.append(f"\n模型架构: {arch.get('总体架构', 'N/A')[:500]}")

        exp = self._project_data.get("experiment_design", {})
        if exp:
            datasets = exp.get("数据集", [])
            if datasets:
                brief_parts.append(f"\n数据集: {json.dumps(datasets, ensure_ascii=False)[:300]}")

        return "\n".join(brief_parts)

    def _skip_completed_phases(self):
        """跳过已完成的阶段"""
        completed = self.checkpoint.get_completed_phases()

        for task in self.dispatcher.get_all_tasks():
            if task.phase_name in completed:
                task.status = "completed"
                logger.info(f"跳过已完成阶段: {task.phase_name}")

    def _check_directives(self) -> bool:
        """
        检查人工干预指令

        Returns:
            bool: True=继续运行, False=应该停止
        """
        directives = self.directive_mgr.check()

        for d in directives:
            self.memory.add_log("decision", f"人工指令: {d.directive_type} -> {d.target or d.reason[:100]}")

            if d.directive_type == "STOP":
                logger.info("[directive] 收到STOP指令，停止执行")
                self.directive_mgr.acknowledge(d)
                self.directive_mgr.clear_directive_file()
                return False

            elif d.directive_type == "PAUSE":
                logger.info("[directive] 收到PAUSE指令，暂停执行（创建RESUME指令恢复）")
                self.directive_mgr.acknowledge(d)
                # 使用 Event 等待 RESUME，避免忙等待
                self._pause_event.clear()
                while self._running:
                    if self._pause_event.wait(timeout=10):
                        # event 被 set，说明收到 RESUME
                        logger.info("[directive] 收到RESUME指令，恢复执行")
                        break
                    # timeout 后检查是否有新的 STOP 指令
                    new_directives = self.directive_mgr.check()
                    for nd in new_directives:
                        if nd.directive_type == "STOP":
                            self.directive_mgr.acknowledge(nd)
                            return False
                        elif nd.directive_type == "RESUME":
                            logger.info("[directive] 收到RESUME指令，恢复执行")
                            self.directive_mgr.acknowledge(nd)
                            self._pause_event.set()
                            break

            elif d.directive_type == "SKIP":
                self.dispatcher.skip_task_by_name(d.target)
                self.directive_mgr.acknowledge(d)

            elif d.directive_type == "REDO":
                self.dispatcher.redo_task_by_name(d.target)
                self.directive_mgr.acknowledge(d)

            elif d.directive_type == "ADJUST":
                self.memory.add_log("decision", f"方向调整: {d.reason}")
                self.directive_mgr.acknowledge(d)

        self.directive_mgr.clear_directive_file()
        return True

    def _think(self, task: Task) -> str:
        """
        THINK: 分析当前状态，规划下一步

        使用轻量 LLM 调用分析前序章节质量和项目数据，输出执行策略。
        对于重试任务，分析失败原因并给出具体调整建议。
        """
        progress = self.dispatcher.get_progress()

        if task.retry_count > 0:
            # 重试策略：基于失败历史进行分析
            recent_quality = self.quality_gate.get_history()[-3:]
            quality_summary = "; ".join(
                f"{h.get('chapter', '?')}: {h.get('overall_score', 0):.0f}"
                for h in recent_quality
            )

            strategy = (
                f"重试策略(第{task.retry_count}次): {task.target}\n"
                f"历史质量: {quality_summary}\n"
                f"策略: 根据之前的评估反馈调整生成 prompt，重点关注低分维度"
            )
        else:
            strategy = f"首次执行: {task.target}"

        # 使用 LLM 做轻量策略分析（仅在有前序章节时）

        logger.info(f"THINK [{progress['completed']}/{progress['total']}]: {task.target} - {strategy[:200]}")

        return strategy

    def _execute(self, task: Task, thought: str) -> Any:
        """
        EXECUTE: 执行具体任务

        根据任务类型分发到对应的Skill
        """
        phase = task.phase_name
        result = None
        start = time.time()

        try:
            if phase == "phase0":
                # 已在初始化时执行
                result = {"project_data": self._project_data, "ref_data": self._ref_data}

            elif phase == "phase0_5":
                # v7.0: 参考文献池构建 + 全局大纲规划
                # 如果已由 _initialize_project_data 完成，直接通过
                if self._reference_pool or self._outline:
                    result = {"reference_pool_size": len(self._reference_pool)}
                else:
                    self._init_reference_pool_and_outline()
                    result = {"reference_pool_size": len(self._reference_pool)}

            elif phase == "phase0_6":
                # v7.0: 动机确认
                result = self._run_motivation_phase()

            elif phase == "phase0_7":
                # v7.0: 范例学习
                result = {}  # v14: exemplar_learner 已删（0消费空转）

            elif phase == "phase0_65":
                # v10.1: 期刊风格学习 + 内容策略规划
                result = self._run_journal_style_and_content_strategy_phase()

            elif phase == "phase0_8":
                # v7.0: 引用支撑库
                result = self._run_citation_bank_phase()

            elif phase == "phase0_9":
                # v7.0: 写作理由矩阵
                result = {}  # v14: rationale_matrix 已删（0消费空转）

            elif phase == "phase0_95":
                # v7.0: 消融实验自动化
                result = self._run_ablation_phase()

            elif phase == "phase0_98":
                # v11.2: 构建 PaperContext（共享事实源）
                self._build_paper_context()

            elif phase == "phase0_99":
                # v15.7: 图预规划（章节前，文图联动通信回路）
                self._plan_figures_early()



            elif phase in ("phase1", "phase2", "phase3", "phase4", "phase5"):
                ch_num = int(phase.replace("phase", ""))
                result = self._run_chapter_phase(ch_num)

            elif phase == "phase5_1":
                # v7.0: Discussion（期刊扩展章节）
                result = self._generate_extra_chapter("Discussion", "phase5_1")
                self._chapters["5_1"] = result

            elif phase == "phase5_2":
                # v7.0: Limitations and Future Work（期刊扩展章节）
                result = self._generate_extra_chapter("Limitations and Future Work", "phase5_2")
                self._chapters["5_2"] = result

            elif phase == "phase5_5":
                # 生成摘要和关键词（在所有章节完成后）
                from agent.skill_executor import SkillExecutor
                executor = SkillExecutor(self.api_client, self.quality_gate)
                previous_summary = self._build_previous_summary()

                # 提取实验章节的实际数值用于 Abstract
                experiments_summary = ""
                if 4 in self._chapters:
                    experiments_summary = self._chapters[4][:3000]
                    # 提取 "Ours" 行或最佳结果的数值
                    ours_matches = re.findall(
                        r'(?:Ours|ours|Ours \(|proposed)[^\n]*?(\d+\.\d+)',
                        experiments_summary
                    )
                    if ours_matches:
                        experiments_summary += f"\n\n**关键数值（必须使用这些数字）**: {ours_matches[:15]}"

                # v15.8 改动1: 弱点一致性闭环——abstract 必须看到 Limitations 的弱点认知
                # + FactBase 对比结论，避免声称与弱点矛盾（L3 issue[0]/[2] 根因）
                limitations_summary = ""
                if "5_2" in self._chapters:
                    limitations_summary = self._chapters["5_2"][:2000]
                fact_sheet = ""
                if getattr(self, '_factbase', None) and not self._factbase.is_empty():
                    fact_sheet = self._factbase.as_fact_sheet()

                exec_result = executor.execute_with_quality(
                    "abstract",
                    {
                        "article_type": ARTICLE_TYPE,
                        "paper_title": PAPER_TITLE,
                        "innovation_points": self._project_data.get("innovation_points", []),
                        "experiment_design": self._project_data.get("experiment_design", {}),
                        "model_architecture": self._project_data.get("model_architecture", {}),
                        "previous_content": previous_summary,
                        "style_guide": self._ref_data.get("style_guide", {}),
                        "experiments_summary": experiments_summary,
                        "citation_context": self._build_citation_context(),
                        # v15.8: 弱点一致性——abstract 生成时已知 Limitations 承认的弱点
                        "limitations_summary": limitations_summary,
                        "fact_sheet": fact_sheet,
                    },
                    style_guide=self._ref_data.get("style_guide", {}),
                )
                self._abstract = exec_result["content"]
                result = self._abstract

            elif phase == "phase5_6":
                # v15.3 L2: 全章草稿审计 + 一致性（前移闭环）
                # 在 phase5_5（摘要）后、phase6（审查）前，对全章 + 摘要做
                # auditor + cross_chapter，findings 录入 FindingBus 供 _quality_ensure 消费。
                result = self._run_pre_lock_audit()

            elif phase == "phase6":
                result = self._run_review_phase()

            elif phase == "phase6_5":
                # v5.0: 反幻觉审计
                result = self._run_audit_phase()

            elif phase == "phase7":
                result = self._run_output_phase()

        except Exception as e:
            logger.error(f"执行任务 {task.task_id} 失败: {e}")
            raise

        duration = time.time() - start
        self.memory.add_log("log", f"EXECUTE: {task.target} 完成, 耗时 {duration:.0f}s")

        return result

    def _quality_ensure(self, chapter_name: str, content: str):
        """
        对章节内容进行质量评估和自动修改

        v13 PR5: QualityLoop 真闭环 — 修订时不仅看 QualityGate 自身维度，
        还把 FindingBus 里跨子系统问题（cross_chapter 数值矛盾、auditor 引用等）
        注入修订 prompt，让一次修订同时修复多类问题。

        Returns:
            Tuple[str, QualityReport]: (最终内容, 质量报告)
        """
        style_guide = self._ref_data.get("style_guide", {})
        chapter_org = self._ref_data.get("chapter_organizations", {}).get(chapter_name, {})
        previous_content = "\n".join(
            self._chapters.get(i, "")[:500] for i in sorted(self._chapters, key=str)
        )
        # v13 PR5: 从 FindingBus 取该章的跨子系统问题简报
        _brief = ""
        try:
            _brief = self._findings.as_revision_brief(_ch_name_to_loc(chapter_name), max_chars=1200)
        except Exception:
            _brief = ""

        _result = self.quality_gate.evaluate_and_revise(
            chapter_name, content,
            style_guide, chapter_org, previous_content,
            extra_findings_brief=_brief,
        )
        # v13 接线 P0-c: QualityGate 评估结果录入 FindingBus（补 quality 类 findings）
        try:
            _final_report = _result[1] if isinstance(_result, tuple) else None
            if _final_report is not None and getattr(_final_report, "issues", None):
                from agent.core.finding import quality_issues_to_findings as _q2f, Severity
                _ch_loc = self._ch_name_to_loc(chapter_name)
                _ch_loc = self._ch_name_to_loc(chapter_name)
                self._findings.clear(source="quality")  # quality 按章重评，清旧留新
                self._findings.record_many(_q2f(_final_report.issues, chapter_hint=_ch_loc))
        except Exception:
            pass
        return _result

    @staticmethod
    def _ch_name_to_loc(name):
        """章节英文名 → FindingBus location.chapter (chN)。"""
        m = {"introduction": "ch1", "related work": "ch2", "methodology": "ch3",
             "experiments": "ch4", "conclusion": "ch5"}
        return m.get((name or "").strip().lower(), "")

    # ── 章节生成统一入口（消除 phase1–phase5 的重复模式） ──
    _CHAPTER_CONFIGS = {
        1: ("ch1_introduction", "Introduction"),
        2: ("ch2_related_work", "Related Work"),
        3: ("ch3_methodology", "Methodology"),
        4: ("ch4_experiments", "Experiments"),
        5: ("ch5_conclusion", "Conclusion"),
    }

    def _run_chapter_phase(self, phase_num: int) -> str:
        """
        统一处理章节生成（phase1–phase5）。

        流程：构建前序摘要 → 调用 orchestrator → 质量保证 → 存储 → 即时审计
        """
        import importlib
        module_name, chapter_name = self._CHAPTER_CONFIGS[phase_num]
        mod = importlib.import_module(f"agent.skill_orchestrators.{module_name}")
        run_fn = getattr(mod, f"run_chapter{phase_num}")

        # 构建前序章节摘要（chapter 1 无前序章节）
        previous_chapters = {}
        for ch_num in range(1, phase_num):
            if ch_num in self._chapters:
                previous_chapters[ch_num] = self._chapters[ch_num][:2000]

        # v12.2: 注入 Phase 0.65 分析结果到 project_data（消除 16 次 LLM 调用浪费）
        if hasattr(self, '_content_strategy') and self._content_strategy:
            self._project_data['content_strategy'] = self._content_strategy
        if hasattr(self, '_motivation_thread') and self._motivation_thread:
            self._project_data['motivation_thread'] = self._motivation_thread
        # v14 龙骨: outline 注入 project_data（剥包装层，planning_block 读章节契约）
        if hasattr(self, '_outline') and self._outline:
            _ol = self._outline.get("outline", self._outline) if isinstance(self._outline, dict) else {}
            self._project_data['outline'] = _ol
        # v14: rationale_matrix/exemplar_learner 已删（0消费空转）

        kwargs = {"citation_context": self._build_citation_context(),
                  "venue_adapter": self.venue_adapter}
        if phase_num > 1:
            kwargs["previous_chapters"] = previous_chapters
        if phase_num == 5:
            kwargs["skip_limitations"] = self._has_extra_discussion()

        content = run_fn(self._project_data, self._ref_data, **kwargs)
        content, _ = self._quality_ensure(chapter_name, content)
        self._chapters[phase_num] = content
        return content  # 审计在 Phase 6.5 统一做

    def _has_extra_discussion(self) -> bool:
        """检查 venue_adapter 是否配置了独立的 Discussion/Limitations 章节"""
        try:
            extra_sections = self.venue_adapter.get_extra_sections()
            if extra_sections:
                return any(
                    s.lower() in " ".join(extra_sections).lower()
                    for s in ["discussion", "limitations"]
                )
        except Exception as e:
            logger.debug(f"获取额外章节失败: {e}")
        return False

    def _verify(self, task: Task, result: Any):
        """
        VERIFY: 纯代码验证（零LLM成本）

        v8.0 新增：借鉴 auto_research_agent 的 VERIFY 阶段
        - 章节级：即时验证当前章节内容
        - 全文级：在 Phase 7 运行有序门控流水线

        Returns:
            VerifyReport or None
        """
        phase = task.phase_name

        # 只对章节生成任务做验证
        if task.task_type != "generate":
            return None

        # 提取内容字符串
        content = None
        if isinstance(result, str) and len(result) > 50:
            content = result
        elif isinstance(result, dict):
            # 某些 phase 返回 dict，如 phase0
            content = result.get("content", "")
            if not content:
                return None

        if not content:
            return None

        # 确定章节名称
        chapter_names = {
            "phase1": "Introduction", "phase2": "Related Work",
            "phase3": "Methodology", "phase4": "Experiments",
            "phase5": "Conclusion", "phase5_5": "Abstract",
        }
        ch_name = chapter_names.get(phase, phase)

        # 单章节验证
        report = self.verifier.verify_chapter(ch_name, content)

        if not report.passed:
            logger.warning(
                f"[VERIFY] {ch_name} 未通过: {report.summary()}"
            )
            for hint in report.get_fix_hints():
                logger.info(f"  修复建议: {hint}")

        return report

    def _complete_task(self, task, result, reflection: dict):
        """统一完成任务：构造 quality_report 并标记完成"""
        score = reflection.get("quality_score", -1)
        # 直接构造 dict，避免 type('QReport',...)() 动态类的坏味道
        # dispatcher.mark_task_completed 期望接收对象（调 .overall_score / .to_dict()），
        # 这里用 SimpleNamespace 替代动态类，既保留属性访问又更健壮
        from types import SimpleNamespace
        quality_info = SimpleNamespace(
            overall_score=score,
            to_dict=lambda s=None, sc=score: {"overall_score": sc},
        ) if score >= 0 else None
        self.dispatcher.mark_task_completed(task, result, quality_report=quality_info)

        # v12.0: 同步更新分层规划的 AtomicStep 状态
        self.dispatcher.update_step_status(
            task.phase_name, status="completed", actual_value=score
        )

    def _build_paper_context(self):
        """
        v12.1: 构建共享事实字典 PaperContext。

        从 project_data + experiment_design 提取硬件、epochs、loss 项、数据集、
        指标数值、模型名称等，注入到 self._project_data["paper_context"]。

        适配实际 experiment_design.json 的中文嵌套结构：
        {
          "数据集": [{"名称": "...", ...}],
          "训练策略": {"优化器": "...", "学习率": "...", "损失函数": "..."},
          "评估指标": [{"指标名称": "...", "实际达成值": 0.133, ...}],
          "关键实验结果": {"成功发现": [...], "失败与局限性": [...]}
        }
        """
        pd = self._project_data or {}
        # 多路径查找 experiment_design
        exp_design = pd.get("experiment_design", {})
        if not exp_design:
            # 有时 experiment_design 就是顶层字典本身
            if any(k in pd for k in ["数据集", "训练策略", "评估指标"]):
                exp_design = pd

        # ── 提取硬件配置 ──
        hardware = ""
        for key in ["硬件配置", "hardware"]:
            val = exp_design.get(key, "")
            if val:
                hardware = str(val)
                break
        if not hardware:
            impl = exp_design.get("implementation_details", {})
            if isinstance(impl, dict):
                hardware = impl.get("hardware", "")
        if not hardware:
            # 尝试从 project_info.json 或 训练策略 中获取
            for key in ["训练设备", "GPU", "gpu"]:
                val = exp_design.get(key, "")
                if val:
                    hardware = str(val)
                    break

        # ── 提取训练参数 ──
        training_params = {}
        # 先从 训练策略 子字典提取
        strategy = exp_design.get("训练策略", {})
        if isinstance(strategy, dict):
            # v15.3 L1-2: 扩展 key_map 覆盖实际数据格式 + patch_size（L3 issue #3 根因）
            key_map = {
                "优化器": "optimizer", "学习率": "learning_rate",
                "优化器与学习率": "optimizer_lr",
                "权重衰减": "weight_decay", "batch_size": "batch_size",
                "Batch Size": "batch_size",
                "损失函数": "loss_function", "采样与数据策略": "sampling_strategy",
                "epoch": "epochs", "训练轮数": "epochs",
                "Epochs": "epochs",
                "patch_size": "patch_size", "Patch Size": "patch_size",
                "训练尺寸": "patch_size", "patch": "patch_size",
                "其他策略": "other_strategy",
            }
            for cn_key, en_key in key_map.items():
                val = strategy.get(cn_key, "")
                if val and en_key not in training_params:
                    training_params[en_key] = str(val)
        # v15.3 L1-2: 从实验设置文本里抽 patch_size（如 "128×128 patches"）
        for section_key in ["训练策略", "实验设置", "数据集"]:
            section = exp_design.get(section_key, {})
            if isinstance(section, dict):
                section_text = json.dumps(section, ensure_ascii=False)
            elif isinstance(section, str):
                section_text = section
            else:
                continue
            patch_m = re.search(r'(\d{2,4})\s*[×x*]\s*(\d{2,4})\s*(?:patch|crop|tile|image)', section_text, re.IGNORECASE)
            if patch_m and "patch_size" not in training_params:
                training_params["patch_size"] = f"{patch_m.group(1)}x{patch_m.group(2)}"
                break
        # 再用英文 key 做补充（兼容旧格式）
        for key in ["epochs", "batch_size", "optimizer", "learning_rate", "patch_size"]:
            val = exp_design.get(key, "")
            if val and key not in training_params:
                training_params[key] = str(val)

        # ── 提取 loss 函数 ──
        loss_terms = []
        loss_info = ""
        if isinstance(strategy, dict):
            loss_info = strategy.get("损失函数", "")
        if not loss_info:
            loss_info = exp_design.get("loss_function", "") or exp_design.get("损失函数", "")
        if loss_info:
            loss_terms.append(str(loss_info))
        for key in ["loss_terms", "loss_components"]:
            val = exp_design.get(key, [])
            if isinstance(val, list):
                loss_terms.extend(str(v) for v in val)

        # ── 提取数据集 ──
        datasets = exp_design.get("datasets", []) or exp_design.get("数据集", [])
        if isinstance(datasets, str):
            datasets = [datasets]
        elif isinstance(datasets, dict):
            # dict 格式：提取 名称 字段（可能是 list 或 str）
            names = datasets.get("名称", datasets.get("name", []))
            if isinstance(names, (list, tuple, set)):
                datasets = [str(n) for n in names]
            elif isinstance(names, str):
                datasets = [names]
            else:
                datasets = []
        # 处理 list of dict 格式：提取名称
        if isinstance(datasets, list):
            dataset_names = []
            for ds in datasets:
                if isinstance(ds, dict):
                    name = ds.get("名称", ds.get("name", ""))
                    if name:
                        dataset_names.append(name)
                elif isinstance(ds, str):
                    dataset_names.append(ds)
            datasets = dataset_names
        elif isinstance(datasets, (set, tuple)):
            datasets = list(datasets)

        # ── 提取指标数值 ──
        metrics = {}
        # 从 ablation_results 提取
        ablation = self._ablation_results or {}
        if isinstance(ablation, dict):
            main_results = ablation.get("main_results", {})
            if isinstance(main_results, dict):
                for k, v in main_results.items():
                    if isinstance(v, (int, float)):
                        metrics[k] = v
        # 从 评估指标 list of dict 提取（v12.1 新增）
        eval_metrics = exp_design.get("评估指标", [])
        if isinstance(eval_metrics, list):
            for em in eval_metrics:
                if isinstance(em, dict):
                    name = em.get("指标名称", em.get("name", ""))
                    actual = em.get("实际达成值", em.get("actual", ""))
                    if name and actual is not None:
                        try:
                            metrics[name] = float(actual)
                        except (ValueError, TypeError):
                            metrics[name] = str(actual)
        # 从 关键实验结果 / 关键结果 / key_results 提取
        key_results = exp_design.get("关键结果", {}) or exp_design.get("key_results", {})
        if isinstance(key_results, dict):
            # v14: 递归展平嵌套 dict（修 FactBase 空壳断点——旧逻辑只展开一层，嵌套数值被丢）
            def _flatten_metrics(d, prefix=""):
                for k, v in d.items():
                    if isinstance(v, (int, float)) and not isinstance(v, bool):
                        # 保留嵌套前缀（如 "表现.Best MAE"），便于溯源嵌套层级
                        flat_key = (prefix + str(k)) if prefix else str(k)
                        try:
                            metrics[flat_key] = float(v)
                        except (TypeError, ValueError):
                            pass
                    elif isinstance(v, str):
                        # 尝试把 "0.133" 这类数值字符串转 float
                        try:
                            fv = float(v.strip())
                            flat_key = (prefix + str(k)) if prefix else str(k)
                            metrics[flat_key] = fv
                        except ValueError:
                            pass  # 非数值描述串，跳过
                    elif isinstance(v, dict):
                        _flatten_metrics(v, (prefix + str(k) + ".") if prefix else str(k) + ".")
            _flatten_metrics(key_results)
        # 从 关键实验结果.成功发现 解析数值（格式: "Overall MAE 达到 0.133"）
        key_exp = exp_design.get("关键实验结果", {})
        if isinstance(key_exp, dict):
            for item in key_exp.get("成功发现", []):
                if isinstance(item, str):
                    # 尝试解析 "XXX 达到 N.NNN" 格式
                    m = re.search(r'(\S+ MAE)\s+达到\s+([\d.]+)', item)
                    if m:
                        try:
                            metrics[m.group(1)] = float(m.group(2))
                        except ValueError:
                            pass

        # ── 提取模型名称和创新点 ──
        model_name = (pd.get("model_name", "") or pd.get("模型名称", "")
                      or pd.get("项目名称", ""))
        if not model_name:
            arch = pd.get("model_architecture", pd.get("模型架构", {}))
            if isinstance(arch, dict):
                model_name = arch.get("name", arch.get("模型名称", ""))

        innovation_points = pd.get("innovation_points", [])
        inn_names = []
        if isinstance(innovation_points, list):
            for ip in innovation_points[:5]:
                if isinstance(ip, dict):
                    inn_names.append(ip.get("创新点名称", ip.get("name", "")))
                elif isinstance(ip, str):
                    inn_names.append(ip)

        # v13 PR2: 经 FactBase 单一事实源构建 + 持久化（保证落盘，替代旧松散 dict）
        from agent.core.factbase import FactBase, save as _fb_save
        paper_context = {
            "hardware": hardware,
            "training_params": training_params,
            "loss_terms": loss_terms,
            "datasets": datasets,
            "metrics": metrics,
            "model_name": model_name,
            "innovation_names": inn_names,
        }
        _factbase = FactBase.from_dict(paper_context)
        # 注入到 project_data（各 generator 从这里读取）+ self（CrossChapterChecker 用）
        if not isinstance(self._project_data, dict):
            self._project_data = {}
        self._project_data["paper_context"] = paper_context
        self._paper_context = paper_context
        self._factbase = _factbase
        # v13 P1/P2 接线: 把 FactBase 注入 auditor/verifier/cross_chapter
        # （消数值分歧：三者统一读 FactBase，不再各自从 project_data 重推导）
        if hasattr(self, 'auditor') and self.auditor is not None:
            self.auditor.set_factbase(_factbase)
        if hasattr(self, 'verifier') and self.verifier is not None:
            self.verifier.set_factbase(_factbase)
        if hasattr(self, 'cross_chapter_checker') and self.cross_chapter_checker is not None:
            self.cross_chapter_checker.set_factbase(_factbase)
        # 持久化：FactBase 保证 factbase.json + 兼容 paper_context.json 都落盘
        try:
            _fb_save(_factbase, OUTPUT_DIR)
        except OSError as e:
            logger.error(f"[FactBase] 持久化失败 [{e}] — 验收器将无法读到事实源")
            # 不静默降级：抛出由上层 Phase 0.98 决定（但当前 _build_paper_context 被
            # try/except 包住，所以这里至少 error 级别记录 + 不返回空 dict）

        logger.info(f"[FactBase] 构建完成: "
                     f"hardware={hardware[:50] if hardware else 'N/A'}, "
                     f"training_params={list(training_params.keys())}, "
                     f"loss_terms={len(loss_terms)}, "
                     f"datasets={datasets}, "
                     f"metrics={list(metrics.keys())}, "
                     f"model={model_name}")

        return paper_context

    def _plan_figures_early(self):
        """v15.7 phase0_99: 图规划前移——章节前规划图，建立文图联动通信回路。

        根因：planner 原在 Phase7.28（章节后）规划，结果从未流入章节生成 → 7 张图全 orphan。
        解法：前移到此处（章节前），用 abstract+innovation 规划（method_text 留空，章节未生成），
        填 manifest(PLANNED) + 构建章节图指令塞 project_data['figure_directives']，
        后续 planning_block 自动注入章节 prompt。Phase7.28 复用此 plan（ablation_hash 一致）。
        """
        from tools.figure_planner import plan_figures
        _content = {
            "title": PAPER_TITLE,
            "abstract": (getattr(self, '_abstract', '') or ''
                         or (self._outline or {}).get('abstract', '')),
            "method_text": "",  # 章节未生成，留空——planner 靠 abstract+innovation 规划
            "innovations": self._project_data.get("innovation_points", []),
        }
        _venue = (getattr(self.venue_adapter, 'venue_name', 'IEEE TCSVT')
                  if self.venue_adapter else 'IEEE TCSVT')
        try:
            plan = plan_figures(
                _content, venue=_venue,
                content_brief=getattr(self, '_content_strategy', None),
            )
        except Exception as e:
            logger.warning(f"[phase0_99] 图预规划失败（章节将无图引用指令）: {e}")
            return
        # ablation_hash 与 Phase7.28 一致 → 7.28 复用此 plan 不重新规划
        plan["_ablation_hash"] = (hash(json.dumps(self._ablation_results, sort_keys=True,
                                                   default=str))
                                  if self._ablation_results else 0)
        try:
            with open(os.path.join(OUTPUT_DIR, "figure_plan.json"), "w", encoding="utf-8") as f:
                json.dump(plan, f, ensure_ascii=False, indent=2)
        except Exception as we:
            logger.warning(f"[phase0_99] figure_plan.json 写盘失败: {we}")
        # 填 manifest(PLANNED) + 构建章节图指令
        from agent.core.figure_manifest import FigureEntry, FigStatus, FigType, _TYPE_TO_SECTION
        _type_map = {"teaser": FigType.TEASER, "architecture": FigType.ARCHITECTURE,
                     "module_detail": FigType.MODULE_DETAIL, "ablation": FigType.ABLATION,
                     "comparison": FigType.COMPARISON, "qualitative": FigType.QUALITATIVE}
        directives = {}  # {章节号(str): [(label, 描述), ...]}
        for f_fig in plan.get("figures", []):
            ft = f_fig.get("fig_type", "")
            ftype = _type_map.get(ft, FigType.MODULE_DETAIL)
            sec = _TYPE_TO_SECTION.get(ftype, "")
            fig_id = f_fig.get("fig_id", ft)
            self._figure_manifest.add(FigureEntry(
                fig_id=fig_id, fig_type=ftype, label=f"fig:{fig_id}",
                belongs_to_section=sec,
                supports_claim=f_fig.get("title", fig_id),
                status=FigStatus.PLANNED,
            ))
            if sec:
                directives.setdefault(sec, []).append(
                    (f"fig:{fig_id}", f_fig.get("title", ft)))
        self._project_data['figure_directives'] = directives
        logger.info(f"[phase0_99] 图预规划完成: {len(plan.get('figures', []))} 张, "
                    f"manifest 填 PLANNED, 章节指令: "
                    f"{ {k: len(v) for k, v in directives.items()} }")

    def _build_citation_context(self) -> str:
        """v14: 委托给 CitationInjector。注：每次新建实例（citation_bank 会变），
        内联缓存可能不命中但不影响正确性。"""
        from agent.citation_injector import CitationInjector
        _inj = CitationInjector(
            reference_pool=self._reference_pool,
            citation_bank=self._citation_bank,
            factbase=getattr(self, '_factbase', None),
            paper_context=getattr(self, '_paper_context', None),

        )
        result = _inj.build()
        # 回写 cite_key_map / title_to_key（BibTeX 阶段依赖）
        self._cite_key_map = _inj.cite_key_map
        self._title_to_key = _inj.title_to_key
        return result

    # v15.7: LLM 常用命令 → 所需宏包映射（LLM 可能用了未 load 的命令）
    _CMD_TO_PACKAGE = {
        "makecell": "makecell", "multirow": "multirow",
        "toprule": "booktabs", "midrule": "booktabs", "bottomrule": "booktabs",
        "tabularx": "tabularx", "subfloat": "subfig",
        "definecolor": "xcolor", "rowcolor": "colortbl",
        "bm": "bm", "boldsymbol": "amsmath",
        "mathbb": "amssymb", "mathcal": "amsmath",
    }

    def _ensure_packages_loaded(self, tex_path: str):
        """v15.7: 编译前校验——LLM 可能用了未 load 宏包的命令（如 makecell），
        导致 Undefined control sequence。扫描用到的命令，自动补缺失宏包。

        这是系统性缺口的修复：系统从不校验"LLM 输出的命令是否在已 load 宏包内"。
        历史三次运行未触发是概率问题（LLM 恰好没用复杂表格命令），非没有隐患。
        """
        import re as _re
        if not os.path.exists(tex_path):
            return
        with open(tex_path, "r", encoding="utf-8") as f:
            tex = f.read()
        # 已 load 的宏包（展开 a,b 形式）
        _loaded = set()
        for m in _re.finditer(r'\\usepackage(?:\[[^\]]*\])?\{([^}]+)\}', tex):
            for p in m.group(1).split(","):
                _loaded.add(p.strip())
        # 扫描用到的命令，找缺失宏包
        _missing_pkgs = []
        for cmd, pkg in self._CMD_TO_PACKAGE.items():
            if pkg in _loaded:
                continue
            if _re.search(r'\\' + cmd + r'\b', tex):
                _missing_pkgs.append(pkg)
        if not _missing_pkgs:
            return
        # 在 documentclass 后插入缺失宏包
        _unique = sorted(set(_missing_pkgs))
        _insert = "\n".join(f"\\usepackage{{{p}}}" for p in _unique)
        _doc_idx = tex.find("\\documentclass")
        if _doc_idx == -1:
            logger.warning(f"[v15.7] 无法插入宏包（无 documentclass）: {_unique}")
            return
        _line_end = tex.find("\n", _doc_idx)
        tex = tex[:_line_end + 1] + _insert + "\n" + tex[_line_end + 1:]
        with open(tex_path, "w", encoding="utf-8") as f:
            f.write(tex)
        logger.info(f"[v15.7] 宏包校验：自动补 {len(_unique)} 个缺失宏包: {_unique}")

    def _validate_cite_keys(self, tex_path: str) -> dict:
        """
        v15.5 A1.1: 引用前置校验门 —— 写盘后、bib 构建前拦截编造的 cite key。

        真相源 = self._cite_key_map（CitationInjector 用 generate_bib_key 确定性生成）。
        合法 key 形如 'he2016'/'honauer2016'（surname+year）；LLM 编造的 key 形如
        'urbanlf_dataset'（数据集名 snake_case），两者形态不交集，故 fuzzy 门槛从严。

        策略（宁可留痕不可误修）：
          - key 在 map 内 → 通过
          - 不在 → 仅当与某合法 key 形态接近（同 surname + 年份差 ≤1）才修正
          - 否则 → 替换为 \\textbf{[REF?-原key]} 留痕，计入 unknown（不再静默删）

        Returns:
            {"fixed": [(bad, good), ...], "unknown": [bad_key, ...], "changed": bool}
        """
        import re as _re
        if not os.path.exists(tex_path):
            return {"fixed": [], "unknown": [], "changed": False}

        with open(tex_path, "r", encoding="utf-8") as f:
            tex_content = f.read()

        key_map = getattr(self, '_cite_key_map', {})
        if not key_map:
            logger.warning("[v15.5] _cite_key_map 为空，跳过 cite 前置校验")
            return {"fixed": [], "unknown": [], "changed": False}

        valid_keys = set(key_map.keys())
        # 提取所有 \cite{...}（支持多 key 逗号分隔）
        cite_spans = list(_re.finditer(r'\\cite\{([^}]+)\}', tex_content))
        if not cite_spans:
            logger.info(f"[v15.5] cite 前置校验：tex 无 \\cite{{}}，跳过 "
                        f"(map 有 {len(valid_keys)} 个合法 key)")
            return {"fixed": [], "unknown": [], "changed": False}

        _total_keys = sum(len(m.group(1).split(",")) for m in cite_spans)
        logger.info(f"[v15.5] cite 前置校验启动：{_total_keys} 个 cite key "
                    f"vs map {len(valid_keys)} 个合法 key")

        fixed_pairs = []   # (bad_key, good_key)
        unknown_keys = []  # 无法修正的 bad key

        for m in cite_spans:
            inner = m.group(1)
            parts = [p.strip() for p in inner.split(",")]
            new_parts = []
            has_bad = False
            for k in parts:
                if not k or k in valid_keys:
                    new_parts.append(k)
                    continue
                # 不在 map → 尝试严格 fuzzy（同 surname + 年份差 ≤1）
                good = self._fuzzy_match_cite_key(k, valid_keys)
                if good:
                    fixed_pairs.append((k, good))
                    new_parts.append(good)
                else:
                    # 留痕而非删除：标记为 unknown
                    unknown_keys.append(k)
                    has_bad = True

            # v15.8 修复1: 留痕方式重写——不能在 \cite{} 内部放 \textbf{}
            # （花括号嵌套破坏 LaTeX + offset 越界破坏周围文字）。
            # 正确做法：含 bad key 的整条 \cite{} 替换为可见留痕（在 cite 外部）。
            if has_bad:
                # 该 \cite{} 含编造 key → 整条替换为留痕标记
                _valid_in_cite = [p for p in new_parts if not p.startswith("[REF?")]
                _bad_in_cite = [k for k in parts if k not in valid_keys
                                and not self._fuzzy_match_cite_key(k, valid_keys)]
                if _valid_in_cite:
                    # 混合 cite（有合法有编造）→ 保留合法的，编造的留痕在外部
                    _valid_cite = "\\cite{" + ", ".join(_valid_in_cite) + "}"
                    _ref_marker = "".join(r"\textbf{[REF?-%s]}" % k for k in _bad_in_cite)
                    _replacement = _valid_cite + _ref_marker
                else:
                    # 全是编造 → 整条替换
                    _replacement = "".join(r"\textbf{[REF?-%s]}" % k for k in _bad_in_cite)
                tex_content = (tex_content[:m.start()] + _replacement
                               + tex_content[m.end():])
                # 重扫以避免 offset 失效（\cite{} 不多，性能可接受）
                cite_spans = list(_re.finditer(r'\\cite\{([^}]+)\}', tex_content))
            elif ", ".join(new_parts) != inner:
                # 只有 fuzzy 修正（无 bad key）→ 替换内部
                tex_content = (tex_content[:m.start(1)] + ", ".join(new_parts)
                               + tex_content[m.end(1):])
                cite_spans = list(_re.finditer(r'\\cite\{([^}]+)\}', tex_content))

        changed = bool(fixed_pairs or unknown_keys)
        if changed:
            with open(tex_path, "w", encoding="utf-8") as f:
                f.write(tex_content)
            if fixed_pairs:
                logger.info(f"[v15.5] cite 前置校验修正 {len(fixed_pairs)} 个 key: "
                            f"{fixed_pairs}")
            if unknown_keys:
                logger.warning(f"[v15.5] cite 前置校验发现 {len(unknown_keys)} 个"
                               f"无法修正的编造 key，已留痕 [REF?]: {unknown_keys}")
        else:
            logger.info(f"[v15.5] cite 前置校验通过：所有 cite key 均合法（无需修正）")
        return {"fixed": fixed_pairs, "unknown": unknown_keys, "changed": changed}

    @staticmethod
    def _fuzzy_match_cite_key(bad_key: str, valid_keys: set) -> Optional[str]:
        """
        v15.5 A1.1: 严格 fuzzy 匹配。仅当 bad_key 与某合法 key 同 surname
        且年份差 ≤1 时才返回该合法 key；否则返回 None（交由留痕）。

        关键判据是"有无年份"——合法 key 形如 'he2016'（surname+year），
        编造 key 形如 'urbanlf_dataset'（无年份）。surname 长度不设下限，
        以兼容 'he'/'li'/'hu' 等中文姓短 surname。
        """
        import re as _re
        bad_letter = ''.join(_re.findall(r'[a-z]', bad_key.lower()))
        bad_digits = ''.join(_re.findall(r'\d', bad_key))
        # 必须有年份 + surname 前缀（≥2 字符，挡住纯数字/单字母噪声）
        if len(bad_letter) < 2 or not bad_digits:
            return None

        for vk in valid_keys:
            vk_letter = ''.join(_re.findall(r'[a-z]', vk.lower()))
            vk_digits = ''.join(_re.findall(r'\d', vk))
            if len(vk_letter) < 2 or not vk_digits:
                continue
            # surname 必须完全相等（不取前缀，避免 'ho' 误中 'honauer'），
            # 仅年份差 ≤1 容错（he2015 → he2016 这类笔误）。
            if (bad_letter == vk_letter
                    and abs(int(bad_digits) - int(vk_digits)) <= 1):
                return vk
        return None

    def _ensure_bib_has_all_cited_keys(self, tex_path: str):
        """
        v15.5 A1.2: 前置校验（_validate_cite_keys）已先拦截编造 key，
        本方法只负责补 bib 条目（map 有但 bib 缺的 key）。
        v14.0 的"静默删 cite"分支已删除——编造 key 现以 [REF?] 留痕。
        """
        import re as _re
        if not os.path.exists(tex_path):
            return

        with open(tex_path, "r", encoding="utf-8") as f:
            tex_content = f.read()

        # 提取所有 cite key
        cited_keys = set(_re.findall(r'\\cite\{([^}]+)\}', tex_content))
        flat_keys = set()
        for k in cited_keys:
            for part in k.split(","):
                flat_keys.add(part.strip())

        # 读取现有 bib
        bib_path = tex_path.replace("main.tex", "references.bib")
        if os.path.exists(bib_path):
            with open(bib_path, "r", encoding="utf-8") as f:
                bib_content = f.read()
            existing_keys = set(_re.findall(r'@\w+\{([^,\s]+)', bib_content))
        else:
            bib_content = ""
            existing_keys = set()

        missing = flat_keys - existing_keys
        if not missing:
            return

        logger.info(f"[Phase 7.8b] 补充 {len(missing)} 个缺失 bib 条目: {missing}")

        # v14: 直接使用缓存的 _cite_key_map（不再独立重建）
        key_map = getattr(self, '_cite_key_map', {})
        if not key_map:
            logger.warning("[Phase 7.8b] _cite_key_map 为空，跳过补充")
            return

        from tools.bibtex_builder import BibTeXBuilder
        builder = BibTeXBuilder(os.path.dirname(os.path.dirname(tex_path)))
        new_entries = []

        # v15.5 A1.2: 编造 key 已被前置门 _validate_cite_keys 拦截/留痕，
        # 这里只补"map 有但 bib 没生成"的 key。不再有静默删 cite 分支。
        for missing_key in missing:
            paper = key_map.get(missing_key)
            if paper:
                entry = builder._create_bib_entry_with_doi(paper, missing_key)
                if not entry:
                    entry = builder._create_bib_entry(paper, missing_key)
                if entry:
                    new_entries.append(entry)
            else:
                # 不应到达：前置门已把不在 map 的 key 留痕为 [REF?]，
                # 到这里说明前置门没跑——记 warning 不再删除
                logger.warning(f"[Phase 7.8b] key '{missing_key}' 不在 _cite_key_map"
                               f"（前置门应已拦截），跳过补 bib")

        if new_entries:
            with open(bib_path, "a", encoding="utf-8") as f:
                f.write("\n\n")
                f.write("\n".join(new_entries))
            logger.info(f"[Phase 7.8b] 已补充 {len(new_entries)} 个 bib 条目")

    def _reflect(self, task: Task, result: Any,
                 verify_report=None) -> Dict[str, Any]:
        """
        REFLECT: 评估执行结果

        记录质量分 + should_retry + VERIFY 报告决策。
        跨章节一致性在 Phase 7.2 统一做（不在这里重复）。
        """
        reflection = {
            "should_retry": False,
            "strategy": "",
            "quality_score": -1,
        }

        # 章节生成任务：质量评估已在内循环完成，直接记录
        if task.task_type == "generate" and task.phase_name.startswith("phase"):
            phase_num = task.phase_name.replace("phase", "")
            chapter_names = {
                1: "Introduction", 2: "Related Work",
                3: "Methodology", 4: "Experiments", 5: "Conclusion"
            }
            # phase5_5 = Abstract
            if task.phase_name == "phase5_5":
                chapter_name = "abstract"
            elif phase_num.isdigit() and int(phase_num) in chapter_names:
                chapter_name = chapter_names[int(phase_num)]
            else:
                chapter_name = ""

            if chapter_name:
                # 获取最近一次质量评估结果
                history = self.quality_gate.get_history()
                for h in reversed(history):
                    h_chapter = h.get("chapter", "")
                    if h_chapter.lower() == chapter_name.lower():
                        reflection["quality_score"] = h.get("overall_score", -1)
                        break

                self.memory.add_log("quality",
                                   f"{chapter_name} 最终质量: {reflection['quality_score']:.1f}/100")

                # should_retry: 质量未达标 → 触发重试（QualityGate 内循环已尝试修订）
                effective_threshold = self.quality_gate.PASS_THRESHOLD
                if task.phase_name == "phase5_5":
                    effective_threshold = 55.0
                if reflection["quality_score"] < effective_threshold:
                    reflection["should_retry"] = True
                    reflection["strategy"] = "revise"

        # ====== v8.0: VERIFY 报告影响决策 ======
        if verify_report is not None:
            from agent.verifier import VerifyReport
            if isinstance(verify_report, VerifyReport):
                # 如果 VERIFY 发现严重问题（score < 40），强制重试
                if not verify_report.passed and verify_report.total_score < 40:
                    reflection["should_retry"] = True
                    reflection["strategy"] = "revise"
                    logger.warning(
                        f"[REFLECT] VERIFY 未通过 (score={verify_report.total_score:.1f})，强制重试"
                    )
                # 记录 VERIFY 分数到 memory
                self.memory.add_log(
                    "quality",
                    f"VERIFY {task.phase_name}: {verify_report.total_score:.1f}/100 "
                    f"({'PASS' if verify_report.passed else 'FAIL'})"
                )

        return reflection

    def _run_review_phase(self) -> Dict:
        """Phase 6: 参考文献审查（内容审查已由 QualityGate 在生成阶段完成）"""
        results = {}

        if CHECK_REFERENCES:
            logger.info("\n" + "=" * 60)
            logger.info("  Phase 6: 参考文献审查")
            logger.info("=" * 60)

            full_content = "\n\n".join(self._chapters.values())
            from agent.skill_orchestrators.reference_checker import run_reference_checker
            verification = run_reference_checker(
                full_content,
                cite_key_map=getattr(self, '_cite_key_map', None),
            )
            results["reference_verification"] = verification

            with open(f"{OUTPUT_DIR}/reference_verification_final.json", 'w', encoding='utf-8') as f:
                json.dump(verification, f, ensure_ascii=False, indent=2)

        return results

    def _run_pre_lock_audit(self) -> Dict:
        """Phase 5.6: 全章草稿审计 + 一致性（v15.3 L2 前移闭环）

        在 phase5_5（摘要）后、phase6（审查）前执行：
        1. auditor.audit_chapter × 5 章 → FindingBus(chN)
        2. cross_chapter.check_all(chapters, abstract) → FindingBus(chN)
        3. 若 FindingBus 有 critical → 触发受影响章节的 _quality_ensure rerun

        这是 v15.3 的核心：让 auditor/cross_chapter 的 findings 在草稿态
        （正文未锁）就被消费，而非死在 Phase 6.5/7.2 的 FindingBus 坟墓里。
        _quality_ensure 内部已调 as_revision_brief → 能取到这些 findings。
        """
        logger.info("\n" + "=" * 60)
        logger.info("  Phase 5.6: 全章草稿审计 + 一致性（v15.3 前移闭环）")
        logger.info("=" * 60)

        results = {"pre_lock_audit": True, "reruns": []}
        chapter_names = {
            1: "Introduction", 2: "Related Work",
            3: "Methodology", 4: "Experiments", 5: "Conclusion"
        }

        # 兜底: 确保 auditor/cross_chapter 注入 FactBase
        _fb = getattr(self, '_factbase', None)
        if _fb and not _fb.is_empty():
            if hasattr(self, 'auditor') and not getattr(self.auditor, '_factbase', None):
                self.auditor.set_factbase(_fb)
            if hasattr(self, 'cross_chapter_checker') and not getattr(self.cross_chapter_checker, '_factbase', None):
                self.cross_chapter_checker.set_factbase(_fb)

        # 1. auditor 审计各章 → FindingBus
        audit_findings_count = 0
        if hasattr(self, 'auditor') and self.auditor is not None:
            for num, name in chapter_names.items():
                if num in self._chapters:
                    try:
                        report = self.auditor.audit_chapter(
                            f"phase5_6", name,
                            self._chapters[num],
                            self._project_data, self._ref_data
                        )
                        from agent.core.finding import audit_report_to_findings as _a2f
                        _ch_loc = f"ch{num}"
                        recorded = self._findings.record_many(_a2f(report, chapter_hint=_ch_loc))
                        audit_findings_count += len(recorded)
                    except Exception as e:
                        logger.warning(f"[Phase 5.6] auditor {name} 失败: {e}")
        logger.info(f"[Phase 5.6] auditor 录入 {audit_findings_count} findings")

        # 2. cross_chapter 一致性 → FindingBus
        cc_findings_count = 0
        if hasattr(self, 'cross_chapter_checker') and self.cross_chapter_checker is not None:
            try:
                pc = getattr(self, '_paper_context', None)
                if pc:
                    self.cross_chapter_checker.set_paper_context(pc)
                issues, _, _ = self.cross_chapter_checker.check_all(
                    self._chapters, self._abstract, auto_fix=False
                )
                from agent.core.finding import cross_chapter_issues_to_findings
                self._findings.clear(source="cross_chapter")
                recorded = self._findings.record_many(cross_chapter_issues_to_findings(issues))
                cc_findings_count = len(recorded)
                logger.info(f"[Phase 5.6] cross_chapter 录入 {cc_findings_count} findings")
            except Exception as e:
                logger.warning(f"[Phase 5.6] cross_chapter 失败: {e}")

        # 3. 若有 critical findings → 触发受影响章节 rerun
        from agent.core.finding import Severity
        critical_chapters = set()
        for f in self._findings.all():
            if getattr(f, 'severity', None) == Severity.CRITICAL:
                ch = getattr(f.location, 'chapter', None) if hasattr(f, 'location') else None
                if ch and ch.startswith("ch"):
                    critical_chapters.add(ch)

        if critical_chapters:
            logger.info(f"[Phase 5.6] 发现 critical findings，触发 rerun: {critical_chapters}")
            ch_num_map = {"ch1": (1, "Introduction"), "ch2": (2, "Related Work"),
                          "ch3": (3, "Methodology"), "ch4": (4, "Experiments"),
                          "ch5": (5, "Conclusion")}
            for ch_loc in critical_chapters:
                if ch_loc in ch_num_map:
                    num, name = ch_num_map[ch_loc]
                    if num in self._chapters:
                        old_content = self._chapters[num]
                        # _quality_ensure 内部调 as_revision_brief 取 FindingBus brief
                        new_content, report = self._quality_ensure(name, old_content)
                        if new_content != old_content:
                            self._chapters[num] = new_content
                            results["reruns"].append({
                                "chapter": name, "revised": True,
                                "score": getattr(report, 'overall_score', 0)
                            })
                            logger.info(f"[Phase 5.6] {name} rerun 完成 (score={getattr(report, 'overall_score', 0):.1f})")
        else:
            logger.info(f"[Phase 5.6] 无 critical findings，无需 rerun")

        results["total_findings"] = audit_findings_count + cc_findings_count
        results["critical_reruns"] = len(results["reruns"])
        logger.info(f"[Phase 5.6] 完成: {results['total_findings']} findings, "
                     f"{results['critical_reruns']} reruns")
        return results

    def _run_audit_phase(self) -> Dict:
        """Phase 6.5: 反幻觉审计（v5.0 新增）"""
        logger.info("\n" + "=" * 60)
        logger.info("  Phase 6.5: 反幻觉审计")
        logger.info("=" * 60)

        if not ENABLE_AUDIT:
            logger.info("[audit] 审计功能未启用（ENABLE_AUDIT=False）")
            return {"skipped": True}

        results = {}

        # 1. 审计各章节
        chapter_names = {
            1: "Introduction", 2: "Related Work",
            3: "Methodology", 4: "Experiments", 5: "Conclusion"
        }
        # v14 兜底: 确保 auditor/verifier/cross_chapter 都注入 FactBase
        _fb = getattr(self, '_factbase', None)
        if _fb and not _fb.is_empty():  # v14: 空 FactBase 不注入（会让数值检查静默跳过）
            if hasattr(self, 'auditor') and not getattr(self.auditor, '_factbase', None):
                self.auditor.set_factbase(_fb)
            if hasattr(self, 'verifier') and not getattr(self.verifier, '_factbase', None):
                self.verifier.set_factbase(_fb)
            if hasattr(self, 'cross_chapter_checker') and not getattr(self.cross_chapter_checker, '_factbase', None):
                self.cross_chapter_checker.set_factbase(_fb)

        for num, name in chapter_names.items():
            if num in self._chapters:
                logger.info(f"[audit] 审计 {name}...")
                report = self.auditor.audit_chapter(
                    f"phase{num}", name,
                    self._chapters[num],
                    self._project_data, self._ref_data
                )
                results[f"chapter{num}_audit"] = report.to_dict()
                # v13 接线: auditor 审计结果录入 FindingBus（供 QualityLoop 修订回流）
                from agent.core.finding import audit_report_to_findings as _a2f
                _ch_loc = f"ch{num}"
                _recorded = self._findings.record_many(_a2f(report, chapter_hint=_ch_loc))
                logger.info(f"[Phase6.5] {name}: 录入 {len(_recorded)} auditor findings, "
                            f"bus 总计 {len(self._findings.all())}")

                # 打印审计摘要
                critical = sum(1 for i in report.issues if i.severity == "critical")
                warnings = sum(1 for i in report.issues if i.severity == "warning")
                if critical > 0:
                    logger.warning(f"  [!] {critical} 个严重问题，{warnings} 个警告")
                    for issue in report.issues:
                        if issue.severity == "critical":
                            logger.error(f"    - CRITICAL: {issue.description[:100]}")
                else:
                    logger.info(f"  通过 ({warnings} 个警告)")

        # 2. 审计摘要
        if self._abstract:
            logger.info(f"[audit] 审计 Abstract...")
            report = self.auditor.audit_abstract(
                self._abstract, self._chapters, self._project_data
            )
            results["abstract_audit"] = report.to_dict()

        # 3. 保存审计报告
        self.auditor.save_reports(OUTPUT_DIR)

        # 4. 打印审计汇总
        summary = self.auditor.get_summary_report()
        logger.info("\n" + "-" * 40)
        logger.info(f"  审计汇总: {summary['total_phases_audited']} 个阶段")
        logger.info(f"  严重问题: {summary['critical_issues']}")
        logger.info(f"  警告: {summary['warning_issues']}")
        logger.info(f"  整体通过: {'是' if summary['overall_passed'] else '否'}")
        logger.info("-" * 40)

        return results

    def _run_output_phase(self) -> Dict:
        """Phase 7: 输出（含全局打磨、引用解析和跨章节一致性检查）"""
        logger.info("\n" + "=" * 60)
        logger.info("  Phase 7: 生成最终输出")
        logger.info("=" * 60)

        results = {}

        # Phase 7.0–7.26: 全局打磨 + 门控 + 一致性 + 公式 + 去重
        self._postprocess_content()

        # Phase 7.28: 图表生成
        figure_latex_snippets = self._generate_figures(results)

        # Phase 7.3–7.9: LaTeX/DOCX/Markdown 生成 + BibTeX + 约束预检
        self._generate_latex_output(results, figure_latex_snippets)

        self._run_table_fallback()

        # ====== Phase 8–9: PDF 编译 + 验证 + 分层验收 + 评价 ======
        self._compile_and_validate(results)

        # 消融实验
        if RUN_ABLATION:
            from tools.ablation_designer import run_ablation_designer
            ablation_result = run_ablation_designer(self._project_data, self._ref_data)
            results["ablation_design"] = f"{OUTPUT_DIR}/ablation_design.json"

            # 如果实验结果已存在，生成可视化
            from tools.result_visualizer import run_result_visualizer
            viz_result = run_result_visualizer(
                ablation_design=ablation_result.get("ablation_design"),
            )
            results["ablation_viz"] = viz_result

        return results

    def _load_outline(self) -> dict:
        """加载 outline.json"""
        path = os.path.join(OUTPUT_DIR, "outline.json")
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.debug(f"大纲加载失败: {e}")
        return {}

    def _generate_latex_output(self, results: Dict, figure_latex_snippets: str):
        """Phase 7.3–7.9: LaTeX/DOCX/Markdown 生成 + BibTeX + 约束预检"""

        # ── 读取架构图 PDF ──
        arch_pdf_path = ""
        _arch_pdf = f"{OUTPUT_DIR}/chapter3/architecture_figure.pdf"
        if os.path.exists(_arch_pdf):
            arch_pdf_path = _arch_pdf
            logger.info(f"[Phase 7.3] 使用架构图 PDF: {_arch_pdf}")
        else:
            logger.warning("[Phase 7.3] architecture_figure.pdf 不存在，跳过架构图注入")

        if arch_pdf_path:
            import shutil as _shutil2
            _latex_figures = f"{OUTPUT_DIR}/latex/figures"
            os.makedirs(_latex_figures, exist_ok=True)
            _arch_dst = os.path.join(_latex_figures, os.path.basename(arch_pdf_path))
            if arch_pdf_path != _arch_dst:
                try:
                    _shutil2.copy2(arch_pdf_path, _arch_dst)
                    logger.info(f"[Phase 7.3] 架构图已复制到 {_arch_dst}")
                except Exception as _e:
                    logger.warning(f"[Phase 7.3] 复制架构图失败: {_e}")

        # ── 摘要 + 关键词 ──
        abstract = getattr(self, '_abstract', '')
        if not abstract:
            innovation_points = self._project_data.get("innovation_points", [])
            experiment_design = self._project_data.get("experiment_design", {})
            try:
                abstract_prompt = (
                    f'请为论文"{PAPER_TITLE}"生成一段学术摘要（约200-250词）。'
                    f'创新点：{json.dumps(innovation_points, ensure_ascii=False)[:1000]}。'
                    f'关键结果：{json.dumps(experiment_design.get("关键结果", {}), ensure_ascii=False)[:500]}。'
                    f'请直接给出英文摘要：'
                )
                abstract = self.api_client.call_generation(abstract_prompt)
            except Exception as e:
                from agent.core.errors import classify as _cls_abs
                _lvl, _, _ = _cls_abs(e)
                logger.error(f"[摘要] 生成失败 [{_lvl}]: {e}")
                abstract = "[DEGRADED: 摘要生成失败，需人工补写]"
                results["abstract_failed"] = True

        keywords = ""
        if "Keywords:" in abstract or "keywords:" in abstract:
            kw_match = re.search(r'\*\*Keywords?:\*\*\s*(.+)', abstract)
            if kw_match:
                keywords = kw_match.group(1).strip()
        if not keywords:
            try:
                keywords_prompt = f'请为论文"{PAPER_TITLE}"生成5-8个英文关键词，用逗号分隔：'
                keywords = self.api_client.call_light(keywords_prompt)
            except Exception as e:
                from agent.core.errors import classify as _cls_kw
                _lvl, _, _ = _cls_kw(e)
                logger.error(f"[关键词] 生成失败 [{_lvl}]: {e}")
                keywords = "[DEGRADED: 关键词生成失败]"
                results["keywords_failed"] = True

        # ── LaTeX / DOCX 输出 ──
        if OUTPUT_LATEX:
            from tools.latex_converter import run_latex_converter
            chapter_list = [self._chapters.get(i, "") for i in range(1, 6)]
            # 添加额外章节（Discussion, Limitations 等）
            for extra_key in sorted(k for k in self._chapters if isinstance(k, str)):
                extra_content = self._chapters[extra_key]
                if extra_content and len(extra_content.strip()) > 50:
                    extra_name_map = {"5_1": "Discussion", "5_2": "Limitations and Future Work"}
                    section_name = extra_name_map.get(extra_key, extra_key)
                    if not extra_content.strip().startswith('#'):
                        extra_content = f"# {section_name}\n\n{extra_content}"
                    chapter_list.append(extra_content)

            # 架构图注入到 chapter 3（源A = Phase3 PDF, 源B = figure_planner）
            if figure_latex_snippets and len(chapter_list) >= 3:
                chapter3_content = chapter_list[2]
                if '\\subsection{' in chapter3_content:
                    if not arch_pdf_path:
                        fig_match = re.search(
                            r'(\\begin\{figure\*?\}.*?\\end\{figure\*?\})',
                            figure_latex_snippets, re.DOTALL,
                        )
                        if fig_match:
                            arch_figure = fig_match.group(1)
                            chapter3_content = chapter3_content.replace(
                                '\\subsection{',
                                arch_figure + '\n\n\\subsection{', 1,
                            )
                            chapter_list[2] = chapter3_content
                            logger.info("[Phase 7.3] 架构图(源B)已注入 chapter 3")
                    else:
                        logger.info("[Phase 7.3] 已有架构图 PDF(源A)，跳过源B架构图注入 chapter 3")

            run_latex_converter(chapter_list, arch_pdf_path, abstract, keywords)
            results["latex"] = f"{OUTPUT_DIR}/latex/main.tex"

            # 注入剩余图表 LaTeX 到 main.tex
            if figure_latex_snippets:
                tex_path = f"{OUTPUT_DIR}/latex/main.tex"
                if os.path.exists(tex_path):
                    with open(tex_path, "r", encoding="utf-8") as f:
                        tex_content = f.read()
# v13 接线 P0-e: 从 FigureManifest 派生 remaining_figures，消除双重注入 bug
                    # 旧 bug: arch_pdf 存在时 remaining = 全量 snippets（架构图被注入两次）
                    # 新: 架构图已由 run_latex_converter 注入 ch3，remaining 只取非架构图
                    from agent.core.figure_manifest import FigType
                    # 直接遍历 usable（已做筛选/去重），避免 O(n²) 的 all() ∩ usable
                    _non_arch = [e for e in self._figure_manifest.usable_for_injection()
                                 if e.fig_type != FigType.ARCHITECTURE]
                    # 文图对账：正文 \ref{fig:X} 都该有 manifest 条目
                    _missing_refs = self._figure_manifest.validate_linkage(tex_content)
                    if _missing_refs:
                        logger.warning(f"[Phase 7.3] 文图对账: {len(_missing_refs)} 个 "
                                       f"\ref{{fig:}} 无对应图: {_missing_refs[:5]}")
                    # 用公开 API 渲染非架构图（不伸手进私有 _single_figure）
                    remaining_figures = self._figure_manifest.to_latex_snippets(
                        exclude_types=[FigType.ARCHITECTURE])
                    _end_doc = "\end{document}"
                    # v15.6 E1: 锚点按优先级——图必须插在参考文献区 *之前*。
                    # v15.4 #3 的盲区：只认 \bibliographystyle，但 Phase 7.3 时刻
                    # tex 里常是 \begin{thebibliography}（要等 Phase 7.8 才转换），
                    # 导致走 elif 把图插在 thebibliography 之后 → 图墙。
                    _anchors = ["\\bibliographystyle", "\\begin{thebibliography}",
                                "\\bibliography{"]
                    _anchor = next((a for a in _anchors if a in tex_content), None)
                    if remaining_figures and _anchor:
                        tex_content = tex_content.replace(
                            _anchor,
                            remaining_figures + "\n\n" + _anchor,
                            1,
                        )
                    elif remaining_figures:
                        if _end_doc in tex_content:
                            tex_content = tex_content.replace(
                                _end_doc,
                                remaining_figures + "\n\n" + _end_doc,
                            )
                        else:
                            tex_content += "\n\n" + remaining_figures
                    # v15.6 E1: 位置校验扩展——figure 不得在 \end{document} 后，
                    # 也不得在任何 bibliography 锚点之后（否则图墙）。
                    if remaining_figures and _end_doc in tex_content:
                        _end_idx = tex_content.rfind(_end_doc)
                        _fig_idx = tex_content.rfind("\\begin{figure")
                        if _fig_idx > _end_idx:
                            logger.warning("[Phase 7.3] 检测到 figure 在 \\end{document} 之后，"
                                           "重新定位到 \\end{document} 前")
                            _after_end = tex_content[_end_idx + len(_end_doc):]
                            tex_content = tex_content[:_end_idx] + _after_end + "\n" + _end_doc
                        else:
                            # 检查 figure 是否在 bibliography 区之后（图墙主因）
                            for _b in _anchors:
                                _b_idx = tex_content.rfind(_b)
                                if _b_idx > -1 and _fig_idx > _b_idx:
                                    logger.warning(f"[Phase 7.3] 检测到 figure 在 {_b} 之后"
                                                   f"（图墙风险），请检查注入逻辑")
                                    break
                    with open(tex_path, "w", encoding="utf-8") as f:
                        f.write(tex_content)
                    logger.info(f"[Phase 7.3] 图表LaTeX代码已注入main.tex ({len(remaining_figures)} chars)")

                    # v15.7: dangling fig ref 降级——前移规划让正文引用了图，
                    # 但图可能渲染失败(非RENDERED)导致没生成 \label → 引用悬空。
                    # 不能静默删（那是老路），降级为可见提示让读者知道图缺失。
                    import re as _dre  # v15.8 fix: _re 作用域不跨方法，局部导入
                    _actual_labels = set(_dre.findall(r'\\label\{(fig:[^}]+)\}', tex_content))
                    _all_refs = set(_dre.findall(r'\\ref\{(fig:[^}]+)\}', tex_content))
                    _dangling = sorted(_all_refs - _actual_labels)
                    if _dangling:
                        for _dref in _dangling:
                            tex_content = _dre.sub(
                                r'\\ref\{' + _dre.escape(_dref) + r'\}',
                                r'\\textit{(fig. unavailable)}',
                                tex_content)
                        with open(tex_path, "w", encoding="utf-8") as f:
                            f.write(tex_content)
                        logger.warning(f"[Phase 7.3] {len(_dangling)} 个 fig ref 对应的图"
                                       f"渲染失败(label缺失)，已降级为可见提示: {_dangling}")

            # v15.7: 宏包校验——LLM 可能用了未 load 的命令（如 makecell），自动补缺
            _tex_path = f"{OUTPUT_DIR}/latex/main.tex"
            if os.path.exists(_tex_path):
                self._ensure_packages_loaded(_tex_path)

            # 复制 figures/ 到 latex/figures/
            figures_src = os.path.join(OUTPUT_DIR, "figures")
            figures_dst = os.path.join(OUTPUT_DIR, "latex", "figures")
            if os.path.exists(figures_src):
                try:
                    import shutil as _shutil
                    os.makedirs(figures_dst, exist_ok=True)
                    for _f in os.listdir(figures_src):
                        _src_f = os.path.join(figures_src, _f)
                        if os.path.isfile(_src_f):
                            _shutil.copy2(_src_f, os.path.join(figures_dst, _f))
                    logger.info(f"[Phase 7.3] 数据图已复制到 {figures_dst}")
                except Exception as _e:
                    logger.warning(f"[Phase 7.3] 复制数据图失败: {_e}")
        else:
            from tools.markdown2docx_converter import MarkdownToDocxConverter
            converter = MarkdownToDocxConverter()
            full_content = "\n\n".join(self._chapters.values())
            converter.convert(full_content, f"{OUTPUT_DIR}/full_paper.docx")
            results["docx"] = f"{OUTPUT_DIR}/full_paper.docx"

        # ── 保存 Markdown ──
        all_chapters = [self._chapters[key]
                        for key in sorted(self._chapters.keys(), key=str)]
        full_md = "\n\n---\n\n".join(all_chapters)
        try:
            from tools.formula_processor import strip_formula_tags
            full_md = strip_formula_tags(full_md)
        except Exception as e:
            logger.debug(f"公式标记清理失败: {e}")
        with open(f"{OUTPUT_DIR}/full_paper.md", 'w', encoding='utf-8') as f:
            f.write(full_md)
        results["markdown"] = f"{OUTPUT_DIR}/full_paper.md"

        # ── Phase 7.8: BibTeX 引用生成 ──
        try:
            logger.info("[Phase 7.8] 生成 BibTeX 引用...")
            from tools.bibtex_builder import BibTeXBuilder
            builder = BibTeXBuilder(OUTPUT_DIR)
            cite_key_map = getattr(self, '_cite_key_map', {})
            citation_map = {}  # v13: 预初始化，防止 build 抛异常时 UnboundLocalError
            if cite_key_map:
                try:
                    _, citation_map = builder.build_from_cite_key_map(cite_key_map)
                    logger.info(f"[Phase 7.8] 使用 _cite_key_map 构建: {len(citation_map)} 条引用")
                except Exception as be:
                    from agent.core.errors import classify as _cls_bib
                    _lvl, _, _ = _cls_bib(be)
                    logger.error(f"[Phase 7.8] BibTeX 构建失败 [{_lvl}]: {be}")
                    results["bibtex_failed"] = True
            else:
                logger.warning("[Phase 7.8] _cite_key_map 为空，跳过 BibTeX 生成")
                results["bibtex_failed"] = True
            results["bibtex"] = f"{OUTPUT_DIR}/latex/references.bib"
            results["citation_map"] = len(citation_map) if citation_map else 0

            if OUTPUT_LATEX:
                tex_path = f"{OUTPUT_DIR}/latex/main.tex"
                if os.path.exists(tex_path):
                    with open(tex_path, "r", encoding="utf-8") as f:
                        tex_content = f.read()
                    bib_pattern = re.compile(
                        r'\\begin\{thebibliography\}.*?\\end\{thebibliography\}',
                        re.DOTALL,
                    )
                    if bib_pattern.search(tex_content):
                        tex_content = bib_pattern.sub(
                            r'\\bibliographystyle{IEEEtran}\n\\bibliography{references}',
                            tex_content,
                        )
                        logger.info("[Phase 7.8] thebibliography → \\bibliography{references}")
                    with open(tex_path, "w", encoding="utf-8") as f:
                        f.write(tex_content)
                    # v15.5 A1: 前置校验门先跑（拦截/修正/留痕编造 cite key）
                    self._validate_cite_keys(tex_path)
                    self._ensure_bib_has_all_cited_keys(tex_path)
        except Exception as e:
            logger.warning(f"[Phase 7.8] BibTeX 生成失败: {e}")

        # ── Phase 7.9–7.91: 约束预检 + 表格独立编译验证 ──
        try:
            logger.info("[Phase 7.9] 运行约束预检（编译前结构审计）...")
            from tools.latex_constraint_checker import run_constraint_check
            tex_path = f"{OUTPUT_DIR}/latex/main.tex"
            if os.path.exists(tex_path):
                with open(tex_path, "r", encoding="utf-8") as f:
                    tex = f.read()
                constraint_result = run_constraint_check(
                    tex, template_type="ieee_trans", auto_fix=True
                )
                if not constraint_result["all_passed"]:
                    with open(tex_path, "w", encoding="utf-8") as f:
                        f.write(constraint_result["fixed_content"])
                    logger.warning(f"[Phase 7.9] 约束预检修复: "
                                   f"{constraint_result['critical_count']} critical, "
                                   f"{constraint_result['warning_count']} warnings")
                    results["constraint_audit"] = constraint_result
                    # v13 接线: LaTeX 约束违规录入 FindingBus
                    from agent.core.finding import violations_to_findings as _v2f
                    _violations = constraint_result.get("violations", [])
                    if _violations:
                        self._findings.record_many(_v2f(_violations))
                else:
                    logger.info("[Phase 7.9] 约束预检通过")

                # Phase 7.91: 表格独立编译验证
                logger.info("[Phase 7.91] 表格独立编译验证...")
                from tools.latex_constraint_checker import validate_all_tables
                with open(tex_path, "r", encoding="utf-8") as f:
                    tex_for_tables = f.read()
                validated = validate_all_tables(tex_for_tables, f"{OUTPUT_DIR}/latex")
                if validated != tex_for_tables:
                    with open(tex_path, "w", encoding="utf-8") as f:
                        f.write(validated)
                    logger.info("[Phase 7.91] 表格验证修复已写回")
                else:
                    logger.info("[Phase 7.91] 所有表格编译验证通过")
            else:
                logger.warning("[Phase 7.9] main.tex 不存在，跳过约束预检")
        except Exception as e:
            logger.warning(f"[Phase 7.9] 约束预检失败（不阻塞）: {e}")

    def _postprocess_content(self):
        """Phase 7.15–7.26: 有序门控 + 跨章节一致性 + 公式处理 + 去重"""
        # ── Phase 7.15: 有序门控流水线 ──
        logger.info("[Phase 7.15] 有序门控流水线（VERIFY + 质量综合评估）...")
        try:
            pipeline_result = self.gate_pipeline.run(
                self._chapters, self._abstract, "",
                skip_llm_gate=True,
            )
            logger.info(f"[Phase 7.15] 门控结果:\n{pipeline_result.summary()}")
            if not pipeline_result.passed:
                fix_plan = pipeline_result.get_fix_plan()
                if fix_plan:
                    logger.warning("[Phase 7.15] 修复计划:")
                    for i, hint in enumerate(fix_plan, 1):
                        logger.warning(f"  {i}. {hint}")
                    recheck = self.gate_pipeline.run(
                        self._chapters, self._abstract, "", skip_llm_gate=True,
                    )
                    if recheck.passed:
                        logger.info("[Phase 7.15] 自动修复成功，流水线重新通过")
                    else:
                        logger.warning(f"[Phase 7.15] 自动修复后仍未通过: "
                                       f"score={recheck.weighted_score:.1f}")
            with open(f"{OUTPUT_DIR}/gate_pipeline_report.json", 'w', encoding='utf-8') as f:
                json.dump(pipeline_result.to_dict(), f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"有序门控流水线失败（不影响输出）: {e}")

        # ── Phase 7.2: 跨章节一致性检查 ──
        logger.info("[Phase 7.2] 跨章节一致性检查...")
        try:
            pc = getattr(self, '_paper_context', None)
            if pc:
                self.cross_chapter_checker.set_paper_context(pc)
            # v14: cross_chapter 只报告不一致，不自动改正文（避免数值交叉污染）
            # 数值修正由 QualityLoop 修订层判断（它能看上下文）
            issues, _, _ = self.cross_chapter_checker.check_all(
                self._chapters, self._abstract, auto_fix=False  # v14: 只报告不改正文
            )
            fix_count = len(self.cross_chapter_checker._fixes_applied)
            if fix_count:
                logger.info(f"[Phase 7.2] 发现 {fix_count} 处数值不一致（已报告，不自动改）")
            critical = [i for i in issues if i.get("severity") == "critical"]
            if critical:
                logger.warning(f"[Phase 7.2] 发现 {len(critical)} 个严重一致性问题:")
                for issue in critical:
                    logger.warning(f"  - {issue.get('description', '')[:100]}")
            else:
                logger.info(f"[Phase 7.2] 一致性检查通过 ({len(issues)} 个警告)")
            # v13 PR4: 统一录入 FindingBus（供 QualityLoop 修订回流）
            from agent.core.finding import cross_chapter_issues_to_findings
            self._findings.clear(source="cross_chapter")
            self._findings.record_many(cross_chapter_issues_to_findings(issues))
            logger.info(f"[Phase 7.2] FindingBus: {self._findings.summary()}")
            with open(f"{OUTPUT_DIR}/cross_chapter_check.json", 'w', encoding='utf-8') as f:
                json.dump(issues, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"跨章节检查失败（不影响输出）: {e}")

        # ── Phase 7.25: 公式处理 ──
        logger.info("[Phase 7.25] 处理 <formula> 标记...")
        try:
            from tools.formula_processor import (
                process_formulas, strip_formula_tags, reset_formula_counter,
            )
            reset_formula_counter()
            total_formulas = 0
            for ch_key in list(self._chapters.keys()):
                content = self._chapters[ch_key]
                if '<formula>' in content:
                    processed = process_formulas(content)
                    before = content.count('<formula>')
                    remaining = len(re.findall(r'<formula>', processed))
                    if remaining > 0:
                        processed = strip_formula_tags(processed)
                    total_formulas += (before - remaining)
                    self._chapters[ch_key] = processed
            if self._abstract and '<formula>' in self._abstract:
                self._abstract = strip_formula_tags(self._abstract)
            logger.info(f"[Phase 7.25] 公式处理完成: {total_formulas} 个公式标记已转换")
        except Exception as e:
            logger.warning(f"公式处理失败（不影响输出）: {e}")

        # ── Phase 7.26: 去重检查 ──
        logger.info("[Phase 7.26] 内容去重检查...")
        try:
            self._deduplicate_content()
        except Exception as e:
            logger.warning(f"去重检查失败（不影响输出）: {e}")

    @staticmethod
    def _build_figure_data(fig_type: str, ablation_results, project_data, factbase) -> Dict:
        """v13.2 #1: 按图类型构建数据图 data。

        诚实原则：只用真实数据（FactBase.metrics），绝不合成造假数值。
        - ablation: 需 ablation_results 有真实变体数值，否则返回 {}（走 TikZ 示意降级）
        - comparison: 需 FactBase 有真实 Ours 值 + experiment_design 有真实基线数值，
          否则返回 {}（不合成基线）
        无真实数据时返回 {} → figure_generator 走 _gen_data_figure_llm（TikZ 示意，诚实降级）。
        """
        if fig_type == "ablation":
            ab = ablation_results or {}
            variants = ab.get("experiments", ab.get("ablation_design", {}).get("variants", ab.get("variants", [])) if isinstance(ab.get("ablation_design"), dict) else ab.get("variants", []))
            # 必须有真实变体数值（非合成）才画
            if not isinstance(variants, list) or not variants:
                return {}
            comps = ["Full Model"]
            metric_lists = {}
            # 从每个 variant 提取真实数值
            has_real = False
            for var in variants[:4]:
                if not isinstance(var, dict):
                    continue
                vn = var.get("name", var.get("variant", "?"))
                comps.append(str(vn)[:20])
                # 变体需带 metrics/results 字段才算真实
                vm = var.get("metrics", var.get("results", {}))
                if isinstance(vm, dict) and vm:
                    has_real = True
                    for k, v in vm.items():
                        fv = ResearchLoop._try_float(v)
                        if fv is not None:
                            metric_lists.setdefault(k, []).append(fv)
            if not has_real or not metric_lists:
                return {}  # 无真实变体数值 → 诚实降级
            # 补 Full Model 行（从 FactBase 或 experiment_design）
            full_vals = {}
            if factbase and getattr(factbase, "metrics", None):
                for k in metric_lists:
                    fv = ResearchLoop._try_float(factbase.metrics.get(k))
                    if fv is not None:
                        full_vals[k] = fv
            for k, lst in metric_lists.items():
                lst.insert(0, full_vals.get(k, 0.0))  # Full 在前
            return {"title": "Ablation Study", "components": comps, "metrics": metric_lists}

        if fig_type == "comparison":
            # 需真实 Ours 值 + 真实基线数值（experiment_design 里带数值的 baselines）
            ed = (project_data or {}).get("experiment_design", {})
            baselines = ed.get("baselines", ed.get("对比方法", []))
            if not isinstance(baselines, list):
                return {}
            # 真实 Ours 值
            ours_vals = []
            metric_names = []
            if factbase and getattr(factbase, "metrics", None):
                for m in list(factbase.metrics.keys())[:3]:
                    fv = ResearchLoop._try_float(factbase.metrics[m])
                    if fv is not None:
                        metric_names.append(m); ours_vals.append(fv)
            if not metric_names:
                return {}
            # 真实基线数值（每个 baseline 需带 metrics/results）
            methods = ["Ours"]
            values = [ours_vals]
            for bl in baselines[:3]:
                if not isinstance(bl, dict):
                    continue
                bm = bl.get("metrics", bl.get("results", {}))
                if not isinstance(bm, dict) or not bm:
                    continue  # 无数值的基线跳过
                bn = bl.get("name", bl.get("method", "?"))
                row = []
                for m in metric_names:
                    row.append(ResearchLoop._try_float(bm.get(m)) or 0.0)
                methods.append(str(bn)[:20]); values.append(row)
            if len(values) < 2:
                return {}  # 无真实基线数值 → 诚实降级
            return {"title": "SOTA Comparison", "methods": methods,
                    "metrics": metric_names, "values": values}
        return {}

    @staticmethod
    def _try_float(v):
        """安全转 float，失败返回 None。"""
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    def _load_or_plan_figures(self, plan_cache: str, paper_content: Dict,
                              venue: str, planner=None) -> Dict:
        """
        v15.5 A2.2: figure plan 缓存——首次规划后落盘，后续读盘复用。
        失效条件：_force_replan=True 或 ablation_results hash 变化。

        提取为独立方法以便单元测试（不必 mock 整个 _generate_figures 渲染链）。
        planner 参数默认惰性导入 plan_figures，测试可注入 mock。
        """
        _abl_hash = hash(json.dumps(self._ablation_results, sort_keys=True,
                                    default=str)) if self._ablation_results else 0
        # 1. 尝试读盘
        if not self._force_replan and os.path.exists(plan_cache):
            try:
                with open(plan_cache, "r", encoding="utf-8") as f:
                    _cached = json.load(f)
                if (_cached.get("figures")
                        and _cached.get("_ablation_hash") == _abl_hash):
                    logger.info(f"[Phase 7.28] 读盘 figure_plan.json 复用 "
                                f"(source={_cached.get('_source')}, "
                                f"{len(_cached['figures'])} 张)")
                    return _cached
            except Exception as ce:
                logger.warning(f"[Phase 7.28] 读 plan 缓存失败，重新规划: {ce}")
        # 2. 缓存未命中 → 重新规划
        if planner is None:
            from tools.figure_planner import plan_figures as planner
        plan_result = planner(
            paper_content, venue=venue,
            experiment_data=self._ablation_results if self._ablation_results else None,
        )
        plan_result["_ablation_hash"] = _abl_hash
        try:
            with open(plan_cache, "w", encoding="utf-8") as f:
                json.dump(plan_result, f, ensure_ascii=False, indent=2)
            logger.info(f"[Phase 7.28] figure_plan.json 已落盘 "
                        f"(source={plan_result.get('_source')}, "
                        f"{len(plan_result.get('figures', []))} 张)")
        except Exception as we:
            logger.warning(f"[Phase 7.28] 写 plan 缓存失败: {we}")
        return plan_result

    def _generate_figures(self, results: Dict) -> str:
        """Phase 7.28: 规划并生成论文图表，返回 figure LaTeX snippets"""
        figure_latex_snippets = ""
        try:
            logger.info("[Phase 7.28] 规划并生成论文图表...")
            from tools.figure_planner import plan_figures
            from tools.figure_generator import generate_figure_from_plan

            paper_content = {
                "title": PAPER_TITLE,
                "abstract": getattr(self, '_abstract', ''),
                "method_text": self._chapters.get(3, ''),
                "innovations": self._project_data.get("innovation_points", []),
            }
            venue_name = (getattr(self.venue_adapter, 'venue_name', 'IEEE TCSVT')
                          if self.venue_adapter else 'IEEE TCSVT')
            # v15.5 A2.2: plan 缓存逻辑提取到 _load_or_plan_figures（可独立测试）
            plan_cache = os.path.join(OUTPUT_DIR, "figure_plan.json")
            plan_result = self._load_or_plan_figures(
                plan_cache, paper_content, venue_name,
                planner=plan_figures,
            )
            fig_plans = plan_result.get("figures", [])

            if not fig_plans:
                logger.info("[Phase 7.28] figure_planner 未规划出图表，跳过")
                return figure_latex_snippets

            logger.info(f"[Phase 7.28] 规划了 {len(fig_plans)} 个图表")
            # v15.7: 前移规划时 method_text 空，module_detail caption 粗糙；
            # 用成品章节补充（轻量字段填充，非 LLM 重新规划）
            for fp in fig_plans:
                _cap = fp.get("caption", "")
                if not _cap or len(_cap) < 10:
                    fp["caption"] = fp.get("title", fp.get("fig_id", ""))
            figures_dir = os.path.join(OUTPUT_DIR, "figures")
            for fp in fig_plans:
                try:
                    # v13.2 #1: 按图类型注入结构化 data（让数据图能渲染而非降级 TikZ）
                    _fdata = self._build_figure_data(fp.get("fig_type", ""), self._ablation_results,
                                                     self._project_data, self._factbase)
                    if _fdata:
                        fp = {**fp, "data": _fdata}
                    fig_result = generate_figure_from_plan(
                        fp, figures_dir, venue=venue_name,
                        project_path=(self._project_data.get('project_path')
                                      if isinstance(self._project_data, dict) else None),
                    )
                    if fig_result and fig_result.get("pdf_path"):
                        # v15.7: manifest 录入改 add→update（phase0_99 已 add PLANNED，避免重复）
                        from agent.core.figure_manifest import FigureEntry, FigType, FigStatus
                        _fig_id = fp.get("fig_id", "fig")
                        _size_type = fp.get("size_type", "double")
                        _caption = fp.get("caption", fp.get("title", _fig_id))
                        _fig_filename = os.path.basename(fig_result["pdf_path"])
                        _fig_tex_path = f"figures/{_fig_filename}"
                        _type_map = {"teaser": FigType.TEASER, "architecture": FigType.ARCHITECTURE,
                                     "ablation": FigType.ABLATION, "comparison": FigType.COMPARISON,
                                     "qualitative": FigType.QUALITATIVE}
                        _existing = self._figure_manifest.get(_fig_id)
                        if _existing:
                            # phase0_99 已 add(PLANNED) → update 为 RENDERED + 填 source_pdf/caption
                            self._figure_manifest.update(
                                _fig_id, status=FigStatus.RENDERED,
                                source_pdf=_fig_tex_path, caption=_caption,
                                size_type=_size_type,
                                supports_claim=fp.get("key_message", _caption[:40]),
                            )
                        else:
                            # 前移规划未覆盖的图（如 resume 旧 checkpoint）→ 兜底 add
                            self._figure_manifest.add(FigureEntry(
                                fig_id=_fig_id,
                                fig_type=_type_map.get(fp.get("fig_type", ""), FigType.MODULE_DETAIL),
                                source_pdf=_fig_tex_path,
                                caption=_caption,
                                supports_claim=fp.get("key_message", _caption[:40]),
                                status=FigStatus.RENDERED,
                                size_type=_size_type,
                            ))
                except Exception as fe:
                    logger.warning(f"[Phase 7.28] 图表 {fp.get('fig_id', '?')} 生成失败: {fe}")
            # v13 接线 P0: 从 manifest 生成 LaTeX（经筛选规则，替代裸字符串）
            figure_latex_snippets = self._figure_manifest.to_latex_snippets()
            _n_ok = len(self._figure_manifest.usable_for_injection())
            _n_total = len(fig_plans)
            if _n_ok:
                logger.info(f"[Phase 7.28] 图表生成完成: {_n_ok}/{_n_total} 可注入")
                results["figures"] = figure_latex_snippets
                results["figure_manifest"] = self._figure_manifest.summary()
            else:
                logger.error(f"[Phase 7.28] {_n_total} 个图表全部失败（0 可注入）")
                results["figures_failed"] = True
        except Exception as e:
            from agent.core.errors import classify as _cls_err
            _lvl, _, _ = _cls_err(e)
            logger.error(f"[Phase 7.28] 图表生成失败 [{_lvl}]: {e}")
            results["figures_failed"] = True
        return figure_latex_snippets

    def _run_table_fallback(self):
        """Phase 7.95: v11.6 通用表格兜底（确保 ≥3 个表格）"""
        try:
            tex_path = f"{OUTPUT_DIR}/latex/main.tex"
            if not os.path.exists(tex_path):
                return
            with open(tex_path, "r", encoding="utf-8") as f:
                tex = f.read()
            table_count = tex.count("\\begin{table")
            MIN_TABLES = 3
            if table_count >= MIN_TABLES:
                return

            logger.info(f"[Phase 7.95] 表格仅 {table_count} 个，需补充至 {MIN_TABLES} 个")
            need = MIN_TABLES - table_count

            ptitle = PAPER_TITLE or "the proposed method"
            exp_design = self._project_data.get("experiment_design", {})
            innovations = self._project_data.get("innovation_points", [])
            inn_names = [ip.get("创新点名称", f"Component {i+1}")
                         for i, ip in enumerate(innovations[:4])]
            cite_keys = re.findall(r'\\cite\{([^}]+)\}', tex)

            table_types = ["experimental settings and dataset details",
                           "ablation study on key components",
                           "comparison with state-of-the-art methods"]
            table_idx = table_count
            tables_to_inject = []

            for t_i in range(need):
                t_type = table_types[min(table_idx + t_i, len(table_types) - 1)]
                table_prompt = (
                    f'Generate ONE LaTeX table for the paper "{ptitle}".\n'
                    f'Table type: {t_type}\n'
                    f'Key components: {", ".join(inn_names)}\n'
                    f'Experiment design: {json.dumps(exp_design, ensure_ascii=False)[:800]}\n\n'
                    f'Rules:\n'
                    f'- Use \\toprule/\\midrule/\\bottomrule (booktabs)\n'
                    f'- Include \\caption{{...}} and \\label{{tab:...}}\n'
                    f'- Use "--" for unknown metric values, do NOT fabricate numbers\n'
                    f'- Keep 4-6 data rows\n'
                    f'- Output ONLY LaTeX code starting with \\begin{{table}}'
                )
                try:
                    resp = self.api_client.call_generation(table_prompt)
                    if resp:
                        tm = re.search(
                            r'\\begin\{table.*?\\end\{table\*?\}', resp, re.DOTALL
                        )
                        if tm:
                            tables_to_inject.append(tm.group(0))
                except Exception as te:
                    logger.warning(f"[Phase 7.95] 表格 {t_i+1} LLM生成失败: {te}")

            while len(tables_to_inject) < need:
                t_i = len(tables_to_inject)
                tables_to_inject.append(
                    f'\\begin{{table}}[t]\n\\centering\n'
                    f'\\caption{{[Placeholder — replace with actual data]}}\n'
                    f'\\label{{tab:placeholder_{table_idx + t_i}}}\n'
                    f'\\begin{{tabular}}{{lc}}\n\\toprule\n'
                    f'Item & Value \\\\\n\\midrule\n'
                    f'\\multicolumn{{2}}{{c}}{{-- to be filled --}} \\\\\n'
                    f'\\bottomrule\n\\end{{tabular}}\n\\end{{table}}'
                )

            injection = "\n\n".join(tables_to_inject)
            if "\\end{document}" in tex:
                tex = tex.replace("\\end{document}", injection + "\n\n\\end{document}")
            else:
                tex += "\n\n" + injection
            with open(tex_path, "w", encoding="utf-8") as f:
                f.write(tex)
            logger.info(f"[Phase 7.95] 已补充 {len(tables_to_inject)} 个表格"
                        f" (共 {table_count + len(tables_to_inject)} 个)")
        except Exception as e:
            logger.warning(f"[Phase 7.95] 表格补充失败（不阻塞）: {e}")

    def _compile_and_validate(self, results: Dict):
        """Phase 8–9: PDF 编译 + 验证 + 分层验收 + 输出评价"""
        # ── Phase 8: PDF 编译 ──
        try:
            logger.info("[Phase 8] 编译 PDF...")
            from tools.pdf_compiler import run_pdf_compiler
            pdf_result = run_pdf_compiler(OUTPUT_DIR)
            if pdf_result.get("success"):
                results["pdf"] = pdf_result["pdf_path"]
                results["pdf_pages"] = pdf_result.get("pages", 0)
                results["pdf_engine"] = pdf_result.get("engine", "unknown")
                logger.info(f"[Phase 8] PDF 编译成功: {pdf_result['pdf_path']} "
                            f"({pdf_result.get('pages', '?')} 页, {pdf_result.get('engine')})")
            else:
                results["pdf_error"] = pdf_result.get("error", "unknown")
                logger.warning(f"[Phase 8] PDF 编译失败: {pdf_result.get('error')}")
        except Exception as e:
            results["pdf_error"] = str(e)
            logger.warning(f"[Phase 8] PDF 编译异常: {e}")

        # ── Phase 8.5: PDF 编译验证 ──
        try:
            logger.info("[Phase 8.5] 运行 PDF 编译验证...")
            from tools.pdf_validator import run_pdf_validator
            validation_result = run_pdf_validator(
                OUTPUT_DIR, api_client=self.api_client, max_retries=3,
            )
            results["pdf_validation"] = validation_result
            if validation_result.get("passed"):
                logger.info(f"[Phase 8.5] PDF 验证通过 "
                            f"(修复 {validation_result['auto_fix_attempts']['fixed']} 个问题)")
            else:
                critical_count = sum(
                    1 for issue in validation_result.get("compile_log_issues", [])
                    if issue.get("severity") == "critical"
                )
                logger.warning(f"[Phase 8.5] PDF 验证未通过: "
                               f"{critical_count} 个严重问题, "
                               f"修复 {validation_result['auto_fix_attempts']['fixed']} 个")
                results["pdf_validation_issues"] = [
                    issue for issue in validation_result.get("compile_log_issues", [])
                    if issue.get("severity") == "critical"
                ][:5]
        except Exception as e:
            results["pdf_validation_error"] = str(e)
            logger.warning(f"[Phase 8.5] PDF 验证异常: {e}")

        # ── Phase 8.8: v12.0 分层验收 ──
        try:
            plan = self.dispatcher.get_plan()
            if plan:
                logger.info("[Phase 8.8] 运行分层验收（原子级/抽象级/全局级）...")
                for task in self.dispatcher.get_all_tasks():
                    if task.status == "completed":
                        step = plan.get_step_by_phase(task.phase_name)
                        if step and step.status == "pending":
                            step.status = "completed"
                validation_report = self.validation_engine.run_validation(plan)
                overall = validation_report.get("overall", {})
                pass_rate = overall.get("pass_rate", 0)
                failed_goals = validation_report.get("failed_goals", [])
                logger.info(f"[Phase 8.8] 验收完成: 通过率 {pass_rate:.1f}%, "
                            f"失败 Goals: {failed_goals}")
                results["hierarchical_validation"] = validation_report
                if failed_goals:
                    for goal_id in failed_goals:
                        goal = next((g for g in plan.goals if g.goal_id == goal_id), None)
                        if goal:
                            for step in goal.steps:
                                if step.status == "failed" and step.fallback:
                                    logger.warning(f"[Phase 8.8] {step.step_id} 失败, "
                                                   f"建议降级: {step.fallback}")
            else:
                logger.info("[Phase 8.8] 无分层规划，跳过分层验收")
        except Exception as e:
            logger.warning(f"[Phase 8.8] 分层验收失败（不阻塞）: {e}")

        # ── Phase 9: 输出评价（paperjury 范式：找问题带证据）──
        try:
            logger.info("[Phase 9] 运行输出评价（paperjury 对抗式审稿）...")
            from tools.output_evaluator import run_output_evaluator
            outline = self._load_outline()
            hier_report = results.get("hierarchical_validation")
            eval_result = run_output_evaluator(
                OUTPUT_DIR, api_client=self.api_client,
                outline=outline, unified_results=None,
                hierarchical_report=hier_report,
            )
            results["evaluation"] = eval_result.get("overall", {})
            grade = eval_result.get("overall", {}).get("overall_grade", "?")

            # v14 paperjury: L3 issues 录入 FindingBus（带 evidence_anchor + close_criterion）
            l3_issues = eval_result.get("L3_academic_quality", {}).get("issues", [])
            if l3_issues:
                from agent.core.finding import Finding, Severity, Location
                self._findings.clear(source="l3_review")
                for issue in l3_issues:
                    if not isinstance(issue, dict):
                        continue
                    sev = Severity.CRITICAL if issue.get("significance") == "major" else Severity.WARNING
                    self._findings.record(Finding(
                        source="l3_review",
                        kind=f"review:{issue.get('kind', 'substantive')}",
                        severity=sev,
                        description=issue.get("summary", ""),
                        location=Location(raw=issue.get("section", "")),
                        evidence_anchor=issue.get("evidence_anchor", ""),
                        close_criterion=issue.get("close_criterion", ""),
                    ))
                logger.info(f"[Phase 9] L3 issues 录入 FindingBus: {len(l3_issues)} 条")
                # v14: L3 close_criterion 写进报告（供人工/下一轮参考）
                results["l3_findings"] = [f.to_dict() for f in self._findings.by(source="l3_review")]

            logger.info(f"[Phase 9] 评价完成: Grade={grade}")


        except Exception as e:
            results["evaluation_error"] = str(e)
            logger.warning(f"[Phase 9] 评价失败: {e}")

    def _build_previous_summary(self, max_chars_per_chapter: int = 1500) -> str:
        """构建前序章节摘要"""
        summary = ""
        for num in [1, 2, 3, 4]:
            if num in self._chapters:
                summary += f"Chapter {num} summary:\n{self._chapters[num][:max_chars_per_chapter]}...\n\n"
        return summary

    def _deduplicate_content(self):
        """
        去重检查（v11.1 增强）：
        1. 去除重复的章节标题（连续相同标题去重）
        2. 检查 Discussion/Conclusion 之间段落级重复
        3. 去除残留的 <formula> 标记
        4. 【v11.1】跨章节段落级去重（Introduction vs Related Work 等）
        """
        import difflib

        # 1. 对每个章节去除重复标题
        for ch_key in list(self._chapters.keys()):
            content = self._chapters[ch_key]
            lines = content.split('\n')
            cleaned = []
            prev_title = ""
            for line in lines:
                stripped = line.strip()
                if stripped.startswith('#'):
                    # 检查是否与前一个标题重复
                    if stripped.lower() == prev_title.lower():
                        logger.info(f"[去重] 移除重复标题: {stripped[:60]}")
                        continue
                    prev_title = stripped
                cleaned.append(line)
            self._chapters[ch_key] = '\n'.join(cleaned)

        # 2. 检查 Discussion 和 Conclusion 之间的段落级重复
        conclusion_text = self._chapters.get(5, "")
        for extra_key in ["5_1", "5_2"]:
            if extra_key not in self._chapters:
                continue
            extra_text = self._chapters[extra_key]
            # 提取段落
            extra_paras = [p.strip() for p in extra_text.split('\n\n') if len(p.strip()) > 50]
            concl_paras = [p.strip() for p in conclusion_text.split('\n\n') if len(p.strip()) > 50]

            deduped_paras = []
            removed = 0
            for para in extra_paras:
                is_dup = False
                for cpara in concl_paras:
                    # 使用前200字符比较，阈值降低到0.5以捕获语义重复
                    ratio = difflib.SequenceMatcher(None, para[:200], cpara[:200]).ratio()
                    if ratio > 0.5:
                        is_dup = True
                        removed += 1
                        break
                if not is_dup:
                    deduped_paras.append(para)

            if removed > 0:
                logger.info(f"[去重] {extra_key} 移除了 {removed} 个与 Conclusion 重复的段落")
                self._chapters[extra_key] = '\n\n'.join(deduped_paras)

        # 3. 额外章节之间的去重（Discussion vs Limitations）
        extra_keys = [k for k in ["5_1", "5_2"] if k in self._chapters]
        for i in range(len(extra_keys)):
            for j in range(i + 1, len(extra_keys)):
                key_a, key_b = extra_keys[i], extra_keys[j]
                paras_a = [p.strip() for p in self._chapters[key_a].split('\n\n') if len(p.strip()) > 50]
                paras_b = [p.strip() for p in self._chapters[key_b].split('\n\n') if len(p.strip()) > 50]
                deduped_b = []
                removed = 0
                for para_b in paras_b:
                    is_dup = any(
                        difflib.SequenceMatcher(None, para_b[:200], pa[:200]).ratio() > 0.5
                        for pa in paras_a
                    )
                    if is_dup:
                        removed += 1
                    else:
                        deduped_b.append(para_b)
                if removed > 0:
                    logger.info(f"[去重] {key_b} 移除了 {removed} 个与 {key_a} 重复的段落")
                    self._chapters[key_b] = '\n\n'.join(deduped_b)

        # 4.【v11.1】跨章节段落级去重（Introduction vs Related Work）
        # 检测前几章之间的内容重复
        chapter_keys = [k for k in [1, 2, 3, 4] if k in self._chapters]
        if len(chapter_keys) >= 2:
            # 收集前面章节的段落指纹
            seen_fingerprints = {}  # {fingerprint: chapter_key}
            for ch_key in chapter_keys:
                content = self._chapters[ch_key]
                paras = [p.strip() for p in content.split('\n\n') if len(p.strip()) > 80]
                deduped_paras = []
                removed = 0
                for para in paras:
                    # 生成段落指纹（去标点+小写+去空格后取前100字符）
                    fp = re.sub(r'[^a-z0-9]', '', para.lower())[:100]
                    if not fp or len(fp) < 30:
                        deduped_paras.append(para)
                        continue
                    # 检查是否与前面章节的段落高度相似
                    is_dup = False
                    for existing_fp, existing_ch in seen_fingerprints.items():
                        # 快速比对：如果前60个字符有80%重合则视为重复
                        overlap = sum(a == b for a, b in zip(fp[:60], existing_fp[:60])) / 60
                        if overlap > 0.85:
                            is_dup = True
                            break
                    if is_dup:
                        removed += 1
                        logger.debug(f"[dedup] removed cross-chapter dup: {para[:80]!r}")
                    else:
                        deduped_paras.append(para)
                        seen_fingerprints[fp] = ch_key

                if removed > 0:
                    logger.info(f"[去重] 章节 {ch_key} 移除了 {removed} 个跨章节重复段落")
                    # v11.6: 保持原文段落顺序，逐一判断是否需要去重
                    final_paras = []
                    for para in content.split('\n\n'):
                        para = para.strip()
                        if not para:
                            continue
                        if len(para) <= 80:
                            final_paras.append(para)
                        else:
                            fp = re.sub(r'[^a-z0-9]', '', para.lower())[:100]
                            is_dup = any(
                                sum(a == b for a, b in zip(fp[:60], efp[:60])) / 60 > 0.85
                                for efp in seen_fingerprints
                            ) if fp and len(fp) >= 30 else False
                            if not is_dup:
                                final_paras.append(para)
                    self._chapters[ch_key] = '\n\n'.join(final_paras)

    def _save_all_state(self):
        """保存全部状态变量到检查点（不触发持久化，由 save_checkpoint 触发）"""
        self.checkpoint.save_state("chapters", self._chapters)
        self.checkpoint.save_state("project_data", self._project_data)
        self.checkpoint.save_state("ref_data", self._ref_data)
        self.checkpoint.save_state("reference_pool", self._reference_pool)
        self.checkpoint.save_state("outline", self._outline)
        self.checkpoint.save_state("motivation_thread", self._motivation_thread)
        self.checkpoint.save_state("style_profile", self._style_profile)
        self.checkpoint.save_state("citation_bank", self._citation_bank)
        self.checkpoint.save_state("abstract", self._abstract)
        self.checkpoint.save_state("ablation_results", self._ablation_results)

    def _save_checkpoint(self, task: Task):
        """保存检查点（全部状态 + 阶段记录）"""
        duration = time.time() - self._start_time

        # 保存全部状态变量
        self._save_all_state()

        # 保存阶段检查点（同时触发持久化到磁盘）
        quality = -1.0
        # 兼容 dict / SimpleNamespace / None：quality_report 可能是
        # dispatcher.to_dict() 后的 dict，也可能是 except 分支留下的 SimpleNamespace
        qr = task.quality_report
        if qr:
            if isinstance(qr, dict):
                quality = qr.get("overall_score", -1.0)
            else:
                quality = getattr(qr, "overall_score", -1.0)

        self.checkpoint.save_checkpoint(
            task.phase_name, task.phase_name.replace("phase", ""),
            status=task.status, duration_seconds=duration,
            quality_score=quality
        )

    def _init_reference_pool_and_outline(self):
        """构建参考文献池和全局大纲（从 _initialize_project_data 提取）"""
        logger.info("[Phase 0.5a] 构建真实参考文献池...")
        try:
            from agent.skill_orchestrators.reference_pool_builder import run_reference_pool_builder
            self._reference_pool = run_reference_pool_builder(
                self._project_data, self._ref_data, self.api_client
            )
            logger.info(f"[Phase 0.5a] 参考文献池: {len(self._reference_pool)} 篇真实论文")
        except Exception as e:
            logger.warning(f"参考文献池构建失败: {e}")
            self._reference_pool = []

        logger.info("[Phase 0.5b] 生成全局大纲...")
        try:
            from agent.skill_orchestrators.structure_planner import run_structure_planner
            self._outline = run_structure_planner(
                self._project_data, self._ref_data, self.api_client
            )
            self.checkpoint.save_state("outline", self._outline)
        except Exception as e:
            logger.warning(f"大纲规划失败: {e}")
            self._outline = {}

        self.checkpoint.save_state("reference_pool", self._reference_pool)
        _p0_5_ok = bool(self._reference_pool) or bool(self._outline)
        self.checkpoint.save_checkpoint(
            "phase0_5", 0.5,
            status="completed" if _p0_5_ok else "partial"
        )
        if not _p0_5_ok:
            logger.error("[Phase 0.5] reference_pool + outline 均失败，标记 partial")

    def _run_motivation_phase(self) -> dict:
        """Phase 0.6: 动机确认子流程"""
        logger.info("\n" + "=" * 60)
        logger.info("  Phase 0.6: 动机确认与动机线程构建")
        logger.info("=" * 60)

        try:
            from agent.motivation_engine import MotivationEngine
            engine = MotivationEngine(self.api_client)
            result = engine.run(
                self._project_data, self._ref_data, OUTPUT_DIR
            )
            self._motivation_thread = result.get("motivation_thread", "")
            self._motivation_result = result  # 保存完整结果（含 anchors）供 ContentStrategist 使用
            self.checkpoint.save_state("motivation_thread", self._motivation_thread)
            logger.info(f"[Phase 0.6] 动机线程已构建: {len(self._motivation_thread)} 字符")
            return result
        except Exception as e:
            logger.warning(f"动机确认失败（不阻塞主流程）: {e}")
            self._motivation_thread = ""
            return {"status": "skipped", "reason": str(e)}

    def _run_journal_style_and_content_strategy_phase(self) -> dict:
        """Phase 0.65: v10.1 期刊风格学习 + 内容策略规划"""
        logger.info("\n" + "=" * 60)
        logger.info("  Phase 0.65: 期刊风格自适应 + 内容策略规划")
        logger.info("=" * 60)

        result = {"journal_style": {}, "content_strategy": {}}

        # Step 1: 期刊风格学习（从 ref_pdf 学习）
        try:
            from agent.journal_style_learner import JournalStyleLearner
            from agent.skill_orchestrators.ref_pdf_analyzer import load_ref_papers

            papers = load_ref_papers(REF_PDF_PATH)
            if papers:
                venue_name = getattr(self.venue_adapter.profile, 'venue_name', 'Unknown') if self.venue_adapter else 'Unknown'
                learner = JournalStyleLearner(self.api_client)
                journal_style = learner.learn(papers, venue_name)
                self._journal_style = journal_style
                result["journal_style"] = journal_style
                # 将学到的风格传递给 VenueAdapter，使各章节能获取到
                if self.venue_adapter:
                    try:
                        self.venue_adapter.set_journal_style(journal_style)
                    except Exception as e:
                        logger.debug(f"风格传递失败: {e}")
                self.checkpoint.save_state("journal_style", journal_style)
                logger.info(f"[Phase 0.65] 期刊风格学习完成: {venue_name}")
            else:
                self._journal_style = {}
                logger.info("[Phase 0.65] 无参考论文，跳过期刊风格学习")
        except Exception as e:
            logger.warning(f"期刊风格学习失败（不阻塞）: {e}")
            self._journal_style = {}

        # Step 2: 内容策略规划（基于创新点 + 期刊风格 + 动机线程）
        try:
            from agent.content_strategist import ContentStrategist
            from config.project_config import TARGET_VENUE

            venue_name = TARGET_VENUE or "Unknown"
            innovation_points = self._project_data.get("innovation_points", [])
            motivation_result = getattr(self, '_motivation_result', {})  # Phase 0.6 存储的完整结果

            strategist = ContentStrategist(self.api_client)
            content_strategy = strategist.plan(
                project_data=self._project_data,
                innovation_points=innovation_points,
                venue_name=venue_name,
                journal_style=self._journal_style,
                motivation_thread=motivation_result if motivation_result else None,
            )
            self._content_strategy = content_strategy
            result["content_strategy"] = content_strategy
            self.checkpoint.save_state("content_strategy", content_strategy)
            logger.info(f"[Phase 0.65] 内容策略规划完成: {len(content_strategy)} 章")

            # Step 3: 将内容策略更新到大纲
            if self._outline and content_strategy:
                self._update_outline_with_strategy(content_strategy)

        except Exception as e:
            logger.warning(f"内容策略规划失败（不阻塞）: {e}")
            self._content_strategy = {}

        return result

    def _update_outline_with_strategy(self, content_strategy: dict):
        """将内容策略更新到已有大纲"""
        try:
            outline_data = self._outline
            outline = outline_data.get("outline", {})
            for chapter_name, strategy in content_strategy.items():
                if chapter_name in outline:
                    outline[chapter_name]["content_strategy"] = strategy
            self.checkpoint.save_state("outline", outline_data)
            logger.info("[Phase 0.65] 大纲已更新（注入内容策略）")
        except Exception as e:
            logger.warning(f"大纲更新失败: {e}")

    def _run_citation_bank_phase(self) -> dict:
        """Phase 0.8: 引用支撑库构建"""
        logger.info("\n" + "=" * 60)
        logger.info("  Phase 0.8: 引用支撑库构建")
        logger.info("=" * 60)

        try:
            # 使用已有的引用管理器 + 参考文献池
            # 如果有 reference_pool，基于 pool 构建 claim 级映射
            if not self._reference_pool:
                logger.warning("[Phase 0.8] 无参考文献池，跳过引用支撑库构建")
                return {"status": "skipped", "reason": "no reference pool"}

            from agent.citation_manager import CitationManager
            cm = CitationManager(self.api_client)
            result = cm.build_citation_bank(
                self._reference_pool, self._project_data, OUTPUT_DIR
            )
            self._citation_bank = result
            self.checkpoint.save_state("citation_bank", result)
            logger.info(f"[Phase 0.8] 引用支撑库: {len(result.get('claims', []))} 个 claim")
            return result
        except Exception as e:
            logger.warning(f"引用支撑库构建失败（不阻塞）: {e}")
            self._citation_bank = {}
            return {"status": "skipped", "reason": str(e)}

    def _run_ablation_phase(self) -> dict:
        """Phase 0.95: 消融实验自动化"""
        logger.info("\n" + "=" * 60)
        logger.info("  Phase 0.95: 消融实验自动化")
        logger.info("=" * 60)

        try:
            from ablation.orchestrator import AblationOrchestrator
            orch = AblationOrchestrator()
            result = orch.run(
                self._project_data, OUTPUT_DIR,
                self.venue_adapter.get_ablation_config(),
            )
            self._ablation_results = result
            self.checkpoint.save_state("ablation_results", result)
            logger.info(f"[Phase 0.95] 消融实验完成: {len(result.get('experiments', []))} 组")
            return result
        except Exception as e:
            logger.warning(f"消融实验失败（不阻塞）: {e}")
            self._ablation_results = {}
            return {"status": "failed", "reason": str(e)}

    def _generate_extra_chapter(self, chapter_name: str, phase_name: str) -> str:
        """生成额外章节（Discussion / Limitations 等）"""
        logger.info(f"[{phase_name}] 生成 {chapter_name}...")

        budget = self.venue_adapter.get_section_word_budget(chapter_name)
        previous_summary = self._build_previous_summary()
        motivation = getattr(self, '_motivation_thread', '')
        citation_context = self._build_citation_context()

        # 传入 Conclusion 摘要，避免重复内容
        conclusion_summary = ""
        if 5 in self._chapters:
            conclusion_summary = f"\n**Conclusion 章节摘要（不要重复以下内容）**:\n{self._chapters[5][:1500]}\n"

        prompt = f"""Write the "{chapter_name}" section for the paper "{PAPER_TITLE}".

Target: ~{budget['target']} words (range: {budget['min']}-{budget['max']}).

Previous chapters summary:
{previous_summary[:2000]}
{conclusion_summary}
{f'Motivation thread: {motivation[:500]}' if motivation else ''}

  # v14: rationale_matrix 已删，此行不再输出

Innovation points: {json.dumps(self._project_data.get('innovation_points', []), ensure_ascii=False)[:800]}

Venue style: {self.venue_adapter.profile.writing_style.get('tone', 'formal')}.

{citation_context}

**关键约束**：不要重复 Conclusion 章节中已经提到的内容。提供新的分析和见解。
**LANGUAGE**: Write in English ONLY. No Chinese characters anywhere.
**NO NEW EQUATIONS**: This section analyzes existing results. Do NOT introduce new mathematical formulations.

Write in English, LaTeX-compatible Markdown format. Do NOT include a top-level section title, just start with the content. Use $$...$$ for display math and $...$ for inline math:
"""
        content = ""
        try:
            content = self.api_client.call_generation(prompt)
        except Exception as ge:
            from agent.core.errors import classify as _cls_ge
            _lvl, _, _ = _cls_ge(ge)
            logger.error(f"额外章节 '{chapter_name}' 生成失败 [{_lvl}]: {ge}")
        if not content:
            from agent.core.errors import DegradedResult
            logger.error(f"额外章节 '{chapter_name}' 生成失败 → DegradedResult（不进最终 PDF）")
            return DegradedResult(
                content=f"[DEGRADED: {chapter_name} 生成失败]",
                reason="LLM 生成返回空或异常",
                source=f"extra_chapter:{chapter_name}",
            )

        # 质量检查
        content, _ = self._quality_ensure(chapter_name, content)

        return content  # 审计在 Phase 6.5 统一做
