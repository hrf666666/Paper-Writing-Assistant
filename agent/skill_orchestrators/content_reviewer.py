# -*- coding: utf-8 -*-
"""
Skill: 内容审查器
审查每章内容的：
1. 句式和表述意义是否清晰（仿写参考PDF的写法）
2. 文法撰写风格是否学术化（避免口语化）
3. 内容逻辑是否连贯
4. 引用是否自然
"""

import os
import json

from config.project_config import (
    PAPER_TITLE, OUTPUT_DIR, get_article_type_info
)
from agent.base_orchestrator import BaseOrchestrator

import logging
logger = logging.getLogger(__name__)

# 基类实例：统一 LLM 调用
_orch = BaseOrchestrator(output_dir=OUTPUT_DIR)

MAX_REVIEW_ROUNDS = 3  # 最大审查轮次


def review_chapter(chapter_content, chapter_name, style_guide, chapter_org):
    """
    审查单个章节的内容
    
    返回：(is_approved, issues_list, revised_content)
    """
    article_info = get_article_type_info()
    
    # 构建风格参考
    style_ref = ""
    if style_guide and isinstance(style_guide, dict):
        sentence_patterns = style_guide.get("句式特征", {})
        vocabulary = style_guide.get("用词特征", [])
        citation_style = style_guide.get("引用风格", {})
        
        if sentence_patterns:
            style_ref += f"参考句式模式：{json.dumps(sentence_patterns, ensure_ascii=False)[:1000]}\n"
        if vocabulary:
            style_ref += f"参考学术用词：{vocabulary[:20]}\n"
        if citation_style:
            style_ref += f"参考引用风格：{json.dumps(citation_style, ensure_ascii=False)[:500]}\n"
    
    if chapter_org and isinstance(chapter_org, dict):
        patterns = chapter_org.get("关键句式模板", {})
        if patterns:
            style_ref += f"参考句式模板：{json.dumps(patterns, ensure_ascii=False)[:1000]}\n"
    
    prompt = f"""
你是一名{article_info['name']}级别的学术论文审稿专家和语言学家。请审查以下论文"{chapter_name}"章节的内容。

**审查维度**：

1. **句式审查**：每一句的句式是否清晰、是否有明确的表述意义？是否存在以下问题：
   - 句子过长或结构混乱
   - 空洞的过渡句（没有实质内容）
   - 逻辑跳跃（前后句没有逻辑联系）
   - 与参考PDF的写法风格不符

2. **文法审查**：表述是否学术化？是否存在以下问题：
   - 口语化表达（如"we can see that", "it is obvious that"）
   - 不严谨的表述（如"greatly improve", "very effective"）
   - 应使用更精确的学术词汇的位置

3. **逻辑审查**：论述逻辑是否连贯？
   - 段落之间的过渡是否自然
   - 论证是否有据可依
   - 结论是否从论据自然推出

4. **引用审查**：引用是否自然？
   - 引用是否融入句式
   - 引用的位置是否合理

{style_ref}

**待审查内容**：
<chapter_content>
{chapter_content[:8000]}
</chapter_content>

请以json格式给出审查结果，包含：
- "approved": boolean, 是否通过审查
- "issues": list, 每个元素是一个dict，包含：
  - "type": 问题类型（"句式"|"文法"|"逻辑"|"引用"）
  - "original": 原文片段
  - "problem": 问题描述
  - "suggestion": 修改建议（给出具体的修改后文本）
- "overall_comment": 整体评价

回复以```json开头，以```结尾，无需添加任何解释说明。
"""
    
    response = _orch.call_reasoning(prompt)
    review_result = _orch.parse_json_with_retry(
        prompt, call_method="call_reasoning",
        default={"approved": True, "issues": [], "overall_comment": "审查结果解析失败，默认通过"}
    )
    # 如果 parse_json_with_retry 返回了带 approved 字段的 dict，直接使用
    if not isinstance(review_result, dict) or "approved" not in review_result:
        review_result = {
            "approved": True,
            "issues": [],
            "overall_comment": "审查结果解析失败，默认通过",
        }
    
    return review_result


