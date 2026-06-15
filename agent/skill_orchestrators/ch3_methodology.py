# -*- coding: utf-8 -*-
"""
Skill: 第三章 - Methodology / 方法设计
核心任务：
1. 总体描述：输入→模块→特征→处理→输出
2. TikZ绘制整体架构图
3. 各模块小节：公式+详细架构+功能目标
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


def generate_tikz_architecture(model_architecture, figure_style, paper_title,
                                innovation_points=None, article_type_info=None):
    """生成TikZ架构图代码 - 委托给tools/tikz_generator"""
    from tools.tikz_generator import generate_tikz_from_architecture
    
    output_path = f"{OUTPUT_DIR}/chapter3/architecture_figure.tex"
    tikz_code = generate_tikz_from_architecture(
        model_architecture, figure_style, output_path,
        innovation_points=innovation_points,
        article_type_info=article_type_info,
    )
    return tikz_code


def generate_methodology(project_data, ref_data, previous_chapters=None, citation_context=""):
    """生成第三章 Methodology"""
    
    innovation_points = project_data.get("innovation_points", [])
    model_architecture = project_data.get("model_architecture", {})
    experiment_design = project_data.get("experiment_design", {})
    project_info = project_data.get("project_info", {})
    
    style_guide = ref_data.get("style_guide", {})
    chapter_org = ref_data.get("chapter_organizations", {}).get("Methodology", {})
    figure_style = ref_data.get("figure_style", {})
    article_info = get_article_type_info()
    
    style_instruction = build_style_instruction(style_guide, chapter_org, chapter_name="Methodology")

    # 构建前序章节摘要
    prev_summary = ""
    if previous_chapters:
        if 1 in previous_chapters:
            prev_summary += f"Introduction 摘要:\n{previous_chapters[1][:1000]}\n"
        if 2 in previous_chapters:
            prev_summary += f"Related Work 摘要:\n{previous_chapters[2][:1000]}\n"

    innovation_summary = ""
    for i, ip in enumerate(innovation_points, 1):
        innovation_summary += f"创新点{i}: {ip.get('创新点名称', 'N/A')}\n"
        innovation_summary += f"  内容: {'; '.join(ip.get('创新点工作内容', []))}\n"

    # ==================== 3.1 总体架构概述 ====================
    logger.info("[chapter3] 生成 3.1 总体架构概述...")

    # 生成TikZ架构图
    logger.info("[chapter3] 生成TikZ架构图...")
    try:
        tikz_code = generate_tikz_architecture(model_architecture, figure_style, PAPER_TITLE,
                                               innovation_points=innovation_points,
                                               article_type_info=article_info)
    except Exception as e:
        logger.error(f"[chapter3] TikZ架构图生成失败: {e}")
        tikz_code = "% TikZ architecture figure generation failed"

    # 构建前序章节摘要块
    _prev_summary_block = ""
    if prev_summary:
        _prev_summary_block = f"**前序章节摘要（保持术语一致）**:\n{prev_summary}"

    prompt_3_1 = f"""
你是一名{article_info['name']}级别的学术论文写作专家。请为论文"{PAPER_TITLE}"撰写第3.1节"Overall Architecture"。

**核心任务**：总体描述模型架构。具体要求：
1. 第一段：高层描述本研究提出的方法（"In this section, we present..."）
2. 第二段：描述输入格式和预处理（输入什么、维度、如何处理）
3. 第三段：描述整体数据流（经过哪些模块、提取了哪些特征、做了哪些处理）
4. 第四段：描述输出格式和后处理
5. 参照架构图进行描述，关键模块名需与图中一致

**模型架构信息**：
<model_architecture>
{json.dumps(model_architecture, ensure_ascii=False, indent=2)[:6000]}
</model_architecture>

<innovation_points>
{innovation_summary}
</innovation_points>

**架构图TikZ代码**（用于对齐描述）：
<tikz_code>
{tikz_code[:3000]}
</tikz_code>

{style_instruction}

{_prev_summary_block}

{citation_context}

{build_citation_instruction(3)}

请使用学术英语撰写。请直接输出LaTeX代码。行内公式用 $...$，行间公式用 \\begin{{equation}}...\\end{{equation}}。
架构图引用使用 "Fig.~\\ref{{fig:architecture}}" 或 "As illustrated in Fig.~\\ref{{fig:architecture}}"。
**LANGUAGE**: Write in English ONLY. No Chinese characters anywhere.
**LATEX SYNTAX**: Every \\begin{{X}} must have a matching \\end{{X}}.
**重要**：不要输出 \\section 或 \\subsection 标题。直接从正文开始，只输出LaTeX代码：
"""
    
    try:
        section_3_1 = _orch.call_generation(prompt_3_1)
    except Exception as e:
        logger.error(f"[chapter3] 3.1 生成失败: {e}")
        section_3_1 = ""
    
    # ==================== 3.2~3.N 各模块详解 ====================
    modules = model_architecture.get("模块详情", [])
    if not modules:
        # 如果没有模块详情，从创新点推导
        modules = []
        for ip in innovation_points:
            modules.append({
                "模块名": ip.get("创新点名称", "Module"),
                "输入": "待补充",
                "核心操作": "; ".join(ip.get("创新点工作内容", [])),
                "输出": "待补充",
                "关键公式": ip.get("支撑证据", ""),
            })
    
    module_sections = []
    for idx, module in enumerate(modules):
        module_name = module.get("模块名", f"Module {idx+1}")
        section_num = idx + 2  # 3.2, 3.3, ...
        
        prompt_module = f"""
你是一名{article_info['name']}级别的学术论文写作专家。请为论文"{PAPER_TITLE}"撰写第3.{section_num}节"{module_name}"。

**核心任务**：详细描述该模块的架构设计、功能和目标。

