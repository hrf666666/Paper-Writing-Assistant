# -*- coding: utf-8 -*-
"""
Skill编排器 - 多步生成工作流的Python实现

每个编排器封装了单次 prompt 无法表达的多步逻辑：
- 多步串行生成（子节间上下文传递）
- 外部工具调用（论文搜索、TikZ生成、PDF解析等）
- 动态循环（子节数量取决于项目数据）
- 条件分支（消融实验开关等）

skills/ 目录只保留声明式的 SKILL.yaml + prompt.md，
这里是对应的 Python 编排逻辑。
"""

from agent.skill_orchestrators.project_analyzer import run_project_analyzer
from agent.skill_orchestrators.ref_pdf_analyzer import run_ref_pdf_analyzer
from agent.skill_orchestrators.ch1_introduction import run_chapter1
from agent.skill_orchestrators.ch2_related_work import run_chapter2
from agent.skill_orchestrators.ch3_methodology import run_chapter3
from agent.skill_orchestrators.ch4_experiments import run_chapter4
from agent.skill_orchestrators.ch5_conclusion import run_chapter5
from agent.skill_orchestrators.content_reviewer import run_content_reviewer
from agent.skill_orchestrators.reference_checker import run_reference_checker
from agent.skill_orchestrators.reference_pool_builder import run_reference_pool_builder
from agent.skill_orchestrators.structure_planner import run_structure_planner
