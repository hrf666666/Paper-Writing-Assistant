# -*- coding: utf-8 -*-
"""
Skill: 第一章 - Introduction / 前言
核心任务：强调待解决问题的重要性和难度
"""

import os
import json

from config.project_config import (
    PAPER_TITLE, OUTPUT_DIR, get_article_type_info
)
from agent.base_orchestrator import BaseOrchestrator, build_style_instruction, build_citation_instruction

import logging
logger = logging.getLogger(__name__)

# 基类实例：统一 LLM 调用
_orch = BaseOrchestrator(output_dir=OUTPUT_DIR)


def generate_introduction(project_data, ref_data, citation_context="", venue_adapter=None):
    """
    生成第一章 Introduction
    
    核心任务：
    1. 强调待解决问题的重要性和难度
    2. 指出现有方法的不足
    3. 介绍本研究的动机和贡献
    """
    
    innovation_points = project_data.get("innovation_points", [])
    experiment_design = project_data.get("experiment_design", {})
    model_architecture = project_data.get("model_architecture", {})
    project_info = project_data.get("project_info", {})
    # v13.2 #3: 激活休眠能力 — motivation_thread（动机锚点，已生成却从未进 prompt）
    motivation_thread = project_data.get("motivation_thread", "")
    # v13.2 #3: 预计算 motivation 块（f-string 不能含反斜杠表达式）
    _motivation_block = ""
    if motivation_thread:
        _motivation_block = "<motivation_thread>\n" + motivation_thread[:2000] + "\n</motivation_thread>\n"
    
    style_guide = ref_data.get("style_guide", {})
    chapter_org = ref_data.get("chapter_organizations", {}).get("Introduction", {})
    
    article_info = get_article_type_info()
    
    # 构建创新点摘要
    innovation_summary = ""
    for i, ip in enumerate(innovation_points, 1):
        innovation_summary += f"\n创新点{i}: {ip.get('创新点名称', 'N/A')}\n"
        innovation_summary += f"  工作内容: {'; '.join(ip.get('创新点工作内容', []))}\n"
        innovation_summary += f"  价值: {ip.get('创新点价值', 'N/A')}\n"
    
    # 构建写作风格指导
    style_instruction = build_style_instruction(style_guide, chapter_org, chapter_name="Introduction", venue_adapter=venue_adapter)
    
    # ==================== 子节1.1: 研究背景与问题重要性 ====================
    _cite_instruction = build_citation_instruction(min_cites=8)
    prompt_1_1 = f"""
你是一名{article_info['name']}级别的学术论文写作专家。请为论文"{PAPER_TITLE}"撰写第1.1节"研究背景与问题重要性"。

**核心任务**：强调待解决问题的重要性和难度。具体要求：
1. 从宏观领域背景切入，说明该研究领域的广泛影响和重要价值
2. 聚焦到具体问题，说明该问题的核心难点和挑战性
3. 用具体数据和实例说明问题的严重性（如性能退化幅度、现有方法的局限性等）
4. 强调解决该问题的紧迫性和必要性

**项目信息**：
<innovation_points>
{innovation_summary}
</innovation_points>

<experiment_design>
{json.dumps(experiment_design, ensure_ascii=False, indent=2)[:3000]}
</experiment_design>

<project_report>
{project_info.get('report_content', '')[:4000]}
</project_report>
{_motivation_block}{style_instruction}

{citation_context}

{_cite_instruction}

请使用学术英语撰写，文风严谨但不失流畅。请直接输出IEEE Transactions格式的LaTeX代码。行内公式用 $...$，行间公式用 \\begin{{equation}}...\\end{{equation}} 或 \\begin{{align}}...\\end{{align}}。加粗用 \\textbf{{...}}。列表用 \\begin{{itemize}}\\item ...\\end{{itemize}}。
**重要**：不要输出 \\section 或 \\subsection 标题，标题由系统自动添加。不要输出 \\documentclass 或 \\begin{{document}}。直接从正文内容开始，只输出LaTeX代码：
"""
    
    logger.info("[chapter1] 生成 1.1 研究背景与问题重要性...")
    try:
        section_1_1 = _orch.call_generation(prompt_1_1)
    except Exception as e:
        logger.error(f"[chapter1] 1.1 生成失败: {e}")
        section_1_1 = ""
    
    # ==================== 子节1.2: 现有方法的不足 ====================
    _cite_instruction_12 = build_citation_instruction(min_cites=5)
    prompt_1_2 = f"""
你是一名{article_info['name']}级别的学术论文写作专家。请为论文"{PAPER_TITLE}"撰写第1.2节"现有方法的局限性"。

**核心任务**：系统分析现有方法的不足，为本研究的必要性提供支撑。具体要求：
1. 按类别梳理现有方法（传统方法、早期深度学习方法、近期方法）
2. 每类方法指出2-3个关键不足，不足之处应与本研究可解决的问题相对应
3. 不足的论述要有逻辑层次：从方法论层面到具体技术层面
4. 结尾自然过渡到"因此，亟需一种...的方法"

**项目信息**：
<innovation_points>
{innovation_summary}
</innovation_points>

<experiment_design>
{json.dumps(experiment_design, ensure_ascii=False, indent=2)[:2000]}
</experiment_design>

**前序章节内容**（用于保持连贯性）：
<previous_content>
{section_1_1[:2000]}
</previous_content>

{style_instruction}

{citation_context}

{_cite_instruction_12}

请使用学术英语撰写。请直接输出LaTeX代码。行内公式用 $...$，行间公式用 \\begin{{equation}}...\\end{{equation}}。
**LANGUAGE**: Write in English ONLY. No Chinese characters anywhere.
**LATEX SYNTAX**: Every \\begin{{X}} must have a matching \\end{{X}}.
**重要**：不要输出 \\section 或 \\subsection 标题。直接从正文开始，只输出LaTeX代码：
"""
    
    logger.info("[chapter1] 生成 1.2 现有方法的局限性...")
    try:
        section_1_2 = _orch.call_generation(prompt_1_2)
    except Exception as e:
        logger.error(f"[chapter1] 1.2 生成失败: {e}")
        section_1_2 = ""
    
    # ==================== 子节1.3: 本文方法与贡献 ====================
    _cite_instruction_13 = build_citation_instruction(min_cites=3)
    prompt_1_3 = f"""
你是一名{article_info['name']}级别的学术论文写作专家。请为论文"{PAPER_TITLE}"撰写第1.3节"本文方法与贡献"。

**核心任务**：清晰介绍本文的方法思路和核心贡献。具体要求：
1. 先用一段话总体描述本文的核心思路（"In this paper, we propose..."）
2. 分条列出3个核心贡献（contributions），每条包含：提出了什么、解决了什么问题、带来了什么提升
3. 贡献的描述要具体，包含关键的技术细节，避免泛泛而谈
4. 最后简要说明实验验证的结论（如"实验表明我们的方法在XX指标上达到了XX"）

**项目信息**：
<innovation_points>
{innovation_summary}
</innovation_points>

<model_architecture>
{json.dumps(model_architecture, ensure_ascii=False, indent=2)[:3000]}
</model_architecture>

<experiment_design>
{json.dumps(experiment_design, ensure_ascii=False, indent=2)[:2000]}
</experiment_design>

**前序章节内容**：
<previous_content>
{section_1_2[:2000]}
</previous_content>

{style_instruction}

{citation_context}

{_cite_instruction_13}

请使用学术英语撰写。贡献列表使用 \\begin{{enumerate}} \\item \\textbf{{Contribution 1}}: ... \\end{{enumerate}} 格式。请直接输出LaTeX代码。行内公式用 $...$，行间公式用 \\begin{{equation}}...\\end{{equation}}。
**重要**：不要输出 \\section 或 \\subsection 标题。直接从正文开始，只输出LaTeX代码：
"""
    
    logger.info("[chapter1] 生成 1.3 本文方法与贡献...")
    try:
        section_1_3 = _orch.call_generation(prompt_1_3)
    except Exception as e:
        logger.error(f"[chapter1] 1.3 生成失败: {e}")
        section_1_3 = ""
    
    # ==================== 组装完整章节 ====================
    full_chapter = f"""\section{{Introduction}}

{section_1_1}

{section_1_2}

{section_1_3}
"""
    
    return full_chapter


