# -*- coding: utf-8 -*-
"""
Skill: 第二章 - Related Work / 相关工作
核心任务：
- 传统方法、现代方法分类综述
- 每小节文章数总体一致
- 对比所提方法的不足，不足之处指向本项目可解决的问题
"""

import os
import json

from config.project_config import (
    PAPER_TITLE, OUTPUT_DIR, get_article_type_info
)
from agent.base_orchestrator import BaseOrchestrator, build_style_instruction
from api.paper_search import search_papers, get_paper_details

import logging
logger = logging.getLogger(__name__)

# 基类实例：统一 LLM 调用
_orch = BaseOrchestrator(output_dir=OUTPUT_DIR)


def _search_related_papers(keywords, size=5):
    """搜索相关论文"""
    try:
        result = search_papers(keywords, size)
        papers = []
        if "data" in result and result["data"]:
            for paper_brief in result["data"][:size]:
                details = get_paper_details(paper_brief["id"])
                if "data" in details and details["data"]:
                    paper_info = details["data"][0]
                    title = paper_info.get("title", "")
                    authors = [a.get("name", "") for a in paper_info.get("authors", []) if a.get("name")]
                    year = paper_info.get("year", "")
                    abstract = paper_info.get("abstract", "")
                    venue = paper_info.get("venue", {}).get("raw", "") if paper_info.get("venue") else ""
                    papers.append({
                        "title": title,
                        "authors": authors[:3],
                        "year": year,
                        "abstract": abstract[:500] if abstract else "",
                        "venue": venue,
                    })
        return papers
    except Exception as e:
        logger.warning(f"  [chapter2] 论文搜索失败: {e}")
        return []


def _determine_subsections(innovation_points, experiment_design, ref_data):
    """根据项目创新点和领域信息，确定相关工作的小节划分"""
    
    domain_info = ref_data.get("domain_info", {})
    
    prompt = f"""
你是一名学术论文结构设计专家。请为论文"{PAPER_TITLE}"设计"Related Work"章节的小节划分。

要求：
1. 划分为3个子节，分别覆盖：传统方法、基于深度学习的XX方法、基于深度学习的YY方法
2. 每个子节应讨论3-4篇代表性工作，各子节的文章数量应总体一致
3. 每个子节的最后要分析所提方法的不足，这些不足应指向本项目可以解决的问题
4. 子节之间的递进关系应清晰：从传统到现代，从通用到具体

项目创新点：
{json.dumps(innovation_points, ensure_ascii=False, indent=2)}

实验设计概要：
{json.dumps(experiment_design, ensure_ascii=False, indent=2)[:2000]}

请以json格式给出，包含"subsections"字段（list），每个元素包含"title"(子节标题)、"scope"(综述范围描述)、"key_aspects"(需要重点讨论的方面list)、"target_shortcomings"(需要指出的不足list)。
回复以```json开头，以```结尾。
"""
    
    return _orch.parse_json_with_retry(
        prompt, call_method="call_reasoning",
        default={
            "subsections": [
                {"title": "Traditional Methods", "scope": "传统方法", "key_aspects": ["手工特征", "物理模型"], "target_shortcomings": ["依赖假设", "泛化差"]},
                {"title": "Deep Learning Based Methods for XX", "scope": "基于深度学习的XX方法", "key_aspects": ["网络架构", "损失设计"], "target_shortcomings": ["假设限制", "场景受限"]},
                {"title": "Deep Learning Based Methods for YY", "scope": "基于深度学习的YY方法", "key_aspects": ["关键模块", "训练策略"], "target_shortcomings": ["未建模", "性能退化"]},
            ]
        }
    )


