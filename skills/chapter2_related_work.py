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
from tqdm import tqdm

from config.project_config import (
    PAPER_TITLE, OUTPUT_DIR, get_article_type_info
)
from agent.api_client import get_api_client
from api.paper_search import search_papers, get_paper_details
from utils.chapter1_utils import extract_json_from_string

# 延迟初始化API客户端
_api = None

def _get_api():
    global _api
    if _api is None:
        _api = get_api_client()
    return _api


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
        print(f"  [chapter2] 论文搜索失败: {e}")
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
    
    response = _get_api().call_reasoning(prompt)
    try:
        structure = extract_json_from_string(response)
    except Exception:
        structure = {
            "subsections": [
                {"title": "Traditional Methods", "scope": "传统方法", "key_aspects": ["手工特征", "物理模型"], "target_shortcomings": ["依赖假设", "泛化差"]},
                {"title": "Deep Learning Based Methods for XX", "scope": "基于深度学习的XX方法", "key_aspects": ["网络架构", "损失设计"], "target_shortcomings": ["假设限制", "场景受限"]},
                {"title": "Deep Learning Based Methods for YY", "scope": "基于深度学习的YY方法", "key_aspects": ["关键模块", "训练策略"], "target_shortcomings": ["未建模", "性能退化"]},
            ]
        }
    
    return structure


def generate_related_work(project_data, ref_data):
    """生成第二章 Related Work"""
    
    innovation_points = project_data.get("innovation_points", [])
    experiment_design = project_data.get("experiment_design", {})
    style_guide = ref_data.get("style_guide", {})
    chapter_org = ref_data.get("chapter_organizations", {}).get("Related Work", {})
    article_info = get_article_type_info()
    
    # 确定小节划分
    print("[chapter2] 确定相关工作小节划分...")
    structure = _determine_subsections(innovation_points, experiment_design, ref_data)
    
    with open(f"{OUTPUT_DIR}/chapter2_structure.json", 'w', encoding='utf-8') as f:
        json.dump(structure, f, ensure_ascii=False, indent=2)
    
    style_instruction = _build_style_instruction(style_guide, chapter_org, is_related_work=True)
    
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
        print(f"[chapter2] 搜索 '{title}' 相关论文...")
        search_keywords = [[PAPER_TITLE.split()[0], keyword] for keyword in key_aspects[:2]]
        related_papers = _search_related_papers(search_keywords, size=5)
        
        # 构建论文摘要
        papers_summary = ""
        for p in related_papers:
            authors_str = ", ".join(p["authors"][:2]) + (" et al." if len(p["authors"]) > 2 else "")
            papers_summary += f"- {authors_str} ({p['year']}) "{p['title']}" - {p['venue']}\n  摘要: {p['abstract'][:200]}\n"
        
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

请使用学术英语撰写。引用使用<citation>["keyword1","keyword2"]</citation>标记。Markdown格式。直接给出内容：
"""
        
        print(f"[chapter2] 生成 2.{idx+1} {title}...")
        section_content = _get_api().call_generation(prompt)
        sections.append(section_content)
    
    # ==================== 2.x 总结与过渡 ====================
    prompt_summary = f"""
你是一名{article_info['name']}级别的学术论文写作专家。请为论文"{PAPER_TITLE}"的Related Work章节撰写总结段落。

要求：简要总结各小节讨论的方法类别及其共性不足，然后自然过渡到本文方法：
"Inspired by these observations, we propose a ... approach that addresses the aforementioned limitations by ..."

本研究的创新点：
{innovation_summary}

前序内容摘要：
{sections[-1][:1000]}

请使用学术英语，2-3句话。Markdown格式。直接给出内容：
"""
    
    print("[chapter2] 生成总结过渡段...")
    summary_section = _get_api().call_generation(prompt_summary)
    
    # 组装完整章节
    full_chapter = "# 2. Related Work\n\n"
    for idx, (subsec, content) in enumerate(zip(subsections, sections)):
        full_chapter += f"## 2.{idx+1} {subsec['title']}\n\n{content}\n\n"
    full_chapter += summary_section
    
    return full_chapter


def _build_style_instruction(style_guide, chapter_org, is_related_work=False):
    """构建写作风格指导"""
    instruction = "**写作风格指导**：\n"
    
    if is_related_work:
        instruction += """
- Related Work 特殊要求：
  1. 每篇被讨论的工作用1-2段描述，先说方法核心思路再说结果/局限
  2. 工作之间的过渡句要体现递进或对比关系（"While X focuses on..., Y extends to..."）
  3. 每个小节的最后一段集中讨论该类方法的不足
  4. 不足的论述要具体，不能泛泛说"performance is limited"
  5. 引用要自然融入句式："Author et al. [1] proposed..." 或 "Recent work [2,3] has shown..."
"""
    
    if style_guide and isinstance(style_guide, dict):
        vocabulary = style_guide.get("用词特征", [])
        if vocabulary:
            instruction += f"- 学术用词：{vocabulary[:15]}\n"
        
        citation_style = style_guide.get("引用风格", {})
        if citation_style:
            instruction += f"- 引用风格：{citation_style}\n"
    
    if chapter_org and isinstance(chapter_org, dict):
        patterns = chapter_org.get("关键句式模板", {})
        if patterns:
            instruction += "- 关键句式模板：\n"
            for k, v in list(patterns.items())[:5]:
                instruction += f"  {k}: {v}\n"
    
    instruction += """
- 重要要求：
  1. 文风学术化，禁止口语化
  2. 论述有逻辑层次，每句话都有明确目的
  3. 不足分析要自然指向本研究能解决的问题
"""
    
    return instruction


def run_chapter2(project_data, ref_data):
    """主入口：生成第二章"""
    os.makedirs(f"{OUTPUT_DIR}/chapter2", exist_ok=True)
    
    print("[chapter2] 开始生成第二章 Related Work...")
    chapter_content = generate_related_work(project_data, ref_data)
    
    with open(f"{OUTPUT_DIR}/chapter2/chapter2_related_work.md", 'w', encoding='utf-8') as f:
        f.write(chapter_content)
    
    print("[chapter2] 第二章生成完成！")
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
    print(result[:500])