def run_chapter1(project_data, ref_data, citation_context="", venue_adapter=None):
    """主入口：生成第一章"""
    os.makedirs(f"{OUTPUT_DIR}/chapter1", exist_ok=True)
    
    logger.info("[chapter1] 开始生成第一章 Introduction...")
    try:
        chapter_content = generate_introduction(project_data, ref_data,
                                                  citation_context=citation_context,
                                                  venue_adapter=venue_adapter)
    except Exception as e:
        logger.error(f"[chapter1] 第一章生成失败: {e}")
        chapter_content = "\\section{Introduction}\n\n(生成失败，请重新运行)\n"
    
    # 保存章节文件
    try:
        _orch.save_output("chapter1_introduction.md", chapter_content, subdir="chapter1")
    except Exception as e:
        logger.error(f"[chapter1] 保存失败: {e}")
    
    logger.info("[chapter1] 第一章生成完成！")
    return chapter_content


if __name__ == "__main__":
    # 独立运行时，从output目录读取前置数据
    project_data = {}
    ref_data = {}
    
    for fname in ["innovation_points.json", "experiment_design.json", "model_architecture.json"]:
        fpath = f"{OUTPUT_DIR}/{fname}"
        if os.path.exists(fpath):
            with open(fpath, 'r', encoding='utf-8') as f:
                project_data[fname.replace(".json", "")] = json.load(f)
    
    result = run_chapter1(project_data, ref_data)
    logger.info(result[:500])
