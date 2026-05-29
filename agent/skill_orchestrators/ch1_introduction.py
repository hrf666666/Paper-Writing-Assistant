# -*- coding: utf-8 -*-
"""
Skill: 第一章 - Introduction / 前言
核心任务：强调待解决问题的重要性和难度
"""

import os
import json
from tqdm import tqdm

from config.project_config import (
    PAPER_TITLE, OUTPUT_DIR, get_article_type_info
)
from agent.base_orchestrator import BaseOrchestrator

import logging
logger = logging.getLogger(__name__)

# 基类实例：统一 LLM 调用
_orch = BaseOrchestrator(output_dir=OUTPUT_DIR)


def generate_introduction(project_data, ref_data):
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
    style_instruction = _build_style_instruction(style_guide, chapter_org)
    
    # ==================== 子节1.1: 研究背景与问题重要性 ====================
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

{style_instruction}

请使用学术英语撰写，文风严谨但不失流畅。对于潜在可以添加引用的部分，使用<citation>["keyword1", "keyword2"]</citation>标记。
对于行内公式，使用 `$...$` 格式；对于行间公式，使用 `$$...$$` 格式。使用Markdown格式。
**重要**：不要输出章节顶级标题（如 "# 1. Introduction"），该标题已由系统自动添加。直接从正文内容开始。请直接给出内容，无需解释：
"""
    
    logger.info("[chapter1] 生成 1.1 研究背景与问题重要性...")
    try:
        section_1_1 = _orch.call_generation(prompt_1_1)
    except Exception as e:
        logger.error(f"[chapter1] 1.1 生成失败: {e}")
        section_1_1 = ""
    
    # ==================== 子节1.2: 现有方法的不足 ====================
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

请使用学术英语撰写。引用使用<citation>标记。行内公式用 `$...$`，行间公式用 `$$...$$`。Markdown格式。
**重要**：不要输出子节标题（如 "## 1.1 ..."），直接从正文开始。直接给出内容：
"""
    
    logger.info("[chapter1] 生成 1.2 现有方法的局限性...")
    try:
        section_1_2 = _orch.call_generation(prompt_1_2)
    except Exception as e:
        logger.error(f"[chapter1] 1.2 生成失败: {e}")
        section_1_2 = ""
    
    # ==================== 子节1.3: 本文方法与贡献 ====================
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

请使用学术英语撰写。贡献列表使用Markdown格式（- **Contribution 1**: ...）。行内公式用 `$...$`，行间公式用 `$$...$$`。全程使用Markdown格式，不要混用LaTeX。
**重要**：不要输出子节标题，直接从正文开始。直接给出内容：
"""
    
    logger.info("[chapter1] 生成 1.3 本文方法与贡献...")
    try:
        section_1_3 = _orch.call_generation(prompt_1_3)
    except Exception as e:
        logger.error(f"[chapter1] 1.3 生成失败: {e}")
        section_1_3 = ""
    
    # ==================== 组装完整章节 ====================
    full_chapter = f"""# 1. Introduction

{section_1_1}

{section_1_2}

{section_1_3}
"""
    
    return full_chapter


def _build_style_instruction(style_guide, chapter_org):
    """构建写作风格指导文本（v9.3: 集成 IEEE Trans 期刊风格配置）"""
    instruction = "**写作风格指导**：\n"
    
    # v9.3: 加载 IEEE Trans 期刊风格配置（P2 优先级规则）
    try:
        import os
        from config.ieee_trans_style_profile import (
            get_ieee_trans_style_profile,
            get_section_requirements,
            get_red_flags,
        )
        
        profile = get_ieee_trans_style_profile()
        intro_req = get_section_requirements("Introduction")
        red_flags = get_red_flags()
        
        instruction += f"\n**IEEE Transactions 期刊特定规则**（P2 优先级，必须遵守）：\n"
        instruction += f"\n### Introduction 结构要求\n"
        instruction += f"- 结构序列：{intro_req.get('structure', 'N/A')}\n"
        instruction += f"- 贡献列表：最多 {intro_req.get('contributions', {}).get('max_items', 3)} 项，陈述为事实而非意图\n"
        instruction += f"- 贡献格式：{intro_req.get('contributions', {}).get('format', 'N/A')}\n"
        
        instruction += f"\n### 禁止模式 (Red Flags)\n"
        for flag in red_flags[:5]:  # 只显示前 5 个
            instruction += f"- {flag}\n"
        
        instruction += f"\n### 语言风格\n"
        lang = profile.get('language_style_profile', {})
        instruction += f"- 语态：{lang.get('voice', 'N/A')}\n"
        instruction += f"- 句长：{lang.get('sentence_length', 'N/A')}\n"
        instruction += f"- 模糊程度：{lang.get('hedging_level', 'N/A')}\n"
        instruction += "\n"
    except Exception as e:
        logger.debug(f"[IEEE Trans 风格配置] 加载失败: {e}")
    
    # v9.2: 加载学术写作风格指南（P4 优先级规则）
    try:
        import os
        style_guide_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "skills", "academic_writing_style", "style_guide.md"
        )
        if os.path.exists(style_guide_path):
            with open(style_guide_path, 'r', encoding='utf-8') as f:
                style_guide_content = f.read()
            instruction += f"\n**学术写作基础规范**（P4 优先级）：\n"
            instruction += style_guide_content[:1500]  # 截取关键部分
            instruction += "\n"
    except Exception as e:
        logger.debug(f"[风格指南] 加载失败: {e}")
    
    if style_guide:
        if isinstance(style_guide, dict):
            sentence_patterns = style_guide.get("句式特征", {})
            if sentence_patterns:
                instruction += "- 常用句式模式：\n"
                for pattern_type, examples in sentence_patterns.items():
                    if isinstance(examples, (list, dict)):
                        instruction += f"  {pattern_type}: {examples}\n"
            
            vocabulary = style_guide.get("用词特征", [])
            if vocabulary:
                instruction += f"- 学术用词：{vocabulary[:20]}\n"
            
            citation_style = style_guide.get("引用风格", {})
            if citation_style:
                instruction += f"- 引用风格：{citation_style}\n"
    
    if chapter_org:
        if isinstance(chapter_org, dict):
            structure = chapter_org.get("章节结构", [])
            if structure:
                instruction += f"- 参考组织结构：{structure}\n"
            
            patterns = chapter_org.get("关键句式模板", {})
            if patterns:
                instruction += f"- 关键句式模板：\n"
                for k, v in patterns.items():
                    instruction += f"  {k}: {v}\n"
    
    instruction += """
- 重要要求：
  1. 文风必须学术化，禁止口语化表达
  2. 每句话都要有明确的论述目的，避免空洞的过渡句
  3. 论述要有逻辑层次：从宏观到微观，从问题到方案
  4. 引用要自然融入句式，不能生硬堆砌
  5. **严格避免 AI 风格词汇**（如 revolutionize, groundbreaking, unprecedented 等）
  6. **括号内容不超过 20 词**，超长内容应拆分为独立句子
  7. **句子长度控制在 20-30 词**，避免超过 40 词的长句
"""
    
    return instruction


def run_chapter1(project_data, ref_data):
    """主入口：生成第一章"""
    os.makedirs(f"{OUTPUT_DIR}/chapter1", exist_ok=True)
    
    logger.info("[chapter1] 开始生成第一章 Introduction...")
    try:
        chapter_content = generate_introduction(project_data, ref_data)
    except Exception as e:
        logger.error(f"[chapter1] 第一章生成失败: {e}")
        chapter_content = "# 1. Introduction\n\n(生成失败，请重新运行)\n"
    
    # 保存Markdown版本
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
