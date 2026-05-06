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
from agent.api_client import get_api_client

# 延迟初始化API客户端，避免模块级初始化导致 import 失败和测试难以 mock
_api = None

def _get_api():
    global _api
    if _api is None:
        _api = get_api_client()
    return _api


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
对于公式，使用<formula>...</formula>标记。使用Markdown格式。请直接给出内容，无需解释：
"""
    
    print("[chapter1] 生成 1.1 研究背景与问题重要性...")
    section_1_1 = _get_api().call_generation(prompt_1_1)
    
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

请使用学术英语撰写。对于引用、公式分别使用<citation>和<formula>标记。Markdown格式。直接给出内容：
"""
    
    print("[chapter1] 生成 1.2 现有方法的局限性...")
    section_1_2 = _get_api().call_generation(prompt_1_2)
    
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

请使用学术英语撰写。贡献列表使用Markdown格式（- **Contribution 1**: ...）。全程使用Markdown格式，不要混用LaTeX。直接给出内容：
"""
    
    print("[chapter1] 生成 1.3 本文方法与贡献...")
    section_1_3 = _get_api().call_generation(prompt_1_3)
    
    # ==================== 组装完整章节 ====================
    full_chapter = f"""# 1. Introduction

{section_1_1}

{section_1_2}

{section_1_3}
"""
    
    return full_chapter


def _build_style_instruction(style_guide, chapter_org):
    """构建写作风格指导文本"""
    instruction = "**写作风格指导**：\n"
    
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
"""
    
    return instruction


def run_chapter1(project_data, ref_data):
    """主入口：生成第一章"""
    os.makedirs(f"{OUTPUT_DIR}/chapter1", exist_ok=True)
    
    print("[chapter1] 开始生成第一章 Introduction...")
    chapter_content = generate_introduction(project_data, ref_data)
    
    # 保存Markdown版本
    with open(f"{OUTPUT_DIR}/chapter1/chapter1_introduction.md", 'w', encoding='utf-8') as f:
        f.write(chapter_content)
    
    print("[chapter1] 第一章生成完成！")
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
    print(result[:500])