def apply_revisions(chapter_content, issues):
    """根据审查意见修改内容"""
    
    if not issues:
        return chapter_content
    
    issues_summary = "\n".join([
        f"- [{iss.get('type', '?')}] 原文: \"{iss.get('original', '')[:100]}\" → 问题: {iss.get('problem', '')} → 建议: {iss.get('suggestion', '')[:100]}"
        for iss in issues
    ])
    
    prompt = f"""
你是一名学术论文修改专家。请根据以下审查意见修改论文章节内容。

**审查意见**：
{issues_summary}

**待修改内容**：
<chapter_content>
{chapter_content[:8000]}
</chapter_content>

**修改要求**：
1. 严格按照审查意见逐一修改
2. 修改时保持原文的整体结构和论述逻辑
3. 不引入新的内容，只修改被指出的问题
4. 修改后的文本必须更加学术化、逻辑更清晰
5. 保持原有的<citation>和<formula>标记

请直接给出修改后的完整章节LaTeX代码（保持LaTeX格式），无需解释修改了什么：
"""
    
    revised_content = _orch.call_generation(prompt)
    return revised_content


def run_content_reviewer(chapter_content, chapter_name, style_guide, chapter_org):
    """
    主入口：运行内容审查
    
    执行多轮审查，每轮审查→修改→再审查，直到通过或达到最大轮次
    """
    logger.info(f"[content_reviewer] 开始审查 '{chapter_name}'...")
    
    current_content = chapter_content
    
    for round_num in range(1, MAX_REVIEW_ROUNDS + 1):
        logger.info(f"[content_reviewer] 第 {round_num}/{MAX_REVIEW_ROUNDS} 轮审查...")
        
        try:
            review_result = review_chapter(current_content, chapter_name, style_guide, chapter_org)
        except Exception as e:
            logger.error(f"[content_reviewer] 第{round_num}轮审查失败: {e}")
            break
        
        approved = review_result.get("approved", True)
        issues = review_result.get("issues", [])
        comment = review_result.get("overall_comment", "")
        
        logger.info(f"[content_reviewer] 审查结果: {'通过' if approved else '需修改'}")
        logger.info(f"[content_reviewer] 发现问题: {len(issues)} 个")
        if comment:
                logger.info(f"[content_reviewer] 评价: {comment[:200]}")
        
        # 保存审查结果
        try:
            _orch.save_output(f"review_{chapter_name}_round{round_num}.json", review_result)
        except Exception as e:
            logger.error(f"[content_reviewer] 保存审查结果失败: {e}")
        
        if approved or not issues:
            logger.info(f"[content_reviewer] '{chapter_name}' 审查通过！")
            break
        
        # 根据审查意见修改
        logger.info(f"[content_reviewer] 根据审查意见修改内容...")
        try:
            current_content = apply_revisions(current_content, issues)
        except Exception as e:
            logger.error(f"[content_reviewer] 修改内容失败: {e}")
            break
    
    return current_content


if __name__ == "__main__":
    # 测试：审查第一章
    chapter_path = f"{OUTPUT_DIR}/chapter1/chapter1_introduction.md"
    if os.path.exists(chapter_path):
        with open(chapter_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        style_path = f"{OUTPUT_DIR}/writing_style_guide.json"
        style_guide = {}
        if os.path.exists(style_path):
            with open(style_path, 'r', encoding='utf-8') as f:
                style_guide = json.load(f)
        
        result = run_content_reviewer(content, "Introduction", style_guide, {})
        with open(f"{OUTPUT_DIR}/chapter1/chapter1_introduction_reviewed.md", 'w', encoding='utf-8') as f:
            f.write(result)
