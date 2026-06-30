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

        # v11.8: 合并论文等级约束 + 禁用术语检测（只调用一次 get_article_type_info）
        tier_constraint_text = ""
        prohibited_issues = []
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

                # 同时检测禁用术语（无需二次调用 get_article_type_info）
                for term in prohibited:
                    if term.lower() in chapter_content.lower():
                        replacement = preferred.get(term, "更准确的CS术语")
                        prohibited_issues.append({
                            "dimension": "academic_rigor",
                            "description": f'论文中出现了禁用术语"{term}"，该术语不适合{article_info["name"]}级别论文，应替换为"{replacement}"',
                            "location": term,
                        })

            if writing_style:
                tier_constraint_text += "\n**写作风格标准**（评估时参照）：\n"
                for key, desc in writing_style.items():
                    tier_constraint_text += f"  - {key}: {desc}\n"
        except Exception as e:
            logger.debug(f"写作风格加载失败: {e}")

        # v11.8: 学术风格二次评价 — checker 不可用时跳过加权，不给免费分
        style_check_issues = []
        style_available = False
        style_score = 0.0
        style_result = {"passed": True, "score": 0.0, "issues": [], "suggestions": []}
        try:
            from agent.academic_style_checker import AcademicStyleChecker
            style_checker = AcademicStyleChecker()
            style_result = style_checker.check_style_compliance(chapter_content, chapter_name)
            style_score = style_result["score"]
            style_available = True

            # 将风格问题转换为质量门控 issues
            for issue in style_result["issues"]:
                if issue["severity"] in ["critical", "warning"]:
                    style_check_issues.append({
                        "dimension": "academic_style",
                        "description": f"[风格检查] {issue.get('suggestion', issue['type'])}",
                        "location": issue.get("context", "")[:80],
                    })

            # 记录风格检查报告到日志
            if not style_result["passed"]:
                logger.info(f"[风格检查] {chapter_name} 未通过: score={style_score:.1f}")
                for suggestion in style_result["suggestions"][:3]:
                    logger.info(f"  建议: {suggestion}")
        except Exception as e:
            logger.debug(f"[风格检查] 检查器不可用，跳过风格加权: {e}")

        prompt = f"""You are an Unflinching Academic Gatekeeper reviewing the "{chapter_name}" section of an IEEE journal paper.
Find what is actually wrong, with surgical precision. Separate fatal flaws from fixable nits.

TWO-PASS REVIEW:
Pass 1 - Fatal-flaw diagnostic: Missing claims support, logical gaps, terminology errors, formatting issues.
Pass 2 - Forensic: For each candidate, specify WHERE exactly, WHY it is a flaw, what evidence settles it.

{style_ref}
{tier_constraint_text}

**Section under review:**
<chapter_content>
{chapter_content[:6000]}
</chapter_content>

{"**Previous sections summary:**" + previous_content[:1000] if previous_content else ""}

Output JSON with BOTH dimensions (0-100) AND issues (each with evidence + close_criterion):

```json
{{
  "dimensions": {{
    "academic_rigor": <0-100>,
    "logical_coherence": <0-100>,
    "citation_naturalness": <0-100>,
    "content_completeness": <0-100>
  }},
  "issues": [
    {{
      "dimension": "academic_rigor|logical_coherence|citation_naturalness|content_completeness",
      "description": "<what is wrong>",
      "evidence_anchor": "<EXACT verbatim quote from the text>",
      "close_criterion": "<what specific change would fix this>",
      "significance": "major|minor"
    }}
  ],
  "suggestions": ["s1", "s2"]
}}
```

Each issue MUST have an evidence_anchor (EXACT quote - if you cannot quote it, do NOT file it).
If no real issues, return empty issues list.
```json ... ``` only."""

        try:
            response = self.api_client.call_evaluation(prompt)
            result = self.api_client.parse_json_response(response, default={})

            if isinstance(result, dict):
                report.dimensions = result.get("dimensions", {})
                report.issues = result.get("issues", []) + prohibited_issues + style_check_issues
                report.suggestions = result.get("suggestions", [])
                report.should_retry = result.get("should_retry", False)
                report.retry_strategy = result.get("retry_strategy", "revise")

                # 如果有禁用术语或风格问题，强制标记需要修改
                if prohibited_issues or style_check_issues:
                    report.should_retry = True
                    if report.retry_strategy == "revise" or not report.retry_strategy:
                        report.retry_strategy = "revise"

                # 计算综合得分（融合 LLM 评估 + 风格检查）
                if report.dimensions:
                    llm_score = sum(report.dimensions.values()) / len(report.dimensions)
                    if style_available:
                        # 风格评分权重 30%，LLM 评分权重 70%
                        report.overall_score = llm_score * 0.7 + style_score * 0.3
                    else:
                        # checker 不可用时只用 LLM 分数，不给免费分
                        report.overall_score = llm_score
                    # v11.8: should_retry 由代码决定，不依赖 LLM 判断
                    # v12.2: 禁用术语/风格问题也必须触发重试（修复覆盖 bug）
                    score_based_retry = report.overall_score < self.PASS_THRESHOLD
                    issue_based_retry = bool(prohibited_issues or style_check_issues)
                    report.should_retry = score_based_retry or issue_based_retry
                    report.passed = (
                        report.overall_score >= self.PASS_THRESHOLD
                        and len(prohibited_issues) == 0
                        and style_result.get("passed", True)
                    )
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

        # v16.3: 落盘章节质量分（供 G4 验收器读取——验收器纯文件读取架构）
        self._persist_score(chapter_name, report)

        return report

    def _persist_score(self, chapter_name: str, report) -> None:
        """把章节质量分落盘到 output/quality_scores.json。

        验收器（ValidationEngine）纯从 output_dir 读文件，读不到内存 _history。
        落盘后 G4 能用 quality_score_N metric 读到分数，采信语义判断替代硬编码字数。
        """
        import os
        path = os.path.join(OUTPUT_DIR, "quality_scores.json")
        data = {}
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        data[chapter_name] = {
            "score": round(report.overall_score, 1),
            "passed": report.passed,
            "issues_count": len(report.issues),
            "timestamp": time.time(),
        }
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except IOError:
            pass

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
                           report: QualityReport,
                           extra_findings_brief: str = "") -> str:
        """
        根据质量报告生成修改指令

        v13 PR5: 接受 extra_findings_brief（来自 FindingBus 的跨子系统问题简报，
        如 cross_chapter 数值矛盾、auditor 引用问题），让修订同时修复一致性问题。

        Args:
            chapter_name: 章节名
            chapter_content: 原始内容
            report: 质量报告
            extra_findings_brief: FindingBus.as_revision_brief() 的输出（可选）

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
{extra_findings_brief}

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

请直接给出修改后的完整章节LaTeX代码（保持LaTeX格式），无需解释：
"""

        return prompt

    def revise(self, chapter_name: str, chapter_content: str,
               report: QualityReport, extra_findings_brief: str = "") -> str:
        """
        根据质量报告执行修改，返回修改后的内容

        Args:
            chapter_name: 章节名
            chapter_content: 原始内容
            report: 质量报告
            extra_findings_brief: FindingBus 跨子系统问题简报（可选）

        Returns:
            str: 修改后的章节内容
        """
        prompt = self.get_revision_prompt(chapter_name, chapter_content, report,
                                          extra_findings_brief)
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
                            max_rounds: int = None,
                            extra_findings_brief: str = "") -> Tuple[str, QualityReport]:
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
                _before_revise = current_content
                current_content = self.revise(chapter_name, current_content, report,
                                              extra_findings_brief)
                # v16.3 第五批 B3修复: revise 后回归守卫——独立于 evaluate 的确定性检查
                # 防止 revise 引入回归（cite 丢失/段落大幅缩短/内容损坏）
                _regression = self._check_revise_regression(chapter_name, _before_revise, current_content)
                if _regression:
                    logger.warning(f"[质量门控] '{chapter_name}' revise 引入回归: {_regression}，回退")
                    current_content = _before_revise  # 回退到改前
                    report.should_retry = False  # 不再重试（避免反复改坏）

        return current_content, report

    def _check_revise_regression(self, chapter_name: str,
                                before: str, after: str) -> str:
        """v16.3 B3修复: revise 后独立回归守卫（确定性，不依赖 evaluate）。

        职能边界：只检查 revise 是否引入确定性回归，不评写作质量。
        检查项：
        1. cite 丢失（改前有 cite，改后没了）
        2. 内容大幅缩短（改后 < 改前 50%，可能丢失段落）
        3. 内容损坏（LLM 思考碎片/乱码注入）
        Returns: 回归描述（""=无回归）
        """
        import re
        if not after or len(after.strip()) < 50:
            return "改后内容为空或过短"
        # 1. cite 丢失
        _before_cites = set(re.findall(r'\\cite\{[^}]+\}', before))
        _after_cites = set(re.findall(r'\\cite\{[^}]+\}', after))
        _lost = _before_cites - _after_cites
        if _lost and len(_lost) >= 2:
            return f"丢失 {len(_lost)} 个 cite"
        # 2. 大幅缩短
        if len(before) > 500 and len(after) < len(before) * 0.5:
            return f"内容缩短 {len(before)}→{len(after)}（>50%）"
        # 3. 内容损坏（LLM 思考碎片）
        _garbage_signals = ["But they said", "Alternative:", "bad.", ",,,"]
        if any(s in after and s not in before for s in _garbage_signals):
            return "注入 LLM 思考碎片/乱码"
        return ""

    def get_history(self) -> List[Dict]:
        """获取评估历史"""
        return self._history.copy()
