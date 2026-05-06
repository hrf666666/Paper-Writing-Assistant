# -*- coding: utf-8 -*-
"""
自主研究循环引擎 - THINK → EXECUTE → REFLECT 闭环

核心架构参考 auto-deep-researcher 的 while self._running 循环：
- THINK: 分析当前状态，规划下一步
- EXECUTE: 执行具体任务（章节生成、审查等）
- REFLECT: 评估结果，更新记忆，决定下一步

这是替代原线性流水线的核心引擎。
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

        self._running = False
        self._cycle_count = 0
        self._start_time = 0.0
        self._project_data = {}
        self._ref_data = {}
        self._chapters: Dict[int, str] = {}
        self._abstract: str = ""
        self._pause_event = threading.Event()  # PAUSE/RESUME 同步事件

    def run(self, resume: bool = True):
        """
        启动自主循环

        Args:
            resume: 是否从检查点恢复
        """
        self._running = True
        self._start_time = time.time()

        print("=" * 60)
        print("  论文范文写作助手 v6.0 - 全自主循环架构")
        print("=" * 60)
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

        # 规划任务
        self.dispatcher.plan_tasks(self._project_data, self._ref_data)

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
                    print("\n[pipeline] 所有任务已完成！")
                    break

                # 3. THINK: 分析当前状态
                thought = self._think(task)
                self.memory.add_log("log", f"THINK: {thought[:200]}")

                # 4. EXECUTE: 执行任务
                self.dispatcher.mark_task_running(task)
                result = self._execute(task, thought)

                # 5. REFLECT: 评估结果
                reflection = self._reflect(task, result)

                # 6. 根据反思结果决定下一步
                if reflection.get("should_retry"):
                    # retry_count 仅在此处递增，避免与 mark_task_failed 双重递增
                    self.dispatcher.reschedule_task(
                        task, reflection.get("strategy", "retry")
                    )
                else:
                    self.dispatcher.mark_task_completed(task, result)

                # 7. 保存检查点
                self._save_checkpoint(task)

                # 8. 更新记忆
                self.memory.save()

            except KeyboardInterrupt:
                print("\n[pipeline] 收到中断信号，保存状态...")
                self._running = False
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
                self.memory.save()

                # 将当前运行中的任务标记为失败（task 在循环开头赋值，此处一定已定义）
                try:
                    if task is not None and hasattr(task, 'status') and task.status == "running":
                        self.dispatcher.mark_task_failed(task, str(e))
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

        print("\n" + "=" * 60)
        print(f"  执行完成！耗时 {elapsed/60:.1f} 分钟，共 {self._cycle_count} 个循环")
        print(f"  完成: {progress['completed']}/{progress['total']}")
        print(f"  失败: {progress['failed']}/{progress['total']}")
        print("=" * 60)

        print(self.checkpoint.get_summary())

    def _print_config(self):
        """打印当前配置"""
        article_info = get_article_type_info()
        print(f"  论文标题: {PAPER_TITLE}")
        print(f"  文章类型: {ARTICLE_TYPE} ({article_info['name']})")
        print(f"  项目代码: {PROJECT_CODE_PATH}")
        print(f"  参考PDF: {REF_PDF_PATH}")
        print(f"  输出格式: {'LaTeX' if OUTPUT_LATEX else 'Word'}")
        print(f"  质量门控: 已启用（阈值 {self.quality_gate.PASS_THRESHOLD}）")
        print(f"  参考文献审查: {'是' if CHECK_REFERENCES else '否'}")
        print(f"  反幻觉审计: {'是' if ENABLE_AUDIT else '否'}")
        print(f"  消融实验: {'是' if RUN_ABLATION else '否'}")

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
                print(f"[pipeline] 已将旧输出归档到 {new_dir_path}")
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
                print(f"[pipeline] 从检查点恢复，最后完成阶段: {last_phase}")
                # 恢复项目数据
                self._project_data = self.checkpoint.get_state("project_data", {})
                self._ref_data = self.checkpoint.get_state("ref_data", {})
                self._chapters = self.checkpoint.get_state("chapters", {})
                return bool(self._project_data)
        return False

    def _initialize_project_data(self):
        """初始化项目数据（Phase 0）"""
        from skills.project_analyzer import run_project_analyzer
        from skills.ref_pdf_analyzer import run_ref_pdf_analyzer

        print("\n" + "=" * 60)
        print("  Phase 0: 分析工程代码与参考论文")
        print("=" * 60)

        # 分析工程代码
        print("\n[Phase 0.1] 分析项目工程代码...")
        self._project_data = run_project_analyzer()

        # 分析参考PDF
        print("\n[Phase 0.2] 分析参考论文PDF...")
        self._ref_data = run_ref_pdf_analyzer()

        # 初始化记忆中的项目简报
        self.memory.brief = self._build_project_brief()

        # 保存到检查点
        self.checkpoint.save_state("project_data", self._project_data)
        self.checkpoint.save_state("ref_data", self._ref_data)
        self.checkpoint.save_checkpoint("phase0", 0, status="completed")

        # ====== Phase 0.5: 参考文献池构建 + 全局大纲规划 ======
        print("\n" + "=" * 60)
        print("  Phase 0.5: 参考文献池构建 + 全局大纲规划")
        print("=" * 60)

        # 构建参考文献池
        print("\n[Phase 0.5a] 构建真实参考文献池...")
        try:
            from skills.reference_pool_builder import run_reference_pool_builder
            self._reference_pool = run_reference_pool_builder(
                self._project_data, self._ref_data, self.api_client
            )
            print(f"[Phase 0.5a] 参考文献池: {len(self._reference_pool)} 篇真实论文")
        except Exception as e:
            logger.warning(f"参考文献池构建失败（不影响后续流程）: {e}")
            self._reference_pool = []

        # 全局大纲规划
        print("\n[Phase 0.5b] 生成全局大纲...")
        try:
            from skills.structure_planner import run_structure_planner
            self._outline = run_structure_planner(
                self._project_data, self._ref_data, self.api_client
            )
            self.checkpoint.save_state("outline", self._outline)
        except Exception as e:
            logger.warning(f"大纲规划失败（不影响后续流程）: {e}")
            self._outline = {}

        # 保存参考文献池到检查点
        self.checkpoint.save_state("reference_pool", self._reference_pool)
        self.checkpoint.save_checkpoint("phase0_5", 0.5, status="completed")

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
                print("[directive] 收到STOP指令，停止执行")
                self.directive_mgr.acknowledge(d)
                self.directive_mgr.clear_directive_file()
                return False

            elif d.directive_type == "PAUSE":
                print("[directive] 收到PAUSE指令，暂停执行（创建RESUME指令恢复）")
                self.directive_mgr.acknowledge(d)
                # 使用 Event 等待 RESUME，避免忙等待
                self._pause_event.clear()
                while self._running:
                    if self._pause_event.wait(timeout=10):
                        # event 被 set，说明收到 RESUME
                        print("[directive] 收到RESUME指令，恢复执行")
                        break
                    # timeout 后检查是否有新的 STOP 指令
                    new_directives = self.directive_mgr.check()
                    for nd in new_directives:
                        if nd.directive_type == "STOP":
                            self.directive_mgr.acknowledge(nd)
                            return False
                        elif nd.directive_type == "RESUME":
                            print("[directive] 收到RESUME指令，恢复执行")
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

            elif phase == "phase1":
                from skills.chapter1_introduction import run_chapter1
                content = run_chapter1(self._project_data, self._ref_data)
                content, report = self._quality_ensure("Introduction", content)
                result = content
                self._chapters[1] = result
                # v5.0: 即时审计
                if ENABLE_AUDIT:
                    self._quick_audit("phase1", "Introduction", result)

            elif phase == "phase2":
                from skills.chapter2_related_work import run_chapter2
                content = run_chapter2(self._project_data, self._ref_data)
                content, report = self._quality_ensure("Related Work", content)
                result = content
                self._chapters[2] = result
                if ENABLE_AUDIT:
                    self._quick_audit("phase2", "Related Work", result)

            elif phase == "phase3":
                from skills.chapter3_methodology import run_chapter3
                content = run_chapter3(self._project_data, self._ref_data)
                content, report = self._quality_ensure("Methodology", content)
                result = content
                self._chapters[3] = result
                if ENABLE_AUDIT:
                    self._quick_audit("phase3", "Methodology", result)

            elif phase == "phase4":
                from skills.chapter4_experiments import run_chapter4
                content = run_chapter4(self._project_data, self._ref_data)
                content, report = self._quality_ensure("Experiments", content)
                result = content
                self._chapters[4] = result
                if ENABLE_AUDIT:
                    self._quick_audit("phase4", "Experiments", result)

            elif phase == "phase5":
                from skills.chapter5_conclusion import run_chapter5
                content = run_chapter5(self._project_data, self._ref_data)
                content, report = self._quality_ensure("Conclusion", content)
                result = content
                self._chapters[5] = result
                if ENABLE_AUDIT:
                    self._quick_audit("phase5", "Conclusion", result)

            elif phase == "phase5_5":
                # 生成摘要和关键词（在所有章节完成后）
                from agent.skill_executor import SkillExecutor
                executor = SkillExecutor(self.api_client, self.quality_gate)
                previous_summary = self._build_previous_summary()
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
            self._chapters.get(i, "")[:500] for i in sorted(self._chapters)
        )

        return self.quality_gate.evaluate_and_revise(
            chapter_name, content,
            style_guide, chapter_org, previous_content
        )

    def _reflect(self, task: Task, result: Any) -> Dict[str, Any]:
        """
        REFLECT: 评估执行结果

        增强：
        1. 记录质量分数
        2. 跨章节一致性检查（在 Methodology 之后开始）
        3. 失败模式识别
        4. 基于反思的决策建议
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
                if reflection["quality_score"] < self.quality_gate.PASS_THRESHOLD:
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

        return reflection

    def _run_review_phase(self) -> Dict:
        """Phase 6: 参考文献审查（内容审查已由 QualityGate 在生成阶段完成）"""
        results = {}

        if CHECK_REFERENCES:
            print("\n" + "=" * 60)
            print("  Phase 6: 参考文献审查")
            print("=" * 60)

            full_content = "\n\n".join(self._chapters.values())
            from skills.reference_checker import run_reference_checker
            verification = run_reference_checker(full_content)
            results["reference_verification"] = verification

            with open(f"{OUTPUT_DIR}/reference_verification_final.json", 'w', encoding='utf-8') as f:
                json.dump(verification, f, ensure_ascii=False, indent=2)

        return results

    def _run_audit_phase(self) -> Dict:
        """Phase 6.5: 反幻觉审计（v5.0 新增）"""
        print("\n" + "=" * 60)
        print("  Phase 6.5: 反幻觉审计")
        print("=" * 60)

        if not ENABLE_AUDIT:
            print("[audit] 审计功能未启用（ENABLE_AUDIT=False）")
            return {"skipped": True}

        results = {}

        # 1. 审计各章节
        chapter_names = {
            1: "Introduction", 2: "Related Work",
            3: "Methodology", 4: "Experiments", 5: "Conclusion"
        }
        for num, name in chapter_names.items():
            if num in self._chapters:
                print(f"\n[audit] 审计 {name}...")
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
                    print(f"  [!] {critical} 个严重问题，{warnings} 个警告")
                    for issue in report.issues:
                        if issue.severity == "critical":
                            print(f"    - CRITICAL: {issue.description[:100]}")
                else:
                    print(f"  通过 ({warnings} 个警告)")

        # 2. 审计摘要
        if self._abstract:
            print(f"\n[audit] 审计 Abstract...")
            report = self.auditor.audit_abstract(
                self._abstract, self._chapters, self._project_data
            )
            results["abstract_audit"] = report.to_dict()

        # 3. 保存审计报告
        self.auditor.save_reports(OUTPUT_DIR)

        # 4. 打印审计汇总
        summary = self.auditor.get_summary_report()
        print("\n" + "-" * 40)
        print(f"  审计汇总: {summary['total_phases_audited']} 个阶段")
        print(f"  严重问题: {summary['critical_issues']}")
        print(f"  警告: {summary['warning_issues']}")
        print(f"  整体通过: {'是' if summary['overall_passed'] else '否'}")
        print("-" * 40)

        return results

    def _run_output_phase(self) -> Dict:
        """Phase 7: 输出（含引用解析和跨章节一致性检查）"""
        print("\n" + "=" * 60)
        print("  Phase 7: 生成最终输出")
        print("=" * 60)

        results = {}

        # ====== Phase 7.1: 引用解析 ======
        print("\n[Phase 7.1] 解析引用标记...")
        try:
            from agent.citation_manager import run_citation_manager
            full_content_raw = "\n\n".join(self._chapters.values())
            resolved_text, bibliography, cite_stats = run_citation_manager(
                full_content_raw, self.api_client, self._reference_pool
            )
            print(f"[Phase 7.1] 引用解析: {cite_stats['total_citations']} 个引用, "
                  f"{cite_stats.get('unverified_count', 0)} 个未验证")

            # 用解析后的内容更新 chapters
            # 使用章节标题分割，比固定分隔符更可靠
            chapter_keys = sorted(self._chapters.keys())
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

        # ====== Phase 7.2: 跨章节一致性检查 ======
        print("\n[Phase 7.2] 跨章节一致性检查...")
        try:
            issues = self.cross_chapter_checker.check_all(
                self._chapters, self._abstract
            )
            critical = [i for i in issues if i.get("severity") == "critical"]
            if critical:
                print(f"[Phase 7.2] 发现 {len(critical)} 个严重一致性问题:")
                for issue in critical:
                    print(f"  - {issue.get('description', '')[:100]}")
            else:
                print(f"[Phase 7.2] 一致性检查通过 ({len(issues)} 个警告)")

            with open(f"{OUTPUT_DIR}/cross_chapter_check.json", 'w', encoding='utf-8') as f:
                json.dump(issues, f, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.warning(f"跨章节检查失败（不影响输出）: {e}")

        # ====== Phase 7.3: 生成最终输出 ======
        print("\n[Phase 7.3] 生成输出文件...")

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
            chapter_list = [self._chapters.get(i, "") for i in range(1, 6)]
            latex_paper = run_latex_converter(chapter_list, tikz_code, abstract, keywords)
            results["latex"] = f"{OUTPUT_DIR}/latex/main.tex"
        else:
            from tools.markdown2docx_converter import MarkdownToDocxConverter
            converter = MarkdownToDocxConverter()
            full_content = "\n\n".join(self._chapters.values())
            converter.convert(full_content, f"{OUTPUT_DIR}/full_paper.docx")
            results["docx"] = f"{OUTPUT_DIR}/full_paper.docx"

        # 保存Markdown
        full_md = "\n\n---\n\n".join(self._chapters.values())
        with open(f"{OUTPUT_DIR}/full_paper.md", 'w', encoding='utf-8') as f:
            f.write(full_md)
        results["markdown"] = f"{OUTPUT_DIR}/full_paper.md"

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

    def _build_previous_summary(self) -> str:
        """构建前序章节摘要"""
        summary = ""
        for num in [1, 2, 3, 4]:
            if num in self._chapters:
                summary += f"Chapter {num} summary:\n{self._chapters[num][:500]}...\n\n"
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

    def _save_checkpoint(self, task: Task):
        """保存检查点"""
        duration = time.time() - self._start_time

        # 保存章节状态
        self.checkpoint.save_state("chapters", self._chapters)
        self.checkpoint.save_state("project_data", self._project_data)
        self.checkpoint.save_state("ref_data", self._ref_data)

        # 保存阶段检查点
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