**模块信息**：
- 模块名：{module_name}
- 输入：{module.get('输入', 'N/A')}
- 核心操作：{module.get('核心操作', 'N/A')}
- 输出：{module.get('输出', 'N/A')}
- 关键公式：{module.get('关键公式', 'N/A')}

**具体要求**：
1. 首先说明该模块的设计动机和目标（为什么需要这个模块）
2. 详细描述模块的架构设计，包括：
   - 输入的格式和维度
   - 每一步处理操作及其数学公式（给出完整的公式推导）
   - 输出的格式和维度
3. 每个公式的每个符号都要有明确解释
4. 说明该模块与前后模块的衔接关系
5. 突出该模块的创新点和与现有方法的不同之处

**公式要求**（关键）：
- 每个子节至少包含1个独立的行间公式（使用 \\begin{{equation}}...\\end{{equation}} 格式）
- 不要只给出文字描述，必须有数学形式化
- 公式中的每个变量都要在正文中定义

**模型整体架构**（用于保持一致性）：
{json.dumps(model_architecture, ensure_ascii=False, indent=2)[:2000]}

**前序模块内容**（用于保持连贯性）：
<previous_content>
{module_sections[-1][:1500] if module_sections else section_3_1[:1500]}
</previous_content>

{style_instruction}

{citation_context}

{build_citation_instruction(2)}

请使用学术英语撰写。请直接输出LaTeX代码。行内公式用 $...$，行间公式用 \\begin{{equation}}...\\end{{equation}}。
**重要**：不要输出 \\section 或 \\subsection 标题。直接从正文开始，只输出LaTeX代码：
"""
        
        logger.info(f"[chapter3] 生成 3.{section_num} {module_name}...")
        try:
            section_content = _orch.call_generation(prompt_module)
        except Exception as e:
            logger.error(f"[chapter3] 3.{section_num} {module_name} 生成失败: {e}")
            section_content = f"(模块 {module_name} 生成失败)\n"
        module_sections.append(section_content)
    
    # ==================== 3.N+1 损失函数/训练目标 ====================
    prompt_loss = f"""
你是一名{article_info['name']}级别的学术论文写作专家。请为论文"{PAPER_TITLE}"撰写第3.{len(modules)+2}节"Training Objective / Loss Function"。

**核心任务**：描述完整的训练目标和损失函数设计。

**项目信息**：
<experiment_design>
{json.dumps(experiment_design, ensure_ascii=False, indent=2)[:3000]}
</experiment_design>

<innovation_points>
{innovation_summary}
</innovation_points>

<loss_config>
{project_info.get('loss_config_content', '')[:4000]}
</loss_config>

**具体要求**：
1. 给出总体损失函数的定义（必须使用 \\begin{{equation}}...\\end{{equation}} 行间公式）
2. 逐项解释每个损失项的物理/几何含义（每个损失项至少一个独立公式）
3. 说明各损失项之间的权重设置及理由
4. 如有物理一致性约束或正则化，详细说明其推导过程

**公式要求**：
- 总体损失函数必须是行间公式
- 每个损失分量也应有独立的公式定义
- 确保至少有2-3个行间公式（\\begin{{equation}}...\\end{{equation}}）

{style_instruction}

{citation_context}

{build_citation_instruction(2)}

请使用学术英语撰写。请直接输出LaTeX代码。行内公式用 $...$，行间公式用 \\begin{{equation}}...\\end{{equation}}。直接给出LaTeX代码：
"""
    
    logger.info(f"[chapter3] 生成 3.{len(modules)+2} Training Objective...")
    try:
        section_loss = _orch.call_generation(prompt_loss)
    except Exception as e:
        logger.error(f"[chapter3] Training Objective 生成失败: {e}")
        section_loss = ""
    
    # ==================== 组装完整章节 ====================
    full_chapter = f"""\section{{Methodology}}

{section_3_1}

"""
    for idx, (module, content) in enumerate(zip(modules, module_sections)):
        full_chapter += f"\\subsection{{{module.get('模块名', f'Module {idx+1}')}}}\n\n{content}\n\n"
    
    full_chapter += f"\\subsection{{Training Objective}}\n\n{section_loss}\n"
    
    return full_chapter, tikz_code

def run_chapter3(project_data, ref_data, previous_chapters=None, citation_context=""):
    """主入口：生成第三章"""
    os.makedirs(f"{OUTPUT_DIR}/chapter3", exist_ok=True)
    
    logger.info("[chapter3] 开始生成第三章 Methodology...")
    try:
        chapter_content, tikz_code = generate_methodology(project_data, ref_data, previous_chapters,
                                                            citation_context=citation_context)
    except Exception as e:
        logger.error(f"[chapter3] 第三章生成失败: {e}")
        chapter_content = "\\section{Methodology}\n\n(生成失败，请重新运行)\n"
        tikz_code = ""
    
    try:
        _orch.save_output("chapter3_methodology.md", chapter_content, subdir="chapter3")
    except Exception as e:
        logger.error(f"[chapter3] 保存章节内容失败: {e}")
    
    try:
        _orch.save_output("architecture_figure.tex", tikz_code, subdir="chapter3")
    except Exception as e:
        logger.error(f"[chapter3] 保存TikZ文件失败: {e}")
    
    logger.info("[chapter3] 第三章生成完成！")
    return chapter_content


if __name__ == "__main__":
    project_data = {}
    ref_data = {}
    for fname in ["innovation_points.json", "experiment_design.json", "model_architecture.json"]:
        fpath = f"{OUTPUT_DIR}/{fname}"
        if os.path.exists(fpath):
            with open(fpath, 'r', encoding='utf-8') as f:
                project_data[fname.replace(".json", "")] = json.load(f)
    result = run_chapter3(project_data, ref_data)
