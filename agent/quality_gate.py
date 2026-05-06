# -*- coding: utf-8 -*-
"""
质量门控 - 质量评估与反馈循环

特性：
1. 每章生成后自动评估质量
2. 质量不达标触发重试/策略调整
3. 评估维度：学术规范、逻辑连贯、引用自然、内容完整
4. 支持自定义质量阈值
"""

import json
import time
import logging
from typing import Optional, Dict, Any, List, Tuple

from agent.api_client import get_api_client
from config.project_config import PAPER_TITLE, OUTPUT_DIR

logger = logging.getLogger(__name__)


class QualityReport:
    """质量评估报告"""

    def __init__(self):
        self.passed: bool = False
        self.overall_score: float = 0.0
        self.dimensions: Dict[str, float] = {}
        self.issues: List[Dict[str, str]] = []
        self.suggestions: List[str] = []
        self.should_retry: bool = False
        self.retry_strategy: str = ""  # "revise" | "regenerate" | "adjust_prompt"

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "overall_score": self.overall_score,
            "dimensions": self.dimensions,
            "issues": self.issues,
            "suggestions": self.suggestions,
            "should_retry": self.should_retry,
            "retry_strategy": self.retry_strategy,
        }


class QualityGate:
    """
    质量门控

    在每章生成后进行质量评估：
    1. 评估4个维度：学术规范、逻辑连贯、引用自然、内容完整
    2. 根据综合得分决定是否通过
    3. 不通过时给出修改建议和重试策略
    4. 超过最大重试次数则标记为"有条件通过"
    """

    PASS_THRESHOLD = 70.0       # 通过阈值
    MAX_RETRY_ROUNDS = 3        # 最大重试轮次

    def __init__(self, api_client=None):
        self.api_client = api_client or get_api_client()
        self._history: List[Dict] = []

    def evaluate(self, chapter_name: str, chapter_content: str,
                 style_guide: Dict = None, chapter_org: Dict = None,
                 previous_content: str = "") -> QualityReport:
        """
        评估章节质量

        Args:
            chapter_name: 章节名称
            chapter_content: 章节内容
            style_guide: 写作风格指导
            chapter_org: 章节组织参考
            previous_content: 前序章节内容（用于评估连贯性）

        Returns:
            QualityReport: 质量评估报告
        """
        report = QualityReport()

        # 构建风格参考
        style_ref = ""
        if style_guide and isinstance(style_guide, dict):
            vocabulary = style_guide.get("用词特征", [])
            if vocabulary:
                style_ref += f"参考学术用词: {vocabulary[:15]}\n"
            citation_style = style_guide.get("引用风格", {})
            if citation_style:
                style_ref += f"参考引用风格: {json.dumps(citation_style, ensure_ascii=False)[:300]}\n"

        if chapter_org and isinstance(chapter_org, dict):
            patterns = chapter_org.get("关键句式模板", {})
            if patterns:
                style_ref += f"参考句式模板: {json.dumps(patterns, ensure_ascii=False)[:500]}\n"

        # 构建论文等级约束
        tier_constraint_text = ""
        try:
            from config.project_config import get_article_type_info
            article_info = get_article_type_info()
            prohibited = article_info.get("prohibited_terms", [])
            preferred = article_info.get("preferred_terms", {})
            tier = article_info.get("tier", "")
            writing_style = article_info.get("writing_style", {})
            
            if prohibited:
                tier_constraint_text += f"\n**论文等级**: {article_info['name']} ({tier})\n"
                tier_constraint_text += "**必须检查的禁用术语**（如果出现在文中，必须在issues中指出）：\n"
                for term in prohibited:
                    replacement = preferred.get(term, "使用更准确的CS学术术语")
                    tier_constraint_text += f'  - "{term}" → 应替换为: {replacement}\n'
            
            if writing_style:
                tier_constraint_text += "\n**写作风格标准**（评估时参照）：\n"
                for key, desc in writing_style.items():
                    tier_constraint_text += f"  - {key}: {desc}\n"
        except Exception:
            pass

        # 检测禁用术语
        prohibited_issues = []
        try:
            from config.project_config import get_article_type_info
            article_info = get_article_type_info()
            for term in article_info.get("prohibited_terms", []):
                if term.lower() in chapter_content.lower():
                    replacement = article_info.get("preferred_terms", {}).get(term, "更准确的CS术语")
                    prohibited_issues.append({
                        "dimension": "academic_rigor",
                        "description": f'论文中出现了禁用术语"{term}"，该术语不适合{article_info["name"]}级别论文，应替换为"{replacement}"',
                        "location": term,
                    })
        except Exception:
            pass

        prompt = f"""
你是一名顶级学术期刊的审稿专家。请从以下4个维度评估论文章节 "{chapter_name}" 的质量：

**评估维度**（每项0-100分）：

1. **学术规范** (academic_rigor)
   - 表述是否学术化，有无口语化表达
   - 论证是否严谨，有无逻辑跳跃
   - 术语使用是否准确一致
   - 是否存在不当术语（如使用了教育领域术语而非CS领域术语）

2. **逻辑连贯** (logical_coherence)
   - 段落间过渡是否自然
   - 论证链条是否完整
   - 与前序章节的衔接是否流畅

3. **引用自然** (citation_naturalness)
   - <citation>标记位置是否合理
   - 引用是否融入句式
   - 引用密度是否适中

4. **内容完整** (content_completeness)
   - 是否覆盖了该章节应有的核心内容
   - 公式、图表、数据是否充分
   - 细节深度是否足够

{style_ref}
{tier_constraint_text}

**待评估内容**：
<chapter_content>
{chapter_content[:6000]}
</chapter_content>

{"**前序章节摘要**：" + previous_content[:1000] if previous_content else ""}

请以json格式给出评估结果：
{{
  "dimensions": {{
    "academic_rigor": 分数,
    "logical_coherence": 分数,
    "citation_naturalness": 分数,
    "content_completeness": 分数
  }},
  "issues": [
    {{"dimension": "维度名", "description": "问题描述", "location": "原文片段[:80]"}}
  ],
  "suggestions": ["修改建议1", "修改建议2"],
  "should_retry": true/false,
  "retry_strategy": "revise"/"regenerate"/"adjust_prompt"
}}

回复以```json开头，以```结尾。
"""

        try:
            response = self.api_client.call_reasoning(prompt)
            result = self.api_client.parse_json_response(response, default={})

            if isinstance(result, dict):
                report.dimensions = result.get("dimensions", {})
                report.issues = result.get("issues", []) + prohibited_issues
                report.suggestions = result.get("suggestions", [])
                report.should_retry = result.get("should_retry", False)
                report.retry_strategy = result.get("retry_strategy", "revise")

                # 如果有禁用术语，强制标记需要修改
                if prohibited_issues:
                    report.should_retry = True
                    if report.retry_strategy == "revise" or not report.retry_strategy:
                        report.retry_strategy = "revise"

                # 计算综合得分
                if report.dimensions:
                    report.overall_score = sum(report.dimensions.values()) / len(report.dimensions)
                    report.passed = report.overall_score >= self.PASS_THRESHOLD and len(prohibited_issues) == 0
                else:
                    report.overall_score = 0
                    report.passed = False
            else:
                report.passed = False  # JSON 解析失败时不通过，需要重试
                report.overall_score = 0
                report.should_retry = True
                report.retry_strategy = "revise"
                report.issues.append({
                    "dimension": "system",
                    "description": f"质量评估结果JSON解析失败，原始响应非dict类型",
                    "location": "",
                })

        except Exception as e:
            logger.error(f"质量评估失败: {e}")
            report.passed = False  # 评估失败时不通过，由上层决定是否继续
            report.overall_score = -1
            report.should_retry = True
            report.retry_strategy = "revise"
            report.issues.append({
                "dimension": "system",
                "description": f"质量评估过程异常: {str(e)[:200]}",
                "location": "",
            })

        # 记录评估历史
        self._history.append({
            "chapter": chapter_name,
            "timestamp": time.time(),
            **report.to_dict()
        })

        return report

    def should_retry(self, report: QualityReport, current_round: int) -> bool:
        """
        判断是否应该重试

        Args:
            report: 质量报告
            current_round: 当前重试轮次

        Returns:
            bool: 是否应该重试
        """
        if current_round >= self.MAX_RETRY_ROUNDS:
            logger.info(f"已达最大重试轮次({self.MAX_RETRY_ROUNDS})，不再重试")
            return False
        return report.should_retry and not report.passed

    def get_revision_prompt(self, chapter_name: str, chapter_content: str,
                           report: QualityReport) -> str:
        """
        根据质量报告生成修改指令

        Args:
            chapter_name: 章节名
            chapter_content: 原始内容
            report: 质量报告

        Returns:
            str: 修改指令prompt
        """
        issues_summary = "\n".join([
            f"- [{iss.get('dimension', '?')}] {iss.get('description', '')} (位置: \"{iss.get('location', '')}\")"
            for iss in report.issues
        ])

        suggestions_text = "\n".join(f"- {s}" for s in report.suggestions)

        prompt = f"""
你是一名学术论文修改专家。请根据以下审查意见修改论文章节内容。

**章节**: {chapter_name}

**质量评估**:
- 综合得分: {report.overall_score:.1f}/100
- 各维度得分: {json.dumps(report.dimensions, ensure_ascii=False)}

**发现的问题**:
{issues_summary}

**修改建议**:
{suggestions_text}

**待修改内容**:
<chapter_content>
{chapter_content[:8000]}
</chapter_content>

**修改要求**:
1. 严格按照审查意见逐一修改
2. 保持原文整体结构和论述逻辑
3. 不引入新内容，只修改被指出的问题
4. 修改后必须更加学术化、逻辑更清晰
5. 保持原有的<citation>和<formula>标记

请直接给出修改后的完整章节内容（Markdown格式），无需解释：
"""

        return prompt

    def revise(self, chapter_name: str, chapter_content: str,
               report: QualityReport) -> str:
        """
        根据质量报告执行修改，返回修改后的内容

        Args:
            chapter_name: 章节名
            chapter_content: 原始内容
            report: 质量报告

        Returns:
            str: 修改后的章节内容
        """
        prompt = self.get_revision_prompt(chapter_name, chapter_content, report)
        try:
            revised = self.api_client.call_generation(prompt)
            logger.info(f"章节 '{chapter_name}' 修改完成")
            return revised
        except Exception as e:
            logger.error(f"章节修改失败: {e}")
            return chapter_content  # 修改失败时返回原文

    def evaluate_and_revise(self, chapter_name: str, chapter_content: str,
                            style_guide: Dict = None, chapter_org: Dict = None,
                            previous_content: str = "",
                            max_rounds: int = None) -> Tuple[str, QualityReport]:
        """
        评估-修改循环：评估质量，不达标则自动修改后重新评估

        Args:
            chapter_name: 章节名称
            chapter_content: 章节内容
            style_guide: 写作风格指导
            chapter_org: 章节组织参考
            previous_content: 前序章节内容
            max_rounds: 最大修改轮次（默认使用 MAX_RETRY_ROUNDS）

        Returns:
            Tuple[str, QualityReport]: (最终内容, 最终质量报告)
        """
        if max_rounds is None:
            max_rounds = self.MAX_RETRY_ROUNDS

        current_content = chapter_content

        for round_num in range(max_rounds + 1):
            report = self.evaluate(
                chapter_name, current_content,
                style_guide, chapter_org, previous_content
            )

            logger.info(f"[质量门控] '{chapter_name}' 第{round_num}轮评估: "
                       f"{report.overall_score:.1f}/100 ({'通过' if report.passed else '不通过'})")

            if report.passed or not report.should_retry:
                break

            if round_num < max_rounds:
                # 执行修改
                logger.info(f"[质量门控] '{chapter_name}' 根据评估结果修改内容...")
                current_content = self.revise(chapter_name, current_content, report)

        return current_content, report

    def get_history(self) -> List[Dict]:
        """获取评估历史"""
        return self._history.copy()
