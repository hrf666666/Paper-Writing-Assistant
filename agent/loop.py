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
from config.project_config import (
    PAPER_TITLE, ARTICLE_TYPE, PROJECT_CODE_PATH, REF_PDF_PATH,
    OUTPUT_DIR, WORKSPACE_DIR, OUTPUT_LATEX,
    CHECK_REFERENCES, RUN_ABLATION, ENABLE_AUDIT, get_article_type_info,
    ENABLE_MOTIVATION_ENGINE, ENABLE_EXEMPLAR_LEARNING,
    ENABLE_RATIONALE_MATRIX, ENABLE_SEVEN_ANCHOR_TEST,
    ENABLE_MULTI_REVIEWER, ENABLE_CLOSED_BOOK_REWRITE,
)

logger = logging.getLogger(__name__)


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

    def __init__(self, api_client: UnifiedAPIClient = None):
        self.api_client = api_client or get_api_client()
        self.memory = MemoryManager(OUTPUT_DIR)
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

        # v5.5: 引用管理器
        from agent.citation_manager import CitationManager
        self.citation_manager = CitationManager(self.api_client)

        # v5.5: 参考文献池
        self._reference_pool = []

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

        # 3. 恒定大小上下文管理器（3层记忆）
        from agent.bounded_context import BoundedContextManager
        self.bounded_ctx = BoundedContextManager(budget=5000)

        # 4. 章节级状态机
        from agent.chapter_state_machine import PaperStateMachine
        self.paper_sm = PaperStateMachine()

        # 5. ToolTrace 反捏造
        from agent.tool_trace import ToolTrace
        self.tool_trace = ToolTrace()

        self._running = False
        self._cycle_count = 0
        self._start_time = 0.0
        self._project_data = {}
        self._ref_data = {}
        self._chapters: Dict = {}  # 支持 int 和 str 键（如 "5_1", "5_2"）
        self._abstract: str = ""
        self._pause_event = threading.Event()  # PAUSE/RESUME 同步事件

        # v7.0: 初始化所有状态变量，防止恢复后 AttributeError
        self._reference_pool = []
        self._outline = {}
        self._motivation_thread = ""
        self._exemplar_dossier = {}
        self._style_profile = {}
        self._citation_bank = {}
        self._rationale_matrix = {}
        self._ablation_results = {}

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
        for key in chapter_keys:
            if key in chapter_names_map:
                self.paper_sm.register_chapter(key, chapter_names_map[key])
        # 额外章节
        extra_sections = self.venue_adapter.get_extra_sections()
        for i, sec in enumerate(extra_sections or [], 1):
            self.paper_sm.register_chapter(f"phase5_{i}", sec)

        # v8.0: 初始化 BoundedContext 长期记忆
        if self._project_data:
            self.bounded_ctx.set_project_brief(self._build_project_brief())
            innovations = self._project_data.get("innovation_points", [])
            if innovations:
                self.bounded_ctx.set_innovation_points(innovations)

        # 跳过已完成的阶段
        if resume:
            self._skip_completed_phases()

        # ====== 核心循环 ======
        while self._running:
            self._cycle_count += 1

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
                    # 递增 retry_count 并检查是否达到最大重试次数
                    task.retry_count += 1
                    if task.retry_count >= task.max_retries:
                        logger.warning(f"任务 {task.task_id} 达到最大重试({task.max_retries})，强制完成")
                        quality_info = None
                        if reflection.get("quality_score", -1) >= 0:
                            quality_info = type('QReport', (), {
                                'overall_score': reflection["quality_score"],
                                'to_dict': lambda self=None: {"overall_score": reflection["quality_score"]},
                            })()
                        self.dispatcher.mark_task_completed(task, result, quality_report=quality_info)
                    else:
                        self.dispatcher.reschedule_task(
                            task, reflection.get("strategy", "retry")
                        )
                else:
                    quality_info = None
                    if reflection.get("quality_score", -1) >= 0:
                        quality_info = type('QReport', (), {
                            'overall_score': reflection["quality_score"],
                            'to_dict': lambda self=None: {"overall_score": reflection["quality_score"]},
                        })()
                    self.dispatcher.mark_task_completed(task, result, quality_report=quality_info)

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
                # 恢复所有状态
                self._project_data = self.checkpoint.get_state("project_data", {})
                self._ref_data = self.checkpoint.get_state("ref_data", {})
                self._chapters = self.checkpoint.get_state("chapters", {})
                self._reference_pool = self.checkpoint.get_state("reference_pool", [])
                self._outline = self.checkpoint.get_state("outline", {})
                self._motivation_thread = self.checkpoint.get_state("motivation_thread", "")
                self._exemplar_dossier = self.checkpoint.get_state("exemplar_dossier", {})
                self._style_profile = self.checkpoint.get_state("style_profile", {})
                self._citation_bank = self.checkpoint.get_state("citation_bank", {})
                self._rationale_matrix = self.checkpoint.get_state("rationale_matrix", {})
                self._abstract = self.checkpoint.get_state("abstract", "")
                self._ablation_results = self.checkpoint.get_state("ablation_results", {})
                logger.info(
                    f"[pipeline] 恢复状态: chapters={len(self._chapters)}, "
                    f"ref_pool={len(self._reference_pool)}, "
                    f"outline={bool(self._outline)}, "
                    f"ablation={bool(self._ablation_results)}"
                )

                # v8.0: 恢复 BoundedContext 章节 summary（从 chapters 重建）
                for key, content in self._chapters.items():
                    if content and isinstance(content, str):
                        self.bounded_ctx.update_chapter_summary(str(key), content)

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
        context = self.memory.build_context_for_prompt(max_chars=2000)
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
        chapter_names = {1: "Introduction", 2: "Related Work", 3: "Methodology",
                        4: "Experiments", 5: "Conclusion"}
        phase_num_str = task.phase_name.replace("phase", "").replace("_", ".")

        chapter_num = 0
        try:
            chapter_num = int(phase_num_str.split(".")[0])
        except (ValueError, IndexError):
            pass

        if task.phase_name.startswith("phase") and chapter_num > 0:
            if chapter_num > 1 and chapter_num in chapter_names:
                previous_summary = self._build_previous_summary()
                if previous_summary and len(previous_summary) > 100:
                    try:
                        think_prompt = f"""Based on the previous chapters summary, provide a 2-sentence strategy for writing {chapter_names[chapter_num]}.
Focus on maintaining consistency with previous content and addressing any gaps.

Previous chapters summary:
{previous_summary[:1000]}

Respond with just the strategy, no explanation:"""
                        llm_strategy = self.api_client.call_light(think_prompt)
                        if llm_strategy:
                            strategy += f"\nLLM策略建议: {llm_strategy.strip()[:200]}"
                    except Exception:
                        pass  # LLM 调用失败不影响主流程

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
                result = self._run_exemplar_phase()

            elif phase == "phase0_8":
                # v7.0: 引用支撑库
                result = self._run_citation_bank_phase()

            elif phase == "phase0_9":
                # v7.0: 写作理由矩阵
                result = self._run_rationale_matrix_phase()

            elif phase == "phase0_95":
                # v7.0: 消融实验自动化
                result = self._run_ablation_phase()

            elif phase == "phase1":
                from agent.skill_orchestrators.ch1_introduction import run_chapter1
                content = run_chapter1(self._project_data, self._ref_data)
                content, report = self._quality_ensure("Introduction", content)
                result = content
                self._chapters[1] = result
                # v8.0: 更新 BoundedContext
                self.bounded_ctx.update_chapter_summary("1", result)
                self.bounded_ctx.extract_symbols_from_content(result)
                # v5.0: 即时审计
                if ENABLE_AUDIT:
                    self._quick_audit("phase1", "Introduction", result)

            elif phase == "phase2":
                from agent.skill_orchestrators.ch2_related_work import run_chapter2
                previous_chapters = {}
                if 1 in self._chapters:
                    previous_chapters[1] = self._chapters[1][:2000]
                content = run_chapter2(self._project_data, self._ref_data,
                                       previous_chapters=previous_chapters)
                content, report = self._quality_ensure("Related Work", content)
                result = content
                self._chapters[2] = result
                if ENABLE_AUDIT:
                    self._quick_audit("phase2", "Related Work", result)
                # v8.0: 更新 BoundedContext
                self.bounded_ctx.update_chapter_summary("2", result)

            elif phase == "phase3":
                from agent.skill_orchestrators.ch3_methodology import run_chapter3
                previous_chapters = {}
                for ch_num in [1, 2]:
                    if ch_num in self._chapters:
                        previous_chapters[ch_num] = self._chapters[ch_num][:2000]
                content = run_chapter3(self._project_data, self._ref_data,
                                       previous_chapters=previous_chapters)
                content, report = self._quality_ensure("Methodology", content)
                result = content
                self._chapters[3] = result
                if ENABLE_AUDIT:
                    self._quick_audit("phase3", "Methodology", result)
                # v8.0: 更新 BoundedContext
                self.bounded_ctx.update_chapter_summary("3", result)
                self.bounded_ctx.extract_symbols_from_content(result)

            elif phase == "phase4":
                from agent.skill_orchestrators.ch4_experiments import run_chapter4
                previous_chapters = {}
                for ch_num in [1, 2, 3]:
                    if ch_num in self._chapters:
                        previous_chapters[ch_num] = self._chapters[ch_num][:2000]
                content = run_chapter4(self._project_data, self._ref_data,
                                       previous_chapters=previous_chapters)
                content, report = self._quality_ensure("Experiments", content)
                result = content
                self._chapters[4] = result
                if ENABLE_AUDIT:
                    self._quick_audit("phase4", "Experiments", result)
                # v8.0: 更新 BoundedContext
                self.bounded_ctx.update_chapter_summary("4", result)

            elif phase == "phase5":
                from agent.skill_orchestrators.ch5_conclusion import run_chapter5
                previous_chapters = {}
                for ch_num in [1, 2, 3, 4]:
                    if ch_num in self._chapters:
                        previous_chapters[ch_num] = self._chapters[ch_num][:2000]
                # 检查是否有独立的 Discussion/Limitations 章节
                has_extra_discussion = False
                try:
                    extra_sections = self.venue_adapter.get_extra_sections()
                    if extra_sections:
                        has_extra_discussion = any(
                            s.lower() in " ".join(extra_sections).lower()
                            for s in ["discussion", "limitations"]
                        )
                except Exception:
                    pass
                content = run_chapter5(self._project_data, self._ref_data,
                                       previous_chapters=previous_chapters,
                                       skip_limitations=has_extra_discussion)
                content, report = self._quality_ensure("Conclusion", content)
                result = content
                self._chapters[5] = result
                if ENABLE_AUDIT:
                    self._quick_audit("phase5", "Conclusion", result)

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
                    },
                    style_guide=self._ref_data.get("style_guide", {}),
                )
                self._abstract = exec_result["content"]
                result = self._abstract

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

        Returns:
            Tuple[str, QualityReport]: (最终内容, 质量报告)
        """
        style_guide = self._ref_data.get("style_guide", {})
        chapter_org = self._ref_data.get("chapter_organizations", {}).get(chapter_name, {})
        previous_content = "\n".join(
            self._chapters.get(i, "")[:500] for i in sorted(self._chapters, key=str)
        )

        return self.quality_gate.evaluate_and_revise(
            chapter_name, content,
            style_guide, chapter_org, previous_content
        )

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

        # 更新章节状态机
        sm = self.paper_sm.get_chapter(phase)
        if sm and not sm.is_complete:
            next_phase = sm.get_next_phase()
            if next_phase:
                sm.advance(
                    next_phase.value, content,
                    verify_score=report.total_score,
                    verify_passed=report.passed,
                    reason=f"VERIFY after {phase}",
                )

        return report

    def _reflect(self, task: Task, result: Any,
                 verify_report=None) -> Dict[str, Any]:
        """
        REFLECT: 评估执行结果

        增强：
        1. 记录质量分数
        2. 跨章节一致性检查（在 Methodology 之后开始）
        3. 失败模式识别
        4. 基于反思的决策建议
        5. v8.0: 结合 VERIFY 报告做决策
        """
        reflection = {
            "should_retry": False,
            "strategy": "",
            "quality_score": -1,
            "cross_chapter_issues": [],
            "failure_patterns": [],
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

                # 失败模式识别：检测是否有维度持续低分
                # Abstract 使用更低的质量阈值（摘要难以达到 70+）
                effective_threshold = self.quality_gate.PASS_THRESHOLD
                if task.phase_name == "phase5_5":
                    effective_threshold = 55.0  # Abstract 专用阈值

                if reflection["quality_score"] < effective_threshold:
                    reflection["should_retry"] = True
                    reflection["strategy"] = "revise"
                    for h in reversed(history[-3:]):
                        h_chapter = h.get("chapter", "")
                        if h_chapter.lower() == chapter_name.lower():
                            dims = h.get("dimensions", {})
                            for dim_name, score in dims.items():
                                if score < 50:
                                    reflection["failure_patterns"].append(
                                        f"{dim_name} 得分 {score:.0f} < 50，需要重点改进"
                                    )
                            break

            # 跨章节一致性检查（在 Methodology 之后的每个章节）
            phase_num_int = 0
            try:
                phase_num_int = int(phase_num.replace("_", ".").split(".")[0])
            except ValueError:
                pass

            if phase_num_int >= 3 and len(self._chapters) >= 2:
                issues = self.cross_chapter_checker.check_all(
                    self._chapters, self._abstract
                )
                critical_issues = [i for i in issues if i.get("severity") == "critical"]
                if critical_issues:
                    reflection["cross_chapter_issues"] = critical_issues
                    logger.warning(
                        f"[REFLECT] 跨章节一致性检查发现 {len(critical_issues)} 个严重问题"
                    )

        # ====== v8.0: VERIFY 报告影响决策 ======
        if verify_report is not None:
            from agent.verifier import VerifyReport
            if isinstance(verify_report, VerifyReport):
                # 如果 VERIFY 发现严重问题（score < 40），强制重试
                if not verify_report.passed and verify_report.total_score < 40:
                    reflection["should_retry"] = True
                    reflection["strategy"] = "revise"
                    reflection["failure_patterns"].extend(
                        f"VERIFY: {c['name']} - {c['details'][:80]}"
                        for c in verify_report.get_failures()[:3]
                    )
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
            verification = run_reference_checker(full_content)
            results["reference_verification"] = verification

            with open(f"{OUTPUT_DIR}/reference_verification_final.json", 'w', encoding='utf-8') as f:
                json.dump(verification, f, ensure_ascii=False, indent=2)

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
        for num, name in chapter_names.items():
            if num in self._chapters:
                logger.info(f"[audit] 审计 {name}...")
                report = self.auditor.audit_chapter(
                    f"phase{num}", name,
                    self._chapters[num],
                    self._project_data, self._ref_data
                )
                results[f"chapter{num}_audit"] = report.to_dict()

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

        # ====== Phase 7.0: 全局打磨 ======
        try:
            logger.info("[Phase 7.0] 全局打磨...")
            from tools.global_polisher import run_global_polisher
            polish_result = run_global_polisher(
                OUTPUT_DIR, self._chapters,
                abstract=self._abstract or "",
                api_client=self.api_client,
            )
            if polish_result.get("polished_chapters"):
                self._chapters = polish_result["polished_chapters"]
            changes = polish_result.get("total_changes", 0)
            logger.info(f"[Phase 7.0] 打磨完成: {changes} 处修改")
        except Exception as e:
            logger.warning(f"[Phase 7.0] 全局打磨失败: {e}")

        # ====== Phase 7.1: 引用解析 ======
        logger.info("[Phase 7.1] 解析引用标记...")
        try:
            from agent.citation_manager import run_citation_manager
            full_content_raw = "\n\n".join(self._chapters.values())
            resolved_text, bibliography, cite_stats = run_citation_manager(
                full_content_raw, self.api_client, self._reference_pool
            )
            logger.info(f"[Phase 7.1] 引用解析: {cite_stats['total_citations']} 个引用, "
                  f"{cite_stats.get('unverified_count', 0)} 个未验证")

            # 用解析后的内容更新 chapters
            # 使用章节标题分割，比固定分隔符更可靠
            chapter_keys = sorted(self._chapters.keys(), key=str)
            chapter_names_map = {
                1: "Introduction", 2: "Related Work",
                3: "Methodology", 4: "Experiments", 5: "Conclusion"
            }
            # 首先尝试按标记分割
            marker = "\n\n---\n\n"
            if marker in resolved_text:
                resolved_parts = resolved_text.split(marker)
                if len(resolved_parts) == len(chapter_keys):
                    for key, part in zip(chapter_keys, resolved_parts):
                        self._chapters[key] = part
                else:
                    # 分割不匹配，按章节标题定位
                    self._split_by_chapter_titles(resolved_text, chapter_keys, chapter_names_map)
            else:
                # 无分隔标记，按章节标题定位
                self._split_by_chapter_titles(resolved_text, chapter_keys, chapter_names_map)

            results["bibliography"] = bibliography
            results["citation_stats"] = cite_stats

            # 保存参考文献
            with open(f"{OUTPUT_DIR}/references.md", 'w', encoding='utf-8') as f:
                f.write(bibliography)

        except Exception as e:
            logger.warning(f"引用解析失败（不影响输出）: {e}")

        # ====== Phase 7.15: v8.0 有序门控流水线 ======
        logger.info("[Phase 7.15] v8.0 有序门控流水线（VERIFY + 质量综合评估）...")
        try:
            bibliography = results.get("bibliography", "")
            pipeline_result = self.gate_pipeline.run(
                self._chapters, self._abstract, bibliography,
                skip_llm_gate=True,  # LLM评估已在章节生成时完成
            )
            logger.info(f"[Phase 7.15] 门控结果:\n{pipeline_result.summary()}")

            # 如果被阻断，记录修复计划
            if not pipeline_result.passed:
                fix_plan = pipeline_result.get_fix_plan()
                if fix_plan:
                    logger.warning("[Phase 7.15] 修复计划:")
                    for i, hint in enumerate(fix_plan, 1):
                        logger.warning(f"  {i}. {hint}")

                    # 尝试自动修复：清理残留标记
                    self._auto_fix_issues(fix_plan)

                    # 修复后重新验证一次
                    recheck = self.gate_pipeline.run(
                        self._chapters, self._abstract,
                        results.get("bibliography", ""),
                        skip_llm_gate=True,
                    )
                    if recheck.passed:
                        logger.info("[Phase 7.15] 自动修复成功，流水线重新通过")
                    else:
                        logger.warning(f"[Phase 7.15] 自动修复后仍未通过: score={recheck.weighted_score:.1f}")

            # 保存门控报告
            with open(f"{OUTPUT_DIR}/gate_pipeline_report.json", 'w', encoding='utf-8') as f:
                json.dump(pipeline_result.to_dict(), f, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.warning(f"有序门控流水线失败（不影响输出）: {e}")

        # ====== Phase 7.18: v8.0 ToolTrace 报告 ======
        logger.info("[Phase 7.18] ToolTrace 反捏造报告...")
        try:
            trace_report = self.tool_trace.verify_claims(self._chapters)
            logger.info(
                f"[Phase 7.18] 引用验证: "
                f"{trace_report['verified_citations']}/{trace_report['total_citations']} 已验证"
            )
            with open(f"{OUTPUT_DIR}/tool_trace_report.json", 'w', encoding='utf-8') as f:
                json.dump(trace_report, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"ToolTrace 报告失败（不影响输出）: {e}")

        # ====== Phase 7.2: 跨章节一致性检查 ======
        logger.info("[Phase 7.2] 跨章节一致性检查...")
        try:
            issues = self.cross_chapter_checker.check_all(
                self._chapters, self._abstract
            )
            critical = [i for i in issues if i.get("severity") == "critical"]
            if critical:
                logger.warning(f"[Phase 7.2] 发现 {len(critical)} 个严重一致性问题:")
                for issue in critical:
                    logger.warning(f"  - {issue.get('description', '')[:100]}")
            else:
                logger.info(f"[Phase 7.2] 一致性检查通过 ({len(issues)} 个警告)")

            with open(f"{OUTPUT_DIR}/cross_chapter_check.json", 'w', encoding='utf-8') as f:
                json.dump(issues, f, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.warning(f"跨章节检查失败（不影响输出）: {e}")

        # ====== Phase 7.25: 公式处理 ======
        logger.info("[Phase 7.25] 处理 <formula> 标记...")
        try:
            from tools.formula_processor import process_formulas, strip_formula_tags, reset_formula_counter
            import re as _re
            for ch_key in list(self._chapters.keys()):
                content = self._chapters[ch_key]
                if '<formula>' in content:
                    processed, stats = process_formulas(content), {}
                    remaining = len(_re.findall(r'<formula>', processed))
                    if remaining > 0:
                        processed = strip_formula_tags(processed)
                    self._chapters[ch_key] = processed
            if self._abstract and '<formula>' in self._abstract:
                self._abstract = strip_formula_tags(self._abstract)
            logger.info("[Phase 7.25] 公式处理完成")
        except Exception as e:
            logger.warning(f"公式处理失败（不影响输出）: {e}")

        # ====== Phase 7.26: 去重检查 ======
        logger.info("[Phase 7.26] 内容去重检查...")
        try:
            self._deduplicate_content()
        except Exception as e:
            logger.warning(f"去重检查失败（不影响输出）: {e}")

        # ====== Phase 7.28: 图表生成 ======
        figure_latex_snippets = ""
        try:
            logger.info("[Phase 7.28] 生成论文图表...")
            from tools.figure_generator import run_figure_generator, generate_latex_figure_includes
            fig_results = run_figure_generator(
                OUTPUT_DIR, self._project_data, self._ablation_results)
            if fig_results:
                logger.info(f"[Phase 7.28] 生成 {len(fig_results)} 个图表")
                figure_latex_snippets = generate_latex_figure_includes(OUTPUT_DIR)
                results["figures"] = fig_results
        except Exception as e:
            logger.warning(f"[Phase 7.28] 图表生成失败: {e}")

        # ====== Phase 7.3: 生成最终输出 ======
        logger.info("[Phase 7.3] 生成输出文件...")

        # 读取TikZ架构图
        tikz_code = ""
        tikz_path = f"{OUTPUT_DIR}/chapter3/architecture_figure.tex"
        if os.path.exists(tikz_path):
            with open(tikz_path, 'r', encoding='utf-8') as f:
                tikz_code = f.read()

        # 使用已生成的Abstract（由phase5_5生成）
        abstract = getattr(self, '_abstract', '')
        if not abstract:
            innovation_points = self._project_data.get("innovation_points", [])
            experiment_design = self._project_data.get("experiment_design", {})
            try:
                abstract_prompt = f'请为论文"{PAPER_TITLE}"生成一段学术摘要（约200-250词）。创新点：{json.dumps(innovation_points, ensure_ascii=False)[:1000]}。关键结果：{json.dumps(experiment_design.get("关键结果", {}), ensure_ascii=False)[:500]}。请直接给出英文摘要：'
                abstract = self.api_client.call_generation(abstract_prompt)
            except Exception:
                abstract = "Abstract to be generated."

        # 提取关键词
        keywords = ""
        if "Keywords:" in abstract or "keywords:" in abstract:
            kw_match = re.search(r'\*\*Keywords?:\*\*\s*(.+)', abstract)
            if kw_match:
                keywords = kw_match.group(1).strip()
        if not keywords:
            try:
                keywords_prompt = f'请为论文"{PAPER_TITLE}"生成5-8个英文关键词，用逗号分隔：'
                keywords = self.api_client.call_light(keywords_prompt)
            except Exception:
                keywords = "deep learning, light field, depth estimation"

        if OUTPUT_LATEX:
            from tools.latex_converter import run_latex_converter
            # 包含主章节 + 额外章节（Discussion, Limitations 等）
            chapter_list = [self._chapters.get(i, "") for i in range(1, 6)]
            # 添加额外章节到 LaTeX 输出，为其添加 section 标题
            for extra_key in sorted(k for k in self._chapters if isinstance(k, str)):
                extra_content = self._chapters[extra_key]
                if extra_content and len(extra_content.strip()) > 50:
                    # 将 "5_1" 映射为章节名
                    extra_name_map = {"5_1": "Discussion", "5_2": "Limitations and Future Work"}
                    section_name = extra_name_map.get(extra_key, extra_key)
                    # 为额外章节添加 section 标题，避免嵌入 Conclusion 内
                    if not extra_content.strip().startswith('#'):
                        extra_content = f"# {section_name}\n\n{extra_content}"
                    chapter_list.append(extra_content)
            
            # Fix B1: 将架构图注入到 chapter 3 (Methodology)
            # 在传递给 LaTeX converter 之前，将 figure 插入到 chapter 3 内容中
            if figure_latex_snippets and len(chapter_list) >= 3:
                # 在 chapter 3 的第一个 \subsection 之前插入架构图
                chapter3_content = chapter_list[2]  # index 2 = chapter 3
                if '\\subsection{' in chapter3_content:
                    # 提取第一个 figure 环境（架构图）
                    fig_match = re.search(
                        r'(\\begin\{figure\}.*?\\end\{figure\})',
                        figure_latex_snippets,
                        re.DOTALL
                    )
                    if fig_match:
                        arch_figure = fig_match.group(1)
                        chapter3_content = chapter3_content.replace(
                            '\\subsection{',
                            arch_figure + '\n\n\\subsection{',
                            1
                        )
                        chapter_list[2] = chapter3_content
                        logger.info("[Phase 7.3] 架构图已注入 chapter 3 (Methodology)")
            
            latex_paper = run_latex_converter(chapter_list, tikz_code, abstract, keywords)
            results["latex"] = f"{OUTPUT_DIR}/latex/main.tex"

            # 注入其他图表 LaTeX 代码到 main.tex（放在参考文献之前）
            # 排除已注入到 chapter 3 的架构图
            if figure_latex_snippets:
                tex_path = f"{OUTPUT_DIR}/latex/main.tex"
                if os.path.exists(tex_path):
                    with open(tex_path, "r", encoding="utf-8") as f:
                        tex_content = f.read()
                    # 移除已注入的架构图（避免重复）
                    fig_match = re.search(
                        r'(\\begin\{figure\}.*?\\end\{figure\})',
                        figure_latex_snippets,
                        re.DOTALL
                    )
                    remaining_figures = figure_latex_snippets
                    if fig_match:
                        remaining_figures = figure_latex_snippets.replace(fig_match.group(1), '', 1).strip()
                    
                    # 在 \bibliographystyle 之前插入剩余图表
                    if remaining_figures and "\\bibliographystyle" in tex_content:
                        tex_content = tex_content.replace(
                            "\\bibliographystyle",
                            remaining_figures + "\n\n\\bibliographystyle"
                        )
                    elif remaining_figures:
                        tex_content += "\n\n" + remaining_figures
                    with open(tex_path, "w", encoding="utf-8") as f:
                        f.write(tex_content)
                    logger.info("[Phase 7.3] 其他图表LaTeX代码已注入main.tex")

            # 确保 figures/ 目录在 latex/ 下也可访问
            figures_src = os.path.join(OUTPUT_DIR, "figures")
            figures_dst = os.path.join(OUTPUT_DIR, "latex", "figures")
            if os.path.exists(figures_src) and not os.path.exists(figures_dst):
                try:
                    import shutil as _shutil
                    _shutil.copytree(figures_src, figures_dst)
                except Exception:
                    pass
        else:
            from tools.markdown2docx_converter import MarkdownToDocxConverter
            converter = MarkdownToDocxConverter()
            full_content = "\n\n".join(self._chapters.values())
            converter.convert(full_content, f"{OUTPUT_DIR}/full_paper.docx")
            results["docx"] = f"{OUTPUT_DIR}/full_paper.docx"

        # 保存Markdown（包含额外章节）
        all_chapters = []
        for key in sorted(self._chapters.keys(), key=lambda x: (str(x))):
            all_chapters.append(self._chapters[key])
        full_md = "\n\n---\n\n".join(all_chapters)
        
        # 最终去重：去除残留的 <formula> 和 <citation> 标记
        try:
            from tools.formula_processor import strip_formula_tags
            full_md = strip_formula_tags(full_md)
        except Exception:
            pass
        # 清理残留的 <citation> 标记
        full_md = re.sub(r'<citation>(.*?)</citation>', r'[ref]', full_md, flags=re.DOTALL)
        
        with open(f"{OUTPUT_DIR}/full_paper.md", 'w', encoding='utf-8') as f:
            f.write(full_md)
        results["markdown"] = f"{OUTPUT_DIR}/full_paper.md"

        # ====== Phase 7.8: BibTeX 引用生成 ======
        try:
            logger.info("[Phase 7.8] 生成 BibTeX 引用...")
            from tools.bibtex_builder import run_bibtex_builder
            bib_content, citation_map = run_bibtex_builder(OUTPUT_DIR)
            results["bibtex"] = f"{OUTPUT_DIR}/latex/references.bib"
            results["citation_map"] = len(citation_map)

            # 替换 LaTeX 中的 [N] 为 \cite{}
            if citation_map and OUTPUT_LATEX:
                from tools.bibtex_builder import BibTeXBuilder
                builder = BibTeXBuilder(OUTPUT_DIR)
                builder._citation_map = citation_map
                tex_path = f"{OUTPUT_DIR}/latex/main.tex"
                if os.path.exists(tex_path):
                    with open(tex_path, "r", encoding="utf-8") as f:
                        tex_content = f.read()
                    tex_content = builder.replace_numeric_with_cite(tex_content)
                    with open(tex_path, "w", encoding="utf-8") as f:
                        f.write(tex_content)
                    logger.info(f"[Phase 7.8] LaTeX 引用替换完成: {len(citation_map)} 条")
        except Exception as e:
            logger.warning(f"[Phase 7.8] BibTeX 生成失败: {e}")

        # ====== Phase 7.9: 约束预检（编译前结构合规审计） ======
        try:
            logger.info("[Phase 7.9] 运行约束预检（编译前结构审计）...")
            from tools.latex_constraint_checker import run_constraint_check
            tex_precheck_path = f"{OUTPUT_DIR}/latex/main.tex"
            if os.path.exists(tex_precheck_path):
                with open(tex_precheck_path, "r", encoding="utf-8") as f:
                    precheck_tex = f.read()
                constraint_result = run_constraint_check(
                    precheck_tex, template_type="ieee_trans", auto_fix=True
                )
                if not constraint_result["all_passed"]:
                    # 写回修复后的内容
                    with open(tex_precheck_path, "w", encoding="utf-8") as f:
                        f.write(constraint_result["fixed_content"])
                    logger.warning(
                        f"[Phase 7.9] 约束预检修复: "
                        f"{constraint_result['critical_count']} critical, "
                        f"{constraint_result['warning_count']} warnings"
                    )
                    results["constraint_audit"] = constraint_result
                else:
                    logger.info("[Phase 7.9] 约束预检通过")

                # ── Phase 7.91: 表格独立编译验证（render-then-insert） ──
                logger.info("[Phase 7.91] 表格独立编译验证（render-then-insert）...")
                from tools.latex_constraint_checker import validate_all_tables
                latex_dir = f"{OUTPUT_DIR}/latex"
                with open(tex_precheck_path, "r", encoding="utf-8") as f:
                    tex_for_table_validation = f.read()
                validated_tex = validate_all_tables(tex_for_table_validation, latex_dir)
                if validated_tex != tex_for_table_validation:
                    with open(tex_precheck_path, "w", encoding="utf-8") as f:
                        f.write(validated_tex)
                    logger.info("[Phase 7.91] 表格验证修复已写回")
                else:
                    logger.info("[Phase 7.91] 所有表格编译验证通过")
            else:
                logger.warning("[Phase 7.9] main.tex 不存在，跳过约束预检")
        except Exception as e:
            logger.warning(f"[Phase 7.9] 约束预检失败（不阻塞）: {e}")

        # ====== Phase 8: PDF 编译 ======
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

        # ====== Phase 8.5: PDF 编译验证 ← 新增 ======
        try:
            logger.info("[Phase 8.5] 运行 PDF 编译验证...")
            from tools.pdf_validator import run_pdf_validator
            validation_result = run_pdf_validator(
                OUTPUT_DIR,
                api_client=self.api_client,
                max_retries=3,
            )
            results["pdf_validation"] = validation_result

            if validation_result.get("passed"):
                logger.info(
                    f"[Phase 8.5] PDF 验证通过 "
                    f"(修复 {validation_result['auto_fix_attempts']['fixed']} 个问题)"
                )
            else:
                critical_count = sum(
                    1 for issue in validation_result.get("compile_log_issues", [])
                    if issue.get("severity") == "critical"
                )
                logger.warning(
                    f"[Phase 8.5] PDF 验证未通过: "
                    f"{critical_count} 个严重问题, "
                    f"修复 {validation_result['auto_fix_attempts']['fixed']} 个"
                )
                # 记录关键问题到 results
                results["pdf_validation_issues"] = [
                    issue for issue in validation_result.get("compile_log_issues", [])
                    if issue.get("severity") == "critical"
                ][:5]  # 最多记录 5 个关键问题
        except Exception as e:
            results["pdf_validation_error"] = str(e)
            logger.warning(f"[Phase 8.5] PDF 验证异常: {e}")

        # ====== Phase 9: 输出有效性 + 完整度评价 ======
        try:
            logger.info("[Phase 9] 运行输出评价（对标 IEEE TCSVT）...")
            from tools.output_evaluator import run_output_evaluator
            outline = self._load_outline()
            eval_result = run_output_evaluator(
                OUTPUT_DIR, api_client=self.api_client,
                outline=outline, unified_results=None,
            )
            results["evaluation"] = eval_result.get("overall", {})
            grade = eval_result.get("overall", {}).get("overall_grade", "?")
            logger.info(f"[Phase 9] 评价完成: Grade={grade}")
        except Exception as e:
            results["evaluation_error"] = str(e)
            logger.warning(f"[Phase 9] 评价失败: {e}")

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
            except Exception:
                pass
        return {}

    def _build_previous_summary(self, max_chars_per_chapter: int = 1500) -> str:
        """构建前序章节摘要"""
        summary = ""
        for num in [1, 2, 3, 4]:
            if num in self._chapters:
                summary += f"Chapter {num} summary:\n{self._chapters[num][:max_chars_per_chapter]}...\n\n"
        return summary

    def _quick_audit(self, phase_name: str, chapter_name: str, content: str):
        """
        v5.0: 章节生成后即时审计（轻量版）

        仅做参考文献反向检索和内容真实性快速检查，
        详细审计在 phase6_5 进行
        """
        try:
            report = self.auditor.audit_chapter(
                phase_name, chapter_name, content,
                self._project_data, self._ref_data
            )
            critical = sum(1 for i in report.issues if i.severity == "critical")
            if critical > 0:
                logger.warning(f"[即时审计] {chapter_name} 发现 {critical} 个严重问题")
                for issue in report.issues:
                    if issue.severity == "critical":
                        logger.warning(f"  - {issue.description[:100]}")
        except Exception as e:
            logger.debug(f"即时审计异常（不阻塞）: {e}")

    def _deduplicate_content(self):
        """
        去重检查：
        1. 去除重复的章节标题（连续相同标题去重）
        2. 检查 Discussion/Conclusion 之间段落级重复
        3. 去除残留的 <formula> 标记
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

    def _auto_fix_issues(self, fix_hints: List[str]):
        """
        v8.0: 根据修复建议自动修复可修复的问题
        """
        import re as _re
        fixed = 0

        for hint in fix_hints:
            hint_lower = hint.lower()

            # 修复残留标记
            if "formula_processor" in hint_lower or "formula" in hint_lower:
                try:
                    from tools.formula_processor import strip_formula_tags
                    for ch_key in list(self._chapters.keys()):
                        content = self._chapters[ch_key]
                        if '<formula>' in content:
                            self._chapters[ch_key] = strip_formula_tags(content)
                            fixed += 1
                except Exception:
                    pass

            # 修复 citation 标记
            if "citation_manager" in hint_lower or "citation" in hint_lower:
                for ch_key in list(self._chapters.keys()):
                    content = self._chapters[ch_key]
                    cleaned = _re.sub(r'<citation>(.*?)</citation>', r'[ref]', content, flags=_re.DOTALL)
                    if cleaned != content:
                        self._chapters[ch_key] = cleaned
                        fixed += 1

            # 修复 [?] → 移除无法解析的引用标记
            if "引用" in hint_lower or "[?]" in hint_lower:
                for ch_key in list(self._chapters.keys()):
                    content = self._chapters[ch_key]
                    # 将 [?] 替换为空字符串（更好的做法是完全移除）
                    cleaned = content.replace('[?]', '')
                    if cleaned != content:
                        self._chapters[ch_key] = cleaned
                        fixed += 1

        if fixed > 0:
            logger.info(f"[auto_fix] 自动修复了 {fixed} 个问题")

    def _save_all_state(self):
        """保存全部状态变量到检查点（不触发持久化，由 save_checkpoint 触发）"""
        self.checkpoint.save_state("chapters", self._chapters)
        self.checkpoint.save_state("project_data", self._project_data)
        self.checkpoint.save_state("ref_data", self._ref_data)
        self.checkpoint.save_state("reference_pool", self._reference_pool)
        self.checkpoint.save_state("outline", self._outline)
        self.checkpoint.save_state("motivation_thread", self._motivation_thread)
        self.checkpoint.save_state("exemplar_dossier", self._exemplar_dossier)
        self.checkpoint.save_state("style_profile", self._style_profile)
        self.checkpoint.save_state("citation_bank", self._citation_bank)
        self.checkpoint.save_state("rationale_matrix", self._rationale_matrix)
        self.checkpoint.save_state("abstract", self._abstract)
        self.checkpoint.save_state("ablation_results", self._ablation_results)

    def _save_checkpoint(self, task: Task):
        """保存检查点（全部状态 + 阶段记录）"""
        duration = time.time() - self._start_time

        # 保存全部状态变量
        self._save_all_state()

        # 保存阶段检查点（同时触发持久化到磁盘）
        quality = -1.0
        if task.quality_report and isinstance(task.quality_report, dict):
            quality = task.quality_report.get("overall_score", -1.0)

        self.checkpoint.save_checkpoint(
            task.phase_name, task.phase_name.replace("phase", ""),
            status=task.status, duration_seconds=duration,
            quality_score=quality
        )

    def _split_by_chapter_titles(self, text: str, chapter_keys: list,
                                  chapter_names_map: dict):
        """
        按章节标题在文本中定位并分割内容到各章。

        策略：按已知的章节标题（如 "Introduction", "Methodology" 等）在文本中
        搜索，将两次匹配之间的内容归为该章节。
        """
        import re

        # 按章节名构建正则，按章节名长度降序排列避免短名误匹配
        sorted_chapters = sorted(
            [(k, chapter_names_map.get(k, "")) for k in chapter_keys],
            key=lambda x: len(x[1]), reverse=True
        )

        # 找到每个章节标题在文本中的位置
        positions = []
        for ch_key, ch_name in sorted_chapters:
            if not ch_name:
                continue
            # 匹配 Markdown 标题格式的章节名（如 "# Introduction", "## 1. Introduction"等）
            pattern = rf'(?:^|\n)(?:#+\s*(?:\d+\.?\s*)?)?{re.escape(ch_name)}'
            for m in re.finditer(pattern, text, re.IGNORECASE):
                positions.append((m.start(), ch_key, ch_name))
                break  # 只取第一个匹配

        if not positions:
            logger.warning("[_split_by_chapter_titles] 未找到任何章节标题，跳过分割")
            return

        # 按位置排序
        positions.sort(key=lambda x: x[0])

        # 分割
        for i, (pos, ch_key, ch_name) in enumerate(positions):
            end_pos = positions[i + 1][0] if i + 1 < len(positions) else len(text)
            content = text[pos:end_pos].strip()
            if content:
                self._chapters[ch_key] = content

        logger.info(f"[_split_by_chapter_titles] 按标题分割完成，已更新 {len(positions)} 个章节")

    # ==================================================================
    # v7.0 子流程方法
    # ==================================================================

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
        self.checkpoint.save_checkpoint("phase0_5", 0.5, status="completed")

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
            self.checkpoint.save_state("motivation_thread", self._motivation_thread)
            logger.info(f"[Phase 0.6] 动机线程已构建: {len(self._motivation_thread)} 字符")
            return result
        except Exception as e:
            logger.warning(f"动机确认失败（不阻塞主流程）: {e}")
            self._motivation_thread = ""
            return {"status": "skipped", "reason": str(e)}

    def _run_exemplar_phase(self) -> dict:
        """Phase 0.7: 深度范例学习"""
        logger.info("\n" + "=" * 60)
        logger.info("  Phase 0.7: 深度范例学习（6层阅读协议）")
        logger.info("=" * 60)

        try:
            from agent.exemplar_learner import ExemplarLearner
            learner = ExemplarLearner(self.api_client)
            result = learner.run(
                self._ref_data, REF_PDF_PATH, OUTPUT_DIR
            )
            self._exemplar_dossier = result.get("dossier", {})
            self._style_profile = result.get("style_profile", {})
            self.checkpoint.save_state("exemplar_dossier", self._exemplar_dossier)
            self.checkpoint.save_state("style_profile", self._style_profile)
            return result
        except Exception as e:
            logger.warning(f"范例学习失败（不阻塞）: {e}")
            self._exemplar_dossier = {}
            self._style_profile = {}
            return {"status": "skipped", "reason": str(e)}

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

    def _run_rationale_matrix_phase(self) -> dict:
        """Phase 0.9: 写作理由矩阵"""
        logger.info("\n" + "=" * 60)
        logger.info("  Phase 0.9: 写作理由矩阵（事前规划型）")
        logger.info("=" * 60)

        try:
            from agent.rationale_matrix import RationaleMatrix
            matrix_gen = RationaleMatrix(self.api_client)
            result = matrix_gen.run(
                self._project_data, self._ref_data,
                self._motivation_thread if hasattr(self, '_motivation_thread') else "",
                self._exemplar_dossier if hasattr(self, '_exemplar_dossier') else {},
                OUTPUT_DIR,
            )
            self._rationale_matrix = result
            self.checkpoint.save_state("rationale_matrix", result)
            logger.info(f"[Phase 0.9] 写作矩阵: {len(result.get('rows', []))} 行")
            return result
        except Exception as e:
            logger.warning(f"写作矩阵生成失败（不阻塞）: {e}")
            self._rationale_matrix = {}
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
        matrix = getattr(self, '_rationale_matrix', {})

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

{f'Key rationale points: {json.dumps(matrix.get("rows", [])[:3], ensure_ascii=False)[:800]}' if matrix else ''}

Innovation points: {json.dumps(self._project_data.get('innovation_points', []), ensure_ascii=False)[:800]}

Venue style: {self.venue_adapter.profile.writing_style.get('tone', 'formal')}.

**关键约束**：不要重复 Conclusion 章节中已经提到的内容。提供新的分析和见解。

Write in English, LaTeX-compatible Markdown format. Do NOT include a top-level section title, just start with the content. Use $$...$$ for display math and $...$ for inline math:
"""
        content = self.api_client.call_generation(prompt)
        if not content:
            content = f"[To be generated]"

        # 质量检查
        content, _ = self._quality_ensure(chapter_name, content)

        if ENABLE_AUDIT:
            self._quick_audit(phase_name, chapter_name, content)

        return content