def generate_related_work(project_data, ref_data, previous_chapters=None, citation_context=""):
    """生成第二章 Related Work"""
    
    innovation_points = project_data.get("innovation_points", [])
    experiment_design = project_data.get("experiment_design", {})
    style_guide = ref_data.get("style_guide", {})
    chapter_org = ref_data.get("chapter_organizations", {}).get("Related Work", {})
    article_info = get_article_type_info()
    
    # 构建前序章节摘要（用于保持术语和内容衔接）
    prev_summary = ""
    if previous_chapters and 1 in previous_chapters:
        prev_summary = f"""**前序章节（Introduction）摘要**：
{previous_chapters[1][:1500]}

**关键要求**：确保 Related Work 中讨论的方法不足自然指向 Introduction 中提出的创新点。不要重复 Introduction 中已经涵盖的背景内容。
"""
    
    # 确定小节划分
    logger.info("[chapter2] 确定相关工作小节划分...")
    try:
        structure = _determine_subsections(innovation_points, experiment_design, ref_data)
    except Exception as e:
        logger.error(f"[chapter2] 小节划分失败: {e}")
        structure = {"subsections": [
            {"title": "Traditional Methods", "scope": "传统方法", "key_aspects": [], "target_shortcomings": []},
        ]}
    
    try:
        _orch.save_output("chapter2_structure.json", structure)
    except Exception as e:
        logger.error(f"[chapter2] 保存结构失败: {e}")
    
    style_instruction = build_style_instruction(style_guide, chapter_org, chapter_name="Related Work", is_related_work=True)
    
    innovation_summary = ""
    for i, ip in enumerate(innovation_points, 1):
        innovation_summary += f"创新点{i}: {ip.get('创新点名称', 'N/A')} - {ip.get('创新点价值', 'N/A')}\n"
    
    sections = []
    subsections = structure.get("subsections", [])
    
    for idx, subsec in enumerate(subsections):
        title = subsec.get("title", f"2.{idx+1} Related Approach")
        scope = subsec.get("scope", "")
        key_aspects = subsec.get("key_aspects", [])
        target_shortcomings = subsec.get("target_shortcomings", [])
        
        # 搜索相关论文
        logger.info(f"[chapter2] 搜索 '{title}' 相关论文...")
        try:
            search_keywords = [[PAPER_TITLE.split()[0], keyword] for keyword in key_aspects[:2]]
            related_papers = _search_related_papers(search_keywords, size=5)
        except Exception as e:
            logger.warning(f"[chapter2] 论文搜索失败 '{title}': {e}")
            related_papers = []
        
        # 构建论文摘要
        papers_summary = ""
        for p in related_papers:
            authors_str = ", ".join(p["authors"][:2]) + (" et al." if len(p["authors"]) > 2 else "")
            papers_summary += f"""- {authors_str} ({p['year']}) "{p['title']}" - {p['venue']}\n  摘要: {p['abstract'][:200]}\n"""
        
        # 获取前序子节内容（用于保持连贯性）
        prev_content = sections[-1][:1500] if sections else ""
        
        prompt = f"""
你是一名{article_info['name']}级别的学术论文写作专家。请为论文"{PAPER_TITLE}"撰写第2.{idx+1}节"{title}"。

**核心任务**：综述{scope}领域的代表性工作，并分析其不足。

**具体要求**：
1. 综述3-4篇代表性工作，每篇工作简要描述其核心思路和关键结果
2. 每篇工作的描述应突出其与本研究的关联性
3. 在小节末尾，分析这类方法存在的共性不足
4. 不足的分析应自然指向本研究可以解决的问题：
   {json.dumps(target_shortcomings, ensure_ascii=False)}
5. 各工作之间的过渡要自然，使用对比、递进等论述手法

**本研究的创新点**（用于构建对比关系）：
{innovation_summary}

**相关论文参考**：
{papers_summary if papers_summary else "请根据领域知识自行补充代表性工作。"}

**前序子节内容**：
<previous_content>
{prev_content}
</previous_content>

{style_instruction}

{prev_summary}

{citation_context}

请使用学术英语撰写。引用使用<citation>["keyword1","keyword2"]</citation>标记。请直接输出LaTeX代码。行内公式用 $...$，行间公式用 \begin{{equation}}...\end{{equation}}。
**重要**：不要输出 \section 或 \subsection 标题，标题由系统自动添加。直接从正文开始，只输出LaTeX代码：
"""
        
        logger.info(f"[chapter2] 生成 2.{idx+1} {title}...")
        try:
            section_content = _orch.call_generation(prompt)
        except Exception as e:
            logger.error(f"[chapter2] 2.{idx+1} 生成失败: {e}")
            section_content = f"## 2.{idx+1} {title}\n\n(生成失败)\n"
        sections.append(section_content)
    
    # ==================== 2.x 总结与过渡 ====================
    if not sections:
        logger.warning("[chapter2] 无子节内容，跳过总结段")
        return "# 2. Related Work\n\n(生成失败，请重新运行)\n"
    
    prompt_summary = f"""
你是一名{article_info['name']}级别的学术论文写作专家。请为论文"{PAPER_TITLE}"的Related Work章节撰写总结段落。

要求：简要总结各小节讨论的方法类别及其共性不足，然后自然过渡到本文方法：
"Inspired by these observations, we propose a ... approach that addresses the aforementioned limitations by ..."

本研究的创新点：
{innovation_summary}

前序内容摘要：
{sections[-1][:1000]}

请使用学术英语，2-3句话。直接输出LaTeX代码。不要输出 \section 标题。直接给出内容：
"""
    
    logger.info("[chapter2] 生成总结过渡段...")
    try:
        summary_section = _orch.call_generation(prompt_summary)
    except Exception as e:
        logger.error(f"[chapter2] 总结段生成失败: {e}")
        summary_section = ""
    
    # 组装完整章节
    full_chapter = "\\section{Related Work}\n\n"
    for idx, (subsec, content) in enumerate(zip(subsections, sections)):
        full_chapter += f"\\subsection{{{subsec['title']}}}\n\n{content}\n\n"
    full_chapter += summary_section
    
    return full_chapter

def run_chapter2(project_data, ref_data, previous_chapters=None, citation_context=""):
    """主入口：生成第二章"""
    os.makedirs(f"{OUTPUT_DIR}/chapter2", exist_ok=True)
    
    logger.info("[chapter2] 开始生成第二章 Related Work...")
    try:
        chapter_content = generate_related_work(project_data, ref_data, previous_chapters,
                                                   citation_context=citation_context)
    except Exception as e:
        logger.error(f"[chapter2] 第二章生成失败: {e}")
        chapter_content = "\\section{Related Work}\n\n(生成失败，请重新运行)\n"
    
    try:
        _orch.save_output("chapter2_related_work.md", chapter_content, subdir="chapter2")
    except Exception as e:
        logger.error(f"[chapter2] 保存失败: {e}")
    
    logger.info("[chapter2] 第二章生成完成！")
    return chapter_content


if __name__ == "__main__":
    project_data = {}
    ref_data = {}
    for fname in ["innovation_points.json", "experiment_design.json"]:
        fpath = f"{OUTPUT_DIR}/{fname}"
        if os.path.exists(fpath):
            with open(fpath, 'r', encoding='utf-8') as f:
                project_data[fname.replace(".json", "")] = json.load(f)
    result = run_chapter2(project_data, ref_data)
    logger.info(result[:500])
